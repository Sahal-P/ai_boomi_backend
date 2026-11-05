import type { HouseholdAction, HouseholdStatus, Kind, PaymentStatus, PlanState } from "@/lib/api/admin";

// Words for the admin panel's fixed codes (docs/admin-round/contract.md). Unknown codes fall back
// to a readable form of the code itself, so a new backend state never shows blank.

export const kindLabels: Record<Kind, string> = {
  owner: "Owner",
  pilot: "Village pilot",
  self_serve: "Self-serve",
  pending: "Pending sign-up",
  former_pilot: "Former pilot",
};

export const statusLabels: Record<HouseholdStatus, string> = {
  active: "Active",
  suspended: "Suspended",
  deleted: "Deleted",
};

export const planLabels: Record<PlanState, string> = {
  included: "Included",
  trial: "Trial",
  active: "Premium",
  grace: "Grace",
  free: "Free",
};

export const paymentStatusLabels: Record<PaymentStatus, string> = {
  started: "Started",
  scheduled: "Scheduled",
  pending: "Confirming",
  paid: "Paid",
  failed: "Failed",
  abandoned: "Abandoned",
};

export const actionLabels: Record<HouseholdAction, string> = {
  sign_out: "Sign out everywhere",
  suspend: "Suspend",
  restore: "Restore",
  erase: "Erase",
  premium: "Give Premium days",
  autopay_cancel: "Turn off AutoPay",
  pay_link: "Create pay link",
};

export const languageLabels: Record<string, string> = { en: "English", hi: "Hindi", ml: "Malayalam" };

export const auditLabels: Record<string, string> = {
  login: "Signed in",
  login_failed: "Sign-in failed",
  logout: "Signed out",
  password_changed: "Changed their password",
  sessions_revoked: "Signed out their other browsers",
  admin_created: "Added an admin",
  admin_disabled: "Disabled an admin",
  admin_password_reset: "Password reset on the server",
  admin_enabled: "Re-enabled an admin on the server",
  household_signed_out: "Signed a household out everywhere",
  household_suspended: "Suspended a household",
  household_restored: "Restored a household",
  household_erased: "Erased a household",
  premium_granted: "Gave Premium days",
  autopay_cancelled: "Turned off AutoPay",
  pay_link_created: "Created a pay link",
  payment_reconciled: "Re-checked a payment with PayU",
  signups_tidied: "Tidied sign-ups",
};

export const recordLabels: Record<string, string> = {
  confirmed: "Confirmed",
  needs_review: "To review",
  rejected: "Rejected",
  merged: "Merged",
  failed: "Failed payments",
};

export const dueLabels: Record<string, string> = { upcoming: "Upcoming", paid: "Paid", dismissed: "Dismissed" };

export const importModeLabels: Record<string, string> = {
  gmail: "Gmail",
  eml_upload: "Email upload",
  demo_mailbox: "Sample mailbox",
  gpay_statement: "Google Pay statement",
};

export const usageLabels: Record<string, string> = { ai: "AI answers", voice: "Voice notes" };

export const flagLabels: Record<string, string> = {
  signup_enabled: "Self-serve sign-up",
  whatsapp_enabled: "WhatsApp",
  billing_enabled: "Billing (Premium)",
  payu_autopay_enabled: "PayU AutoPay",
  billing_owner_included: "Owner always included",
  triage_enabled: "Fast decisions",
  statement_import_enabled: "Statement import",
  gmail_for_new_accounts: "Gmail for new accounts",
};

export const limitLabels: Record<string, { label: string; unit: string }> = {
  signup_limit: { label: "Sign-up limit", unit: "households" },
  session_days: { label: "Household session", unit: "days" },
  daily_ai_limit: { label: "Daily AI answers", unit: "per household" },
  daily_voice_limit: { label: "Daily voice notes", unit: "per household" },
  admin_session_hours: { label: "Admin session", unit: "hours" },
};

export const providerLabels: Record<string, string> = {
  assistant: "Assistant",
  transcription: "Speech to text",
  english_hindi_speech: "English and Hindi voice",
  malayalam_speech: "Malayalam voice",
  gmail: "Gmail",
  whatsapp: "WhatsApp",
  fast_decisions: "Fast decisions",
  payu: "PayU",
  email: "Email",
};

export const providerStateLabels: Record<string, string> = {
  configured: "Configured",
  missing: "Missing",
  disabled: "Off",
  off: "Off",
};

/** "needs_review" → "Needs review" for a code without its own label. */
export function readable(code: string): string {
  const text = code.replace(/[_.-]+/g, " ").trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "Unknown";
}

export function label(labels: Record<string, string>, code: string): string {
  return labels[code] ?? readable(code);
}

/** The setting's name in /etc/finboy/production.env. */
export function envName(key: string): string {
  return key.toUpperCase();
}
