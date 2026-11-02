/**
 * FinBoy's public business details, shown on the Contact, Terms, Privacy and Refund pages that
 * PayU checks before it activates payments. The bracketed values are the owner's to fill in
 * before billing opens; `docs/production.md` lists this as a release step.
 */
export const BUSINESS = {
  name: "[Legal business name]",
  address: "[Registered business address]",
  phone: "[Support phone number]",
  grievanceOfficer: "[Grievance officer's name]",
  email: "support@finboy.io",
} as const;

/** The Premium price in rupees, for the public pages; the API's plan carries the charged amount. */
export const PREMIUM_PRICE = "₹299";
