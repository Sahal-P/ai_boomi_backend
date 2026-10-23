"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  deleteImportedData, disconnectConnection, getAuditEvents, getConnections, mailErrorMessage,
  setConnectionPaused, startDemo, syncConnection, uploadEml, type AuditEvent, type MailConnection,
} from "@/lib/api/mail";

export function useImportActions() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);
  async function start(files?: File[]) {
    if (inFlight.current) return;
    if (files && (!files.length || files.length > 50 || files.some((file) =>
      !file.name.toLowerCase().endsWith(".eml") || file.size > 2 * 1024 * 1024))) {
      setError("Choose 1–50 .eml files, up to 2 MB each.");
      return;
    }
    inFlight.current = true;
    setBusy(true);
    setError(null);
    try {
      const result = await (files ? uploadEml(files) : startDemo());
      router.push(`/import/${result.import_run_id}`);
    } catch (reason) { setError(mailErrorMessage(reason)); }
    finally { inFlight.current = false; setBusy(false); }
  }
  return { busy, error, start };
}

export function useConnections() {
  const router = useRouter();
  const [connections, setConnections] = useState<MailConnection[] | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const [version, setVersion] = useState(0);
  const refresh = useCallback(() => setVersion((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([getConnections(controller.signal), getAuditEvents(controller.signal)]).then(
      ([accounts, audit]) => {
        if (!controller.signal.aborted) {
          setConnections(accounts); setEvents(audit); setError(null);
        }
      },
      (reason: unknown) => { if (!controller.signal.aborted) setError(mailErrorMessage(reason)); },
    );
    return () => controller.abort();
  }, [version]);

  async function act(action: "pause" | "resume" | "sync" | "disconnect" | "delete",
    connection?: MailConnection, deleteData = false) {
    if (inFlight.current) return false;
    inFlight.current = true; setBusy(true); setError(null); setNotice(null);
    try {
      if (action === "delete") await deleteImportedData();
      else if (connection) {
        if (action === "sync") {
          const run = await syncConnection(connection.id);
          router.push(`/import/${run.import_run_id}`);
        } else if (action === "disconnect") await disconnectConnection(connection.id, deleteData);
        else await setConnectionPaused(connection.id, action === "pause");
      }
      setNotice(action === "delete" ? "Imported records were deleted. Audit history was kept."
        : action === "disconnect" ? "Gmail access was revoked."
        : action === "pause" ? "Email imports paused." : action === "resume" ? "Email imports resumed." : "Import started.");
      refresh();
      return true;
    } catch (reason) { setError(mailErrorMessage(reason)); return false; }
    finally { inFlight.current = false; setBusy(false); }
  }
  return { connections, events, error, notice, busy, refresh, act };
}
