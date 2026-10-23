"use client";

import { useState } from "react";
import { PrivacyScreen } from "@/components/mail/privacy-screen";
import { useConnections } from "@/hooks/use-connections";
import type { MailConnection } from "@/lib/api/mail";

export default function PrivacyPage() {
  const { connections, events, error, notice, busy, refresh, act } = useConnections();
  const [dialog, setDialog] = useState<MailConnection | "delete" | null>(null);
  const [deleteWithDisconnect, setDeleteWithDisconnect] = useState(false);
  return <PrivacyScreen connections={connections} events={events} error={error} notice={notice} busy={busy}
    onRetry={refresh} onAction={act} dialog={dialog} onDialog={(value) => { setDeleteWithDisconnect(false); setDialog(value); }}
    deleteWithDisconnect={deleteWithDisconnect} onDeleteChoice={setDeleteWithDisconnect} />;
}
