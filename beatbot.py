import os
import io
import imghdr
import time
import logging

from flask import Flask, render_template, jsonify, send_file, \
    make_response, send_from_directory, request
from flask_sse import sse
from flask_mobility import Mobility
from flask_mobility.decorators import mobile_template
from musicpd import MPDClient
from mutagen import File
from PIL import Image
from functools import wraps, update_wrapper
from datetime import datetime, timedelta
app = Flask(__name__)
Mobility(app)
app.config.from_object('config')
app.register_blueprint(sse, url_prefix='/status')


def cache_time(weeks=0, days=0, hours=0, minutes=0, seconds=0):
    timeout = timedelta(weeks=weeks, days=days, hours=hours,
                        minutes=minutes, seconds=seconds)

    def cache_decorator(view):
        @wraps(view)
        def set_cache(*args, **kwargs):
            time_format = "%a, %d %b %Y %H:%M:%S GMT"
            cache_control = 'must-revalidate, max-age='
            response = make_response(view(*args, **kwargs))
            response.headers['Last-Modified'] = \
                datetime.now().strftime(time_format)

            if timeout.total_seconds() == 0:
                cache_control = 'no-store, no-cache, ' + \
                    cache_control + '0'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '-1'
            else:
                cache_control += str(int(timeout.total_seconds()))
                expires = datetime.now() + timeout
                response.headers['Expires'] = \
                    expires.strftime(time_format)

            response.headers['Cache-Control'] = cache_control
            return response
        return update_wrapper(set_cache, view)
    return cache_decorator


def log_to_file(file_name, message):
    fmt_str = '%(asctime)s - %(message)s'
    file_path = os.path.join(app.config['LOG_DIR'], file_name + '.log')

    logging.basicConfig(filename=file_path, level=logging.INFO,
                        format=fmt_str)

    logging.info(request.remote_addr + ': ' + str(message))


@app.route('/')
@mobile_template('index{_mobile}')
def beatbot(template):
    client = get_client()
    stats = client.stats()
    close_client(client)

    site_theme = ''

    if 'SITE_THEME' in app.config:
        site_theme = app.config['SITE_THEME']
        template = template + '_' + site_theme

    template = template + '.html';

    if request.MOBILE:
        thumb_size = app.config['MOBILE_THUMB_SIZE']
        thumb_size_sm = app.config['MOBILE_THUMB_SIZE_SM']
    else:
        thumb_size = app.config['IMAGE_THUMB_SIZE']
        thumb_size_sm = app.config['IMAGE_THUMB_SIZE_SM']

    return render_template(template,
                           site_name=app.config['SITE_NAME'],
                           site_theme=site_theme,
                           stats=stats,
                           background=app.config['BACKGROUND_IMAGE'],
                           stream_url=app.config['STREAM_URL'],
                           public_stream_url=app.config['PUBLIC_STREAM_URL'],
                           thumb_size=thumb_size,
                           thumb_size_sm=thumb_size_sm)


@app.route('/nowplaying.rss')
def rss():
    client = get_client()
    current_song = client.currentsong()
    close_client(client)
    return render_template('nowplaying.rss',
                           site_name=app.config['SITE_NAME'],
                           site_link=app.config['SITE_LINK'],
                           site_desc=app.config['SITE_DESCRIPTION'],
                           title=current_song['title'],
                           artist=current_song['artist'])


@app.route('/.well-known/acme-challenge/<string:file_name>')
def acme_challenge(file_name):
    return send_from_directory('static', file_name)


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
        'currentsong': current_song,
        'status': get_clean_status(client),
        'playlistinfo': get_plinfo(client)
    }

    close_client(client)
    return jsonify(data)


@app.route('/playlistinfo')
def refresh_playlistinfo():
    client = get_client()

    data = {
        'playlistinfo': get_plinfo(client),
        'status': get_clean_status(client)
    }

    close_client(client)
    return jsonify(data)


@app.route('/album_art/<int:song_id>')
@app.route('/album_art/<int:is_small>/<int:song_id>')
@cache_time(minutes=1)
def album_art(song_id, is_small=0):
    if request.MOBILE:
        if is_small:
            size = app.config['MOBILE_THUMB_SIZE_SM']
        else:
            size = app.config['MOBILE_THUMB_SIZE']
    else:
        if is_small:
            if is_small == 1:
                size = app.config['IMAGE_THUMB_SIZE_SM']
            else:
                size = app.config['IMAGE_THUMB_SIZE_TINY']
        else:
            size = app.config['IMAGE_THUMB_SIZE']

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
                lastword = ''
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
    data = {'results': clean_playlist(results)}
    return jsonify(data)


@app.route('/queue_request/<int:song_id>')
def queue_request(song_id):
    client = get_client()

    if (song_id == int(client.currentsong()['id']) or
            song_id == int(client.status()['nextsongid']) or
            song_id > int(client.status()['playlistlength'])):
        return jsonify({'success': 0})

    for _ in range(2):
        next_pos = int(client.status()['nextsong']) + 1

        if next_pos == int(client.status()['playlistlength']):
            next_pos = 0

        client.moveid(song_id, next_pos)

    song = client.playlistid(song_id)[0]
    log_to_file('song_request', song['title'] + ' - ' + song['artist'])

    close_client(client)
    return jsonify({'success': 1,
                    'id': song['id'],
                    'title': song['title'],
                    'artist': song['artist']})


def get_client():
    client = MPDClient()
    client.connect(app.config['MPD_ADDRESS'], app.config['MPD_PORT'])
    return client


def close_client(client):
    client.close()
    client.disconnect()


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
    list_length = app.config['COMING_UP_LENGTH'] + 1
    list_max = int(status['playlistlength'])

    if list_start == list_max:
        list_start = 0

    list_end = min(list_start + list_length, list_max)
    playlistinfo = client.playlistinfo(str(list_start) + ':' +
                                       str(list_end))
    n = len(playlistinfo)

    if n < list_length:
        playlistinfo += client.playlistinfo('0:' + str(list_length - n))

    return clean_playlist(playlistinfo)


def get_clean_status(client):
    while True:
        status = client.status()
        if status['elapsed'] != '0.000':
            break
        time.sleep(100/1000.0)

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


def get_placeholder_image():
    image_file = open(os.path.join(app.root_path,
                                   'static', app.config['PLACEHOLDER_IMAGE']), 'rb')
    image = image_file.read()
    image_file.close()
    return image


def get_image_type(image):
    return imghdr.what('', image)
