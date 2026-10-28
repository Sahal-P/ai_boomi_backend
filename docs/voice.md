# Shared multilingual assistant and speech

Implemented on `feat/finboy-multilingual-voice`, frozen base
`fd618aef74336279e587748b216374d20cc892ad`. Verified 24 October 2026 (IST).
This owner implements backend services and HTTP only. The web and WhatsApp use
these same boundaries; neither transport should implement reasoning or providers.

## Provider decision and actual account state

**The human explicitly changed English/Hindi from Chatterbox to Resemble Ultra
using the existing account credit. Replicate is not used.** The requested Resemble
account was identified in Chrome by its account identity. Its TTS model menu offered
only Ultra. The official [model versions](https://docs.resemble.ai/getting-started/model-versions)
page marks old Chatterbox versions end-of-life, and the
[archive notice](https://docs.resemble.ai/voice-archive) says historical hosted guides
do not establish commercial availability. Those pages were treated as warnings to
verify the account, rather than evidence of a usable Chatterbox entitlement.

The existing Resemble key authenticated voice discovery and live synthesis. No new
account, subscription, funds, training, or cloned voice was created. Current choices:

| Function | Verified model / voice | Real check |
| --- | --- | --- |
| English TTS | Resemble Ultra / stock Lucy (`fb2d2858`, en-US) | Authenticated `/synthesize`, real MP3, browser playback |
| Hindi TTS | Resemble Ultra / stock Fatima (`af3b3fad`, hi) | Authenticated `/synthesize`, real MP3, browser playback |
| Malayalam TTS | `gemini-3.8-flash-tts` / prebuilt Kore | Authenticated `/models` and `/interactions`; WAV converted to MP3, browser playback |
| STT, all three languages | `gpt-transcribe` | Model listed by this OpenAI account; actual transcription of six provider-generated fixtures |
| Assistant understanding and contextual wording | `gpt-6-luna` | Actual Structured Outputs requests, including the purchase-planning regression |

Resemble synthesis selects the voice's current model automatically; **do not send a
`model` field**. The portal/default-model documentation establishes Ultra, while the
synthesis response itself does not echo a model ID. Advanced voice metadata contained
legacy `not_available` model entries even though actual synthesis succeeded. The
successful synthesis and playback checks, rather than those entries, establish
account availability. See [synthesis schema](https://docs.resemble.ai/api-reference/text-to-speech/synthesize),
[voice discovery](https://docs.resemble.ai/api-reference/voices/list-voices), and
[Ultra announcement](https://www.resemble.ai/changelog).

Gemini's current [speech generation guide](https://ai.google.dev/gemini-api/docs/speech-generation)
lists Malayalam and the 3.8 TTS models. This account's `/models` response included
`gemini-3.8-flash-tts`; a real synthetic request returned audio. The adapter implements
the current Interactions schema for the configured 3.8 Flash / Flash-Lite TTS family;
other model families need their documented schema verified before use.

OpenAI's current [file transcription guide](https://developers.openai.com/api/docs/guides/speech-to-text)
uses plural `languages` and returns language codes. The adapter sends `languages`
plus a short bookkeeping vocabulary, rather than the deprecated singular hint API.
[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
and [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) were checked
before the live classification call. No model IDs were selected from memory.

## Backend boundaries and HTTP

- `services/assistant/service.py`: `answer_question(session, *, user_id, text,
  display_style, settings) -> AssistantAnswer`.
- `services/speech/service.py`: `transcribe_audio(*, audio, content_type, settings,
  language_hint=None) -> Transcript`; `synthesize_speech(*, text, language,
  settings) -> SynthesizedAudio`.
- `/api/v1/assistant/ask`: POST `{text, display_style}`. Text is 1–2,000 characters;
  whitespace-only and extra properties fail validation. `display_style` is
  `auto|en|hi|hinglish|ml|manglish`. Returns the frozen answer contract.
- `/api/v1/assistant/transcribe`: POST multipart **`audio`** file, optional
  `language_hint=en|hi|ml`. Returns `{transcript, detected_language}`. Unknown or
  multiple detected languages remain `unknown`, including when a hint was supplied.
  Preserve this transcript as editable in the transport's UI before asking.
- `/api/v1/assistant/speak`: POST `{text, language}` with ≤600 characters and
  `language=en|hi|ml`. Returns actual `audio/mpeg` bytes, `Cache-Control: no-store`.
  Hindi/Malayalam require native script; Hinglish/Manglish answers already provide
  native `speech_text`. Clients should request this independently after `/ask` so
  failed speech never discards a correct text answer.

`InvalidAudio` (a fixed `ValueError` subclass in `speech/media.py`) distinguishes
invalid media/length/type; the HTTP route returns redacted 413/415/422 envelopes.
Service consumers such as WhatsApp should handle it alongside the shared
`ProviderUnavailable`, which carries only fixed codes and maps to HTTP 503.
Absent configuration reports `configuration_missing`; network/auth/quota/provider
or malformed generated media reports `speech_unavailable`. No raw provider error
or user content crosses the error boundary.

## Financial truth and policy

With `OPENAI_API_KEY` and `OPENAI_ASSISTANT_MODEL` configured, every question uses
OpenAI Structured Outputs for understanding and contextual wording. The closed
intent, category, period, education-topic and positive paise schema covers spending,
income, estimated unallocated, obligations, merchant evidence,
affordability/simulation, consumer purchase planning, education, advice decline and scope.
A current calendar month is the default; explicit `YYYY-MM` is supported. Other
relative periods clarify rather than silently querying a different month. Simulations
use the engine's current-month interface and clarify an explicit historical period.
Amounts must be positive explicit rupee literals in the question. Negative or
ambiguous proposals and non-INR requests clarify; an LLM cannot invent a proposal.

Rules remain available for explicitly unconfigured development/test runs and as
validators for provider-selected financial parameters. Production without assistant
configuration returns `configuration_missing`; a configured provider's timeout,
authentication/quota failure, refusal, malformed output or missing contextual reply
returns redacted `assistant_unavailable` instead of silently pretending to answer.
Model amounts and merchants must match the question, record-query periods must
match deterministic resolution, and explicit security picks still decline.

Consumer purchase planning returns `purchase_planning` with policy `clarify`, no
money-engine call, no period and no financial facts. For example, buying a GT 650
"next month" asks about the item, actual quote and cash/financing plan; its model
number is never used as a monthly rupee commitment. A purchase horizon is independent
of supported historical record-query periods. No price/specification lookup, future
cash-flow forecast or one-off purchase simulation is claimed.

The model writes short contextual prose and native-language speech without digits,
currency symbols or percentages (validated), and is instructed to avoid numeric
claims in words, invented prices/rates and unsupported affordability claims. Financial
answers append the complete deterministic engine-backed text, dates, disclaimers
and warnings verbatim. The model never receives ledger rows or engine amounts.
Clarifications, purchase questions and neutral education use the model's prose.
If an introductory speech sentence would exceed the existing audio limit, speech
keeps the complete financial statement. Questions remain independent requests;
no server-side conversation memory or stored question history was added.

All totals come from the existing money engine signatures. There is no independent
SQL, money summation, balance inference, or ledger mutation in this owner. Category
amounts come from `category_breakdown`; summary fields and simulation values come
from their typed engine results. Merchant answers show individual transaction
amounts and explicitly avoid claiming an independently calculated merchant total.
Evidence is restricted to confirmed engine results and summary evidence IDs;
income evidence additionally identifies income records. Review items remain excluded.

The five display styles use the same facts. Speech follows `en`, Devanagari `hi`,
or Malayalam `ml`, including native speech for romanized display. Formatting keeps
integer paise, negative signs and fractional paise visible; it normalizes rupees,
paise, ISO dates and SIP/UPI/EMI pronunciation. Simulations end in the **exact**
contract disclaimer in display text; native speech includes its translated meaning.
Coverage warnings distinguish tracked records from actual available bank funds.

Typed engine fakes verified ₹7,860 food after correction, ₹14,780 estimated
unallocated and ₹9,780 after a ₹5,000 proposal in all five styles. This branch's
engine remains the frozen scaffold: real engine/database acceptance belongs to the
assembled Agent 1 + Agent 3 integration, not to these fake-backed checks.

## Media bounds, codecs and privacy

Multipart is read through a bounded stream and `python-multipart` callbacks entirely
in memory. `UploadFile`/disk spooling is not used. One audio part is allowed, with a
small overhead cap, no duplicate or unknown parts, and an actual audio limit ≤3 MiB.
ffprobe checks the container against its claimed MIME and permits one audio stream.
ffmpeg decodes through pipes at 24 kHz mono 16-bit PCM, stopping slightly beyond the
configured duration to detect and reject >30 seconds instead of silently truncating.
Decoder timeouts are 10 seconds. Network/file protocols are disabled for decoder
inputs. Supported inputs: WAV, MP3, WebM, Ogg/Opus and audio MP4/M4A. Validated audio
is wrapped in a correct WAV header for STT; filenames and MIME alone are not trusted.

Resemble returns base64 MP3; its real response included line breaks, which are removed
before strict base64 validation. Gemini's verified unary output is WAV. Explicit
raw-PCM MIME with codec/rate metadata can be wrapped in WAV; unspecified encodings
are rejected. Generated audio is bounded at 12 MiB / 180 seconds, decoded and encoded
as 24 kHz mono 64 kbps MP3 through pipes. WAV/PCM bytes are never relabeled as MP3.

Services never persist or log raw questions, transcripts, input/generated audio,
provider bodies, secrets or exception messages. The only committed audio is the
explicit synthetic evaluation corpus. Real recordings belong in gitignored
`apps/api/fixtures/voice/real/`; its optional manifest must mark each as
`human_approved=true` before `--real` includes it. Do not use private financial answers
as benchmark fixtures.

Resemble requests omit `project_uuid` and `title`, avoiding intentionally stored
clips. User text is escaped before submission to the text/SSML field. Gemini uses
`store=false`; see [Interactions retention](https://ai.google.dev/gemini-api/docs/interactions-overview).
OpenAI assistant requests also set `store=false`. These are application storage controls,
**not** a claim of zero upstream operational/abuse retention. Resemble's current Ultra
implementation is described as powered by xAI in its official changelog; upstream
retention guarantees were not established. No stored-clip or voice-creation endpoint
is called.

## Settings and runtime

No additional Python packages or migrations. Existing locked OpenAI/httpx/stdlib
are used. System `ffmpeg` and `ffprobe` must be present; verified locally at
`/opt/homebrew/bin`. See `docs/handoffs/agent-3-dependencies.md`.

Backend-only settings: `OPENAI_API_KEY`, `OPENAI_TRANSCRIBE_MODEL`,
`OPENAI_ASSISTANT_MODEL`, `RESEMBLE_API_KEY`, `RESEMBLE_TTS_MODEL`,
`RESEMBLE_VOICE_UUID_EN`, `RESEMBLE_VOICE_UUID_HI`, `RESEMBLE_TTS_BASE_URL`,
`GEMINI_API_KEY`, `GEMINI_TTS_MODEL`, `GEMINI_TTS_VOICE`, `GEMINI_TTS_BASE_URL`,
`FFMPEG_BINARY`, `FFPROBE_BINARY`, `ASSISTANT_TIMEOUT_SECONDS`,
`SPEECH_TIMEOUT_SECONDS`, `PROVIDER_MAX_RETRIES`, `SPEECH_MAX_AUDIO_BYTES`,
`SPEECH_MAX_DURATION_SECONDS`, `SPEECH_MAX_TEXT_CHARACTERS`. The shared bootstrap
provides these. Model/voice choices live in ignored environment files, not defaults
or frontend variables. HTTP uses bounded timeouts and connection-establishment
retries only for TTS; OpenAI uses its bounded SDK retry setting. Redirects are disabled.

The human authorized reusing Layover's Gemini key; it was copied directly into
`~/.config/finboy/secrets.env`. Resemble and OpenAI keys are also backend-only in that
private file and ignored worktree env, mode 600. No key appears in provider URLs.
Agent 3's env uses API 8013, web 3013, exact loopback CORS and database `finboy_p3`.
No database writes/schema changes were made by this owner.

## Recorded benchmark and commands

`pnpm voice:benchmark` runs **offline** rules plus actual fixture media decoding.
`pnpm voice:benchmark --live` actually calls STT on the six recorded fixtures.
`--generate` explicitly makes three provider TTS calls for the synthetic food
questions; it does not regenerate every fixture silently. `--real` includes only
ignored, approved recordings. Output contains aggregate correctness and operational
metrics, never transcripts or provider response bodies. Samples and actual recorded
results are in `apps/api/fixtures/voice/manifest.json` and `benchmark-recorded.json`.
A critical media/language/intent/amount failure exits nonzero; exact-text/WER results
are reported without pretending every wording difference is an amount error.

Corpus: **28 text intent cases**, six each en/hi/ml plus ten romanization, policy,
merchant and simulation cases. **Six actual provider-generated MP3 samples**, two
per language: one number phrase and one question. **Zero human recordings**.

Actual `--generate --live` run on 24 October 2026:

| Language | TTS question ms | STT question ms | Question exact / intent | STT number ms | Number exact / WER | Machine amount check |
| --- | ---: | ---: | --- | ---: | --- | --- |
| English | 2,065 | 1,286 | yes / correct | 2,002 | yes / 0% | passed |
| Hindi | 1,623 | 1,921 | yes / correct | 1,807 | no / 8.33% | passed |
| Malayalam | 3,540 | 857 | yes / correct | 3,014 | yes / 0% | passed |

All six detected languages matched. Five of six transcripts matched exactly after
punctuation normalization. All three number phrases preserved ₹7,860 in the automated
check. All 28 text intents passed. Final benchmark provider failures: **0 of 6 STT**
and **0 of 3 fresh TTS generation calls**. Earlier provider discovery exposed the
base64-whitespace adapter bug; it was fixed and regression-tested before this run.
Human listening confirmation: on 24 October 2026 (IST), the user answered
**“All three clear”** when asked whether the English, Hindi and Malayalam synthetic
number clips clearly say ₹7,860. This validates these three clips only; it does not
measure real-microphone transcription or broader pronunciation quality.
One separate live structured-intent paraphrase classified meals as food spending
correctly in 3,429 ms. Initial macOS-generated en/hi STT smoke inputs are separate
from this six-sample provider corpus and do not count as provider TTS verification.

| Command / check | Actual outcome |
| --- | --- |
| `uv sync --locked --all-packages`, `pnpm install --frozen-lockfile`, `pnpm env:setup` | passed in managed worktree |
| Focused `uv run pytest apps/api/tests/assistant apps/api/tests/speech -q` | 70 passed |
| `pnpm voice:benchmark` | 28/28 intents, six actual MP3s decode; zero live calls |
| `pnpm voice:benchmark --generate --live` | actual provider results in table above |
| `pnpm check` | Ruff, web lint, 204 backend unit tests, 10 web tests, strict types passed; 10 DB integration tests deselected |
| `pnpm build` | production Next.js build passed |
| `git diff --check` | passed |
| PostgreSQL migrations/integration | not run: no schema/write changes; money engine remains a typed fake in this branch |
| Browser MP3 playback | en 3.960 s, hi 3.336 s, ml 4.944 s; all readyState 4, playback time advanced, no media errors |

Browser playback used an isolated temporary loopback-only page containing the three
synthetic files; the tab and server were stopped afterward. It is not a claim of
product-page QA. Agent 3 made no Next.js changes. Product loading/offline/empty/error,
keyboard, microphone-denied and responsive 1440×1000 / 390×844 / 320×740 checks remain
with Agent 2 and final integration. No human microphone recording or WhatsApp delivery
is claimed here. No public ingress, tunnel, additional chat or subagent was created.

## UX answer provenance (24 October 2026)

Bookkeeping answers include opaque data version, resolved IST period, exact evidence
IDs, total evidence count and an explicit sampling flag. Merchant arithmetic uses the
entire matching confirmed non-transfer scope, separating gross outflows, refunds and
net spending before selecting up to ten records. Income evidence is selected before
capping. Today/yesterday/current month/previous month/YYYY-MM are deterministic;
unsupported periods receive period-specific clarification. Localized fact/warning labels
and separate display-script/spoken-language metadata support native and romanized styles.
Providers, refusal boundaries, backend-only keys and independent speech/text fallback
remain unchanged. These changes do not establish human microphone or phone playback.

## Groq transcription routing (capture round, 24 October 2026)

The human chose Groq `whisper-large-v3-turbo` for English/Hindi speech-to-text and kept
OpenAI `gpt-transcribe` for Malayalam (`docs/capture-round/contract.md`). The table above
describes the default `SPEECH_TRANSCRIBE_PROVIDER=openai` mode, which is unchanged.

- Settings (backend-only): `SPEECH_TRANSCRIBE_PROVIDER=openai|groq`, `GROQ_API_KEY`,
  `GROQ_TRANSCRIBE_MODEL` (must equal `whisper-large-v3-turbo`, otherwise
  `configuration_missing`) and `GROQ_BASE_URL` (default
  `https://api.groq.com/openai/v1`, HTTPS without credentials/query).
- `transcribe_audio(...)` and `/api/v1/assistant/transcribe` keep their contract. The
  validated WAV goes to `POST /audio/transcriptions` as multipart with
  `response_format=verbose_json`, `temperature=0`, a language-neutral vocabulary prompt
  and `language` only for en/hi hints, through the bounded no-redirect client.
- A Malayalam hint goes straight to OpenAI. A Groq result is accepted only when its
  reported language maps to en/hi and the transcript uses that script; anything else is
  re-transcribed once by OpenAI. Groq's response language format is undocumented, so
  names and ISO codes are both mapped. Groq failures report `speech_unavailable` and are
  never retried on OpenAI.
- Silence guard: if every Whisper segment has `no_speech_prob > 0.6` and
  `avg_logprob < -1.0`, the transcript is empty, so filler Whisper invents on silence
  never reaches the assistant through WhatsApp.
- Groq retains no inference data by default apart from reliability/abuse logs for up to
  30 days; Zero Data Retention in Groq's data controls removes those. Pricing is $0.04
  per audio hour with a 10-second minimum per request.
- `pnpm voice:benchmark --live` reports `stt_provider` per sample; `--live --no-hint`
  exercises detection and the Malayalam escalation.

Not yet run: no Groq key exists in the private secrets file, so no live Groq call,
capability check or Groq benchmark has been made. Keep `SPEECH_TRANSCRIBE_PROVIDER=openai`
until both live benchmark modes pass for all six fixtures.

## Sarvam AI (Malayalam voice round, 28 October 2026)

The human chose Sarvam for speech-to-text in all three languages, and for Malayalam spoken
replies ([contract](malayalam-round/contract.md)). The code defaults are unchanged: `openai`
transcription and `gemini` Malayalam speech.

**Settings** (backend only):
- `SPEECH_TRANSCRIBE_PROVIDER=sarvam`, `SARVAM_API_KEY`, `SARVAM_STT_MODEL=saaras:v3`;
- `MALAYALAM_TTS_PROVIDER=sarvam`, `SARVAM_TTS_MODEL=bulbul:v3`, `SARVAM_TTS_SPEAKER_ML`;
- `SARVAM_BASE_URL`: default `https://api.sarvam.ai`, HTTPS without credentials or query.

Any other model, or a missing key or voice, gives `configuration_missing`.

**Transcription:**
- The validated WAV goes to `POST /speech-to-text` as multipart with the
  `api-subscription-key` header.
- Fields: `model`, `mode=codemix`, and `language_code` (`en-IN`/`hi-IN`/`ml-IN` from the hint,
  otherwise `unknown`).
- The JSON response is capped at 256 KB, and `transcript` at 2,000 characters.
- The BCP-47 code counts only when the transcript is in that language's script
  (`script_language`).
- Empty text or a null language gives an empty `unknown` transcript, so WhatsApp never acts on
  a guess.
- Any failure is `speech_unavailable` and is never retried on another provider.

**Malayalam speech:**
- JSON `POST /text-to-speech` with `language_code=ml-IN`, `speech_sample_rate=24000` and
  `output_audio_codec=wav`;
- `audios` must hold exactly one base64 WAV;
- the WAV is decoded and re-encoded to MP3 by the existing ffmpeg path.

Bulbul v4 Flash has no Malayalam, and v2 is legacy.

**Why `saaras:v3` in `codemix` mode.** The live check wrote spoken amounts as digits in all
three languages ("₹500"), with brand names in Latin script. `saaras:v4` left Malayalam amounts
as words ("അഞ്ഞൂറ് രൂപ"), which FinBoy's amount reader does not parse. The full table is in the
contract.

**Live benchmark** (`pnpm voice:benchmark --live`, six recorded fixtures, 28 October 2026):

| Mode | Language | Intent | Amount | Exact text | Latency |
| --- | --- | --- | --- | --- | --- |
| With hints | 6/6 | 3/3 | 3/3 | 5/6 | 0.42–0.90 s (first call 2.33 s) |
| `--no-hint` | 6/6 | 3/3 | 3/3 | 5/6 | 0.50–0.78 s |

- The Malayalam number clip came back as "₹7860." in digits, against the fixture's words. The
  amount checker had treated the sentence-final full stop as a decimal point, and
  `amounts_in_question` was fixed so voice questions ending in an amount keep it.
- The OpenAI comparison was not rerun: the key in the private secrets file returned
  `401 token_invalidated`.
- The 24 October OpenAI figures in the table at the top of this page are the baseline.

**Privacy:** Sarvam may train on customer content unless the account opts out, and it keeps
workspace data until a retention period is set. Turn off training and set Model APIs to "No
retention" in Sarvam's dashboard before real households' audio is sent. FinBoy sends no IDs or
names beyond the audio or reply text itself, and stores nothing.

**Pricing** (pay-as-you-go, 28 October 2026):
- speech-to-text ₹0.49 a minute, billed per second;
- Bulbul v3 ₹3 per 1,000 characters;
- 60 requests a minute for each.

**Not verified:** real microphone or WhatsApp voice notes from people, and phone playback of
Bulbul audio.
