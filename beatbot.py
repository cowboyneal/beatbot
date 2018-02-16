import io
import imghdr

from flask import Flask
from flask import render_template, jsonify, send_file
from musicpd import MPDClient
from mutagen import File
app = Flask(__name__)

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

@app.route('/mpd')
def mpd():
    client = get_client()

    current_song = client.currentsong()

    data = {
        'currentsong'  : current_song,
        'status'       : client.status(),
        'playlistinfo' : client.playlistinfo(str(int(current_song['pos']) + 1)
            + ":" + str(int(current_song['pos']) + 11))
    }

    close_client(client)

    return jsonify(data)

@app.route('/album_art/<int:song_id>')
def album_art(song_id):
    client = get_client()
    file_name = client.playlistid(song_id)[0]['file']
    close_client(client)

    song_file = File('/Users/pater/Music/Mixxx/' + file_name)
    image = song_file.tags['APIC:'].data
    image_type = imghdr.what('', image)

    return send_file(io.BytesIO(image),
            attachment_filename=str(song_id) + '.' + image_type,
            mimetype='image/' + image_type)
