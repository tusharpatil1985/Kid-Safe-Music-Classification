# Kid-Safe Music Classification

Classifies whether a music track is appropriate for a given child, producing a
per-age decision with reasons. Designed around a parent who plays music in the
car and wants surprises caught *before* they play, without it becoming a chore.

## Architecture (respect these layers)

- `adapters/` — platform sources (YouTube today; Spotify/Apple later). Each
  normalizes a platform into plain dicts.
- `services/` — the **I/O boundary**. Every module here talks to the outside
  world: lyrics, acoustic features, Gemini, Supabase, ASR. Network lives here.
- `core/` — **pure logic, no network, no side effects.** Fully unit-testable.
  - `core/policy.py` — the decision layer: age bands, thresholds, and the
    approve/block/review routing. Reads scores, never produces them.
  - `core/orchestrator.py` — gathers signals, runs the no-lyrics fork, assembles
    a scored verdict, then calls the policy. Coordinates; does not decide.
- root — entry points (`curate_playlist.py`) and `config.py` (env + later, band
  presets).

Keep scoring and deciding separate. Keep pure logic out of `services/`.

## Non-negotiable design rules

1. **Never fail open.** A missing or failed signal is recorded as *missing*,
   never as a safe score. Do not reintroduce benign defaults in the services or
   neutral-low scores for unverified tracks.
2. **Three buckets, not two.** Decisions are approve / block / **review**.
   Uncertain or borderline cases go to the parent — that's the safe middle
   between fail-open and over-blocking.
3. **Per-signal completeness gate.** A missing signal only forces a review for
   the bands that actually gate on it (tween ignores audio, so missing audio
   doesn't stall a tween decision).
4. **Per-band dimension weighting.** Bands differ in *which* dimensions they
   gate, not just how strict they are. Toddler gates audio-affect hard; tween
   ignores affect and gates only mature content.
5. **Confidence + abstention.** Below a band's `min_confidence`, abstain to the
   parent rather than guess.
6. **Lyrics are untrusted input.** They are scored as data inside a delimiter,
   never followed as instructions.

## Scoring dimensions (1-10, 10 = most concerning)

Semantic (from lyrics): behavioral_defiance, substance_reference,
relational_aggression, romantic_sexual_innuendo. (prosocial_value is scored for
the label but not gated.)
Acoustic-derived (the "scary/intense" signal lyrics miss): sonic_intensity,
affective_darkness — see `acoustic_service.derive_affect`. The underlying
features (`bpm`, `energy`, `valence`, `loudness`) come from on-device `librosa`
analysis of audio downloaded via `services/audio_source.py` — there is no
ISRC/soundnet lookup.

## The no-lyrics fork (in core/orchestrator.py)

No lyrics found ->
- try ASR to recover words -> if recovered, score the transcript
- ASR recovers nothing -> no vocal content found -> decide on audio affect
  alone (neutral-low semantics).

There is no `instrumentalness` signal; vocal presence is inferred from
whether lyrics or ASR produced any text.

## Run / test

- Decision-logic tests (offline, no network): `python test_policy_logic.py`
  from the repo root. Run this after any change to `core/` or the affect math.
- Orchestrator smoke test: `python -m core.orchestrator` from the repo root
  (it's a package module now — not `python core/orchestrator.py`).
- Curate a playlist end-to-end: `python curate_playlist.py`.

When you change thresholds or scoring, run `test_policy_logic.py` and confirm
all assertions still pass before considering the change done.

## Known stubs / next steps

- `derive_affect` coefficients are an uncalibrated heuristic — calibrate against
  a labeled eval set.
- `acoustic_service._estimate_valence` is a placeholder proxy (major/minor key
  estimate + tempo) — replace with a real mood-detection model. This is the
  weakest of the acoustic features.
- `curate_playlist.py` still passes the YouTube id as `isrc`/`track_ref`; real
  canonical-ID resolution across platforms (Spotify/Apple) is deferred until a
  second platform adapter exists.
- No eval set yet — needed to measure per-band false-negative rate and calibrate
  the limit numbers in `core/policy.py`.

## Secrets

API keys live in `.env` (git-ignored). Never read or commit `.env`. Keys:
GEMINI_API_KEY, SUPABASE_URL/KEY, YOUTUBE_CLIENT_*.
