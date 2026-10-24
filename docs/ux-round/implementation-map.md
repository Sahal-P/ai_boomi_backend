# F01–F38 completion matrix

Backend and Product are assembled on `feat/finboy-ux-integration`. The human confirmed
Product finished at `5fd2467` and transferred integration ownership. **Implemented** below
means the software behavior exists and has the listed verification; it does not substitute
for human acceptance. No comprehension, phone performance or playback success is invented.

Evidence: **DB** = actual HTTP/rules/PostgreSQL tests (49); **UI** = browser journeys
at 1440×1000, 390×844 and 320×740 using the explicitly test-only contract double;
**Real UI** = assembled production build, same-origin HTTPS proxy, actual FastAPI and
disposable PostgreSQL, with synthetic uploads and no API double. Provider HTTP boundaries
are mocked in DB tests. Final commands and deployment outcomes: [integration handoff](../handoffs/ux-integration.md).

| Finding | Backend | UI | Verification / remaining acceptance |
| --- | --- | --- | --- |
| F01 | Implemented: dataset separation/backfill | Implemented: read-only sample destination | DB pipeline isolation, mixed quarantine, history preservation and invalid-payment reopening; real UI sample/household separation. Production inventory and additive migration in handoff. |
| F02 | Implemented: overdue/uncertain deductions and repair | Implemented: evidence/resolve/correct dialog | DB due-day/month/year rollover; real UI overdue deduction, resolution/reopen and correction. |
| F03 | Implemented: durable outcomes/current counters | Implemented: partial outcome and Review primary | DB partial upload/retry; UI outcome hierarchy and real uploads. Household comprehension session remains. |
| F04 | Implemented: failed retry and successful dedupe | Implemented: issues/retry/original-file staging | DB stable failed IDs/attempts, selected Gmail refetch, upload retry; UI recovery; real UI idempotent reupload. Google HTTP mocked locally. |
| F05 | Implemented: scan window/cap/continuation/freshness | Implemented: qualifiers beside estimate/Sources | DB IST window, 500 cap, encrypted continuation; UI partial/stale/manual coverage. No automatic or complete-mailbox claim. |
| F06 | No backend change | Implemented: account menu and scroll spacing | UI fixed-layer intersections at 320/390, tab bar hidden while typing. Physical phone keyboard acceptance remains. |
| F07 | Implemented: independent confirmed targets/preview | Implemented: side-by-side compatible matches | DB preview/merge/undo; UI filtered confirmed merge; real UI deliberate merge into confirmed record and undo. |
| F08 | Implemented: extraction vs payment metadata | Implemented: intelligible review reasons, no percentage | DB separate states; UI missing-proof guidance. Human interpretation remains unobserved. |
| F09 | Implemented: atomic correction and confirmation | Implemented: Save and confirm/dirty guards | DB supported fact changes; UI Escape/navigation/session draft preservation. Drafts stay in memory. |
| F10 | Implemented: reversible versioned decisions | Implemented: Undo/reopen/history | DB source/lock/revision/link preservation and stale undo refusal; real UI decision and merge reversal. |
| F11 | Implemented: date/direction/kind and obligation repair | Implemented: bounded correction forms | DB full fact repair and obligation evidence/resolve/correct; real UI obligation repair/reopen. |
| F12 | Implemented: all-unresolved/counts/pagination | Implemented: month/URL/paging controls | DB old unresolved and 201+ rows; UI paging; real UI 205 older source-backed uploads in five batches, record 201 reached. |
| F13 | Implemented: generation plus IST-day version | Implemented: submitted amount/stale results | DB version trigger/clock tests; UI edited-input/changed-record staleness and preserved successful result on error. |
| F14 | Implemented: safe auth/Origin/access contracts | Implemented: safe return paths/in-place reauth | Auth/CORS/redaction regressions; UI unsafe redirect and expired-session dirty draft checks. No public signup. |
| F15 | Implemented: complete merchant/refund/date arithmetic | Implemented: supported prompts/period clarification | DB 16-record gross/refund/net and relative-period tests; real UI food answer requires exact amount and evidence. |
| F16 | Implemented: relevant evidence before cap/exact IDs | Implemented: exact citations/back continuity | DB income evidence/sampled totals; UI citation/back; real UI exact record/evidence dialog. |
| F17 | No backend change | Implemented: readable navigation contrast | UI rendered contrast >=4.5:1 and labels >=11px at all three widths. Physical-device legibility remains human acceptance. |
| F18 | Implemented: real HTTP fixtures/CI persistence | Implemented: three-width browser harness | Combined check/build, DB migration/drift/49 tests, UI and real UI suites. CI runs both; doubles never count as real integration. |
| F19 | Implemented: status and import discovery | Implemented: Sources management | UI account/scan/upload/history placement; real UI staged source import. Privacy retains destructive controls. |
| F20 | Implemented: history/interruption/recovery counters | Implemented: reconnect polling/progress/history | DB worker-lock interruption and committed counters; UI dropped poll recovery; real UI terminal outcomes. |
| F21 | Implemented: cancellation safe checkpoints | Implemented: separate pause/allow/scan/cancel copy | DB committed results preserved; UI accurate controls. Allowing scans does not claim a job resumed. |
| F22 | Implemented: reasons/aggregate unresolved count | Implemented: attention queue/next/previous | UI productive task sequence; real UI review/undo/filtered merge. Human task timing remains unobserved. |
| F23 | Implemented: filtered and aggregate totals | Implemented: URL/debounce/clear/filtered empty | DB filtered zero vs unresolved 201; UI never equates filtered-empty with completion; outcome waits for refreshed zero. |
| F24 | Implemented: event/provenance/effect fields | Implemented: kind/source/payment/effect labels | DB deterministic refund/transfer effects; UI row labels; real UI source-backed record evidence. |
| F25 | Implemented: signed categories/exact drilldown | Implemented: clickable category and obligations | DB linked-refund categories and explicit overrides reconcile with summary/list/assistant; UI exact-period drilldown. |
| F26 | Safe task errors | Implemented: keyboard/focus/status announcements | UI skip/dialog-return/help/live regions; duplicate mobile undo messages removed. Human screen-reader session remains. |
| F27 | Preserved: independent speech failure/text fallback | Implemented: cancellable voice/transcript/playback | UI synthetic stream/tone and denied permission; historical production media HTTP evidence. Real microphone/phone playback remains pending. |
| F28 | Implemented: period/display/script/speech/version | Implemented: paired submitted turns/cancel/session | UI preserves earlier result/style; real UI supported successful answer. No question storage or analytics. |
| F29 | Implemented: source-aware preview/delete/export | Implemented: impact/retention/export controls | DB shared/manual/merge-origin/snapshot/last-proof behavior; UI and real UI preview/export. No destructive live-household test. |
| F30 | Implemented: bounded multipart/retry behavior | Implemented: stage/validate/remove/explicit import | UI invalid-file/size/cancel behavior; real UI 42-file upload and paging batches. Bodies remain memory-only. |
| F31 | Implemented: localized facts/warnings/script metadata | Implemented: localized answer period/evidence/playback | DB native/romanized language tests; UI lang tags and localized controls. Fluent Hindi/Malayalam comprehension and phone pronunciation remain pending. |
| F32 | No backend change | Implemented: consistent compact task headers | UI PageHeader/task-title/grid checks at three widths. First-use task recognition remains human acceptance. |
| F33 | Implemented: fixed safe codes/request IDs | Implemented: task-oriented recovery content map | UI errors identify task/recovery; no provider exception details or credentials. |
| F34 | Implemented: missing/conflict/auth/unavailable | Implemented: independent panel/contextual states | UI secondary failure preserves primary, retryable evidence, missing import, offline/expired/loading states. |
| F35 | No backend change | Implemented: static daily visuals/fallback | UI daily routes carry no WebGL; marketing no-WebGL/reduced motion. Mid-range physical phone startup/input/battery/transfer measurements remain pending. |
| F36 | Implemented: current architecture/domain/operations docs | Implemented: current UI/design/spec references | Documents match actual routes, contracts and state matrix; nonexistent styleguide promise removed. |
| F37 | Stable IDs/IST metadata | Implemented: task titles/date style/keyboard help | UI route titles/keyboard/date checks; private household sign-in explanation and support path. |
| F38 | Implemented: allowlisted operational task events | Implemented: evidence/open-explanation/zero-queue measures | Explanation click never claims understanding; no amounts/questions/merchants in events. Observed pilot sessions and baseline task measures remain pending. |
