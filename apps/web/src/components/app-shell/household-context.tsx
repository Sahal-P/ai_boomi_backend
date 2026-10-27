"use client";

import { createContext, useContext } from "react";
import type { Household, SessionView } from "@/lib/api/auth";

/**
 * `required` is true when the server enforces sign-in (production). `household` names how this
 * household signs in (masked); `signIn` is the server's public sign-in configuration.
 */
export const HouseholdContext = createContext<{
  required: boolean;
  household: Household | null;
  signIn: SessionView["sign_in"] | null;
}>({ required: false, household: null, signIn: null });

export function useHouseholdAccess() {
  return useContext(HouseholdContext);
}
