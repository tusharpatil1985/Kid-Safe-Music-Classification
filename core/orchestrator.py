import asyncio

from core import policy
from services import db_service, acoustic_service, audio_source, lyrics_service, llm_service, asr_service


async def build_verdict(isrc: str, name: str, artist: str) -> dict:
    """
    Gather signals and produce a SCORED verdict (no decisions yet).

    Returns:
      scores          : {dimension: 1-10} for whichever signals resolved
      confidence      : 0.0-1.0 overall certainty
      missing_signals : subset of {"semantic", "acoustic"} that did not resolve
      acoustic_profile / semantic_profile : kept for the stored label
    """
    print("🌐 Downloading audio and pulling lyrics concurrently...")
    audio_path, lyrics = await asyncio.gather(
        audio_source.download_audio(isrc),
        lyrics_service.get_text(isrc, name, artist),
    )

    missing = set()

    try:
        # --- Acoustic / affective path ----------------------------------------
        acoustics = acoustic_service.extract_features(audio_path) if audio_path else {"available": False}
        affect = acoustic_service.derive_affect(acoustics)   # {} if unavailable
        if not acoustics.get("available"):
            missing.add("acoustic")
            print("   ↳ Audio features unavailable.")
        else:
            print(f"   ↳ Affect: intensity={affect['sonic_intensity']}/10, "
                  f"darkness={affect['affective_darkness']}/10")

        # --- Semantic / lyrics path (ASR-based no-lyrics fork) ------------------
        semantic_scores = {}
        semantic_confidence = 0.0

        if lyrics:
            result = await llm_service.analyze_lyrics(lyrics)
            if result is None:
                missing.add("semantic")          # LLM failed -> do NOT fake safe scores
            else:
                semantic_scores = result["scores"]
                semantic_confidence = result["confidence"]
        else:
            print("   ↳ No lyrics found; attempting ASR recovery...")
            recovered = await asr_service.transcribe(audio_path) if audio_path else ""
            if recovered:
                result = await llm_service.analyze_lyrics(recovered)
                if result is None:
                    missing.add("semantic")
                else:
                    semantic_scores = result["scores"]
                    semantic_confidence = result["confidence"]
            else:
                # No vocal content recovered: there is genuinely no semantic
                # content to verify, so neutral-low semantics are legitimate
                # (not fail-open).
                print("   ↳ No vocal content found; deciding on audio affect alone.")
                semantic_scores = {dim: 1 for dim in policy.SEMANTIC_DIMS}
                semantic_confidence = 1.0
    finally:
        audio_source.cleanup(audio_path)

    # --- Assemble scores + overall confidence --------------------------------
    scores = {**semantic_scores, **affect}

    if "semantic" not in missing:
        confidence = semantic_confidence
    elif "acoustic" not in missing:
        confidence = 0.8                     # audio-only call; heuristic, decent
    else:
        confidence = 0.0                     # nothing resolved

    return {
        "scores": scores,
        "confidence": confidence,
        "missing_signals": missing,
        "acoustic_profile": acoustics,
        "affect_profile": affect,
        "semantic_profile": semantic_scores or {"note": "unverified"},
    }


async def process_track(isrc: str, name: str, artist: str):
    """Ingest one track: score it, decide per band, persist the label."""
    print(f"🔄 Pipeline for: {name} by {artist} (ISRC: {isrc})")

    if await db_service.exists(isrc):
        print(f"⏭️  {isrc} already processed; skipping.")
        return

    verdict = await build_verdict(isrc, name, artist)

    print("🧮 Routing per age band...")
    decisions = policy.evaluate_all_bands(
        verdict["scores"], verdict["confidence"], verdict["missing_signals"]
    )
    for band, d in decisions.items():
        reason = ("; ".join(d["reasons"]) or "clear") if d["decision"] != "approve" else "clear"
        print(f"   {band:>13}: {d['decision'].upper():7} ({reason})")

    payload = {
        "isrc": isrc,
        "track_name": name,
        "artist": artist,
        "nutritional_label": {
            "acoustic_profile": verdict["acoustic_profile"],
            "affect_profile": verdict["affect_profile"],
            "semantic_profile": verdict["semantic_profile"],
            "confidence": verdict["confidence"],
            "missing_signals": sorted(verdict["missing_signals"]),
            "decisions": decisions,
        },
    }

    print("💾 Saving label to Supabase...")
    await db_service.save_label(payload)


if __name__ == "__main__":
    asyncio.run(process_track("USUM71900123", "Watermelon Sugar", "Harry Styles"))
