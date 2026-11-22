# Feedback round — contract (22 November 2026)

Households tell the FinBoy team about problems and ideas from the web app, and see what became of
each one. The team reads reports on an admin Feedback page and the owner gets an email for each
new report.

It supersedes earlier statements only where it says so:
- "Admins never see … messages" (admin, advisor and names rounds). Admins now also read the
  feedback a household sends, with its screenshot. Each report opened is audited.
- "PostgreSQL is the only persistent service". As in the conversation round, screenshots are files
  in the private Cloudflare R2 bucket, and their rows stay in PostgreSQL.
- "Images are never stored". A screenshot a household chooses to attach to feedback is kept until
  the household deletes the item or its account.

Everything else still binds:
- Logs never carry feedback text, screen paths or object keys.
- The owner's email carries no words, household names or screenshots.
- Every other privacy promise holds.

## Human decisions (22 November 2026)

- **Placement.** "Send feedback" sits in the account menu, after Privacy & data, on phones and
  desktop. It opens `/feedback?from=<the current path>`.
- **Screenshots.** One optional screenshot per report.
- **The team.** An admin Feedback page, plus an email to the owner for each new report.
- **Status.** The household sees each item as New, Planned or Done.

## What a household sends

| Field | Rule |
| --- | --- |
| `kind` | `problem`, `idea` or `other` |
| `message` | 1–2,000 characters, trimmed. The page asks people to leave out card numbers, passwords and one-time codes. |
| `page` | The app path the menu was opened from: a path only, ≤ 200 characters. The browser and the API both drop queries, fragments and other sites. |
| `screenshot` | Optional `{type, data}`: PNG, JPEG or WebP, base64, at most 1.5 MB decoded. |

- **The screenshot is redrawn on the device.** The browser draws the picked picture on a canvas.
  - The copy is at most 1,600 px wide and 4,000 px tall, never larger than the original.
  - It is WebP, or JPEG where the browser can't write WebP, at falling quality until it fits.
  - The file's location, camera and other details never leave the device.
  - No new dependency.
- **The API checks the bytes.** It decodes strictly, checks the size and checks that the first
  bytes match the declared type (`invalid_screenshot` 422, `screenshot_too_large` 413).
- **Limits.**
  - 10 reports per household per day (`feedback_limit` 429).
  - In production the access middleware refuses a write to `/api/v1/feedback` over 2.2 MB before
    reading it.
  - Only writes are size-checked; reads carry no body.

## What is kept

Table `feedback` (migration `0022_feedback`), deleted with its household (`ON DELETE CASCADE`):
- `id`, `user_id`, `kind`, `message`, `page`;
- `screenshot_key`, `screenshot_type` and `screenshot_bytes` (all null without a screenshot);
- `status` (`new` | `planned` | `done`), `created_at`, `status_changed_at` and `notified_at`.

Check constraints cover the kinds, statuses, types and lengths.

**Screenshots** go in the conversation log's private R2 bucket, using the same `R2_*` values:
- The key is built from IDs only: `finboy-feedback/<user_id>/<feedback_id>.<ext>` in production,
  and `finboy-feedback-dev/` elsewhere (`Settings.feedback_prefix`, not configurable).
- The row is committed first, then the file is put.
- If the upload fails, the report is kept without the screenshot. The reply says
  `screenshot_saved: false` and the page says so.
- Without R2 values the list says `screenshots: false` and the page hides the picker.

## API

Household routes use the household session (`CurrentUser`), the origin rules and the error
envelope:

| Route | Does |
| --- | --- |
| `GET /api/v1/feedback` | The household's last 50 items, newest first, and `screenshots`. `Cache-Control: no-store`. |
| `POST /api/v1/feedback` | Keeps a report (201, `{item, screenshot_saved}`), then emails the owner as a background task. |
| `DELETE /api/v1/feedback/{id}` | Deletes the household's own item and its screenshot (204). Another household's item, or a missing one, is `feedback_not_found` (404). An unreachable R2 is `try_later`, and nothing is deleted. |

Admin routes use `CurrentAdmin`. Their models live in `services/admin/views.py`:

| Route | Does | Audit |
| --- | --- | --- |
| `GET /api/v1/admin/feedback?status=&offset=` | 50 per page: household, kind, status, date, whether there is a screenshot, and the count of New ones. No words. | — |
| `GET /api/v1/admin/feedback/{id}` | The words, the screen and the status dates. | `feedback_viewed` |
| `PATCH /api/v1/admin/feedback/{id}` | `{status}`. The household sees it on its page. | `feedback_status_changed` |
| `GET /api/v1/admin/feedback/{id}/screenshot` | The file from R2, inline, `no-store`, `nosniff`. | `feedback_screenshot_opened` |

The admin overview gains `feedback_new`. The admin nav gains Feedback, under More on phones.
`/admin/feedback?open=<id>` opens a report directly; the owner's email links there.

## The owner's email

- Sent through Resend (`RESEND_API_KEY`) to `FEEDBACK_EMAIL`. With either unset, no email is sent.
- The email has:
  - the subject "FinBoy feedback: a problem" (or "an idea", or "feedback");
  - whether there is a screenshot;
  - a link to the report in the admin panel.
- It never carries the words, the household's name or number, or the screenshot.
- It is sent once: `notified_at` is set after Resend accepts it.
- A failure logs `feedback.notify_failed` (the report ID only). The report stays on the admin page.
- `FEEDBACK_EMAIL` is the owner's private address. It lives only in `/etc/finboy/production.env`,
  never in the repository.

## Deletion and erasure

- A household deletes its own items on the page; the screenshot goes before the row.
- Account deletion (`remove_household_data`) removes the household's `finboy-feedback/<user_id>/`
  folder, then its rows. Like the conversation log, it answers `try_later` while a screenshot
  exists but R2 isn't configured or can't be reached.
- Migration `0022` downgrades only once no feedback rows remain.

## Logging

Only `feedback.screenshot_failed` and `feedback.notify_failed`, each with the report ID. Never the
message, the screen path, the object key or the email address.

## Not in this round

- Feedback on WhatsApp, replies to households beyond the status, or more than one attachment.
- A public roadmap, or votes.
- Editing a sent item (delete and send again).

## Verification

- API unit tests cover:
  - validation and screenshot checks;
  - the daily limit;
  - an R2 failure keeping the report;
  - delete touching only the household's own items;
  - an email without the words, sent once;
  - logs without the words;
  - erasure order;
  - the admin routes and their audit entries;
  - the production size cap.
- Integration covers `0022` up and down, and erasure of feedback rows.
- Web tests cover the client schemas, request bodies, error codes, the screen path filter and the
  screenshot sizing.
- A browser check at desktop and 375 px covers the menu item, sending with and without a
  screenshot, the status after an admin change, delete, and the admin list, report, screenshot
  and status.

## Release

1. Backend first, per [production](../production.md#feedback-release): backup, `alembic upgrade`
   to `0022`, drift check, switch, health.
2. Push main for the web.
3. Add `FEEDBACK_EMAIL` over SSH stdin, after the human confirms the address, and restart
   `finboy.service`.
4. Live check:
   - send a Problem with a screenshot from the owner's household;
   - open it in the admin panel, view the screenshot and set it to Done;
   - confirm the email arrived and the page shows Done.
