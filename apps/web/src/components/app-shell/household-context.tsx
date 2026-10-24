"use client";

import { createContext, useContext } from "react";

/** `required` is true when the server enforces household sign-in (production). */
export const HouseholdContext = createContext<{ required: boolean }>({ required: false });

export function useHouseholdAccess() {
  return useContext(HouseholdContext);
}
