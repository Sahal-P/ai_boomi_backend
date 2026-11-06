"use client";

import { Brain, Check, MessageCircle, Pencil, Trash2, X } from "lucide-react";
import { useId, useState } from "react";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel } from "@/components/feedback/states";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useResource } from "@/hooks/use-resource";
import { deleteThreads } from "@/lib/api/assistant";
import {
  deleteMemories,
  deleteMemory,
  editMemory,
  listMemories,
  MEMORY_TEXT_LIMIT,
  memoryKinds,
  setMemoryEnabled,
  type Memory,
  type MemoryKind,
} from "@/lib/api/memory";
import { formatDayTime } from "@/lib/dates";
import { describeProblem, type Problem } from "@/lib/messages";

const kindLabels: Record<MemoryKind, string> = {
  about: "About you",
  goal: "Goals",
  plan: "Plans and events",
  preference: "How you like replies",
  person: "People",
  note: "Notes",
};

type Confirm = "memories" | "chats" | null;

/** One memory, with edit and delete in place. */
function MemoryRow({
  memory,
  onSaved,
  onDeleted,
  onProblem,
}: {
  memory: Memory;
  onSaved: (memory: Memory) => void;
  onDeleted: (id: string) => void;
  onProblem: (problem: Problem) => void;
}) {
  const id = useId();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(memory.text);
  const [busy, setBusy] = useState(false);
  const text = draft.trim();

  async function save() {
    if (!text || text === memory.text) {
      setEditing(false);
      return;
    }
    setBusy(true);
    try {
      onSaved(await editMemory(memory.id, text));
      setEditing(false);
    } catch (error) {
      onProblem(describeProblem(error, "That memory couldn't be changed"));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await deleteMemory(memory.id);
      onDeleted(memory.id);
    } catch (error) {
      onProblem(describeProblem(error, "That memory couldn't be deleted"));
      setBusy(false);
    }
  }

  if (editing) {
    return (
      <li className="space-y-2 py-3">
        <label htmlFor={`${id}-text`} className="sr-only">
          Memory
        </label>
        <Textarea
          id={`${id}-text`}
          value={draft}
          maxLength={MEMORY_TEXT_LIMIT}
          onChange={(event) => setDraft(event.target.value)}
          className="min-h-20"
        />
        <div className="flex flex-wrap gap-2">
          <Button size="sm" disabled={busy || !text} onClick={() => void save()}>
            <Check aria-hidden="true" /> Save
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() => {
              setDraft(memory.text);
              setEditing(false);
            }}
          >
            <X aria-hidden="true" /> Cancel
          </Button>
        </div>
      </li>
    );
  }
  return (
    <li className="flex items-start gap-3 py-3">
      <div className="min-w-0 flex-1">
        <p className="break-words text-[15px] text-ink">{memory.text}</p>
        <p className="mt-0.5 text-xs text-ink-soft">
          {memory.source === "whatsapp" ? "From WhatsApp" : memory.source === "user" ? "You added it" : "From Ask"} ·{" "}
          {formatDayTime(memory.updated_at)}
        </p>
      </div>
      <Button variant="ghost" size="icon" className="size-11 shrink-0" aria-label={`Edit: ${memory.text}`} disabled={busy} onClick={() => setEditing(true)}>
        <Pencil aria-hidden="true" />
      </Button>
      <Button variant="ghost" size="icon" className="size-11 shrink-0" aria-label={`Delete: ${memory.text}`} disabled={busy} onClick={() => void remove()}>
        <Trash2 aria-hidden="true" />
      </Button>
    </li>
  );
}

/**
 * What FinBoy remembers, like ChatGPT's memory: saved while you ask, used in every answer on the
 * web and WhatsApp, and yours to edit, delete or switch off (docs/advisor-round/contract.md).
 */
