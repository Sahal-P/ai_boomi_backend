"use client";

import { ConnectScreen } from "@/components/mail/connect-screen";
import { useImportActions } from "@/hooks/use-connections";
import { authorizeUrl, oauthErrorMessage } from "@/lib/api/mail";

export function ConnectClient({ errorCode }: { errorCode?: string }) {
  const { busy, error, start } = useImportActions();
  return <ConnectScreen gmailUrl={authorizeUrl()} error={error ?? oauthErrorMessage(errorCode)} busy={busy}
    onDemo={() => void start()} onUpload={(files) => void start(files)} />;
}
