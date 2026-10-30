import { CircleCheck, CircleX } from "lucide-react";

import { InfoTip } from "@/components/ui/InfoTip";
import { fmtTime } from "@/lib/api";
import { GLOSSARY } from "@/lib/glossary";
import type { Check, EventRow, Field, Reason, Status } from "@/lib/types";

const STEPS: { key: string; label: string }[] = [
  { key: "queued", label: "Received" },
  { key: "scored", label: "Scored" },
  { key: "needs_review", label: "Needs a human" },
  { key: "recorded", label: "Decided" },
];

export function StatusStepper({ status, auto }: { status: Status; auto: boolean }) {
  const reached = { queued: 0, scoring: 1, failed: 1, needs_review: 2, recorded: 3 }[status];
  return (
    <ol className="flex flex-wrap items-center gap-2" aria-label="Progress">
      {STEPS.map((s, i) => {
        const skipped = auto && s.key === "needs_review";
        const done = i <= reached && !skipped;
        return (
          <li key={s.key} className="flex items-center gap-2">
            <span
              aria-current={i === reached ? "step" : undefined}
              className={`rounded-full px-3 py-1 text-xs font-semibold ${
                skipped
                  ? "bg-slate-100 text-slate-400 line-through dark:bg-slate-800"
                  : done
                    ? "bg-teal-600 text-white"
                    : "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400"
              }`}
            >
              {i + 1}. {s.label}
            </span>
            {i < STEPS.length - 1 && <span className="h-px w-4 bg-slate-300 dark:bg-slate-700" aria-hidden />}
          </li>
        );
      })}
      {status === "failed" && <li className="text-xs font-semibold text-red-600">Failed: see the error below</li>}
    </ol>
  );
}