export function MemoryScreen() {
  const ids = useId();
  const memories = useResource("memory", (signal) => listMemories(signal));
  const [problem, setProblem] = useState<Problem | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<Confirm>(null);
  const [switching, setSwitching] = useState(false);
  const data = memories.data;

  function update(change: (current: NonNullable<typeof data>) => NonNullable<typeof data>) {
    if (data) memories.replace(change(data));
  }

  async function toggle(enabled: boolean) {
    setSwitching(true);
    setProblem(null);
    try {
      await setMemoryEnabled(enabled);
      update((current) => ({ ...current, enabled }));
      setNotice(enabled ? "Memory is on." : "Memory is off. FinBoy won't use or save memories.");
    } catch (error) {
      setProblem(describeProblem(error, "Memory couldn't be switched"));
    } finally {
      setSwitching(false);
    }
  }

  async function clear(what: Exclude<Confirm, null>) {
    setProblem(null);
    try {
      if (what === "memories") {
        await deleteMemories();
        update((current) => ({ ...current, memories: [] }));
        setNotice("FinBoy has forgotten everything it remembered.");
      } else {
        await deleteThreads();
        update((current) => ({ ...current, chats: 0 }));
        setNotice("Your chat history is cleared.");
      }
    } catch (error) {
      setProblem(describeProblem(error, what === "memories" ? "Memories couldn't be deleted" : "Chats couldn't be deleted"));
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Memory"
        description="What FinBoy remembers about you to give better, more personal answers on the web and WhatsApp."
      />
      <div role="status" aria-live="polite">
        {notice && <p className="rounded-2xl bg-white/60 p-4 text-sm font-medium">{notice}</p>}
      </div>
      {problem && <ProblemNotice problem={problem} />}
      {memories.status === "loading" && <LoadingPanel label="Loading what FinBoy remembers…" />}
      {memories.error !== null && (
        <ProblemNotice problem={describeProblem(memories.error, "Memory couldn't be loaded")} onRetry={memories.reload} />
      )}

      {data && (
        <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[1.4fr_1fr]">
          <section aria-labelledby={`${ids}-saved`} className="surface rounded-3xl p-5 sm:p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 id={`${ids}-saved`} className="text-lg font-semibold">
                  Saved memories
                </h2>
                <p className="mt-1 text-sm text-ink-soft">
                  {data.memories.length} of {data.limit}. Tell FinBoy &ldquo;remember…&rdquo; or &ldquo;forget…&rdquo; any time.
                </p>
              </div>
              <Brain className="mt-1 size-5 shrink-0 text-ink-soft" aria-hidden="true" />
            </div>
            {data.memories.length === 0 ? (
              <p className="mt-4 text-sm text-ink-soft">
                Nothing saved yet. Share your goals, your family or how your income comes, and FinBoy will remember what helps.
              </p>
            ) : (
              memoryKinds
                .filter((kind) => data.memories.some((item) => item.kind === kind))
                .map((kind) => (
                  <div key={kind} className="mt-5">
                    <h3 className="text-sm font-semibold text-ink-soft">{kindLabels[kind]}</h3>
                    <ul className="divide-y">
                      {data.memories
                        .filter((item) => item.kind === kind)
                        .map((item) => (
                          <MemoryRow
                            key={item.id}
                            memory={item}
                            onProblem={setProblem}
                            onSaved={(saved) =>
                              update((current) => ({
                                ...current,
                                memories: current.memories.map((row) => (row.id === saved.id ? saved : row)),
                              }))
                            }
                            onDeleted={(id) =>
                              update((current) => ({ ...current, memories: current.memories.filter((row) => row.id !== id) }))
                            }
                          />
                        ))}
                    </ul>
                  </div>
                ))
            )}
          </section>

          <div className="space-y-5">
            <section aria-labelledby={`${ids}-switch`} className="surface rounded-3xl p-5 sm:p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 id={`${ids}-switch`} className="text-lg font-semibold">
                    Let FinBoy remember
                  </h2>
                  <p className="mt-1 text-sm text-ink-soft">
                    When it&apos;s off, FinBoy neither uses nor saves memories. Saved ones stay until you delete them.
                  </p>
                </div>
                <Switch
                  aria-labelledby={`${ids}-switch`}
                  checked={data.enabled}
                  disabled={switching}
                  onCheckedChange={(value) => void toggle(value)}
                />
              </div>
            </section>
            <section aria-labelledby={`${ids}-delete`} className="surface rounded-3xl p-5 sm:p-6">
              <h2 id={`${ids}-delete`} className="text-lg font-semibold">
                Delete
              </h2>
              <p className="mt-1 flex items-center gap-2 text-sm text-ink-soft">
                <MessageCircle className="size-4" aria-hidden="true" /> {data.chats} {data.chats === 1 ? "chat" : "chats"} with FinBoy kept
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button variant="outline" disabled={!data.memories.length} onClick={() => setConfirm("memories")}>
                  Forget everything
                </Button>
                <Button variant="outline" disabled={!data.chats} onClick={() => setConfirm("chats")}>
                  Clear chat history
                </Button>
              </div>
            </section>
          </div>
        </div>
      )}

      <AlertDialog open={confirm !== null} onOpenChange={(open) => !open && setConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{confirm === "chats" ? "Clear your chat history?" : "Forget everything?"}</AlertDialogTitle>
            <AlertDialogDescription>
              {confirm === "chats"
                ? "Every chat with FinBoy on the web and WhatsApp is deleted. Your records and memories stay."
                : "Every saved memory is deleted. Your records and chats stay. This can't be undone."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                const what = confirm;
                setConfirm(null);
                if (what) void clear(what);
              }}
            >
              {confirm === "chats" ? "Clear chats" : "Forget everything"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
