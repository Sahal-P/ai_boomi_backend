# UX API contract v1.2.0 — 24 October 2026

Baseline b572565aa521a753fbee1271ca0c68e470ff15c8. This committed bootstrap freezes the following contracts for Product. Implementation follows on the same branch. All examples are synthetic. Prefix `/api/v1`; household endpoints retain existing session/Origin protection. Demo reads require no household credentials and perform no persistence. No frontend financial arithmetic.

## Shared types and errors

JSON integers ending `_minor` are paise; currency is INR. Dates are ISO dates; timestamps RFC3339 with offset (IST interpretation). UUIDs are stable IDs. `data_version` and `version` are opaque strings; never parse them. A version covers the household financial snapshot, sources and import state. Capture it from the displayed detail/preview, send it unchanged, and on 409 refetch and ask for a new decision. Previews never write. Existing `GET /transactions` stays an array. Existing routes remain available with additive fields; use the new versioned decisions for mutations.

Error envelope remains `{error:{code:string,message:string,request_id:string}}`, no provider/input detail. Codes: `validation_error` 422, `session_required` 401 (existing auth may use `authentication_required`), `origin_denied` 403, `not_found` 404, `version_conflict`/`decision_conflict`/`import_busy` 409, `demo_read_only` 409, `original_files_required` 409, `source_unavailable` 503. Existing safe codes stay valid. Never translate 401 to an offline message. Bounded queries reject invalid limits/offsets. Missing resources are 404, never an upload error.

`Dataset = "household" | "demo" | "quarantined"`.
`SourceMode = "gmail" | "eml_upload" | "demo_mailbox"`.
`Status = "confirmed" | "needs_review" | "rejected" | "merged" | "failed"`.
`Kind = "purchase" | "salary" | "income_other" | "refund" | "reversal" | "fee" | "bill_payment" | "emi" | "investment" | "transfer"`.
`Category` retains the existing enum in money/models.py. Unsupported enum/input =>422.

## Dataset and money

`GET /demo` => `{dataset:"demo",read_only:true,as_of:string,summary:MoneySummary,transactions:Transaction[],commitments:Commitment[]}`. Stable sample IDs, fixed sample date. `/demo` UI consumes this response exclusively; never send a household import. `POST /imports/demo` is disabled with 409 `demo_read_only` (message directs to /demo); disposable ingestion tests call the pipeline directly.

`GET /money/summary?period=current_month` or `period=month&year=2026&month=10`: existing MoneySummary plus:
```
dataset: "household"; data_version: string;
overdue_commitments_minor: number; uncertain_commitments_minor: number;
unresolved_commitments_minor: number; overdue_commitment_count: number;
coverage: Coverage;
```
`Coverage = {sync_mode:"manual",last_successful_scan_at:string|null,window_start:string|null,window_end:string|null,state:"unknown"|"partial"|"scanned",truncated:boolean,pending_review_count:number,failed_source_count:number,active_import_id:string|null,quarantined_count:number}`. `scanned` means the selected query window was scanned, never a complete bank balance/mailbox. No run =>unknown. Partial failures/truncation =>partial. Pending review count is all unresolved, independent of selected month. Last successful scan and API health are distinct. Categories sorted by descending absolute financial impact, signed net amounts. Existing upcoming field means future/today deductions only. `unresolved_commitments_minor = upcoming + overdue`; uncertain is a subset, conservatively deducted pending repair. Estimate = income - net confirmed outflows - unresolved. Historical summary carries obligations due by period end still unresolved now (not a reconstructed historical balance).

`POST /money/simulations` existing request/response; summary additions bind it to data_version and submitted proposed_monthly_minor. Breakdown adds `overdue_commitments` line.

`GET /money/commitments` preserves upcoming-only array. New `GET /money/obligations?status=unresolved|all|paid|dismissed` defaults unresolved => `{items:Commitment[],data_version:string}`. Each Commitment has existing fields plus `version:string,dataset:"household",liability_state:"upcoming"|"overdue"|"paid"|"dismissed",uncertain:boolean`. `GET /money/obligations/{id}` => `{commitment:Commitment,sources:TransactionSource[],version:string}`. `PATCH /money/obligations/{id}` body `{expected_version:string,label?:string,amount_minor?:positive_integer,due_date?:ISO_date,status?:"upcoming"|"paid"|"dismissed",paid_transaction_id?:UUID|null}` => same detail. Paid link, if supplied, must be a compatible household confirmed outflow; status paid is also an explicit human attestation. Reopening uses upcoming; liability_state is derived from IST today. Changes retain audit provenance.

