"use client";

import { Bot, CircleCheck, LoaderCircle, Send, TriangleAlert, Wrench } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Callout } from "@/components/ui/Callout";
import { InfoTip } from "@/components/ui/InfoTip";
import { ApiError, api, postStream } from "@/lib/api";
import { GLOSSARY } from "@/lib/glossary";
import type { Claim, Grounding } from "@/lib/types";

type Turn =
  | { role: "user"; text: string }
  | { role: "tool"; name: string; source?: string | null }
  | { role: "answer"; text: string; claims: Claim[]; grounding: Grounding }
  | { role: "approval"; title: string; body: string; kind: string; resolved?: string }
  | { role: "error"; text: string };

const TOOL_LABELS: Record<string, string> = {
  get_evidence: "Read the model evidence",
  get_fairness_table: "Read the fairness table",
  get_case: "Read the application",
  get_queue_summary: "Read the queue",
  query_benchmark: "Ran an aggregate query",
  save_report_draft: "Save a report draft",
};

function newThread(): string {
  return `t-${Math.random().toString(36).slice(2, 12)}`;
}

export function AnalystChat({
  page,
  caseId,
  suggestions,
  compact = false,
}: {
  page: string;
  caseId?: string;
  suggestions: string[];
  compact?: boolean;
}) {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [draftEdit, setDraftEdit] = useState("");
  const thread = useRef<string>("");
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    thread.current = newThread();
    api
      .analystStatus()
      .then((s) => setEnabled(s.enabled))
      .catch(() => setEnabled(false));
  }, []);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [turns]);

  const onEvent = ({ event, data }: { event: string; data: Record<string, unknown> }) => {
    if (event === "tool_call" && data.name !== "save_report_draft") {
      setTurns((t) => [...t, { role: "tool", name: String(data.name) }]);
    } else if (event === "tool_result") {
      setTurns((t) => {
        const copy = [...t];
        for (let i = copy.length - 1; i >= 0; i--) {
          const turn = copy[i];
          if (turn.role === "tool" && turn.name === data.name && turn.source === undefined) {
            copy[i] = { ...turn, source: (data.source_id as string | null) ?? null };
            break;
          }
        }
        return copy;
      });
    } else if (event === "answer") {
      setTurns((t) => [
        ...t,
        { role: "answer", text: String(data.text), claims: data.claims as Claim[], grounding: data.grounding as Grounding },
      ]);
    } else if (event === "approval_needed") {
      const req = (data.requests as { args: Record<string, string> }[])[0];
      setDraftEdit(req.args.body ?? "");
      setTurns((t) => [...t, { role: "approval", title: req.args.title, body: req.args.body, kind: req.args.kind }]);
    } else if (event === "error") {
      setTurns((t) => [...t, { role: "error", text: String(data.detail) }]);
    }
  };

  const run = async (path: string, body: Record<string, unknown>) => {
    setBusy(true);
    try {
      await postStream(path, { thread_id: thread.current, page, case_id: caseId ?? null, ...body }, onEvent);
    } catch (e) {
      setTurns((t) => [...t, { role: "error", text: e instanceof ApiError ? e.message : String(e) }]);
    } finally {
      setBusy(false);
    }
  };

  const ask = (text: string) => {
    if (!text.trim() || busy) return;
    setTurns((t) => [...t, { role: "user", text }]);
    setInput("");
    void run("/analyst/chat", { message: text });
  };

  const decide = (decision: "approve" | "edit" | "reject") => {
    setTurns((t) => t.map((x) => (x.role === "approval" && !x.resolved ? { ...x, resolved: decision } : x)));
    void run("/analyst/resume", { decision, edited_body: decision === "edit" ? draftEdit : null });
  };

  if (enabled === false) {
    return (
      <Callout variant="info" title="Analyst disabled">
        No model API key is configured on the server (CREDIT_OPENAI_API_KEY), so the read-only analyst is off. Everything
        else works without it: scoring, reasons, the verifier and the review workflow involve no AI.
      </Callout>
    );
  }

  return (
    <div className="space-y-3">
      <div className={`space-y-3 overflow-y-auto ${compact ? "max-h-96" : "max-h-[32rem]"}`} aria-live="polite">
        {turns.length === 0 && (
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => ask(s)}
                disabled={!enabled || busy}
                className="rounded-full border border-teal-300 px-3 py-1 text-xs font-medium text-teal-800 hover:bg-teal-50 disabled:opacity-50 dark:border-teal-800 dark:text-teal-300 dark:hover:bg-teal-950"
              >
                {s}
              </button>
            ))}
          </div>
        )}
        {turns.map((t, i) => {
          if (t.role === "user")
            return (
              <p key={i} className="ml-auto w-fit max-w-[85%] rounded-xl bg-teal-600 px-3 py-2 text-sm text-white">
                {t.text}
              </p>
            );
          if (t.role === "tool")
            return (
              <p key={i} className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <Wrench className="h-3.5 w-3.5" aria-hidden /> {TOOL_LABELS[t.name] ?? t.name}
                {t.source && <code className="rounded bg-slate-100 px-1 dark:bg-slate-800">{t.source.slice(0, 48)}</code>}
              </p>
            );
          if (t.role === "error")
            return (
              <Callout key={i} variant="error" role="alert">
                {t.text}
              </Callout>
            );
          if (t.role === "approval")
            return (
              <div key={i} className="rounded-xl border border-amber-300 bg-amber-50/60 p-3 text-sm dark:border-amber-900 dark:bg-amber-950/30">
                <p className="font-semibold text-amber-900 dark:text-amber-200">
                  The analyst wants to save a {t.kind.replace("_", " ")} report draft: “{t.title}”
                </p>
                <p className="mt-1 text-xs text-amber-900/80 dark:text-amber-200/80">
                  Approving saves a draft only. Nothing is sent anywhere.
                </p>
                {t.resolved ? (
                  <p className="mt-2 text-xs font-medium">You chose: {t.resolved}</p>
                ) : (
                  <>
                    <label className="mt-2 block text-xs font-medium" htmlFor={`draft-${i}`}>
                      Draft text (edit before saving if you like)
                    </label>
                    <textarea
                      id={`draft-${i}`}
                      value={draftEdit}
                      onChange={(e) => setDraftEdit(e.target.value)}
                      rows={6}
                      className="mt-1 w-full rounded-lg border border-amber-300 bg-white p-2 font-mono text-xs dark:border-amber-800 dark:bg-slate-900"
                    />
                    <div className="mt-2 flex flex-wrap gap-2">
                      <button type="button" onClick={() => decide(draftEdit === t.body ? "approve" : "edit")} className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700">
                        Save draft
                      </button>
                      <button type="button" onClick={() => decide("reject")} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800">
                        Don&apos;t save
                      </button>
                    </div>
                  </>
                )}
              </div>
            );
          return (
            <div key={i} className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-900">
              <div className="mb-2 flex items-center gap-2">
                <Bot className="h-4 w-4 text-teal-600" aria-hidden />
                {t.grounding.verified ? (
                  <Badge variant="green">
                    <CircleCheck className="h-3 w-3" aria-hidden /> {t.grounding.numbers_checked} number(s) checked
                  </Badge>
                ) : (
                  <Badge variant="amber">
                    <TriangleAlert className="h-3 w-3" aria-hidden /> Unverified numbers
                  </Badge>
                )}
                <InfoTip text={GLOSSARY.grounding} />
              </div>
              <p className="whitespace-pre-wrap leading-relaxed text-slate-800 dark:text-slate-200">{t.text}</p>
              {!t.grounding.verified && (
                <ul className="mt-2 list-disc pl-5 text-xs text-amber-800 dark:text-amber-300">
                  {t.grounding.problems.map((p) => (
                    <li key={p}>{p}</li>
                  ))}
                </ul>
              )}
              {t.grounding.verified && (t.grounding.citation_problems?.length ?? 0) > 0 && (
                <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                  Every number was found in the tool results, but {t.grounding.citation_problems?.length} citation(s) point
                  at a different field than the one the number came from.
                </p>
              )}
              {t.claims.length > 0 && (
                <details className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                  <summary className="cursor-pointer">Sources for each number</summary>
                  <ul className="mt-1 space-y-0.5">
                    {t.claims.map((c, j) => (
                      <li key={j}>
                        <code>{c.value}</code> ← <code>{c.source_id}</code> · <code>{c.field}</code>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          );
        })}
        {busy && (
          <p className="flex items-center gap-2 text-xs text-slate-500">
            <LoaderCircle className="h-3.5 w-3.5 animate-spin" aria-hidden /> Analyst is working…
          </p>
        )}
        <div ref={end} />
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
        className="flex gap-2"
      >
        <label htmlFor={`ask-${page}`} className="sr-only">
          Ask the analyst
        </label>
        <input
          id={`ask-${page}`}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          maxLength={2000}
          disabled={!enabled || busy}
          placeholder={enabled === null ? "Checking the analyst…" : "Ask about the evidence, a case, or the data"}
          className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/30 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900"
        />
        <button
          type="submit"
          disabled={!enabled || busy || !input.trim()}
          className="inline-flex items-center gap-1 rounded-lg bg-teal-600 px-3 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-50"
        >
          <Send className="h-4 w-4" aria-hidden /> Ask
        </button>
      </form>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        Read-only. The analyst cannot change any decision and does not see sex, age, marital status or nationality.
      </p>
    </div>
  );
}
