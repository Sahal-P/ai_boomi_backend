# Agent 3 handoff — multilingual assistant and speech

Branch: `feat/finboy-multilingual-voice`.
Frozen base: `fd618aef74336279e587748b216374d20cc892ad`.
Source head: `b0f81e6f20981bf5a79537e86950bea6394fda23`.
Implementation commits: `fd37b14` and `b0f81e6`; the final documentation commit
follows that source head. Resolve the final handoff head with
`git rev-parse feat/finboy-multilingual-voice`; Agent 5 receives its exact SHA in chat.
Managed worktree: `/Users/sahal/.codex/worktrees/finboy-multilingual-voice/ai_boom`.
No merge into main, moving-base refresh, other-owner edit, subagent or new chat.

## Owned changes and integration use

- Shared `answer_question`, `transcribe_audio`, `synthesize_speech` frozen signatures.
- Ask/transcribe/speak HTTP contracts and thin loopback FastAPI routes.
- Closed rules/Structured Outputs intent parsing, grounded slots, advice/scope
  declines, positive-INR proposal guards, deterministic five-style templates,
  exact simulation disclaimer, confirmed engine evidence selection.
- Bounded in-memory multipart, actual media/duration validation and MP3 encoding.
- Backend OpenAI STT, Resemble Ultra en/hi, Gemini Malayalam adapters; no stored
  clip, cloning or training endpoints. No frontend or WhatsApp transport changes.
- 70 focused tests, 28 text cases, six real synthetic-provider MP3s, explicit
  offline/live benchmark and recorded results.

**Human changed the provider requirement:** after account inspection and discussion
of existing credit, the human explicitly chose **Resemble Ultra**, then reconfirmed
“Use Resemble Ultra credit no replicate is needed.” The earlier Replicate approval
is superseded. Integrator should update shared provider documentation accordingly.

`docs/voice.md` has actual model/stock-voice IDs, provider docs, benchmark and privacy
limits. Keys were stored only in the private secrets file and ignored env, mode 600;
never copy keys into integration docs or frontend. Gemini key reuse from Layover was
explicitly authorized. The existing bootstrap settings suffice; no package, lockfile,
DB schema or migration changes are requested. System ffmpeg/ffprobe are required.

Multipart file field is **audio**, optional field **language_hint**. Unknown/mixed
STT stays `unknown`; UI should keep it editable. Request speech independently of the
text answer. Direct service consumers should catch fixed `InvalidAudio` alongside
shared `ProviderUnavailable`. Missing providers remain truthful unavailable states.
Speech keys/voice IDs/model must be set in the integrator's ignored environment;
settings do not silently invent model or voice defaults.

## Actual verification

- `uv sync --locked --all-packages`, `pnpm install --frozen-lockfile`, env setup: pass.
- Focused assistant/speech pytest: **70 passed** without PostgreSQL.
- `pnpm check`: **204 backend unit tests**, 10 web client tests, Ruff, ESLint and
  strict TypeScript passed; 10 PostgreSQL integration tests deselected.
- `pnpm build`: pass; `git diff --check`: pass.
- `pnpm voice:benchmark`: offline 28/28 intents; six actual MP3 files decode.
- `pnpm voice:benchmark --generate --live`: real 3 TTS calls + 6 STT calls, zero
  provider failures. Languages 6/6, spoken-question intents 3/3, exact transcripts
  5/6; Hindi number WER 8.33%, machine amount preservation 3/3.
- Actual OpenAI account models and one live structured-intent paraphrase checked.
- Actual Resemble requested account, model menu and stock-voice metadata checked.
  English Lucy and Hindi Fatima synthesized through authenticated endpoint.
- Actual Gemini account models and Kore Malayalam speech checked, WAV→MP3.
- Browser playback: all three number MP3s decoded, playback time advanced, no media
  errors. Temporary local playback tab/server stopped. Browser captures were
  inspected in tool output; no screenshot file retained. Audio fixtures provide
  reviewable playable artifacts.

## Remaining integration limits

Money truth is verified against typed contract fakes because this branch retains
the frozen engine stub. Agent 5 must assemble Agent 1's engine before real DB
food correction/unallocated/simulation acceptance. Agent 3 adds no independent
financial calculation and performs no PostgreSQL writes/migrations.

No product UI changed. Responsive keyboard/loading/offline/microphone-denied and
real human microphone tests remain for Agent 2/final integration. Human recording
count is **0**; real recordings must stay ignored and require approval. Human
number-listening feedback is pending; automated numeric recognition is not a human
intelligibility score. WhatsApp end-to-end delivery belongs to Agent 4/integration.

Resemble/Gemini provider features have actual playable synthetic live verification;
this does not establish all accents, real microphones or real-finance speech quality.
There is no claim of zero upstream operational retention. Resemble omits project/
title; Gemini and OpenAI intent use store=false. See the provider-retention limits
in docs/voice.md. Human did not create or fund any new subscription for this work.
