# Synthetic fixtures

A1 owns `demo_mailbox/` and `llm_cassettes/`; A3 owns `voice/`.
Owners add these datasets in their feature work. Follow contract §8: synthetic
identities, fake references, masked accounts, and X-FinBoy-Synthetic email headers.
Never add real messages, credentials, tokens, or personal financial records.

`triage/` (fast decisions round) holds the d1-ultra gate for `pnpm eval:triage`: synthetic diary
messages and questions in `cases.json`, and phone pictures in `images/`. Each picture is an SVG
source and its PNG, rendered with macOS Quick Look on a square canvas and cropped to 720×1440.
