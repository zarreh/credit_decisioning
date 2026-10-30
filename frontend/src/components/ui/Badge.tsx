import type { ReactNode } from "react";

import type { BandName, Status } from "@/lib/types";

const VARIANTS = {
  red: "bg-red-50 text-red-700 ring-red-600/20 dark:bg-red-950 dark:text-red-300 dark:ring-red-400/30",
  amber: "bg-amber-50 text-amber-800 ring-amber-600/20 dark:bg-amber-950 dark:text-amber-300 dark:ring-amber-400/30",
  teal: "bg-teal-50 text-teal-700 ring-teal-600/20 dark:bg-teal-950 dark:text-teal-300 dark:ring-teal-400/30",
  indigo: "bg-indigo-50 text-indigo-700 ring-indigo-600/20 dark:bg-indigo-950 dark:text-indigo-300 dark:ring-indigo-400/30",
  green: "bg-emerald-50 text-emerald-700 ring-emerald-600/20 dark:bg-emerald-950 dark:text-emerald-300 dark:ring-emerald-400/30",
  slate: "bg-slate-100 text-slate-700 ring-slate-500/20 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-400/30",
} as const;

export type BadgeVariant = keyof typeof VARIANTS;

export function Badge({ children, variant = "slate" }: { children: ReactNode; variant?: BadgeVariant }) {
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${VARIANTS[variant]}`}>
      {children}
    </span>
  );
}

const STATUS: Record<Status, { label: string; variant: BadgeVariant }> = {
  queued: { label: "Not scored yet", variant: "slate" },
  scoring: { label: "Scoring", variant: "teal" },
  needs_review: { label: "Needs a reviewer", variant: "amber" },
  recorded: { label: "Decided", variant: "green" },
  failed: { label: "Failed", variant: "red" },
};

export function StatusBadge({ status }: { status: Status }) {
  const s = STATUS[status];
  return <Badge variant={s.variant}>{s.label}</Badge>;
}

const BAND: Record<BandName, { label: string; variant: BadgeVariant }> = {
  approve: { label: "Model: approve", variant: "green" },
  refer: { label: "Model: refer to human", variant: "indigo" },
  decline: { label: "Model: recommend decline", variant: "red" },
};

export function BandBadge({ band }: { band: BandName | null }) {
  if (!band) return <Badge>Not scored</Badge>;
  return <Badge variant={BAND[band].variant}>{BAND[band].label}</Badge>;
}

export function DecisionBadge({ decision }: { decision: "approved" | "declined" | null }) {
  if (!decision) return <Badge>Undecided</Badge>;
  return <Badge variant={decision === "approved" ? "green" : "red"}>{decision === "approved" ? "Approved" : "Declined"}</Badge>;
}
