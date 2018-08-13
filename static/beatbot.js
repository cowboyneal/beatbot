var elapsed = 0, duration = 0;
var currentSongId, currentOnDeckId;

var isPlaying = false, volume = parseInt(getCookie('volume')) || 100;
var sourceUrl = $('source').attr('src');
var audio = document.querySelector('audio');

function setCookie(cname, cvalue) {
    var d = new Date();
    d.setTime(d.getTime() + 2592000000);
    var expires = 'expires=' + d.toUTCString();
    document.cookie = cname + '=' + cvalue + ';' + expires;
}

function getCookie(cname) {
    var name = cname + '=';
    var ca = decodeURIComponent(document.cookie).split(';');

    for (var i = 0; i < ca.length; i++) {
        var c = ca[i];

        while (c.charAt(0) == ' ') {
            c = c.substring(1);
        }

        if (c.indexOf(name) == 0) {
            return c.substring(name.length, c.length);
        }
    }

    return '';
}

function updateVolume() {
    if (volume == 0 || audio.muted) {
        $('#mute-button').html('<i class="fas fa-volume-off"></i>');
    } else {
        $('#mute-button').text(volume);
    }
}

function volumeDown() {
    if (volume == 0) {
        return;
    }

    volume -= 5;
    audio.volume = volume/100;
    audio.muted = false;
    setCookie('volume', volume);
    updateVolume();
}

function volumeUp() {
    if (volume == 100) {
        return;
    }

    volume += 5;
    audio.volume = volume/100;
    audio.muted = false;
    setCookie('volume', volume);
    updateVolume();
}

function volumeMute() {
    if (!audio.muted) {
        audio.muted = true;
        updateVolume();
    } else {
        audio.muted = false;
        updateVolume();
    }
}

function playPause() {
    if (isPlaying) {
        $('source').attr('src', '');
        audio.pause();
        setTimeout(function () {
            audio.load();
        });
        isPlaying = false;
        $('#play-button').html('<i class="fas fa-play"></i>');
    } else {
        if (!$('source').attr('src')) {
            $('source').attr('src', sourceUrl);
            audio.load();
        }
        audio.play();
        isPlaying = true;
        $('#play-button').html('<i class="fas fa-stop"></i>');
    }
}

function timeFormat(time) {
    var minutes = Math.trunc(time / 60);
    var seconds = Math.trunc(time % 60);

    if (seconds < 10) {
        seconds = '0' + seconds;
    }

    return minutes + ':' + seconds;
}

function updateProgress(elapsed, duration) {
    var progressPerc = Math.trunc((elapsed / duration) * 100);
    $('#play-progress').attr('style','width: ' + progressPerc +
        '%');
    $('#play-progress').attr('aria-valuenow', progressPerc);
    $('#play-clock-elapsed').text(timeFormat(elapsed));
    $('#play-clock-duration').text(timeFormat(duration));
}

function updateUpNext(playlistInfo) {
    $('tr:has(td)').remove();

    var onDeck = playlistInfo.shift();

    if (onDeck.id != currentOnDeckId) {
        $('#on-deck-thumb').attr('src', 'album_art/1/' + onDeck.id);
        currentOnDeckId = onDeck.id;
    }

    $('#on-deck-name').text(onDeck.title);
    $('#on-deck-artist').text(onDeck.artist);
    $('#on-deck-album').text(onDeck.album);

    $.each(playlistInfo, function (index, song) {
        $('#playlist').append($('<tr/>')
            .append($('<td/>').text(song.title))
            .append($('<td/>').text(song.artist))
            .append($('<td/>').text(song.album))
        );
    });
}

function setYear(songDate) {
    for (var i = 1; i < 5; i++) {
        var digit = songDate.substr(i - 1, 1);

        $('#np-year-' + i).removeClass('badge-primary badge-success badge-danger badge-info');
        $('#np-year-' + i).text(digit);

        switch (parseInt(digit)) {
            case 1:
            case 2:
            case 3:
            case 9:
                $('#np-year-' + i).addClass('badge-danger');
                break;

            case 4:
            case 5:
            case 6:
                $('#np-year-' + i).addClass('badge-success');
                break;

            case 7:
                $('#np-year-' + i).addClass('badge-info');
                break;

            case 8:
            case 0:
                $('#np-year-' + i).addClass('badge-primary');
                break;
        }
    }
}

