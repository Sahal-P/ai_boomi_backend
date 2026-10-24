# Capture round — Groq transcription and WhatsApp screenshot capture

The human authorized this round on 24 October 2026 (IST) from main `5d85595`. It
supersedes the conflicting scope and provider statements in `docs/phase1/contract.md`,
`docs/phase1/parallel-completion.md`, the README and `docs/whatsapp.md` only as stated
here. Every other privacy, money, ingestion, production and access rule stays binding.

## Human decisions

- **Speech-to-text:** Groq `whisper-large-v3-turbo` transcribes English and Hindi.
  Malayalam stays on OpenAI `gpt-transcribe`. Published FLEURS results put Whisper
  large-v3 at roughly 104% WER on Malayalam (Fleurs-SLU, arXiv 2501.06117), and the
  turbo model card reports lower accuracy on low-resource languages.
- **Screenshots:** an allowlisted WhatsApp sender may send a payment screenshot.
  FinBoy may create a `needs_review` record from it, and nothing else.
- **Screenshot reader:** OpenAI vision through the Responses API with `store=false`.
- **Production:** WhatsApp stays disabled in production. Verification is local, through
  the existing restricted webhook ingress.

## Lifted and retained non-goals

This round lifts "no payment screenshots, OCR, or WhatsApp expense capture" for the
review-queue flow only. Still prohibited: confirming, editing, merging, rejecting or
deleting records from WhatsApp; automatic confirmation of screenshot-only records;
broadcasts or unsolicited messages; investment picks; storing images, captions,
transcripts or questions; public multi-user access.

## Speech routing

`SPEECH_TRANSCRIBE_PROVIDER` is `openai` (default, unchanged behaviour) or `groq`.

In `groq` mode a Malayalam hint goes straight to OpenAI. Everything else goes to Groq,
with the language forced for English/Hindi hints. FinBoy accepts a Groq result when it
is silence, or when its reported language is English/Hindi and the transcript uses the
matching script. Anything else (Malayalam, a misdetected language, Urdu-script Hindi)
is re-transcribed once by OpenAI. Groq failures report `speech_unavailable` and are
never retried on another provider. Malayalam or uncertain audio can therefore reach
both providers; privacy copy discloses this.

Silence guard: when every Whisper segment has `no_speech_prob > 0.6` and
`avg_logprob < -1.0`, the transcript is empty, so a hallucinated phrase never reaches
the assistant from WhatsApp.

## Screenshot capture

1. The signed webhook admits an `image` message from an allowlisted, enabled sender
   inside the 24-hour window. Captions are ignored.
2. The image is resolved by Graph media ID, limited to JPEG/PNG up to 5 MiB, with the
   existing host allowlist and MIME, size and SHA-256 checks.
3. ffprobe validates one PNG/MJPEG stream through pipes. ffmpeg re-encodes it through
   pipes, removing metadata and capping the longest side at 2048 px.
4. OpenAI vision returns a verbatim transcript of the visible lines and proposed payment
   fields (status, direction, amount, counterparty, reference, date/time), all as
   untrusted data. Code keeps a field only when it appears in the transcript, refuses
   pending/failed/requested/reversed screens, and renders the grounded date as
   `DD-MM-YY HH:MM`, never later than the message. Non-payment images stop here.
5. The grounded fields become one notification line (`Rs. 500.00 paid to Ravi Kumar via
   UPI on 24-10-26 10:42, UPI Ref: 612345678901`) in a minimal RFC822 message from
   `screenshot@whatsapp.invalid`. It runs through the same import pipeline as uploaded
   `.eml` files (masking, rules, cached extraction, claim grounding, reconciliation and
   audit) in a one-message import run with mode `whatsapp_image`. A busy import returns a
   fixed "try again" reply.

   Why one line instead of the raw transcript: the existing claim rules read fields only
   within the claim's own clause. On a Google Pay layout (amount and "Paid to" on separate
   lines) they extracted nothing, and a PhonePe layout that repeats the amount produced
   two events. The grounded line yields exactly one event per screenshot.
