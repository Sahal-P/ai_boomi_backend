# WhatsApp number activation — 28 October 2026

The human authorized one GrizzlySMS WhatsApp activation costing at most USD 1.85,
and requested a real Cloud API number for the existing FinBoy Meta app. The earlier
phone-app number was left untouched after Meta reported that it was already in use.

## Completed and verified

- Purchased one Czech WhatsApp activation for USD 1.85: public business number
  `+420 730451648`. No second activation or balance top-up was purchased.
- Added it as `FinBoy` to the existing Antlegs WABA `256767114194964` and completed
  Meta SMS verification during the activation window.
- Registered phone ID `1376166788915718` with Cloud API. The registration POST
  returned HTTP 200 and `success=true`. A fresh Graph v26.0 read returned
  `code_verification_status=VERIFIED`, `status=CONNECTED`,
  `platform_type=CLOUD_API`, and `name_status=AVAILABLE_WITHOUT_REVIEW`.
- Created a random registration PIN in a mode-600 operator file under
  `~/.config/finboy/`. The PIN, verification SMS and tokens are not recorded here.
- Subscribed the new WABA to existing app `953180210789448`; POST succeeded and a
  fresh read confirmed the subscription. The app's existing exact production
  webhook callback and active `messages` field were independently confirmed.
- The existing production access token can read the new phone. No token, app
  secret, session key, encryption key or Gmail grant was changed.
- Backed up `/etc/finboy/production.env` privately before changing only
  `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_BUSINESS_ACCOUNT_ID` and
  `WHATSAPP_PUBLIC_NUMBER` to the new phone/WABA context. Restarted only
  `finboy.service`. FinBoy, nginx and PostgreSQL report active.
- Production already had `SIGNUP_ENABLED=true` and `WHATSAPP_ENABLED=true` at
  preflight; these settings were preserved. No household data, allowlist or schema
  was changed.
- Public proxied health returned 200, unauthenticated money summary returned 401,
  and public session configuration returned 200 with the new WhatsApp number.
- Saved the existing hosted privacy, terms and deletion-instructions URLs in Meta
  app settings. Meta's Publish page now reports all required app settings complete.

## Remaining acceptance and limitations

- The human explicitly confirmed publishing the Meta app. The Publish action
  completed and Meta displayed `Published`, an `Unpublish` action, and the
  confirmation "Your app was successfully published" / "Your app is now available
  for the public to use." A browser screenshot records this result.
- The human sent a fresh inbound message to the new number and confirmed receiving
  FinBoy's response. This establishes human-confirmed text messaging on the new
  number. No independent Meta delivery/read status, voice playback, screenshot
  acceptance or second-person sign-up is claimed by this check.
- No blue badge was requested; the human explicitly dropped that requirement.
- Grizzly's FAQ states these are single-use activation numbers, available for
  about 20 minutes, usually one SMS, and cannot be reissued. The human was informed
  before approving the purchase. Successful registration does not establish
  durable number ownership, future SMS recovery, or production suitability.
- The existing user access token was retained; this round did not establish a
  permanent System User credential or new billing setup.
- Hosted privacy/terms pages still contain draft/contact placeholders. A public
  support contact was requested but has not been supplied in this chat.
- Validation was limited to provider registration/subscription reads, operational
  service state and read-only HTTP access checks. No production tests or fixtures
  were run. No application code, schema or dependency changed.

Reference: [GrizzlySMS FAQ](https://grizzlysms.com/faq),
[Meta registration API](https://developers.facebook.com/documentation/business-messaging/whatsapp/reference/whatsapp-business-phone-number/phone-number-registration).

## WhatsApp profile branding

At the human's request, rendered the existing `apps/web/src/app/icon.svg` brand
mark as a 1024-pixel PNG and uploaded/saved it through WhatsApp Manager. The saved
profile preview shows the logo and `FinBoy`. A fresh Graph read confirms a profile
picture is present, `verified_name=FinBoy`, `name_status=AVAILABLE_WITHOUT_REVIEW`,
and `status=CONNECTED`. No display-name change was submitted because the desired
name was already configured. This does not prove the chat header replaces the
number for unsaved contacts: Meta's display-name review/visibility rules still
apply. No username or badge was created, and no app code or dependency changed.
