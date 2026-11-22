"use client";

import { ImageIcon, LoaderCircle, X } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { count, Facts, moment, Pager, Panel, RefreshButton } from "@/components/admin/admin-bits";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel, RefreshingLabel } from "@/components/feedback/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAction } from "@/hooks/use-action";
import { useQueryUpdate } from "@/hooks/use-query-update";
import { useResource } from "@/hooks/use-resource";
import { feedbackKindLabels, feedbackStatusLabels, label } from "@/lib/admin-labels";
import {
  FEEDBACK_STATUSES,
  getAdminFeedback,
  getFeedbackScreenshot,
  listAdminFeedback,
  setFeedbackStatus,
  type FeedbackDetail,
  type FeedbackRow,
  type FeedbackStatus,
} from "@/lib/api/admin";
import { describeProblem } from "@/lib/messages";
import { cn } from "@/lib/utils";

const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function StatusBadge({ status }: { status: FeedbackStatus }) {
  const variant = status === "done" ? "positive" : status === "planned" ? "warning" : "default";
  return <Badge variant={variant}>{feedbackStatusLabels[status]}</Badge>;
}

const who = (row: FeedbackRow) => row.household_name ?? row.short_id;

/** Loads a report's screenshot only when asked; each open is recorded in the audit log. */
function ScreenshotView({ feedbackId }: { feedbackId: string }) {
  const [state, setState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const current = useRef<string | null>(null);
  useEffect(
    () => () => {
      if (current.current) URL.revokeObjectURL(current.current);
    },
    [],
  );
  async function load() {
    setState("loading");
    try {
      const next = URL.createObjectURL(await getFeedbackScreenshot(feedbackId));
      current.current = next;
      setUrl(next);
      setState("ready");
    } catch (reason) {
      setError(reason);
      setState("error");
    }
  }
  if (state === "ready" && url) {
    // A private blob URL: shown as fetched at its own shape, never sent to an image optimiser.
    return (
      <Image
        src={url}
        alt="The screenshot the household attached"
        width={480}
        height={480}
        unoptimized
        className="h-auto max-h-[32rem] w-auto max-w-full rounded-md border border-ink/10"
      />
    );
  }
  return (
    <div className="space-y-1">
      <Button type="button" variant="outline" size="sm" onClick={() => void load()} disabled={state === "loading"}>
        {state === "loading" ? (
          <LoaderCircle aria-hidden="true" className="motion-safe:animate-spin" />
        ) : (
          <ImageIcon aria-hidden="true" />
        )}
        Show screenshot
      </Button>
      {state === "error" && (
        <p role="alert" className="text-xs text-destructive">
          {describeProblem(error, "Couldn't open the screenshot").detail}
        </p>
      )}
    </div>
  );
}

/** One report's words, screen and screenshot, with its status. Opening it is audited. */
function Detail({
  feedbackId,
  onChanged,
  onClose,
}: {
  feedbackId: string;
  onChanged: (detail: FeedbackDetail) => void;
  onClose: () => void;
}) {
  const ids = useId();
  const detail = useResource(`admin-feedback:${feedbackId}`, (signal) => getAdminFeedback(feedbackId, signal));
  const change = useAction();
  const data = detail.data;

  async function choose(status: FeedbackStatus) {
    const result = await change.run("status", "The status wasn't changed", () => setFeedbackStatus(feedbackId, status));
    if (!result) return;
    detail.replace(result);
    onChanged(result);
  }

  return (
    <Panel
      title={data ? `${label(feedbackKindLabels, data.kind)} from ${who(data)}` : "Feedback"}
      description="Opening a report is recorded in the audit log."
      actions={
        <Button variant="ghost" size="icon" aria-label="Close this report" onClick={onClose}>
          <X aria-hidden="true" />
        </Button>
      }
      className="lg:sticky lg:top-6 max-lg:order-first"
    >
      {detail.status === "loading" && <LoadingPanel label="Opening the report…" className="p-4" />}
      {detail.error !== null && (
        <ProblemNotice problem={describeProblem(detail.error, "The report couldn't be opened")} onRetry={detail.reload} />
      )}
      {data && (
        <div className="space-y-4">
          <p className="rounded-2xl bg-white/60 p-4 text-[15px] leading-relaxed break-words whitespace-pre-wrap">
            {data.message}
          </p>
          <Facts
            items={[
              [
                "Household",
                <Link
                  key="household"
                  href={`/admin/households?selected=${data.household_id}`}
                  className={cn("underline underline-offset-4", !data.household_name && "font-mono")}
                >
                  {who(data)}
                </Link>,
              ],
              ["Screen", data.page || "—"],
              ["Sent", moment(data.created_at)],
              ["Status changed", moment(data.status_changed_at)],
            ]}
          />
          {data.has_screenshot && <ScreenshotView feedbackId={data.id} />}
          <div className="max-w-xs">
            <label htmlFor={`${ids}-status`} className="text-xs font-semibold">
              Status the household sees
            </label>
            <select
              id={`${ids}-status`}
              className="field field-select mt-1.5 block h-11 w-full rounded-lg pl-3 text-sm"
              value={data.status}
              disabled={change.busy !== null}
              onChange={(event) => {
                const next = FEEDBACK_STATUSES.find((value) => value === event.target.value);
                if (next && next !== data.status) void choose(next);
              }}
            >
              {FEEDBACK_STATUSES.map((value) => (
                <option key={value} value={value}>
                  {feedbackStatusLabels[value]}
                </option>
              ))}
            </select>
          </div>
          {change.problem && <ProblemNotice problem={change.problem} />}
        </div>
      )}
    </Panel>
  );
}

/** What households report from the web app: the list carries no words; a report opens with them. */
export function FeedbackScreen() {
  const params = useSearchParams();
  const update = useQueryUpdate();
  const ids = useId();
  const status = FEEDBACK_STATUSES.find((value) => value === params.get("status")) ?? null;
  const offsetParam = Number(params.get("offset") ?? 0);
  const offset = Number.isInteger(offsetParam) && offsetParam > 0 ? offsetParam : 0;
  const openParam = params.get("open");
  const open = openParam && GUID.test(openParam) ? openParam.toLowerCase() : null;
  const list = useResource(`admin-feedback:${status ?? "all"}:${offset}`, (signal) =>
    listAdminFeedback(status, offset, signal),
  );
  const [announcement, setAnnouncement] = useState("");
  const page = list.stale ? null : list.data;

  function changed(detail: FeedbackDetail) {
    setAnnouncement(`Marked ${feedbackStatusLabels[detail.status].toLowerCase()}. The household sees it on its feedback page.`);
    if (!page) return;
    const before = page.items.find((item) => item.id === detail.id);
    const movedOutOfNew = before?.status === "new" && detail.status !== "new";
    const movedIntoNew = before && before.status !== "new" && detail.status === "new";
    list.replace({
      ...page,
      new: Math.max(0, page.new + (movedIntoNew ? 1 : 0) - (movedOutOfNew ? 1 : 0)),
      items: page.items.map((item) => (item.id === detail.id ? { ...item, status: detail.status } : item)),
    });
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Feedback"
        description="Problems and ideas households send from the web app. The list shows no words; opening a report shows them and is recorded in the audit log."
        actions={<RefreshButton resource={list} />}
      />
      <div className="max-w-xs">
        <label htmlFor={`${ids}-status`} className="text-xs font-semibold">
          Status
        </label>
        <select
          id={`${ids}-status`}
          className="field field-select mt-1.5 block h-11 w-full rounded-lg pl-3 text-sm"
          value={status ?? ""}
          onChange={(event) => update({ status: event.target.value || null, offset: null })}
        >
          <option value="">All feedback</option>
          {FEEDBACK_STATUSES.map((value) => (
            <option key={value} value={value}>
              {feedbackStatusLabels[value]}
            </option>
          ))}
        </select>
      </div>
      <div role="status" aria-live="polite" className="text-sm font-medium">
        {announcement}
      </div>
      <RefreshingLabel active={list.status === "refreshing"}>Updating feedback…</RefreshingLabel>
      {list.status === "loading" && <LoadingPanel label="Loading feedback…" />}
      {list.error !== null && (
        <ProblemNotice
          problem={describeProblem(list.error, list.data ? "Couldn't refresh — showing the last loaded feedback" : "Feedback couldn't be loaded")}
          onRetry={list.reload}
        />
      )}
      <div className={cn("grid items-start gap-5", open && "lg:grid-cols-2")}>
        {page && (
          <section aria-labelledby={`${ids}-title`} className="min-w-0">
            <h2 id={`${ids}-title`} className="text-base font-semibold">
              {count(page.total)} {page.total === 1 ? "report" : "reports"} · {count(page.new)} new
            </h2>
            {page.items.length === 0 ? (
              <p className="mt-2 text-sm text-ink-soft">{status ? "No feedback in this state." : "No feedback yet."}</p>
            ) : (
              <ul aria-label="Feedback" className="mt-3 space-y-2">
                {page.items.map((row) => (
                  <li key={row.id} className={cn("surface rounded-lg px-4 py-3", row.id === open && "ring-2 ring-ink")}>
                    <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
                      <p className="text-sm">
                        <strong>{label(feedbackKindLabels, row.kind)}</strong>
                        <span className="text-ink-soft">
                          {" "}
                          · {moment(row.created_at)}
                          {row.has_screenshot ? " · Screenshot" : ""}
                        </span>
                      </p>
                      <StatusBadge status={row.status} />
                    </div>
                    <p className="mt-1 text-xs text-ink-soft">
                      From{" "}
                      <Link
                        href={`/admin/households?selected=${row.household_id}`}
                        className={cn("font-semibold text-ink underline underline-offset-4", !row.household_name && "font-mono")}
                      >
                        {who(row)}
                      </Link>
                    </p>
                    <Button
                      size="sm"
                      variant="outline"
                      className="mt-2"
                      aria-current={row.id === open ? "true" : undefined}
                      onClick={() => update({ open: row.id })}
                    >
                      {row.id === open ? "Open now" : "Open"}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
            <Pager
              label="Feedback pages"
              offset={page.offset}
              shown={page.items.length}
              total={page.total}
              nextOffset={page.next_offset}
              onPage={(next) => update({ offset: next ? String(next) : null })}
            />
          </section>
        )}
        {open && <Detail key={open} feedbackId={open} onChanged={changed} onClose={() => update({ open: null })} />}
      </div>
    </div>
  );
}