6. A single untrusted source cannot exceed 0.706 confidence, below the 0.90 needed to
   confirm, so screenshot-only records land in `needs_review`. A screenshot matching an
   existing bank-email record only adds evidence.

## Additive contract changes

- Settings: `SPEECH_TRANSCRIBE_PROVIDER`, `GROQ_API_KEY`, `GROQ_TRANSCRIBE_MODEL`
  (must equal `whisper-large-v3-turbo`), `GROQ_BASE_URL` (default
  `https://api.groq.com/openai/v1`, HTTPS only) and `OPENAI_VISION_MODEL` (verified at
  setup, no default). All are backend-only.
- `transcribe_audio(...)` and `POST /api/v1/assistant/transcribe` are unchanged.
- Source and import mode value `whatsapp_image` in `email_sources.source`,
  `import_runs.mode`, `InboundMessage.source`, transaction source views, import issue
  views and the records source filter. Screenshot runs have retry strategy `none`.
- WhatsApp receipt kind `image`; error codes `invalid_image`, `capture_unavailable`
  and `capture_busy`.
- Migration `0007_whatsapp_capture` (down revision `0006_event_origins`) only widens
  check constraints.

## Privacy

Image bytes, captions and vision transcripts are processed in memory only. PostgreSQL
keeps what it keeps for email: hashes, provider IDs, structured fields and evidence
snippets of at most 80 characters. Groq keeps no inference data by default apart from
reliability/abuse logs for up to 30 days; enabling Zero Data Retention in Groq's data
controls removes those. OpenAI vision requests set `store=false`. These are application
controls, not a claim of zero upstream retention.

## Runtime

Branch `feat/finboy-voice-capture`; loopback API 8041 and web 3041; disposable database
`finboy_capture` on the shared PostgreSQL at 127.0.0.1:5433. Never stop the shared
container. No test suite runs against production. Releasing to voxpay requires the
human's explicit go-ahead after local verification.

## Outcomes — 24 October 2026

The following table records the initial capture-only local verification on
`feat/finboy-voice-capture` against `finboy_capture`. The subsequent committed AI
assistant integration and its verification are recorded in [handoff.md](handoff.md).
Publication and deployment belong to the coordinated release owner.

| Check | Actual outcome |
| --- | --- |
| `pnpm check` | Passed: Ruff, ESLint, 710 backend unit tests, web tests, strict TypeScript |
| `pnpm build` | Passed |
| `pnpm db:migrate` / `pnpm db:check` on `finboy_capture` | Head `0007_whatsapp_capture`, no drift; downgrade to 0006 and re-upgrade passed |
| `pnpm test:integration` on `finboy_capture` | 55 passed, including six screenshot capture tests |
| `pnpm voice:benchmark` (offline) | 28/28 intents, six fixtures decode, zero live calls |
| Browser at 1440×1000, 390×844, 320×740 | Synthetic screenshot record shows its source label and filter, screenshot-specific review/evidence/payment copy, confirm works, Sources lists the run, Privacy copy updated, no overflow or console errors |

The integration tests cover one `needs_review` household record per screenshot,
idempotent retries, bank-alert reconciliation in both arrival orders through the hashed
UPI reference, privacy deletion, the busy path, and a signed duplicated image webhook
processed exactly once. The raw UPI reference never reached PostgreSQL.

Still unverified (needs the human or live providers):

- Live Groq transcription: no `GROQ_API_KEY` in `~/.config/finboy/secrets.env`, so the
  capability check and both live benchmark modes have not run. Keep
  `SPEECH_TRANSCRIBE_PROVIDER=openai` until they pass.
- Live OpenAI vision on a real screenshot: no `OPENAI_VISION_MODEL` is configured or
  verified. Vision, Meta and the model were fakes in every test.
- Phone acceptance: no real WhatsApp image or voice note was sent; production WhatsApp
  stays disabled.
- Import result pages still use email wording ("Possible money emails found") for a
  screenshot run.
