"use client";

import { createContext, useContext } from "react";
import type { Household, SessionView } from "@/lib/api/auth";
import type { Plan } from "@/lib/api/billing";

/**
 * `required` is true when the server enforces sign-in (production). `household` names how this
 * household signs in (masked); `signIn` is the server's public sign-in configuration;
 * `statementImport` says whether Google Pay statements can be imported. `plan` is FinBoy Premium
 * (null while billing is off, when every household has everything); `refresh` re-reads the session
 * after a payment and `updatePlan` applies a plan the API just returned.
 */
export const HouseholdContext = createContext<{
  required: boolean;
  household: Household | null;
  signIn: SessionView["sign_in"] | null;
  statementImport: boolean;
  plan: Plan | null;
  refresh: () => Promise<void>;
  updatePlan: (plan: Plan) => void;
}>({
  required: false,
  household: null,
  signIn: null,
  statementImport: false,
  plan: null,
  refresh: async () => {},
  updatePlan: () => {},
});

export function useHouseholdAccess() {
  return useContext(HouseholdContext);
}