function spawnNotification(id, title, artist, album) {
    var options = {
        body: artist + ' - ' + album,
        icon: 'album_art/' + id
    };

    var n = new Notification(title, options);
}

function fullRefresh() {
    $.ajax({
        url: 'now_playing',
        type: 'GET',
        dataType: 'json',
        success: function(json) {
            $(document).prop('title', 'Beatbot: ' +
                json.currentsong.title + ' - ' +
                json.currentsong.artist);

            if (json.currentsong.id != currentSongId) {
                $('#np-thumb').attr('src', 'album_art/' +
                    json.currentsong.id);
                currentSongId = json.currentsong.id;

                spawnNotification(json.currentsong.id,
                    json.currentsong.title,
                    json.currentsong.artist,
                    json.currentsong.album);
            }

            $('#np-name').text(json.currentsong.title);
            $('#np-artist').text(json.currentsong.artist);
            $('#np-album').text(json.currentsong.album);
            setYear(json.currentsong.date);

            elapsed = Math.floor(json.status.elapsed);
            duration = Math.ceil(json.status.duration);
            updateProgress(elapsed, duration);

            updateUpNext(json.playlistinfo);
        },
        error: function(xhr, status) {
        }
    });
}

function checkSearchKey(e) {
    if (e.keyCode == 13) {
        searchSongs();
    }
}

function searchSongs() {
    var match = $('#search-term').val();

    resetSearchForm(false);

    if (match.length === 0 || !match.trim()) {
        $('#search-error').show();
        return;
    }

    $.ajax({
        url: 'search/' + match,
        type: 'GET',
        dataTyoe: 'json',
        success: function(json) {
            if (json.results.length == 0) {
                $('#search-error').show();
                return;
            }

            var disOption = new Option('Select a song', '', true, true);
            disOption.hidden = true;
            $('#song-select').append(disOption);

            $.each(json.results, function(index, song) {
                $('#song-select').append(new Option(song.title + ' - ' +
                    song.artist, song.id));
            });
        },
        error: function(xhr, status) {
            if (xhr.status == 404) {
                $('#search-error').show();
            }
        }
    });
}

function enableRequestSubmit() {
    $('#queue-button').prop('disabled', false);
}

function resetSearchForm(wipeInput) {
    if (wipeInput) {
        $('#search-term').val('');
    }

    $('#search-error').hide();
    $('option').remove();
    $('#queue-button').prop('disabled', true);
}

function submitRequest() {
    var song_id = $('#song-select').val();

    resetSearchForm(true);
    $('#search-modal').modal('hide');

    $.ajax({
        url: 'queue_request/' + song_id,
        type: 'GET',
        dataType: 'json',
        success: function(json) {
        },
        error: function(xhr, status) {
        }
    });
}

$(function () {
    audio.volume = volume/100;
    updateVolume();

    Notification.requestPermission();

    $('#search-modal').on('shown.bs.modal', function() {
        $('#search-term').focus();
    })

    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            fullRefresh();
        }
    });

    var source = new EventSource(statusUrl);
    source.onmessage = function(event) {
        var message = JSON.parse(event.data).message;

        if (message == 'player') {
            fullRefresh();
            return;
        }

        if (message == 'playlist') {
            $.ajax({
                url: 'playlistinfo',
                type: 'GET',
                dataType: 'json',
                success: function(json) {
                    elapsed = Math.floor(json.status.elapsed);
                    duration = Math.ceil(json.status.duration);
                    updateProgress(elapsed, duration);
                    updateUpNext(json.playlistinfo);
                },
                error: function(xhr, status) {
                }
            });
            return;
        }
    };
    source.onerror = function(event) {
        if (event.target.readyState == EventSource.CLOSED) {
            $('#disco-alert').show();
        }
    };

    fullRefresh();

    timerFunction = setInterval(function() {
        if (!elapsed && !duration) {
            return;
        }

        elapsed++;

        if (elapsed > duration) {
            elapsed = duration;
        }

        updateProgress(elapsed, duration);
    }, 1000);
});
