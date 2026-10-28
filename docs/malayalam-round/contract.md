# Malayalam voice round — contract (28 October 2026)

This contract supersedes earlier statements only where it says so. Two statements give way:
- the sign-up round's Hindi/English-only WhatsApp diary, including its "not in this round:
  Malayalam WhatsApp replies" ([sign-up contract](../signup-round/contract.md));
- the capture round's "Malayalam always uses OpenAI" rule, when the Sarvam provider is chosen.

Everything else in those contracts still binds.

## Human decisions

- **Speech-to-text:** Sarvam AI Saaras for English, Hindi and Malayalam
  (`SPEECH_TRANSCRIBE_PROVIDER=sarvam`).
- **Malayalam spoken replies:** Sarvam AI Bulbul v3 (`MALAYALAM_TTS_PROVIDER=sarvam`). English
  and Hindi replies stay on Resemble.
- **Full Malayalam:** quick add and the WhatsApp money diary read and answer Malayalam.
- **Where it lives:**
  - branch `feat/finboy-malayalam-voice`, cut from `feat/finboy-signup` at `4f0a56f`;
  - loopback API 8061 and web 3061, disposable database `finboy_signup`;
  - no migration, because the language CHECKs already allow `ml`.

The code defaults stay `openai` (speech-to-text) and `gemini` (Malayalam speech), so production
behaves as before until the human releases this ([production](../production.md#sarvam-speech-release-procedure)).

## Live checks (28 October 2026, synthetic audio only)

**Choosing the model.** Five synthetic sentences (Malayalam, Hindi, English) were spoken by
Bulbul and transcribed by each model and mode:

| Model and mode | Malayalam amounts | Hindi "Swiggy पे पाँच सौ" |
| --- | --- | --- |
| `saaras:v3` codemix | ₹500, ₹25000, ₹1200 (digits) | "Swiggy पे ₹500" |
| `saaras:v4` transcribe | "അഞ്ഞൂറ് രൂപ" (words) | "स्विगी पे ₹500" |
| `saaras:v4` codemix | words | "Swiggy पे पाँच सौ रुपये" |

FinBoy reads amounts deterministically and does not read Malayalam number words. So only
`saaras:v3` is accepted, always in `codemix` mode.

**Automatic language detection** (no hint) returned:
- `ml-IN` at probability 1.0;
- `hi-IN` at 0.999;
- `en-IN` at 1.0.

**Benchmark.** `pnpm voice:benchmark --live`, with and without hints, on the six recorded
fixtures:
- every sample passed the language, intent and amount checks;
- exact text matched 5 of 6. The Malayalam number clip came back as "₹7860" in digits instead
  of the fixture's words;
- each call took about 0.4–0.9 s, with 2.3 s for the first, cold call.

The amount checker had treated the full stop in "…₹7860." as a decimal point. It was fixed in
`amounts_in_question`, with tests.

**OpenAI comparison.** Not run: on 28 October the OpenAI key in the private secrets file
returned `401 token_invalidated`. The recorded 24 October OpenAI baseline is 5/6 exact and 3/3
amounts ([voice](../voice.md)).

**Bulbul v3 Malayalam:**
- returns one 24 kHz WAV per request, converted to MP3 as before;
- four stock voices were generated for the human to choose from: kavitha, roopa, shruti and
  gokul. `SARVAM_TTS_SPEAKER_ML` holds the choice, and it has no default.
- In one synthetic round trip "പാൽക്കാരന്" was heard as "തായ്ക്കാരന്". Payee names are always
  shown on the card, and nothing counts until a tap.

## What people get

**Voice:**
- Web Ask and quick add's **Say it** auto-detect the language.
- WhatsApp voice notes are sent with the household's language as a hint.
- A failure is reported, never retried with another provider.
- Nothing heard means an empty transcript, and FinBoy never guesses.

**WhatsApp:** a text in Malayalam script is answered in Malayalam, and `ml` chooses it at any time
(since 29 October 2026, [Reply language](../whatsapp.md#reply-language-29-october-2026)). Before
agreeing, a language command brings the consent card in
that language; afterwards it brings one short note. The Malayalam diary has, name for name with
`english.py`/`hindi.py` (`malayalam.py`):
- consent, welcome, record and due cards and their buttons (each at most 20 characters);
- dues, "കണക്ക്" for the week's summary, and sign-in, sign-up and link cards;
- spoken twins for every card;
- നിർത്തുക or നിർത്തൂ to stop, and തുടങ്ങുക or തുടങ്ങൂ to start.

The consent cards each name the other two languages.

**Reading money (`statement.py`):**
- the prompt covers Malayalam and Manglish;
- the question words include എത്ര anywhere in the sentence;
- dates: ഇന്നലെ, മിനിഞ്ഞാന്ന്, "N-ാം തീയതി";
- due words: തവണ, കുടിശ്ശിക, അടയ്ക്കണം;
- payee names never contain രൂപ;
- the development rules reader knows the Malayalam verbs. A due's day of the month is no longer
  read as a second amount.

**Amounts:**
- Digits, Malayalam digits ൦–൯ and രൂപ are read.
- Malayalam number words are not read, so a typed "അഞ്ഞൂറ്" gets "how many rupees?" in
  Malayalam. Spoken amounts arrive as digits.

**Website:**
- quick add shows "പാൽക്കാരന് 500 കൊടുത്തു" (marked `lang="ml"`);
- the privacy policy and the Privacy page name Sarvam AI.

## Data and privacy

- **Nothing stored:** no audio, transcript or Sarvam request ID is stored. Logs hold no bodies,
  keys or provider errors.
- **Keys:** `SARVAM_API_KEY` is a backend-only secret.
- **Sarvam's defaults:** its privacy policy allows training on customer content unless the
  account opts out, and its retention docs keep workspace data until the owner sets a period.
- **Before release:** before any real household's audio reaches Sarvam, the human turns off
  training and sets Data retention → Model APIs → "No retention". FinBoy's privacy policy
  promises this.
- **Location:** Sarvam does not guarantee processing in India, and FinBoy makes no India-only
  claim.

## Settings (backend only)

| Setting | Value |
| --- | --- |
| `SPEECH_TRANSCRIBE_PROVIDER` | `openai` (default), `groq` or `sarvam` |
| `SARVAM_API_KEY` | secret |
| `SARVAM_STT_MODEL` | `saaras:v3`; anything else is `configuration_missing` |
| `MALAYALAM_TTS_PROVIDER` | `gemini` (default) or `sarvam` |
| `SARVAM_TTS_MODEL` | `bulbul:v3`; v4 Flash has no Malayalam |
| `SARVAM_TTS_SPEAKER_ML` | lowercase Bulbul voice name, chosen by listening |
| `SARVAM_BASE_URL` | default `https://api.sarvam.ai`; HTTPS, no credentials or query |

`/api/v1/readiness` reports transcription and Malayalam speech for whichever providers are
chosen.

## Human steps

1. **Sarvam dashboard:** turn off training on your content and set "No retention", before any
   real household's audio.
2. **Voice:** pick the Malayalam voice.
3. **Wording:** a native speaker reviews the Malayalam copy (`malayalam.py`, both consent cards).
4. **OpenAI key:** replace the invalidated OpenAI key in the private secrets file. If production
   uses the same key, its assistant, money reading and screenshot reading are failing too.
5. **Release:** with approval, follow the [release procedure](../production.md#sarvam-speech-release-procedure).

## Not in this round

- Malayalam amounts typed as words.
- Hindi and English voices moving to Sarvam.
- A Malayalam reminder template.
- Other Indian languages.
- Production deploy.

## Verification (28 October 2026)

**Automated checks:**

| Check | Outcome |
| --- | --- |
| `pnpm check` | Ruff, ESLint, strict types, 1,011 API unit tests and 46 web unit tests passed |
| `pnpm build` | Production Next.js build passed |
| `pnpm test:integration` (`finboy_signup`) | 74 passed |
| `pnpm db:check` | No new operations (no migration in this round) |
| Playwright `signup.spec.ts` and `session.spec.ts` | 45 passed at 1440, 390 and 320 px, including the Malayalam example |

**Live, with synthetic audio and Sarvam:**
- **Benchmark:** the results under "Live checks" above.
- **WhatsApp, through the signed-message path with a stand-in phone (nothing sent to Meta):**
  - "നമസ്കാരം" brought the Malayalam consent card, also spoken (Bulbul MP3);
  - ✅ സമ്മതം brought the Malayalam welcome;
  - a Bulbul-made voice note became the card "💸 ₹500 കൊടുത്തു";
  - ✅ ശരിയാണ് added it, with ↩️ തിരിച്ചെടുക്കുക offered;
  - "കണക്ക്" showed the week;
  - `en` and `ml` switched the language;
  - the synthetic household was removed afterwards.
- **App round trip:** Bulbul spoke "ഇന്നലെ പാൽക്കാരന് അഞ്ഞൂറ് രൂപ കൊടുത്തു." through
  `/assistant/speak`, and Saaras heard it as "ഇന്നലെ പാൽക്കാന് ₹500 കൊടുത്തു." (Malayalam, with
  and without a hint). `/entries/preview` read it as ₹500 money out, yesterday.
- **Browser (local web 3061 and API 8061):**
  - quick add's Malayalam example became a ₹500 money-out card, was saved, and was undone;
  - Ask in Malayalam answered in Malayalam, and **Listen** played Sarvam audio (`readyState`
    4, at 4.97 s of 16.44 s, no media error);
  - at 375 px the sheet does not overflow.

**Not verified:**
- real people's microphone or WhatsApp voice notes, and playback on a phone;
- a native speaker's review of the Malayalam copy;
- reading Malayalam with the OpenAI model, because the local key is invalidated. The rules
  reader was used, so payee names were not filled in.
