"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ContactInput, Plan } from "@/lib/api/billing";

/** Only what PayU still needs: the receipt email, and a phone when no WhatsApp number is linked. */
export function needsContact(contact: Plan["contact"]) {
  return { email: contact.email === null, phone: contact.phone === null };
}

export function ContactFields({
  id,
  contact,
  value,
  onChange,
  labels = { email: "Email for receipts", phone: "Mobile number" },
  disabled = false,
}: {
  id: string;
  contact: Plan["contact"];
  value: ContactInput;
  onChange: (value: ContactInput) => void;
  labels?: { email: string; phone: string };
  disabled?: boolean;
}) {
  const missing = needsContact(contact);
  if (!missing.email && !missing.phone) return null;
  return (
    <div className="space-y-3">
      {missing.email && (
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-email`}>{labels.email}</Label>
          <Input
            id={`${id}-email`}
            type="email"
            inputMode="email"
            autoComplete="email"
            autoCapitalize="none"
            spellCheck={false}
            maxLength={50}
            required
            disabled={disabled}
            value={value.email ?? ""}
            onChange={(event) => onChange({ ...value, email: event.target.value })}
          />
        </div>
      )}
      {missing.phone && (
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-phone`}>{labels.phone}</Label>
          <Input
            id={`${id}-phone`}
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            maxLength={16}
            required
            disabled={disabled}
            value={value.phone ?? ""}
            onChange={(event) => onChange({ ...value, phone: event.target.value })}
          />
        </div>
      )}
    </div>
  );
}
