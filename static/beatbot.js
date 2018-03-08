var timerFunction, currentSongId, currentOnDeckId;
var lastTimer = 0;

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
        $('#on-deck-thumb').attr('src', 'album_art/' +
            onDeck.id + '/125');
        currentOnDeckId = onDeck.id;
    }

    $('#on-deck-name').text(onDeck.title);
    $('#on-deck-artist').text(onDeck.artist);
    $('#on-deck-album').text(onDeck.album);
    $('#on-deck-year').text(onDeck.date);

    $.each(playlistInfo, function (index, song) {
        $('#playlist').append($('<tr/>')
            .append($('<td/>').text(song.title))
            .append($('<td/>').text(song.artist))
            .append($('<td/>').text(song.album))
            .append($('<td/>').text(timeFormat(song.time)))
        );
    });
}

function fullRefresh() {
    var elapsed, duration;
    var timer = 0;
    var timeout = Math.trunc(Math.random() * 31) + 60;

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
            }

            $('#np-name').text(json.currentsong.title);
            $('#np-artist').text(json.currentsong.artist);
            $('#np-album').text(json.currentsong.album);
            $('#np-year').text(json.currentsong.date);

            elapsed = Math.floor(json.status.elapsed);
            duration = Math.ceil(json.status.duration);
            updateProgress(elapsed, duration);

            updateUpNext(json.playlistinfo);

            timerFunction = setInterval(function() {
                timer++;

                if (timer >= timeout &&
                        (duration - elapsed) > 2) {
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

                    timer = 0;
                    return;
                }

                elapsed++;

                if (elapsed > duration) {
                    elapsed = duration;
                }

                updateProgress(elapsed, duration);

                if (elapsed >= duration) {
                    clearInterval(timerFunction);
                    timerFunction = false;
                    fullRefresh();
                }
            }, 1000);
        },
        error: function(xhr, status) {
        }
    });
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

            $.each(json.results, function(index, song) {
                $('#song-select').append(new Option(song.title + ' - ' + song.artist, song.id));
            });
        },
        error: function(xhr, status) {
        }
    });
}

function enableRequestSubmit() {
    // var selection = $('#song-select option:selected').text();
    // $('#queue-button').html('Request Song');
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
            updateUpNext(json.playlistinfo);
        },
        error: function(xhr, status) {
        }
    });
}

$(function () {
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            if (Date.now() - lastTimer > 100) {
                clearInterval(timerFunction);
                timerFunction = false;
            }
        } else {
            if (!timerFunction) {
                lastTimer = Date.now();
                fullRefresh();
            }
        }
    });

    fullRefresh();
});
