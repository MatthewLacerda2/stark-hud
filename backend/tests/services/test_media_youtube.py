"""A YouTube video as an entry in the same queue, whichever way it was pasted.

Nobody has one canonical form of a YouTube link to hand: the address bar gives a
watch URL, the Share button gives a short one, and `yt-dlp` gives eleven bare
characters. All three name the same video, so all three have to end up as the
same track — otherwise the same video queued twice is two different tracks.
"""

import pytest

from schemas.media import MediaTrack, youtube_id
from services import media as service

VIDEO = "QgH9sr7G13Q"


def test_every_shape_a_person_pastes_is_the_same_video() -> None:
    """The address bar, the Share button and yt-dlp, all naming one id."""
    pasted = [
        f"https://www.youtube.com/watch?v={VIDEO}",
        f"https://youtu.be/{VIDEO}",
        VIDEO,
        # The ones that come with something extra on them, which is most of them.
        f"https://www.youtube.com/watch?v={VIDEO}&list=PL123&t=42s",
        f"https://youtu.be/{VIDEO}?t=42",
        f"https://m.youtube.com/watch?v={VIDEO}",
        f"https://music.youtube.com/watch?v={VIDEO}",
        f"https://www.youtube.com/shorts/{VIDEO}",
        f"https://www.youtube.com/embed/{VIDEO}",
        f"youtube.com/watch?v={VIDEO}",
    ]
    queue = service.tracks_from(pasted)
    assert {track.youtube for track in queue} == {VIDEO}
    assert {track.kind for track in queue} == {"youtube"}


def test_a_link_with_no_video_in_it_says_so_in_a_sentence() -> None:
    """Refused as the YouTube link it plainly is, not as a filename."""
    with pytest.raises(ValueError) as refused:
        service.tracks_from(["https://www.youtube.com/watch?v=nope"])
    assert "YouTube link with no video id in it" in str(refused.value)


def test_a_path_is_still_a_path() -> None:
    """Nothing on disk is mistaken for an id: a path has slashes, an id has none."""
    assert youtube_id("/mnt/d_drive/Music/Some Album/01 - Track.mp3") is None
    assert youtube_id("Highway.mp3") is None


def test_a_queue_may_hold_both_and_keeps_its_order(tmp_path) -> None:
    """The point of one widget: an album and a video, played straight through."""
    song = tmp_path / "01 - Track.mp3"
    song.write_bytes(b"id3")
    queue = service.tracks_from([str(song), f"https://youtu.be/{VIDEO}", str(song)])
    assert [track.kind for track in queue] == ["audio", "youtube", "audio"]
    assert [track.path for track in queue] == [str(song), None, str(song)]


def test_a_youtube_track_has_no_file_to_serve() -> None:
    """Nothing about it comes from this board, so there is nothing here to stream."""
    assert MediaTrack(youtube=VIDEO).path is None


def test_a_track_is_one_thing_or_the_other() -> None:
    """Both at once has no meaning, and neither is not a track."""
    for asked in ({}, {"path": "/music/one.mp3", "youtube": VIDEO}):
        with pytest.raises(ValueError) as refused:
            MediaTrack(**asked)
        assert "either a path or a youtube video" in str(refused.value)
