import os
import io
import imghdr

from flask import Flask
from flask import render_template, jsonify, send_file, make_response
from musicpd import MPDClient
from mutagen import File
from PIL import Image
from functools import wraps, update_wrapper
from datetime import datetime
app = Flask(__name__)
app.config.from_object('config')

def get_client():
    client = MPDClient()
    client.connect(app.config['MPD_ADDRESS'], app.config['MPD_PORT'])

    return client

def close_client(client):
    client.close()
    client.disconnect()

@app.route('/')
def beatbot():
    return render_template('index.html',
            stream_url=app.config['STREAM_URL'],
            stream_text=app.config['STREAM_TEXT'])

@app.route('/nowplaying.rss')
def rss():
    client = get_client()
    current_song = client.currentsong()
    close_client(client)

    return render_template('nowplaying.rss', title=current_song['title'],
            artist=current_song['artist'])

def clean_playlist(playlistinfo):
    for song in playlistinfo:
        del song['date']
        del song['disc']
        del song['duration']
        del song['file']
        del song['genre']
        del song['last-modified']
        del song['track']

    return playlistinfo

def get_plinfo(client):
    current_song = client.currentsong()
    status = client.status()

    list_start = int(current_song['pos']) + 1
    list_max = int(status['playlistlength'])

    if (list_start == list_max):
        list_start = 0

    list_end = min(list_start + 10, list_max)
    playlistinfo = client.playlistinfo(str(list_start) + ':' + str(list_end))
    n = len(playlistinfo)

    if (n < 10):
        playlistinfo += client.playlistinfo('0:' + str(10 - n))

    return clean_playlist(playlistinfo)

def get_clean_status(client):
    status = client.status()
    del status['audio']
    del status['bitrate']
    del status['consume']
    del status['mixrampdb']
    del status['nextsong']
    del status['nextsongid']
    del status['playlist']
    del status['playlistlength']
    del status['random']
    del status['repeat']
    del status['single']
    del status['song']
    del status['songid']
    del status['state']
    del status['time']
    del status['volume']
    del status['xfade']

    return status

@app.route('/now_playing')
def now_playing():
    client = get_client()

    current_song = client.currentsong()
    del current_song['disc']
    del current_song['duration']
    del current_song['file']
    del current_song['genre']
    del current_song['last-modified']
    del current_song['time']
    del current_song['track']

    data = {
        'currentsong' : current_song,
        'status'      : get_clean_status(client),
        'playlistinfo': get_plinfo(client)
    }

    close_client(client)

    return jsonify(data)

def nocache(view):
    @wraps(view)
    def no_cache(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Last-Modified'] = datetime.now()
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response
        
    return update_wrapper(no_cache, view)

def get_placeholder_image():
    image_file = open(os.path.join(app.root_path,
        'static', app.config['PLACEHOLDER_IMAGE']), 'rb')
    image = image_file.read()
    image_file.close()

    return image

def get_image_type(image):
    return imghdr.what('', image)

@app.route('/album_art/<int:song_id>')
@nocache
def album_art(song_id):
    client = get_client()
    file_name = client.playlistid(song_id)[0]['file']
    close_client(client)

    song_file = File(os.path.join(app.config['SONG_FILE_DIRECTORY'],
        file_name))

    try:
        image_data = song_file.tags['APIC:'].data
    except:
        image_data = get_placeholder_image()

    image_type = get_image_type(image_data)

    if not image_type:
        image_data = get_placeholder_image()
        image_type = get_image_type(image_data)

    image = Image.open(io.BytesIO(image_data))
    image = image.resize((250, 250), Image.ANTIALIAS)
    image_data = io.BytesIO()
    image.save(image_data, format=image_type)
    image_data = image_data.getvalue()

    return send_file(io.BytesIO(image_data),
        attachment_filename=str(song_id) + '.' + image_type,
        mimetype='image/' + image_type)

@app.route('/search/<string:match>')
def search(match):
    client = get_client()

    results = client.playlistsearch('title', match)
    results += client.playlistsearch('artist', match)

    close_client(client)

    results = [dict(t) for t in set([tuple(d.items()) for d in results])]
    results = sorted(results, key=lambda k: k['title'])
    data = { 'results': clean_playlist(results) }

    return jsonify(data)

@app.route('/playlistinfo')
def refresh_playlistinfo():
    client = get_client()

    data = {
        'playlistinfo': get_plinfo(client),
        'status'      : get_clean_status(client)
    }

    close_client(client)
    return jsonify(data)

@app.route('/queue_request/<int:song_id>')
def queue_request(song_id):
    client = get_client()

    next_pos = client.status()['nextsong']
    client.moveid(song_id, next_pos)
    next_pos = client.status()['nextsong']
    client.moveid(song_id, next_pos)

    close_client(client)
    return refresh_playlistinfo()
