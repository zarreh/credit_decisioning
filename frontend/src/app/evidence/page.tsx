"use client";

import { ChartColumn, FlaskConical, Scale, ShieldCheck, TriangleAlert, Users } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Callout } from "@/components/ui/Callout";
import { Card, CardTitle } from "@/components/ui/Card";
import { InfoTip } from "@/components/ui/InfoTip";
import { PageHeader } from "@/components/ui/PageHeader";
import { ApiError, api, num, pct } from "@/lib/api";
import { docsLink } from "@/lib/docs";
import { GLOSSARY } from "@/lib/glossary";
import type { Evidence, FairnessRow, Interval, VerifierReport } from "@/lib/types";

/** Estimate with its CI drawn as a shaded range on a 0..max scale. */
function RangeBar({ value, ci, max = 1, label }: { value: number; ci: [number, number]; max?: number; label: string }) {
  const at = (x: number) => `${Math.max(0, Math.min(1, x / max)) * 100}%`;
  return (
    <div className="relative h-3 w-full rounded bg-slate-100 dark:bg-slate-800" role="img" aria-label={`${label}: ${num(value)} (95% CI ${num(ci[0])} to ${num(ci[1])})`}>
      <span className="absolute inset-y-0 rounded bg-teal-200 dark:bg-teal-900" style={{ left: at(ci[0]), width: `calc(${at(ci[1])} - ${at(ci[0])})` }} />
      <span className="absolute inset-y-[-2px] w-0.5 bg-teal-700 dark:bg-teal-300" style={{ left: at(value) }} />
    </div>
  );
}

function Metric({ name, tip, a, b, lowerBetter = false }: { name: string; tip?: keyof typeof GLOSSARY; a: Interval; b: Interval; lowerBetter?: boolean }) {
  return (
    <tr className="border-b border-slate-100 last:border-0 dark:border-slate-800">
      <th scope="row" className="px-4 py-2 text-left font-medium">
        {name}
        {tip && <InfoTip text={GLOSSARY[tip]} />}
        {lowerBetter && <span className="ml-1 text-xs font-normal text-slate-400">(lower is better)</span>}
      </th>
      {[a, b].map((m, i) => (
        <td key={i} className="px-4 py-2 font-mono text-sm tabular-nums">
          {num(m.estimate, 3)} <span className="text-xs text-slate-500">[{num(m.ci95[0], 3)}, {num(m.ci95[1], 3)}]</span>
        </td>
      ))}
    </tr>
  );
}