## Records, evidence, review

`GET /transactions/page` query: `scope=all|month|unresolved` (default month), `period=current_month|month` + optional year/month as above; `status?`, `category?`, `source?:gmail|eml_upload`, `q?:string(1..160)`, `kind?:Kind`, `dataset=household|quarantined` default household, `limit=50` (1..200), `offset=0` (0..1000000), `data_version?:string`. Scope unresolved always forces needs_review and no date restriction; scope all has no date restriction. Optional explicit month with unresolved narrows date only when `period=month`. `data_version` mismatching =>409 so paging cannot silently omit/repeat after writes. Order occurred_at DESC, id ASC.
Response `{items:Transaction[],total:number,unresolved_total:number,limit:number,offset:number,next_offset:number|null,data_version:string,dataset:"household"|"quarantined"}`. total is filtered; unresolved_total is all household unresolved. Existing Transaction fields plus `dataset:Dataset,source_modes:SourceMode[],source_count:number,extraction_quality:"complete"|"partial",payment_verification:"verified"|"unverified"|"failed",version:string`. Extraction quality is not payment probability. `GET /transactions/{id}` existing detail gains `version:string,decisions:Decision[]`; exact links use `/transactions?selected={id}`. Household evidence excludes demo sources. Demo-only IDs return404. Quarantined record inspection is explicit through page dataset=quarantined and detail identifies quarantine; quarantined values never contribute to money/assistant. Source snippets remain bounded/redacted, never bodies.

`GET /transactions/{id}/merge-candidates` => `{items:Transaction[],suggested_id:UUID|null,data_version:string}`; independent of current queue/search, includes compatible confirmed targets, excludes self/rejected/merged/failed and other datasets. Max100, stable suggested-first order. `POST /transactions/{id}/decision-preview` body `DecisionRequest` => `DecisionPreview`. `POST /transactions/{id}/decisions` same body => `DecisionResult`.
```
DecisionRequest = {expected_version:string,action:"confirm"|"reject"|"reopen"|"correct"|"merge"|"keep-separate",correction?:{category?:Category,merchant?:string,amount_minor?:positive_integer,occurred_at?:RFC3339,direction?:"in"|"out",kind?:Kind},keep_id?:UUID}
DecisionPreview = {version:string,action:string,transaction_id:UUID,keep_id:UUID|null,source_count:number,affected_transaction_ids:UUID[],before_summary:MoneySummary,after_summary:MoneySummary}
Decision = {id:UUID,action:string,created_at:RFC3339,undone_at:RFC3339|null,can_undo:boolean}
DecisionResult = {detail:TransactionDetail,decision_id:UUID,data_version:string}
```
Correction must contain >=1 non-null supported field and validate direction/kind; no future timezone-naive timestamps. Confirm can include a correction and saves it atomically before confirming. Reopen restores needs_review; allow rejected->reopen->confirm. Merge preview identifies survivor and source movement. `POST /transactions/{id}/decisions/{decision_id}/undo` body `{expected_version:string}` => DecisionResult. Undo succeeds only if the snapshot has not changed since the decision; later ingestion/links/locks/revisions cause409, never overwrite new work. Undo appends history and preserves decision/revision provenance. Quarantined records are inspection-only until a source-aware forward repair; no accidental confirm into household.

## Imports and sources

`GET /imports?limit=20&offset=0` (limit1..100,offset0..1000000) => `{items:Import[],total:number,next_offset:number|null}` excludes old demo runs. `GET /imports/{id}` remains same counters, plus `started_at:string|null,finished_at:string|null,outcome:"queued"|"running"|"complete"|"partial"|"failed"|"interrupted"|"cancelled",retryable:boolean,retry_strategy:"refetch_gmail"|"select_original_files"|"none",cancel_requested:boolean,window_start:string|null,window_end:string|null,truncated:boolean,data_version:string`. Existing status remains queued/running/completed/failed (outcome distinguishes partial/cancel/interruption). `needs_review` refers to this run's touched pending records; full queue count is separate. Status completed + failed>0 =>partial. No scheduler, no implicit resume.

