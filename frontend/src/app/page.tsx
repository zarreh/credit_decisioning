"use client";

import {
  ArrowRight,
  Bot,
  Calculator,
  ClipboardCheck,
  FileText,
  FlaskConical,
  ListChecks,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Callout } from "@/components/ui/Callout";
import { Card, CardTitle } from "@/components/ui/Card";
import { InfoTip } from "@/components/ui/InfoTip";
import { ApiError, api, num } from "@/lib/api";
import { docsLink } from "@/lib/docs";
import { GLOSSARY } from "@/lib/glossary";
import type { Evidence, VerifierReport } from "@/lib/types";

const STEPS: { icon: LucideIcon; owner: string; title: string; text: string }[] = [
  { icon: Calculator, owner: "Model", title: "Score", text: "A calibrated logistic regression estimates the chance of a bad outcome." },
  { icon: ListChecks, owner: "Code", title: "Explain", text: "Code applies the cost policy and derives up to four principal reasons from the coefficients." },
  { icon: FileText, owner: "Code", title: "Write and verify", text: "Code fills the notice template; eight independent code checks verify it." },
  { icon: UserCheck, owner: "Human", title: "Decide", text: "A reviewer approves, or sends the verified notice. Overrides need a reason." },
  { icon: Bot, owner: "AI (read-only)", title: "Ask", text: "An analyst agent answers questions and drafts reports. Every number it states is checked." },
];

const OWNER_TONE: Record<string, "teal" | "indigo" | "amber" | "slate"> = {
  Model: "indigo",
  Code: "teal",
  Human: "amber",
  "AI (read-only)": "slate",
};

export default function Home() {
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [report, setReport] = useState<VerifierReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.evidence(), api.verifier()])
      .then(([e, r]) => {
        setEvidence(e);
        setReport(r);
      })
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : String(e)));
  }, []);

  const mutators = report ? Object.values(report.verifier.mutators) : [];
  const applicable = mutators.reduce((s, m) => s + m.applicable, 0);
  const killed = mutators.reduce((s, m) => s + m.killed, 0);

  return (
    <div className="space-y-10">
      <section className="rounded-2xl bg-gradient-to-br from-teal-700 to-indigo-800 px-6 py-10 text-white shadow-sm sm:px-10">
        <p className="text-xs font-semibold uppercase tracking-wider text-teal-100">Verified adverse-action notices</p>
        <h1 className="mt-2 max-w-3xl text-3xl font-bold tracking-tight sm:text-4xl">
          When credit is declined, the applicant must be told the specific reasons. This system makes those reasons
          checkable.
        </h1>
        <p className="mt-4 max-w-3xl text-teal-50">
          A model scores. Code, not AI, decides the band, derives the reasons and writes the notice. A separate code
          verifier checks it, and a human sends it. An AI analyst sits beside the product to explain, never to decide.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/queue" className="inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-semibold text-teal-800 hover:bg-teal-50">
            Open the review queue <ArrowRight className="h-4 w-4" aria-hidden />
          </Link>
          <Link href="/evidence" className="inline-flex items-center gap-2 rounded-lg border border-white/60 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10">
            See the evidence
          </Link>
        </div>
      </section>

      <section aria-labelledby="how">
        <h2 id="how" className="text-lg font-semibold text-slate-900 dark:text-white">
          How it works, and who owns each step
        </h2>
        <ol className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {STEPS.map((s, i) => (
            <li key={s.title}>
              <Card className="h-full">
                <div className="flex items-center justify-between">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-teal-600 text-sm font-bold text-white">{i + 1}</span>
                  <Badge variant={OWNER_TONE[s.owner]}>{s.owner}</Badge>
                </div>
                <p className="mt-3 flex items-center gap-2 font-semibold text-slate-900 dark:text-white">
                  <s.icon className="h-4 w-4 text-teal-600" aria-hidden /> {s.title}
                </p>
                <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{s.text}</p>
              </Card>
            </li>
          ))}
        </ol>
      </section>

      {error && (
        <Callout variant="error" title="Could not load the evidence" role="alert">
          {error}
        </Callout>
      )}

      <section className="grid gap-4 md:grid-cols-3" aria-label="Key results">
        <Card>
          <CardTitle icon={<ShieldCheck className="h-4 w-4" aria-hidden />}>
            Verifier under attack <InfoTip text={GLOSSARY.mutation} />
          </CardTitle>
          {report ? (
            <>
              <p className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">
                {killed.toLocaleString("en-US")} / {applicable.toLocaleString("en-US")}
              </p>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                broken notices rejected across {mutators.length} kinds of defect, with {report.verifier.false_rejects} genuine
                notices wrongly rejected (of {report.verifier.genuine_notices}).
              </p>
            </>
          ) : (
            <p className="mt-3 text-sm text-slate-500">Loading…</p>
          )}
        </Card>
        <Card>
          <CardTitle icon={<Calculator className="h-4 w-4" aria-hidden />}>
            Cost per applicant <InfoTip text={GLOSSARY.expectedCost} />
          </CardTitle>
          {evidence ? (
            <>
              <p className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">{num(evidence.champion.expected_cost.estimate)}</p>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                95% CI {num(evidence.champion.expected_cost.ci95[0])} to {num(evidence.champion.expected_cost.ci95[1])}, against{" "}
                {num(evidence.baselines.decline_everyone)} for declining everyone (n = {evidence.provenance.n}).
              </p>
            </>
          ) : (
            <p className="mt-3 text-sm text-slate-500">Loading…</p>
          )}
        </Card>
        <Card tone="amber">
          <CardTitle icon={<FlaskConical className="h-4 w-4" aria-hidden />}>Finding we disclose</CardTitle>
          {evidence ? (
            <p className="mt-3 text-sm text-slate-700 dark:text-slate-200">
              Age is excluded from the model, yet applicants under 25 are approved at{" "}
              <strong>
                {num(evidence.fairness.age_band.find((r) => r.group === "under 25")?.adverse_impact_ratio ?? 0)}×
              </strong>{" "}
              the rate of the best-treated age group. The remaining features predict age band with AUROC{" "}
              {num(evidence.proxy_audit.age_band.auroc.estimate)}. Dropping a column does not drop its proxies.
            </p>
          ) : (
            <p className="mt-3 text-sm text-slate-500">Loading…</p>
          )}
        </Card>
      </section>

      <Callout variant="info" title="What this is, and is not">
        A method demonstration on the 1994 UCI German Credit benchmark (1,000 applicants, amounts in Deutsche Marks). The
        review queue holds 60 synthetic applicants derived from it. It is not a lender, not compliance advice, and the
        reasons are model attributions, not causes.{" "}
        <a className="font-medium underline" href={docsLink("limits")} target="_blank" rel="noreferrer">
          Read the honest limits
        </a>
        .
      </Callout>

      <Card>
        <CardTitle icon={<ClipboardCheck className="h-4 w-4" aria-hidden />}>Try it</CardTitle>
        <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm text-slate-700 dark:text-slate-300">
          <li>
            Open the <Link className="font-medium text-teal-700 underline dark:text-teal-400" href="/queue">review queue</Link> and pick an application.
          </li>
          <li>Score it. Watch the reasons, the eight verifier checks and the drafted notice appear.</li>
          <li>Decide as the reviewer: send the notice, change its wording, or override with a reason.</li>
          <li>
            Ask the <Link className="font-medium text-teal-700 underline dark:text-teal-400" href="/analyst">analyst</Link> why, or have it draft a queue report.
          </li>
        </ol>
      </Card>
    </div>
  );
}
