# Browser acceptance

Run the actual browser flows in docs/demo-runbook.md against the reviewed integration
environment. This directory records acceptance coverage; it does not pretend a
Playwright suite is installed. Computer QA uses the connected Chrome runtime.

Required viewports: 1440×1000, 390×844, 320×740. Check /, /dashboard, /transactions,
/review, /assistant, /connect, /import/{real run}, /privacy. Observe real imports,
three-source evidence, category correction/history/totals, confirm/reject, simulation,
text + actual audio, keyboard/focus, empty/loading/error/offline/mic-denied/no-WebGL.
Save screenshots and report unexecuted cases explicitly. Never screenshot secrets.

Cross-system executable coverage: `pnpm test:system` exercises actual imports via
HTTP, PostgreSQL, finance APIs, correction/review, multilingual assistant and privacy.
It does not replace browser, human microphone or WhatsApp phone delivery acceptance.
