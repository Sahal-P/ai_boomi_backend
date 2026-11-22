# Conversation round — contract (22 November 2026)

FinBoy keeps the WhatsApp conversation of every household that agrees: what it sends, what FinBoy
replies, its voice notes (the recording and the words heard) and its photos. Admins can read the
conversation, play the voice notes and open the photos in the admin panel. This helps support,
fixing mistakes, and making FinBoy better and more personal.

It supersedes earlier statements only where it says so:
- "Never store messages, audio, images or transcripts" (pilot, sign-up, money manager, capture and
  Malayalam rounds), and "audio, photos, screenshots and diary messages are still never stored"
  (advisor round). These no longer apply to a household that agreed (below).
- "Admins never see … messages, chats" (admin, advisor and names rounds). Admins now see the kept
  messages of households that agreed, and their Ask chats on the web from the day they agreed.
- "PostgreSQL is the only persistent service": kept voice notes and photos are files in a private
  Cloudflare R2 bucket; their rows stay in PostgreSQL.

Everything else still binds:
- Statement PDFs, uploaded emails, quick add input and login codes are never kept. Card,
  account, reference and phone numbers and UPI IDs that people type are masked before anything
  is kept.
- Logs never carry message text, transcripts or file names.
- WhatsApp never merges or deletes records.
- Every other privacy promise holds.

## Human decisions (22 November 2026)

- **Tell people.** The landing hero says that continuing agrees to the terms, and links to
  `/terms`. That page says messages, voice notes and photos are kept and that the FinBoy team can
  see them. WhatsApp sends no consent card, banner or footer.
- **The first message continues.**
  - A greeting gets the welcome. Anything else is handled as a diary message.
  - There is no Agree / No thanks card, including for households that joined earlier.
  - A stored decline (`messages_declined_at`) is left as a decline.
  - The owner, who runs FinBoy, is kept from the release.
- **No app-level encryption.** Text sits in plain PostgreSQL columns, as Ask chats already do.
  Files sit in R2, which encrypts at rest on Cloudflare's side.
- **Storage.**
  - Cloudflare R2, reusing the marketing app's existing R2 keys and its private bucket
    `finboy-growth-media`.
  - Files go in their own folder: `finboy-conversations/` in production,
    `finboy-conversations-dev/` elsewhere.
  - A dedicated bucket later needs env values only.
- **Media kept:** voice notes and photos. Statement PDFs are logged as "PDF statement" next to
  FinBoy's reply; the file is never kept. FinBoy's spoken replies are kept as the words it said.
- **How long:** until the household clears its chat history or deletes its account, or an admin
  erases it.
- **Where:**
  - branch `feat/finboy-conversation-log` from `main` `53749df`;
  - loopback API 8121 and web 3121 (Playwright 3122);
  - disposable database `finboy_signup`;
  - migration `0020_conversations`;
  - one new dependency, `boto3`.

## Flag

`CONVERSATION_LOG_ENABLED` (off by default) turns the whole round on:
- **While off:** nothing is written.
- **While on:** a household's messages are kept from its first message, or from the next message
  if it already uses FinBoy and has not declined.
- **Startup:** with the flag on, startup fails unless `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`,
  `R2_SECRET_ACCESS_KEY` and `R2_BUCKET` are set.
- **Folder:** `R2_PREFIX` picks the folder; unset means one folder per environment.
- **System page:** shows "Message log" and "Voice notes and photos (R2)".

## What is kept (`conversation_messages`, `0020_conversations`)

| Column | Holds |
| --- | --- |
| `direction`, `kind` | in or out; text, voice, photo, document, tap, command, buttons, list, voice_reply, template |
| `text` | what was written, masked; for a spoken reply, its words; for a template, its name and values |
| `transcript`, `language` | what speech-to-text heard in a voice note, and in which language |
| `choices` | the button or list titles FinBoy offered, or the choice a tap made |
| `media_key`, `media_type`, `media_bytes` | a voice note or photo in R2: `<prefix><household>/<message>.<ext>` |
| `outcome`, `receipt_id`, `delivery_id` | a send's state, and links to WhatsApp's receipt (its error code) and delivery (delivered/read) |

`users` gains `messages_kept_from` and `messages_declined_at`. The admin audit actions
`messages_viewed` and `media_opened` are new.
The downgrade refuses while any message remains, because its files in R2 would lose their only
record.

**Recorded where:**
- **Inbound messages:** at admission, beside the receipt. Only admitted messages are recorded;
  ignored ones (after STOP, stale) are not.
- **Transcripts:** where speech-to-text runs, in their own transaction.
- **Replies:** in `send_reply`, the single choke point, for every attempted send.
- **Sends outside replies:** reminders, check-ins and coach messages.
- **Files:**
  - The per-message Meta client holds what it downloaded.
  - After the reply has gone, the voice note or photo is uploaded to R2. Replies are never
    slower.
  - A voice note that couldn't be heard keeps its audio.
- **Failures:** writing is best effort. A failure logs `conversation.log_failed` with a stage only
  and never changes a reply.

