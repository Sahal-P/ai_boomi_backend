"use client";

import { useCallback, useRef, useState } from "react";
import { useResource } from "@/hooks/use-resource";
import { isAbort } from "@/lib/api/http";
import {
  decide,
  getTransaction,
  undoDecision,
  type DecisionRequest,
  type DecisionResult,
} from "@/lib/api/transactions";
import { describeProblem, type Problem } from "@/lib/messages";

export type DecisionOutcome = {
  result: DecisionResult;
  action: DecisionRequest["action"];
  merchant: string;
};

/** One record's evidence plus version-checked decisions and undo. */
export function useRecord(id: string | null) {
  const detail = useResource(id ? `record:${id}` : null, (signal) => getTransaction(id ?? "", signal));
  const replace = detail.replace;
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [failure, setFailure] = useState<unknown>(null);
  const flight = useRef(false);

  const submit = useCallback(
    async (request: DecisionRequest, failureTitle: string): Promise<DecisionOutcome | null> => {
      if (!id || flight.current) return null;
      flight.current = true;
      setBusy(request.action);
      setProblem(null);
      setFailure(null);
      try {
        const result = await decide(id, request);
        replace(result.detail);
        return { result, action: request.action, merchant: result.detail.transaction.merchant };
      } catch (error) {
        if (!isAbort(error)) {
          setProblem(describeProblem(error, failureTitle));
          setFailure(error);
        }
        return null;
      } finally {
        flight.current = false;
        setBusy(null);
      }
    },
    [id, replace],
  );

  const undo = useCallback(
    async (decisionId: string, expectedVersion: string): Promise<DecisionResult | null> => {
      if (!id || flight.current) return null;
      flight.current = true;
      setBusy("undo");
      setProblem(null);
      setFailure(null);
      try {
        const result = await undoDecision(id, decisionId, expectedVersion);
        replace(result.detail);
        return result;
      } catch (error) {
        if (!isAbort(error)) {
          setProblem(describeProblem(error, "That decision wasn't undone"));
          setFailure(error);
        }
        return null;
      } finally {
        flight.current = false;
        setBusy(null);
      }
    },
    [id, replace],
  );

  return {
    detail,
    busy,
    problem,
    failure,
    submit,
    undo,
    clearProblem: () => {
      setProblem(null);
      setFailure(null);
    },
  };
}