`GET /imports/{id}/issues?limit=50&offset=0` => `{items:Issue[],total:number,next_offset:number|null}`. `Issue={id:UUID,source_id:UUID,source_mode:SourceMode,reason:"extraction_failed"|"no_supported_events"|"message_unavailable",retryable:boolean,retry_strategy:"refetch_gmail"|"select_original_files"|"none",attempts:number}`. IDs identify messages privately without subject/body/filename. `POST /imports/{id}/retry` body `{expected_version:string,source_ids?:UUID[]}` (max50; omitted =>first50 failed) =>202 `{import_run_id:UUID}`. Gmail only re-fetches selected failed source IDs. Upload retry =>409 original_files_required; user selects original files via existing POST /imports/eml, which now retries matching failed sources. Successful source remains idempotent. Failed-source counts/attempts survive retry; original source retained and never duplicated. `POST /imports/{id}/cancel` body `{expected_version:string}` => Import; sets request, worker checks between bounded batches and before persistence. An interrupted upload requires original files. An interrupted Gmail run can refetch failed IDs; a new normal scan recovers the remaining window idempotently.

Existing connection list/pause/resume/sync retain payloads. Resume only allows scans. Sync starts a new job. Pause requests cancellation of active scans at safe checkpoints. Existing cross-host OAuth, cookies and registered callbacks unchanged. No new provider consent for local ports.

Upload validation remains all-or-nothing before run creation. Invalid upload returns422/400 safe envelope with fixed code; optional `issues:[{index:number,code:"invalid_type"|"too_large"|"invalid_message"}]` is reserved for a later contract update; Product should validate files locally and never expect server-returned filenames in v1.

## Privacy and operational outcomes

`POST /privacy/deletion-preview` body `{connection_id?:UUID}` => `{version:string,connection_id:UUID|null,source_count:number,event_count:number,removed_transaction_count:number,retained_shared_transaction_count:number,removed_obligation_count:number,retained_shared_obligation_count:number,first_received_at:string|null,last_received_at:string|null,backup_retention_days:7}`. `POST /privacy/delete` body `{expected_version:string,connection_id?:UUID}` => `{status:"ok",data_version:string}`; exact version checked under same admission/ledger lock as preview inputs; never silently delete a changed scope. Existing deletion routes stay compatible but UI uses previewed route. Shared canonical records retain remaining evidence; stale/untrusted canonical values are quarantined rather than silently trusted.

`POST /privacy/export` body `{expected_version:string}` => downloadable JSON with Content-Disposition attachment; `{schema_version:"1.0",dataset:"household",exported_at:RFC3339,data_version:string,transactions:Transaction[],commitments:Commitment[],revisions:RevisionView[]}`. No bodies, snippets, merchant raw text from mail, tokens, hashes, bank/account/reference identifiers. Structured user-facing merchant names/amounts/categories/date and corrections are the requested export. Explicit authenticated click only; never background export.

`GET /privacy/isolation` => `{data_version:string,demo_only_transactions:number,mixed_transactions:number,demo_only_obligations:number,quarantined_obligations:number}` (read-only inventory). Additive migration tags deterministic old demo-only records demo; mixed canonical values quarantined, preserves every source/correction/revision. Forward repair documented separately; no deletion/reset or automatic canonical rewrite.

`POST /privacy/task-outcomes` body `{task:"evidence_opened"|"overview_understood"|"review_completed",subject_id?:UUID}` => `{status:"ok"}`; authenticated/exact Origin, validates subject ownership. Existing audit storage, fixed event codes/IDs and no financial/question/mail content. No external analytics.

## Assistant