export function ContributionBars({
  contributions,
  reasons,
  labels,
}: {
  contributions: Record<string, number>;
  reasons: Reason[];
  labels: Record<string, string>;
}) {
  const rows = Object.entries(contributions).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...rows.map(([, v]) => Math.abs(v)), 0.01);
  const reasonOf = Object.fromEntries(reasons.map((r) => [r.attribute, r.code]));
  return (
    <ul className="space-y-1.5">
      {rows.map(([attribute, value]) => {
        const width = `${(Math.abs(value) / max) * 50}%`;
        const adverse = value > 0;
        return (
          <li key={attribute} className="grid grid-cols-[minmax(0,11rem)_1fr_3.5rem] items-center gap-2 text-xs">
            <span className="truncate text-slate-700 dark:text-slate-300" title={labels[attribute]}>
              {reasonOf[attribute] && (
                <span className="mr-1 rounded bg-red-100 px-1 font-mono font-semibold text-red-700 dark:bg-red-950 dark:text-red-300">
                  {reasonOf[attribute]}
                </span>
              )}
              {labels[attribute] ?? attribute}
            </span>
            <span className="relative h-3 rounded bg-slate-100 dark:bg-slate-800">
              <span className="absolute inset-y-0 left-1/2 w-px bg-slate-400" aria-hidden />
              <span
                className={`absolute inset-y-0 rounded ${adverse ? "left-1/2 bg-red-500" : "right-1/2 bg-emerald-500"}`}
                style={{ width }}
              />
            </span>
            <span className={`text-right font-mono tabular-nums ${adverse ? "text-red-700 dark:text-red-400" : "text-emerald-700 dark:text-emerald-400"}`}>
              {Math.abs(value) < 0.005 ? "0.00" : `${value > 0 ? "+" : ""}${value.toFixed(2)}`}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

const CHECKS: Record<string, { label: string; what: string }> = {
  reasons_match_derivation: { label: "Reasons match the model", what: "The notice lists exactly the reasons code derived, in the same order." },
  reason_count: { label: "One to four reasons", what: "A decline states between one and four principal reasons." },
  no_prohibited_basis: { label: "No prohibited basis", what: "No reason refers to sex, age, marital status, national origin, or similar." },
  specific_reasons: { label: "Specific, not generic", what: "Each reason names the applicant's actual value; no 'did not meet our standards'." },
  decision_consistent: { label: "Decision is consistent", what: "The notice states the same decision that is being recorded." },
  numbers_grounded: { label: "Numbers match the application", what: "Every number in a reason equals the applicant's own field." },
  legal_frame_intact: { label: "Legal text intact", what: "The ECOA paragraph and frame match the reviewed template exactly." },
  approved_wording: { label: "Approved wording only", what: "Each sentence is one of the reviewed variants; no added promises or edits." },
};

export function VerifierChecklist({ checks }: { checks: Check[] }) {
  return (
    <ul className="grid gap-2 sm:grid-cols-2">
      {checks.map((c) => {
        const meta = CHECKS[c.name] ?? { label: c.name, what: "" };
        return (
          <li
            key={c.name}
            className={`rounded-lg border p-2.5 text-xs ${
              c.passed
                ? "border-emerald-200 bg-emerald-50/60 dark:border-emerald-900 dark:bg-emerald-950/30"
                : "border-red-300 bg-red-50 dark:border-red-900 dark:bg-red-950/40"
            }`}
          >
            <p className="flex items-center gap-1.5 font-semibold text-slate-900 dark:text-white">
              {c.passed ? <CircleCheck className="h-4 w-4 text-emerald-600" aria-hidden /> : <CircleX className="h-4 w-4 text-red-600" aria-hidden />}
              {meta.label}
              <span className="sr-only">{c.passed ? "passed" : "failed"}</span>
            </p>
            <p className="mt-0.5 text-slate-600 dark:text-slate-400">{meta.what}</p>
            {!c.passed && <p className="mt-1 font-mono text-red-700 dark:text-red-300">{c.detail}</p>}
            <p className="mt-1 font-mono text-[10px] text-slate-400">{c.name}</p>
          </li>
        );
      })}
    </ul>
  );
}

const EVENT_LABELS: Record<string, string> = {
  started: "Scoring started",
  scored: "Model scored the application",
  auto_approved: "Auto-approved by policy (no review needed)",
  reasons_derived: "Code derived the principal reasons",
  no_reasons: "No adverse reasons found: manual review required",
  verified: "Verifier checked the notice",
  awaiting_review: "Waiting for a human reviewer",
  variants_set: "Reviewer changed the wording",
  approved: "Reviewer approved",
  declined: "Reviewer sent the decline notice",
  failed: "Scoring failed",
};

export function Timeline({ events }: { events: EventRow[] }) {
  return (
    <ol className="relative space-y-3 border-l border-slate-200 pl-5 dark:border-slate-800">
      {events.map((e) => (
        <li key={e.seq} className="relative">
          <span className="absolute -left-[25px] top-1 h-2.5 w-2.5 rounded-full bg-teal-600 ring-4 ring-white dark:ring-slate-900" aria-hidden />
          <p className="text-sm text-slate-800 dark:text-slate-200">
            {EVENT_LABELS[e.kind] ?? e.kind}
            {e.kind === "verified" && (
              <span className={`ml-2 text-xs font-semibold ${e.detail.passed ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400"}`}>
                {e.detail.passed ? "passed" : "failed"}
              </span>
            )}
          </p>
          <p className="font-mono text-[11px] text-slate-400">
            {e.kind} · {e.actor} · {fmtTime(e.at)}
          </p>
        </li>
      ))}
    </ol>
  );
}

export function FieldsTable({ fields }: { fields: Field[] }) {
  return (
    <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
      {fields.map((f) => (
        <div key={f.name} className="flex justify-between gap-3 border-b border-slate-100 py-1 dark:border-slate-800">
          <dt className="text-slate-500 dark:text-slate-400">
            {f.label}
            {!f.used_by_model && (
              <span className="ml-1 rounded bg-slate-100 px-1 text-[10px] uppercase text-slate-500 dark:bg-slate-800">not used by model</span>
            )}
          </dt>
          <dd className="text-right font-medium text-slate-900 dark:text-white">{f.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function TipLabel({ text, tip }: { text: string; tip: keyof typeof GLOSSARY }) {
  return (
    <span>
      {text}
      <InfoTip text={GLOSSARY[tip]} />
    </span>
  );
}
