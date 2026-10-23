# Product UI integration

Agent 5 took over the Agent 2 frontend scope with direct human authorization after
confirming that Agent 2 was not running. Implementation is on feat/finboy-integration.
The premium design is a reviewed uncommitted snapshot from the preserved design
worktree, not a merge of its scaffold HEAD. Source file hashes are in
handoffs/design-snapshot.json. No source/reset/stash/commit was made there.

The snapshot supplies the marketing layout, brand, tokens, motion/3D, models and
navigation. New presentational product components supply dashboard, transactions,
source evidence/history, review actions, simulation and three-language assistant.
A2 connect/import/privacy flows and shared API helpers were preserved. Binary
speech uses the shared validated API base. Every JSON domain response is validated
with zod, including actual Agent 1 PostgreSQL response examples in web client tests.
Amounts stay integer paise; only display formatting/input conversion runs in web.
All totals/simulations and assistant facts come from the backend. Empty/offline/
failed-provider states never fabricate data or audio.

Small hooks own requests, aborts, state and recording lifetime. Microphone input
stops before 30 seconds, caps 3 MB, stops tracks on unmount, and stays memory-only.
Transcripts are editable and require Ask. Audio is fetched independently, MIME/size
checked, exposed through a Blob URL and revoked on replacement/unmount. Speech
failure preserves text. Source evidence is capped by backend and client schemas;
correction submits only changed fields, preserving narrow user locks.

`?graphics=off` forces the same no-WebGL path as a failed context probe. All useful
controls/text are DOM and work in that mode. Reduced-motion CSS and the snapshot's
motion hooks remain. Marketing simulation numbers are labeled synthetic demo;
marketing voice choreography has an explicit illustrative-preview accessibility label.
It is not a live microphone/provider state.

New npm packages were imported at the snapshot's pinned versions: Plus Jakarta Sans,
Anek Malayalam, @gsap/react, GSAP, R3F/fiber/drei/postprocessing, three/@types/three,
postprocessing, maath, motion, lenis and gltfpack (asset build tool). Existing
pnpm-lock.yaml was copied with the exact package snapshot, then frozen install passed.
No Python/GPU/local Chatterbox dependencies were added. Official R3F Canvas fallback
and GSAP React documentation were reviewed before integration. A transient pinned
Prettier invocation formatted new files; it was not added as a project dependency.

Verification: pnpm check/build passed; 15 web client tests include actual API schema
compatibility, malformed payload rejection, exact merge request, integer input,
MP3 failure not becoming fake audio, and multipart transcription contract.
Chrome checked six product pages at all 1440×1000, 390×844 and 320×740 sizes without
horizontal overflow. Actual imported totals, simulation and category correction were
verified through the UI. Supporting screenshots live in the task's integration
visualization directory. Default graphics and explicit fallback were inspected.
Microphone permission was allowed by the human; denied-permission browser acceptance
is still pending. See integration handoff for final live/remaining acceptance state.
