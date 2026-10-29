# FinBoy email setup

Status: Zoho domain ownership, MX, SPF and DKIM are verified; support is the active mailbox and
admin its alias. Resend reports the sending domain verified. A Resend test reached Gmail
with SPF, DKIM and DMARC passing, and its reply reached the support inbox. A separate
admin alias test also arrived in that inbox. After DKIM activation, a Zoho test to Gmail
passed SPF, DKIM and DMARC. No existing product flow calls the outbound
service. The owner deferred notification logic: FinBoy's sign-in stays with WhatsApp and
Google, and no welcome, OTP, password reset or notification flow is enabled. Future
notification features must obtain a verified destination and consent before scheduling
delivery.

## Domain setup

- Zoho Mail's free plan supports one custom domain and up to five users in supported
  regions; its free plan does not include IMAP, POP or ActiveSync. Create the account in
  the intended data center and choose the free plan explicitly. One `support@finboy.io`
  mailbox with `admin@finboy.io` as an alias shares one inbox; if separate access is
  needed create a separate user instead. The sender `noreply@finboy.io` need not be a
  mailbox for Resend. Apply account protection and recovery to the owner account.
- In Zoho Admin Console add `finboy.io` and publish the exact account-specific domain
  ownership TXT record at Hostinger. Verify before changing MX. Create mailbox and alias
  before publishing Zoho's region-specific MX records. Check the provider's displayed
  values and priorities: do not guess data-center-specific records or delete unrelated
  DNS. No existing apex MX/SPF or DMARC records were observed before setup.
- Publish Zoho's SPF and generated DKIM selector as displayed. Never publish multiple
  SPF TXT records on the same hostname. Hostinger currently has `_dmarc.finboy.io` TXT
  `v=DMARC1; p=none` with TTL 3600; this monitoring policy does not request aggregate
  reports until a working report inbox is configured. Review actual authentication before moving toward quarantine or reject.
- In Resend `finboy.io` is configured for **sending**, without domain-wide receiving.
  Resend uses CNAMEs at `send` and `rsend` and a DKIM TXT selector; its return-path
  configuration is distinct from apex Zoho MX.
  Do not replace Zoho's inbound apex MX or create a second SPF policy at the same name.
  Keep tracking disabled for login or security links. Verify sending in Resend.

DNS recorded on 29 October 2026 (all TTL 3600):

| Host | Type | Value |
| --- | --- | --- |
| `@` | MX | `10 mx.zoho.in`, `20 mx2.zoho.in`, `50 mx3.zoho.in` |
| `@` | TXT | `v=spf1 include:zoho.in ~all` |
| `@` | TXT | `zoho-verification=zb09528201.zmverify.zoho.in` |
| `_dmarc` | TXT | `v=DMARC1; p=none` |
| `zoho._domainkey` | TXT | Zoho-generated 2048-bit public key; see Zoho console |
| `resend._domainkey` | TXT | Resend-generated public key; see Resend console |
| `rsend` | CNAME | `rsend-apne1.forge.rmta.net` |
| `send` | CNAME | `send.forge.rmta.net` |

Zoho has verified MX, SPF and DKIM. Resend reports verified, with enforced TLS;
mail to servers without TLS will fail rather than be delivered without encryption.

See [Zoho email delivery](https://www.zoho.com/mail/help/adminconsole/configure-email-delivery.html),
[Zoho pricing](https://www.zoho.com/mail/zohomail-pricing.html), and
[Resend domain verification](https://resend.com/docs/dashboard/domains/introduction).

## Server configuration and operation

`RESEND_API_KEY` belongs only in the private server-side environment, never source control,
frontend variables, browser code, or CI. Obtain a restricted sending key for the verified
FinBoy domain. The transport uses `FinBoy <noreply@finboy.io>` with reply-to
`support@finboy.io`, fixed provider URL, bounded timeouts and retries, and a caller-supplied
UUID idempotency key. Resend deduplicates repeated keys for 24 hours. Provider responses,
recipient addresses, codes, URLs and credentials must not enter operational logs.

The optional `enqueue` helper uses FastAPI in-process background tasks. **It is not a durable
queue**: process termination can discard queued messages. Callers requiring reliable
transactional delivery must implement a durable, privacy-reviewed job design or provide a
retryable user action; do not use this helper as a guarantee. In particular the project
forbids storing login codes, so do not add a plaintext code queue. Delivery acceptance is not
proof of inbox delivery. Do not send real user email until the provider, domain, flow and
receipt have been verified. A domain-restricted sending key is in the private server
environment, but the production API has not been restarted and the code is not deployed.

## Verification

After setup, inspect the authoritative records and both dashboards. Send a synthetic message
from Zoho to an external account and reply to it; send a synthetic Resend message to an
owner-controlled external account and reply to confirm support receives it. Inspect received
message authentication results for SPF, DKIM and DMARC and confirm sender alignment. Avoid
recording email bodies, authentication links or codes. Check both apex MX and the separate
Resend return-path MX. In the event of a provider or DNS failure, preserve existing records
and stop; do not make speculative replacements.
