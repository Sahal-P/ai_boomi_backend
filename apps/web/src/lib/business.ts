/**
 * FinBoy's public business details, shown on the Contact, Terms, Privacy and Refund pages that
 * PayU checks before it activates payments. A detail stays null until the owner has a verified
 * value, and the pages leave out whatever is null rather than show a placeholder.
 * `docs/production.md` lists filling them in as a release step.
 */
export const BUSINESS: {
  name: string | null;
  address: string | null;
  phone: string | null;
  grievanceOfficer: string | null;
  email: string;
} = {
  name: null,
  address: null,
  phone: null,
  grievanceOfficer: null,
  email: "support@finboy.io",
};

/** The Premium price in rupees, for the public pages; the API's plan carries the charged amount. */
export const PREMIUM_PRICE = "₹299";