## Telling households

- The only new line is on the landing hero, under Start on WhatsApp: continuing agrees to the
  terms and conditions, linked to `/terms`. It is not repeated on the nav, the bottom button,
  feature pages or in WhatsApp.
- "clear chat history" (Hindi "चैट हिस्ट्री मिटाओ", Malayalam "ചാറ്റ് മായ്ക്കൂ") deletes the kept
  messages and their files whenever the log is on.

## Deletion and export

- **Erasure.** `remove_household_data` is shared by "Delete my account", pilot erasure, the
  admin's erase and declined sign-ups.
  - It deletes the household's whole R2 folder first, orphans included, then its rows.
  - If R2 can't be reached, or files exist while R2 isn't configured, it answers `try_later` and
    deletes nothing, so no file outlives its row.
  - Keep the R2 values in the env while any file remains.
- **"Clear chat history"** on the Memory page and on WhatsApp also clears the kept messages and
  their files.
- **"Export"** (Privacy & data) adds `messages`: words, transcripts and whether a file was kept.

## Admin

- `GET /api/v1/admin/households/{id}/messages?before=` returns `MessagePage`, newest first, 50 a
  page:
  - WhatsApp rows with their delivered/read status and the receipt's error code;
  - the household's Ask chats on the web from `messages_kept_from` on, masked the same way;
  - the first page records `messages_viewed`.
- `GET /api/v1/admin/messages/{id}/media` streams the file from R2 through the API:
  - every open needs an admin session and records `media_opened`;
  - no shareable links;
  - headers: `no-store`, `nosniff` and an inline disposition;
  - `media_unavailable` (503) while R2 can't be reached.
- `HouseholdDetail.messages` gives kept-from, declined and a count.
- `MessageRow` and `MessagePage` are the only admin models that carry content. The boundary test
  allows them on the messages route only.
- Web: `/admin/households/messages?household=<id>`, linked from the household's "Messages" part.
  - The conversation is drawn as WhatsApp draws it.
  - A voice note plays in a native audio player, with what was heard under it.
  - A photo opens on request.
  - "Load earlier messages", and states for loading, empty, not agreed, declined and errors.

## Privacy notice

The Privacy Policy, Privacy & data, the landing's trust section and "How it works", and the SEO
pages say:
- what is kept, if you agree, and that the FinBoy team can see it and why;
- that each open is recorded;
- that Cloudflare stores the files;
- how long they are kept, and how to clear them.

They go live with the web release, before the flag is turned on.

## Verification (22 November 2026)

Run on `feat/finboy-conversation-log` against the disposable `finboy_signup` database with
`OPENAI_API_KEY` blank, loopback API 8121 and web 3121.

- **Checks:** `pnpm check` passes:
  - 1,716 API unit tests, 139 web unit tests and 20 SEO tests, with lint, format and types clean;
  - the new tests cover masking, the gate, the R2 adapter against botocore's stubber, the
    one-time card, the admin routes and the updated boundary test.

  `pnpm build` passes with `/admin/households/messages`.
- **Database:** `0020_conversations` upgrades with no drift (`pnpm db:check`), then downgrades and
  upgrades again. `pnpm test:integration` passes 129 tests, including the six new ones:
  - a signed admission through to rows: text, voice, tap, replies, transcript, R2 upload, export
    and clearing;
  - delivered/read status in the admin view;
  - web Ask chats only from the agreement date;
  - nothing kept while off, before agreeing or after STOP;
  - erasure deleting the R2 folder, orphans included, before the rows;
  - 52 messages in one second paging without gaps.
- **Live R2** with the marketing app's keys, in `finboy-conversations-dev/`:
  - put, read back byte-for-byte;
  - a folder delete through `ListObjectsV2` + `DeleteObjects` removed 2 files, and both were
    gone afterwards.
- **Real local API in the browser:**
  - A synthetic household's conversation renders as a WhatsApp chat.
  - The voice note (macOS `say` + `afconvert`, AAC) played from R2 through the API: 2.5 s, no
    errors. The photo opened.
  - The audit log shows "Read a household's messages" and "Opened a voice note or photo".
  - At 375 px there is no sideways scroll. A household that hasn't agreed and an unknown ID show
    their states.
  - API logs held only fixed codes: no words, transcripts or keys.
  - Erasing it from the panel left 0 rows and 0 R2 files.
- **Playwright** at 1440, 390 and 320 px:
  - `admin.spec.ts`: 56 passed, 1 skipped (live only), including the new Messages journeys.
  - Full suite: 549 passed and 129 skipped. The copy specs failed until their assertions were
    updated for the new privacy wording, then passed.
  - The only remaining failure is `landing.spec.ts:85` ("Typing is free"), whose region no
    longer exists on `main`, as the names round recorded.
- **Not verified here:**
  - a real WhatsApp voice note or photo from a phone, and Meta's OGG/Opus playback in Safari;
  - a native speaker's check of the Hindi and Malayalam cards;
  - the production release.