`POST /assistant/ask` existing text/display_style. Existing answer plus `data_version:string,dataset:"household",resolved_period:{start:ISO_date,end:ISO_date,label:string}|null,display_language:"en"|"hi"|"ml",display_script:"Latn"|"Deva"|"Mlym",evidence_total:number,evidence_sampled:boolean`. Each fact adds `label:string`; `warning_labels:Record<string,string>` localizes warnings in the selected display style. Existing speech_language and providers unchanged. UI uses returned labels, never title-cases internal keys. Evidence is selected from contributing full-scope rows BEFORE ten-row display cap; stable exact transaction IDs. Merchant spend reports gross outgoing, refunds/reversals incoming, and net amount across ALL matching confirmed non-transfer records. Supported periods: today, yesterday, this/current month, last/previous month, YYYY-MM (English and bounded native equivalents); unsupported dates clarify period specifically. No LLM arithmetic. Missing/unverified data retains honest warning. Display language/script differ from spoken language for Hinglish/Manglish.

## Changelog

- v1.0.0 bootstrap: additive read/pagination/coverage; versioned review/undo/preview; isolated demo; recoverable sources; explicit private export; deterministic answer metadata. Implementations must match these names/types; corrections require a committed changelog before dependent UI changes.

- v1.1.0: Import adds `can_continue:boolean`; `POST /imports/{id}/continue` with `{expected_version:string}` starts a new bounded Gmail job using an encrypted provider continuation, preserving the original IST window. Returns202 `{import_run_id:UUID}`; non-continuable=>422 invalid_decision. `GET /imports/{id}/issues` also follows last-attempt provenance on retry runs. Fact display language is hi/ml for romanized styles with script Latn (use hi-Latn/ml-Latn); spoken language remains native. Shared records retained after source deletion are revalidated against surviving claims and user locks; unsupported canonical values are quarantined. Preview counts describe retained records, which may require review.

Snapshot versions include the IST calculation day as well as the database generation; the token stays opaque. Midnight rollover therefore invalidates stale previews.

- v1.1.1 lifecycle clarification: cancel is an idempotent, monotonic request on the exact run ID. Its expected_version identifies the displayed snapshot but progress-only generation changes do not reject cancellation. Completed jobs return their actual terminal outcome without relabeling it cancelled. Financial decisions, undo, recovery retries and destructive previews retain strict generation checks.


`fixtures/actual-http-v1.json` supplies expanded examples captured from real rules
extraction, HTTP routes and a temporary synthetic user on the assigned disposable
PostgreSQL. It includes demo, summary/page/detail/candidates, decisions/preview/undo,
obligations, import history, all display styles, simulation, export and deletion
preview. The bootstrap state/error variants remain in `fixtures/contract-v1.json`.
Regenerate explicitly with `uv run --package finboy-api python
apps/api/tests/ux/export_examples.py`; its fixture guards reject production and other
databases, make no provider calls, and clean up the temporary user.

- v1.1.2: Source events retain original transaction lineage independently of their current canonical record. Deletion previews/removal include orphaned merge stubs and private decision snapshots derived from removed evidence; operational audit stays. Shared/manual records remain, and loss of the last payment proof reopens review without replacing financial values or locks. Unmapped pre-upgrade merges fail closed with 409 `source_lineage_unavailable` before deletion; the production preflight found none. Storage migration head is 0006_event_origins. Public response field names are unchanged.

- v1.1.3: Import `needs_review` is the current distinct unresolved count linked to that run's sources, so confirm/reopen/merge and guarded eligibility repairs update the next action. The original processing counter remains durably stored for history. The legacy transaction array also returns genuine source/payment/version metadata while retaining its array shape. No response fields changed.

- v1.2.0 rollout compatibility: `POST /money/simulations` and `POST /assistant/ask` accept optional strict boolean `include_overdue_line` (default false). The UX client MUST send true. True returns the explicit overdue line. False preserves the current client's four-label enum by combining future and overdue liabilities into its legacy commitments line, while all calculations and additive summary fields stay correct. This keeps the backend-first deployment compatible with the current frontend. No provider or language behavior changes.

The outcome enum also accepts `overview_explanation_opened`: the UX client uses it
for opening the calculation explanation. `overview_understood` is retained only as
a legacy/self-report event; a click must not be presented as observed comprehension.
Human comprehension remains a separate acceptance session.
