"""
Speech-to-text recovery hook.

When a track has vocals but no captions and no database lyrics, transcribing the
actual audio is the difference between an informed decision and bothering the
parent. transcribe() runs an already-downloaded audio file (see
services.audio_source) through a local Whisper model to recover the words.

If anything fails -- no speech detected, model error -- this returns "" so the
orchestrator treats the semantic signal as unverified and routes the track to
the parent. Per CLAUDE.md rule 1, a failed transcription is not a safe track,
so this function must never raise and never fabricate text.
"""

import asyncio

from faster_whisper import WhisperModel

_MODEL = None


def _get_model() -> WhisperModel:
    """Lazily load the Whisper model once and reuse it across calls."""
    global _MODEL
    if _MODEL is None:
        _MODEL = WhisperModel("base", device="cpu", compute_type="int8")
    return _MODEL


def _run_whisper(path: str) -> str:
    """
    Transcribe the audio at `path` in its source language (no translation).

    Returns "" if no speech segments are detected.
    """
    model = _get_model()
    segments, _info = model.transcribe(path, task="transcribe")
    text = "".join(segment.text for segment in segments)
    return text.strip()


async def transcribe(audio_path: str) -> str:
    """
    Recover lyrics by transcribing an already-downloaded audio file.

    Returns the transcript text in its original language, or "" if the audio
    contained no detectable speech or transcription failed for any other
    reason. This function never raises.
    """
    try:
        return await asyncio.to_thread(_run_whisper, audio_path)
    except Exception as e:
        print(f"❌ ASR failed for {audio_path}: {e}; semantic signal unavailable.")
        return ""


if __name__ == "__main__":
    # Manual smoke test -- needs network and downloads the Whisper model on
    # first run. Not part of the offline test suite.
    from services import audio_source

    async def _main():
        # "Me at the zoo" -- the first video ever uploaded to YouTube, short
        # and known to exist.
        video_id = "jNQXAC9IVRw"
        path = await audio_source.download_audio(video_id)
        try:
            if not path:
                print("Download failed; no transcript recovered.")
                return
            text = await transcribe(path)
            if text:
                print(f"Transcript ({len(text)} chars): {text[:200]}")
            else:
                print("No transcript recovered.")
        finally:
            audio_source.cleanup(path)

    asyncio.run(_main())