function FairnessTable({ rows }: { rows: FairnessRow[] }) {
  return (
    <table className="w-full min-w-[640px] text-left text-sm">
      <thead className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
        <tr>
          <th className="px-3 py-2">Group</th>
          <th className="px-3 py-2">n (bad)</th>
          <th className="w-56 px-3 py-2">Approval rate, 95% CI</th>
          <th className="px-3 py-2">
            Impact ratio <InfoTip text={GLOSSARY.adverseImpactRatio} />
          </th>
          <th className="px-3 py-2">Good applicants declined</th>
          <th className="px-3 py-2">Bad applicants approved</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.group} className="border-t border-slate-100 dark:border-slate-800">
            <td className="px-3 py-2 font-medium">{r.group}</td>
            <td className="px-3 py-2 font-mono tabular-nums">
              {r.n} ({r.n_bad})
            </td>
            {r.status === "ok" && r.approval_rate !== undefined && r.ci95 ? (
              <>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <span className="w-10 font-mono text-xs">{pct(r.approval_rate)}</span>
                    <RangeBar value={r.approval_rate} ci={r.ci95.approval_rate} label={`Approval rate, ${r.group}`} />
                  </div>
                </td>
                <td className="px-3 py-2">
                  <Badge variant={(r.adverse_impact_ratio ?? 1) < 0.8 ? "red" : "green"}>{num(r.adverse_impact_ratio ?? 0)}</Badge>
                </td>
                <td className="px-3 py-2 font-mono text-xs">{pct(r.false_positive_rate ?? 0)}</td>
                <td className="px-3 py-2 font-mono text-xs">{pct(r.false_negative_rate ?? 0)}</td>
              </>
            ) : (
              <td colSpan={4} className="px-3 py-2">
                <Badge variant="amber">insufficient n</Badge> <InfoTip text={GLOSSARY.insufficientN} />
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AgeFinding({ e }: { e: Evidence }) {
  const air = e.fairness.age_band.find((r) => r.group === "under 25")?.adverse_impact_ratio;
  if (air == null) return null;
  const flagged = air < 0.8;
  return (
    <Callout variant={flagged ? "warning" : "info"} title="What the audit shows">
      Under-25 applicants are approved at an impact ratio of {num(air)}, {flagged ? "below" : "above"} the 0.8 screen, even
      though age is not a model input. The permitted features predict the age band with AUROC{" "}
      {num(e.proxy_audit.age_band.auroc.estimate)}, so age still reaches the model through proxies.
      {flagged && " A real lender would have to investigate this before use."}
    </Callout>
  );
}

const ATTRS: { key: "sex" | "age_band" | "foreign_worker"; title: string; note: string }[] = [
  { key: "age_band", title: "Age band", note: "Age is excluded from the model; 62+ is too small to evaluate." },
  { key: "sex", title: "Sex", note: "UCI code A92 is the only female code present and mixes marital statuses, so only female/male is supported." },
  { key: "foreign_worker", title: "Foreign worker", note: "A crude national-origin proxy. Only 37 applicants are not foreign workers." },
];

export default function EvidencePage() {
  const [e, setE] = useState<Evidence | null>(null);
  const [v, setV] = useState<VerifierReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.evidence(), api.verifier()])
      .then(([a, b]) => {
        setE(a);
        setV(b);
      })
      .catch((x: unknown) => setError(x instanceof ApiError ? x.message : String(x)));
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader icon={ChartColumn} eyebrow="Step 3 · Evidence" title="What was measured, on what, and how sure we are" docsHref={docsLink("evidence")}>
        <p>
          Every number here says how many applicants it rests on, who labelled them, what scored them and how uncertain it
          is. Nothing on this page is computed in the browser: it is the committed output of <code>make train</code> and{" "}
          <code>make eval</code>.
        </p>
      </PageHeader>

      {error && (
        <Callout variant="error" title="Could not load the evidence" role="alert">
          {error}
        </Callout>
      )}

      {e && v && (
        <>
          <Callout variant="warning" title="Honest limits">
            <ul className="list-disc space-y-0.5 pl-5">
              <li>German Credit is {Number(e.provenance.n).toLocaleString("en-US")} applicants from 1970s–90s Germany (amounts in DM): not representative of any current lender.</li>
              <li>About 300 bad outcomes, so intervals are wide. Repeated cross-validation is used instead of a single small hold-out.</li>
              <li>Reasons are model attributions relative to the average approved applicant, not causes. The verifier checks faithfulness to them, not that the model is right.</li>
              <li>No credit-bureau data, no real applicants, no legal review. Not compliance advice.</li>
            </ul>
          </Callout>

          <Card padded={false}>
            <div className="p-5 pb-2">
              <CardTitle icon={<ChartColumn className="h-4 w-4" aria-hidden />}>
                Model: interpretable champion vs boosted challenger <InfoTip text={GLOSSARY.outOfFold} />
              </CardTitle>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
                The champion (logistic regression) runs in the product because its reasons are exact. The challenger
                (gradient boosting) exists to measure what interpretability costs.
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-sm">
                <thead className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  <tr>
                    <th className="px-4 py-2 text-left">Metric (95% CI)</th>
                    <th className="px-4 py-2 text-left">Champion</th>
                    <th className="px-4 py-2 text-left">Challenger</th>
                  </tr>
                </thead>
                <tbody>
                  <Metric name="AUROC" tip="auroc" a={e.champion.auroc} b={e.challenger.auroc} />
                  <Metric name="Expected cost" tip="expectedCost" a={e.champion.expected_cost} b={e.challenger.expected_cost} lowerBetter />
                  <Metric name="Brier score" a={e.champion.brier} b={e.challenger.brier} lowerBetter />
                  <Metric name="ECE" tip="calibration" a={e.champion.ece} b={e.challenger.ece} lowerBetter />
                </tbody>
              </table>
            </div>
            <div className="grid gap-3 p-5 sm:grid-cols-3">
              <div className="rounded-lg bg-teal-50 p-3 text-sm dark:bg-teal-950/40">
                <p className="text-xs font-semibold uppercase text-teal-800 dark:text-teal-300">Key finding</p>
                <p className="mt-1">
                  The champion costs <strong>{num(e.champion.expected_cost.estimate)}</strong> per applicant vs{" "}
                  <strong>{num(e.baselines.decline_everyone)}</strong> for declining everyone and{" "}
                  {num(e.baselines.approve_everyone)} for approving everyone.
                </p>
              </div>
              <div className="rounded-lg bg-slate-50 p-3 text-sm dark:bg-slate-800/50">
                <p className="text-xs font-semibold uppercase text-slate-500">Price of interpretability</p>
                <p className="mt-1">
                  Challenger − champion AUROC {num(e.challenger_minus_champion.auroc.estimate, 3)} [
                  {num(e.challenger_minus_champion.auroc.ci95[0], 3)}, {num(e.challenger_minus_champion.auroc.ci95[1], 3)}];{" "}
                  {e.challenger_minus_champion.auroc.ci95[0] <= 0 && e.challenger_minus_champion.auroc.ci95[1] >= 0
                    ? "the interval includes zero, so no difference is established."
                    : "the interval excludes zero: interpretability has a measurable cost here."}
                </p>
              </div>
              <div className="rounded-lg bg-amber-50 p-3 text-sm dark:bg-amber-950/40">
                <p className="text-xs font-semibold uppercase text-amber-800 dark:text-amber-300">Caveat</p>
                <p className="mt-1">
                  {e.champion.ece.estimate < e.champion.ece.ci95[0]
                    ? "ECE's bootstrap interval sits above its own estimate: binned ECE is biased upward when resampled. Read it as a rough range, not a calibrated interval."
                    : "Binned ECE is biased upward when resampled; read its interval as a rough range."}
                </p>
              </div>
            </div>
            <p className="px-5 pb-4 text-xs text-slate-500">
              n = {e.provenance.n} · labels: {e.provenance.label_source} · scorer: {e.provenance.scorer} · model{" "}
              {e.provenance.model_version} · run {e.provenance.run_date} · {e.provenance.validation} · {e.provenance.uncertainty}
            </p>
          </Card>

          <Card>
            <CardTitle icon={<Scale className="h-4 w-4" aria-hidden />}>
              Decision policy <InfoTip text={GLOSSARY.costMatrix} />
            </CardTitle>
            <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">
              Threshold {num(e.policy.threshold, 3)} = {e.policy.cost_decline_good} / ({e.policy.cost_decline_good} + {e.policy.cost_approve_bad}),
              derived from the costs, never tuned. Refer ceiling {e.policy.refer_ceiling} is a reviewer-capacity choice. On the
              benchmark (out-of-fold): {e.policy.band_counts.approve} approve, {e.policy.band_counts.refer} refer,{" "}
              {e.policy.band_counts.decline} decline.
            </p>
          </Card>

          <Card padded={false}>
            <div className="p-5 pb-2">
              <CardTitle icon={<Users className="h-4 w-4" aria-hidden />}>Fairness audit: measure and disclose</CardTitle>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
                Protected attributes are excluded from the model and used only here. Small groups are shown as gaps, not
                hidden. The 0.8 impact-ratio line is a screening heuristic, not a legal finding.
              </p>
            </div>
            {ATTRS.map((a) => (
              <div key={a.key} className="border-t border-slate-100 p-5 dark:border-slate-800">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 className="font-semibold">{a.title}</h3>
                  <p className="text-xs text-slate-500">
                    Proxy audit <InfoTip text={GLOSSARY.proxyAudit} />: AUROC {num(e.proxy_audit[a.key].auroc.estimate)} [
                    {num(e.proxy_audit[a.key].auroc.ci95[0])}, {num(e.proxy_audit[a.key].auroc.ci95[1])}] ({e.proxy_audit[a.key].method})
                  </p>
                </div>
                <p className="mt-1 text-xs text-slate-500">{a.note}</p>
                <div className="mt-2 overflow-x-auto">
                  <FairnessTable rows={e.fairness[a.key]} />
                </div>
              </div>
            ))}
            <div className="p-5 pt-0">
              <AgeFinding e={e} />
            </div>
          </Card>

          <Card padded={false}>
            <div className="p-5 pb-2">
              <CardTitle icon={<ShieldCheck className="h-4 w-4" aria-hidden />}>
                Verifier under attack <InfoTip text={GLOSSARY.mutation} />
              </CardTitle>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
                Every genuine decline notice on the benchmark ({v.verifier.genuine_notices}, both wordings) was broken in{" "}
                {Object.keys(v.verifier.mutators).length} ways. A mutant counts as caught only if the check meant to catch it fails.
                Genuine notices wrongly rejected: <strong>{v.verifier.false_rejects}</strong>.
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  <tr>
                    <th className="px-4 py-2">Mutator</th>
                    <th className="px-4 py-2">Defect injected</th>
                    <th className="px-4 py-2">Intended check</th>
                    <th className="px-4 py-2">Caught</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(v.verifier.mutators).map(([id, m]) => (
                    <tr key={id} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="px-4 py-2 font-mono">{id}</td>
                      <td className="px-4 py-2">{m.defect}</td>
                      <td className="px-4 py-2 font-mono text-xs">{m.intended_checks.join(", ")}</td>
                      <td className="px-4 py-2">
                        <Badge variant={m.killed === m.applicable ? "green" : "red"}>
                          {m.killed}/{m.applicable}
                        </Badge>
                        {m.skipped > 0 && <span className="ml-2 text-xs text-slate-500">{m.skipped} not applicable</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="grid gap-3 p-5 sm:grid-cols-2">
              <div className="rounded-lg bg-slate-50 p-3 text-sm dark:bg-slate-800/50">
                <p className="text-xs font-semibold uppercase text-slate-500">
                  Meta-mutation <InfoTip text={GLOSSARY.metaMutation} />
                </p>
                <p className="mt-1">
                  Each of the {Object.keys(v.meta_mutation).length} checks was switched off in turn;{" "}
                  {Object.values(v.meta_mutation).filter((x) => x === "detected").length} of {Object.keys(v.meta_mutation).length} were
                  noticed by the gate.
                </p>
              </div>
              <div className="rounded-lg bg-slate-50 p-3 text-sm dark:bg-slate-800/50">
                <p className="text-xs font-semibold uppercase text-slate-500">Analyst guard rails</p>
                <p className="mt-1">
                  {v.analyst.passed}/{v.analyst.n} scripted cases pass (grounding, refusals, approval gate). Scorer: scripted
                  stand-in, not a live model.
                </p>
              </div>
            </div>
            <p className="px-5 pb-4 text-xs text-slate-500">
              labels: {v.label_source} · scorer: {v.scorer} · model {v.model_version} · run {v.run_date} · a finite test
              count, not a claim of universal correctness
            </p>
          </Card>

          <Card tone="amber">
            <CardTitle icon={<TriangleAlert className="h-4 w-4" aria-hidden />}>A reason a reviewer would question</CardTitle>
            <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">
              In this 1994 sample, &quot;critical account / credits at other banks&quot; is associated with <em>good</em> outcomes, so
              &quot;all credits at this bank paid back duly&quot; can appear as a reason for decline. The notice states it faithfully
              because it is what the model used; whether a lender should use such a model is a validation question the verifier
              cannot answer.
            </p>
          </Card>
          <p className="flex items-center gap-1 text-xs text-slate-500">
            <FlaskConical className="h-3.5 w-3.5" aria-hidden /> Source: <code>artifacts/evidence.json</code>,{" "}
            <code>artifacts/verifier_report.json</code>.
          </p>
        </>
      )}
      {!e && !error && <p className="text-sm text-slate-500">Loading the evidence…</p>}
    </div>
  );
}
