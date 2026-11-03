# SEO research and delivery

## Evidence and coverage

Source taxonomy: the owner's Gemini report at https://share.gemini.google/b989s0v8cMTF,
read 3 November 2026. All 300 distinct phrases are imported in `gemini-candidates.csv`.
They are candidate phrases, not proof of search demand. No volumes, CPC, traffic,
proprietary difficulty or authority metrics have been invented.

On 3 November, D1 Ultra classified the full set: 156 direct fits, 36 partial fits and
108 exclusions. 58 earlier results were reused from cache. The new classification run
reserved $0.188954 conservatively; a separate 20-topic evidence assessment reserved
$0.038083. These are client estimates, not actual billing. Billing remains unknown.
The default cap is $0.25 per CLI invocation, including retry reservations.

The operator collected 100 exact-query searches through Codex's web search tool and
retained the first ten returned URLs per query (1,000 sampled results). These are not
Google rank positions. The underlying search location/device is unknown; India was
requested as the business audience, not verified as the retrieval location.

One Google desktop snapshot was captured directly for `whatsapp expense tracker india`
at 2026-11-03T18:13:25.448Z, with gl=in, hl=en and pws=0. The nine observed organic results
placed SideNote, Expensebit and Spendzbot first, second and third in that snapshot.
Physical location was not verified. This does not establish persistent or India-wide ranks.

Twenty-one primary reference pages were requested; two were unavailable. A Google Help
fetch from the search tool returned a different Wallet article; direct HTTP inspection
of the requested Google Pay India article confirmed its statement instructions and
replaced that page capture. This discrepancy is not a website defect.

Twenty editorial topic briefs are supported by recorded search and reference-page
captures. D1's gap-label confidence was low (approximately 0.27–0.50), so all scores are
labelled draft heuristics requiring editorial review. A score of 92/100 is not a 92%
chance of ranking. Several topics map to the same page: consolidate them rather than
publishing overlapping pages. The first release remains four feature pages/four guides.

The report's root bot-blocking, absent SSR and unknown-pricing claims conflict with our
public HTTP/browser inspection. Do not change firewalls or authentication based on it.
The sample household stays noindex. PhonePe PDF import, linked partner accounts,
native mobile apps, offline/on-device AI, RSU automation and Splitwise migration remain
unsupported claims and have not been added to marketing pages.

## Operator commands

Run from the repository root:

```
pnpm seo -- discover --input docs/seo/gemini-candidates.csv
pnpm seo -- analyze --limit 300
pnpm seo -- import-serp --input /absolute/path/observations.jsonl
pnpm seo -- assess --input /absolute/path/editorial-reviews.json
pnpm seo -- report
```

Only public research text reaches Liquid. No application startup or database connection
is required. Credentials are read from the existing private operator store; they never
enter reports, browser code, committed files or logs. Four requests may run concurrently.
Responses have size/time limits; transient HTTP failures get at most two retries, each
reserved under the same run ceiling before it starts. If the initial reservation is over
the cap, the invocation stops before credentials are loaded or requests are sent.
The cost estimate uses $0.042 per million input tokens, UTF-8 bytes as a text-token upper
estimate, repeated context for every question and conservative provider framing. Recheck
Liquid's documented pricing before future use. This is not provider-enforced billing.

Private files live under gitignored `output/seo/`: classification/cache JSON, raw search
and page evidence, observation JSONL, Google snapshot, reviewed editorial inputs,
opportunities CSV/JSON, content briefs, competitor observations, a searchable/sortable
HTML report and a Markdown summary. The research outputs are operator artifacts, not
household product data. Export and archive them explicitly before removing the worktree.

SERP JSONL requires query, engine (google/bing/search_tool), country, language, device,
observed_at (timezone-qualified), results (position or null, url, title), plus an HTTPS
evidence URL or an existing relative `search-evidence/*.txt` file. Optional fields record
requested_country and location_verified. Search-tool positions are always null. Import
validates structure and evidence-file presence; the operator must verify source truth.

`assess` accepts a JSON array of reviews with query, target_url, title, angle, outline,
references and ease (0–5). A query must exist in classification and search observations;
reference URLs must resolve to available captured page evidence. D1 assesses a sampled
editorial gap and action intent. Weighted score: 40% fit, 30% gap, 20% action, 10% ease.
No inference of demand, full-page absence or Google difficulty is made.

`pnpm lint:seo` and `pnpm test:seo` are included in `pnpm check`. Tests cover source
normalization, ranking provenance, missing evidence, budget rejection before credential
loading, retry caps, malformed provider responses, score boundaries and CSV injection.

## Website and release

The shared content registry defines the four feature pages/four guides and related links.
Static generation, canonical metadata, branded social imagery, Article/BreadcrumbList
markup, a public-only sitemap, and default noindex outside explicitly public pages keep
product data out of discovery. Public guides have visible authorship/review dates and
synthetic examples. Unknown slugs, including inherited object-property names, return 404.

Search Console URL-prefix verification uses the public HTML tag injected by the optional
`GOOGLE_SITE_VERIFICATION` build variable. Its value is stored as a frontend repository
variable; the production CI build reads it. It is not an AI/provider credential. Keep
actual provider keys, sessions, OAuth settings and finance-route authentication unchanged.
Release follows `docs/voxpay-hosting.md`; no migrations or service additions are needed.
Ownership verification, sitemap acceptance and actual indexing are separate outcomes.
