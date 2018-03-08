import os
import io
import imghdr

from flask     import Flask, render_template, jsonify, send_file, make_response
from musicpd   import MPDClient
from mutagen   import File
from PIL       import Image
from functools import wraps, update_wrapper
from datetime  import datetime
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
    client = get_client()
    stats = client.stats()
    close_client(client)

    return render_template('index.html',
            stats=stats,
            stream_url=app.config['STREAM_URL'],
            stream_text=app.config['STREAM_TEXT'])

@app.route('/nowplaying.rss')
def rss():
    client = get_client()
    current_song = client.currentsong()
    close_client(client)

    return render_template('nowplaying.rss',
            title=current_song['title'],
            artist=current_song['artist'])

def clean_playlist(playlistinfo):
    keys = [
        'disc',
        'duration',
        'file',
        'genre',
        'last-modified',
        'track'
    ]

    for song in playlistinfo:
        for k in keys:
            if k in song:
                del song[k]

    return playlistinfo

def get_plinfo(client):
    current_song = client.currentsong()
    status = client.status()

    list_start = int(current_song['pos']) + 1
    list_max = int(status['playlistlength'])

    if (list_start == list_max):
        list_start = 0

    list_end = min(list_start + app.config['UP_NEXT_LENGTH'], list_max)
    playlistinfo = client.playlistinfo(str(list_start) + ':' + str(list_end))
    n = len(playlistinfo)

    if (n < app.config['UP_NEXT_LENGTH']):
        playlistinfo += client.playlistinfo('0:' +
            str(app.config['UP_NEXT_LENGTH'] - n))

    return clean_playlist(playlistinfo)

def get_clean_status(client):
    status = client.status()

    keys = [
        'audio',
        'bitrate',
        'consume',
        'mixrampdb',
        'mixrampdelay',
        'nextsong',
        'nextsongid',
        'playlist',
        'playlistlength',
        'random',
        'repeat',
        'single',
        'song',
        'songid',
        'state',
        'time',
        'volume',
        'xfade'
    ]

    for k in keys:
        if k in status:
            del status[k]

    return status

@app.route('/now_playing')
def now_playing():
    client = get_client()

    current_song = client.currentsong()

    keys = [
        'disc',
        'duration',
        'file',
        'genre',
        'last-modified',
        'time',
        'track'
    ]

    for k in keys:
        if k in current_song:
            del current_song[k]

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
@app.route('/album_art/<int:song_id>/<int:size>')
@nocache
def album_art(song_id, size = app.config['IMAGE_THUMB_SIZE']):
    if size > 600:
        size = 600

    client = get_client()
    file_name = client.playlistid(song_id)[0]['file']
    close_client(client)

    song_file = File(os.path.join(app.config['SONG_FILE_DIRECTORY'],
        file_name))

    if (file_name.endswith('mp3') and 'APIC:' in song_file.tags and
            song_file.tags['APIC:'].data):
        image_data = song_file.tags['APIC:'].data
    elif (file_name.endswith('flac') and song_file.pictures and
            song_file.pictures[0].data):
        image_data = song_file.pictures[0].data
    else:
        image_data = get_placeholder_image()

    image_type = get_image_type(image_data)

    if not image_type:
        image_data = get_placeholder_image()
        image_type = get_image_type(image_data)

    image = Image.open(io.BytesIO(image_data))
    image = image.resize((size, size), Image.ANTIALIAS)
    image_data = io.BytesIO()
    image.save(image_data, format=image_type)
    image_data.seek(0)

    return send_file(image_data, attachment_filename=str(song_id) +
        '.' + image_type, mimetype='image/' + image_type)

@app.route('/search/<string:match>')
def search(match):
    client = get_client()

    results = []
    neg_results = []
    lastword = ''

    for word in match.split():
        if word.startswith('"'):
            if not word.endswith('"'):
                lastword = word[1:]
                continue
            else:
                word = word[1:-1]
        elif lastword:
            if word.endswith('"'):
                word = lastword + ' ' + word[:-1]
                lastword = '';
            else:
                lastword += ' ' + word
                continue
        elif word.startswith('-'):
            neg_results += client.playlistsearch('title', word[1:])
            neg_results += client.playlistsearch('artist', word[1:])
            continue

        results += client.playlistsearch('title', word)
        results += client.playlistsearch('artist', word)

    close_client(client)

    results = [dict(t) for t in set([tuple(d.items()) for d in results])]
    neg_results = [dict(t) for t in set([tuple(d.items())
        for d in neg_results])]
    results = [item for item in results if item not in neg_results]
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

    for _ in range(2):
        next_pos = int(client.status()['nextsong']) + 1

        if next_pos == int(client.status()['playlistlength']):
            next_pos = 0;

        client.moveid(song_id, next_pos)

    close_client(client)
    return refresh_playlistinfo()
