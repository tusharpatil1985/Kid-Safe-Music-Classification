"""
Shared audio download for feature extraction and ASR. See CLAUDE.md.

A track's audio is downloaded at most once per run and reused by both
acoustic_service.extract_features and asr_service.transcribe. Per CLAUDE.md
rule 1, download_audio never raises -- a failed download means "audio
unavailable", not a safe default, so callers must treat None as a missing
signal.
"""

import asyncio
import os
import tempfile
import uuid

import yt_dlp

from config import YTDLP_COOKIE_FILE


def _download(track_ref: str) -> str:
    """
    NOTE: PoC path -- track_ref is currently a YouTube video id (see
    curate_playlist.py) and this uses yt-dlp directly against YouTube. Once
    canonical-ID resolution lands, this should resolve track_ref to whatever
    audio source is authoritative and this function can change in isolation.

    Raises on failure; download_audio catches.
    """
    out_path = os.path.join(tempfile.gettempdir(), f"audio_{uuid.uuid4().hex}")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_path + ".%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
        }],
        # YouTube's signature/n-challenge requires a JS runtime + solver
        # script; without these, only image formats resolve.
        "js_runtimes": {"node": {}},
        "remote_components": {"ejs:github"},
    }
    if YTDLP_COOKIE_FILE:
        ydl_opts["cookiefile"] = YTDLP_COOKIE_FILE

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://music.youtube.com/watch?v={track_ref}"])

    final_path = out_path + ".wav"
    if not os.path.exists(final_path):
        raise FileNotFoundError(f"expected audio file not found: {final_path}")
    return final_path


async def download_audio(track_ref: str) -> str | None:
    """
    Download the audio for `track_ref` to a temp wav file and return its path,
    or None on any failure. Never raises.
    """
    try:
        return await asyncio.to_thread(_download, track_ref)
    except Exception as e:
        print(f"❌ Audio download failed for {track_ref}: {e}")
        return None


def cleanup(path: str | None) -> None:
    """Remove the temp audio file, if any. Never raises."""
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass


if __name__ == "__main__":
    async def _smoke_test():
        path = await download_audio("NGMd3kfoGVo")
        print("downloaded to:", path)
        if path:
            print("exists:", os.path.exists(path), "size:", os.path.getsize(path))
            cleanup(path)

    asyncio.run(_smoke_test())
