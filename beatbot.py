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

SONG_FILE_DIRECTORY = '/Users/pater/Music/Mixxx/'
PLACEHOLDER_IMAGE = 'notfound.jpg'

def get_client():
    client = MPDClient()
    client.connect('localhost', 6600)

    return client

def close_client(client):
    client.close()
    client.disconnect()

@app.route('/')
def beatbot():
    return render_template('index.html')

@app.route('/nowplaying.rss')
def rss():
    client = get_client()

    current_song = client.currentsong()
    now_playing = current_song['title'] + ' - ' + current_song['artist']

    close_client(client)

    return render_template('nowplaying.rss', now_playing=now_playing)

def get_plinfo(client):
    current_song = client.currentsong()
    status = client.status()

    list_start = str(int(current_song['pos']) + 1)
    list_end = str(min(int(current_song['pos']) + 11,
            int(status['playlistlength']) - 1))

    return client.playlistinfo(list_start + ":" + list_end)

@app.route('/mpd')
def mpd():
    client = get_client()

    current_song = client.currentsong()
    status = client.status()

    data = {
        'currentsong' : current_song,
        'status'      : status,
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
        'static/' + PLACEHOLDER_IMAGE), 'rb')
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

    song_file = File(SONG_FILE_DIRECTORY + file_name)

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
    data = { 'results': results }

    return jsonify(data)

@app.route('/playlistinfo')
def refresh_playlistinfo():
    client = get_client()

    data = { 'playlistinfo': get_plinfo(client) }

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
