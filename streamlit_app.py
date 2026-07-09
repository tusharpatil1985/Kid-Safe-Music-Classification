"""
Streamlit test harness for the lyrics classifier.

Lyrics-only: exercises services.llm_service.analyze_lyrics + core.policy, the
same functions the real pipeline uses. Never imports the audio path
(audio_source/acoustic_service/asr_service) -- there is no yt-dlp/librosa/
whisper dependency here, only the semantic scorer and the decision layer.
"""

import asyncio
import os

import streamlit as st

# Must happen before importing config/services.llm_service: GEMINI_API_KEY is
# read as a module-level constant at import time in config.py.
if "GEMINI_API_KEY" not in os.environ:
    try:
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
    except (KeyError, FileNotFoundError):
        pass  # local run without secrets.toml; config.py falls back to .env

from core import policy
from services.llm_service import analyze_lyrics

st.set_page_config(page_title="Kid-Safe Music Classifier", layout="wide")

DECISION_RENDER = {
    "approve": st.success,
    "block": st.error,
    "review": st.warning,
}

st.sidebar.header("Age bands")
selected_bands = st.sidebar.multiselect(
    "Show decisions for",
    options=list(policy.BANDS.keys()),
    default=list(policy.BANDS.keys()),
    format_func=lambda b: b.replace("_", " ").title(),
)

st.title("Kid-Safe Music Classifier")
st.caption("Lyrics-only test harness — no audio signal, so acoustic-gated bands "
           "will always show review for that reason.")

col1, col2 = st.columns(2)
title = col1.text_input("Title (optional)")
artist = col2.text_input("Artist (optional)")
lyrics = st.text_area("Lyrics", height=280, placeholder="Paste lyrics here...")

if st.button("Classify", type="primary"):
    if not lyrics.strip():
        st.warning("Paste some lyrics first.")
    else:
        with st.spinner("Scoring lyrics..."):
            result = asyncio.run(analyze_lyrics(lyrics))

        missing_signals = {"acoustic"}  # audio is never gathered by this tool
        if result is None:
            scores, confidence = {}, 0.0
            missing_signals.add("semantic")
        else:
            scores, confidence = result["scores"], result["confidence"]

        st.session_state["result"] = result
        st.session_state["scores"] = scores
        st.session_state["confidence"] = confidence
        st.session_state["missing_signals"] = missing_signals
        st.session_state["decisions"] = policy.evaluate_all_bands(
            scores, confidence, missing_signals
        )

if "decisions" in st.session_state:
    if st.session_state["result"] is None:
        st.error("Couldn't classify lyrics (LLM call failed) — treating semantic signal as missing.")

    if not selected_bands:
        st.info("Select at least one age band in the sidebar.")

    for band in selected_bands:
        verdict = st.session_state["decisions"][band]
        st.subheader(band.replace("_", " ").title())
        render = DECISION_RENDER[verdict["decision"]]
        render(f"**{verdict['decision'].upper()}**")
        if verdict["reasons"]:
            for reason in verdict["reasons"]:
                st.markdown(f"- {reason}")
        else:
            st.markdown("- no concerns flagged")

        with st.expander("Raw scores & confidence"):
            scores = st.session_state["scores"]
            for dim in policy.SEMANTIC_DIMS:
                score = scores.get(dim)
                st.write(f"{dim}: {score if score is not None else 'missing'}")
            result = st.session_state["result"]
            if result is not None:
                st.write(f"prosocial_value: {result['prosocial_value']}")
            st.write(f"confidence: {st.session_state['confidence']:.2f}")
            st.write(f"missing_signals: {sorted(st.session_state['missing_signals'])}")
