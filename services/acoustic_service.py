"""
On-device acoustic feature extraction. See CLAUDE.md.

Features come from librosa analysis of audio already downloaded by
services.audio_source -- there is no ISRC lookup. extract_features never
raises and never fakes calm defaults (CLAUDE.md rule 1): any decode or
analysis failure returns {"available": False}, which the orchestrator
records as a missing "acoustic" signal.
"""

import numpy as np
import librosa


def extract_features(audio_path: str) -> dict:
    """
    Compute affect-relevant features from a downloaded audio file.

    On success returns {"available": True, "bpm", "energy", "valence",
    "loudness"} -- the same shape the old soundnet-backed get_features
    returned, so derive_affect() is unchanged. On ANY failure returns
    {"available": False}.
    """
    try:
        y, sr = librosa.load(audio_path, mono=True)

        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(np.atleast_1d(tempo)[0])

        rms = librosa.feature.rms(y=y)
        mean_rms = float(np.mean(rms))

        # Coarse normalization: typical music RMS is well under 1.0, so scale
        # up before clamping to spread values across 0..1.
        energy = min(max(mean_rms * 5.0, 0.0), 1.0)

        # dB relative to full scale, roughly -60..0 for typical tracks.
        loudness = 20 * np.log10(mean_rms) if mean_rms > 0 else -60.0
        loudness = float(max(loudness, -60.0))

        valence = _estimate_valence(y, sr, bpm)

        return {
            "available": True,
            "bpm": bpm,
            "energy": energy,
            "valence": valence,
            "loudness": loudness,
        }
    except Exception as e:
        print(f"   ↳ Acoustic feature extraction failed ({e}); marking audio unavailable.")
        return {"available": False}


# Major/minor key profiles (Krumhansl-Schmuckler), used only by the valence
# proxy below.
_MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def _estimate_valence(y: np.ndarray, sr: int, bpm: float) -> float:
    """
    PLACEHOLDER proxy for musical valence (happy/sad), pending a real
    mood-detection model. Combines a major/minor key estimate (via chroma
    correlation against Krumhansl-Schmuckler key profiles) with tempo: a
    major-leaning key and faster tempo nudge valence up, minor-leaning and
    slower nudge it down. This is the weakest feature here -- don't read too
    much into the exact coefficients.
    """
    chroma = np.mean(librosa.feature.chroma_cqt(y=y, sr=sr), axis=1)

    major_corr = max(
        float(np.corrcoef(chroma, np.roll(_MAJOR_PROFILE, i))[0, 1]) for i in range(12)
    )
    minor_corr = max(
        float(np.corrcoef(chroma, np.roll(_MINOR_PROFILE, i))[0, 1]) for i in range(12)
    )

    # major_bias: ~1 strongly major, ~0 strongly minor, ~0.5 ambiguous.
    total = major_corr + minor_corr
    major_bias = 0.5 if total == 0 else major_corr / total

    tempo_norm = min(max((bpm - 60) / 120, 0.0), 1.0)

    valence = 0.7 * major_bias + 0.3 * tempo_norm
    return min(max(valence, 0.0), 1.0)


def derive_affect(features: dict) -> dict:
    """
    Map raw audio features to 1-10 safety-relevant affect scores (10 = worst).
    This is the 'scary / intense' signal that pure-lyrics classification misses.

    Heuristic and meant to be calibrated against a labeled set -- the structure
    is the point, not the exact coefficients.
    """
    if not features.get("available"):
        return {}

    energy = features.get("energy", 0.5)
    valence = features.get("valence", 0.5)
    bpm = features.get("bpm", 100)
    loudness = features.get("loudness")

    # Loud + energetic + fast -> intense / overstimulating.
    loud_norm = 0.5 if loudness is None else min(max((loudness + 40) / 40, 0.0), 1.0)
    tempo_norm = min(max((bpm - 60) / 120, 0.0), 1.0)
    intensity = 0.5 * energy + 0.3 * loud_norm + 0.2 * tempo_norm

    # Low valence, amplified when energetic -> angry / aggressive / dark.
    darkness = (1.0 - valence) * (0.5 + 0.5 * energy)

    return {
        "sonic_intensity": _to_scale(intensity),
        "affective_darkness": _to_scale(darkness),
    }


def _to_scale(x: float) -> int:
    return int(round(1 + max(0.0, min(1.0, x)) * 9))


if __name__ == "__main__":
    import asyncio
    from services import audio_source

    async def _main():
        # "Me at the zoo" -- the first video ever uploaded to YouTube, short
        # and known to exist.
        video_id = "jNQXAC9IVRw"
        path = await audio_source.download_audio(video_id)
        try:
            if not path:
                print("Download failed; audio unavailable.")
                return
            features = extract_features(path)
            print(f"Features: {features}")
            print(f"Affect:   {derive_affect(features)}")
        finally:
            audio_source.cleanup(path)

    asyncio.run(_main())
