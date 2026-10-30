"use client";

import { Bot, Calculator, FileText, History, ListChecks, Play, ShieldCheck, UserCheck } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AnalystChat } from "@/components/AnalystChat";
import { ContributionBars, FieldsTable, StatusStepper, Timeline, TipLabel, VerifierChecklist } from "@/components/ApplicationParts";
import { BandBadge, DecisionBadge, StatusBadge } from "@/components/ui/Badge";
import { Callout } from "@/components/ui/Callout";
import { Card, CardTitle } from "@/components/ui/Card";
import { Meter } from "@/components/ui/Meter";
import { ApiError, api, fmtTime, pct } from "@/lib/api";
import type { Detail } from "@/lib/types";

const button = "inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50";

export default function ApplicationPage() {
  const { id } = useParams<{ id: string }>();
  const [app, setApp] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [comment, setComment] = useState("");
  const [variants, setVariants] = useState<Record<string, string>>({});

  const load = useCallback(() => {
    api
      .application(id)
      .then((a) => {
        setApp(a);
        setVariants(Object.fromEntries((a.notice?.reasons ?? []).map((r) => [r.code, r.variant])));
      })
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : String(e)));
  }, [id]);

  useEffect(load, [load]);

  const call = async (fn: () => Promise<Detail>) => {
    setBusy(true);
    setError(null);
    try {
      const next = await fn();
      setApp(next);
      setVariants(Object.fromEntries((next.notice?.reasons ?? []).map((r) => [r.code, r.variant])));
      setComment("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      load();
    } finally {
      setBusy(false);
    }
  };

  const act = (action: string, extra: Record<string, unknown> = {}) =>
    call(() => api.act(id, { action, expected_revision: app?.revision, comment: comment.trim() || null, ...extra }));

  if (!app) {
    return error ? (
      <Callout variant="error" title="Could not load this application" role="alert">
        {error} <Link className="underline" href="/queue">Back to the queue</Link>
      </Callout>
    ) : (
      <p className="text-sm text-slate-500">Loading…</p>
    );
  }

  const labels = Object.fromEntries(app.fields.map((f) => [f.name, f.label]));
  const verified = app.verification?.passed === true;
  const reviewing = app.status === "needs_review";
  const override = app.recommendation === "decline";
  const variantsChanged = (app.notice?.reasons ?? []).some((r) => variants[r.code] !== r.variant);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-teal-700 dark:text-teal-400">
            <Link href="/queue" className="hover:underline">Review queue</Link> · Application
          </p>
          <h1 className="mt-1 font-mono text-3xl font-bold text-slate-900 dark:text-white">{app.id}</h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            {app.credit_amount.toLocaleString("en-US")} DM over {app.duration_months} months for {app.purpose}. A synthetic applicant.
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            <StatusBadge status={app.status} />
            <BandBadge band={app.recommendation} />
            <DecisionBadge decision={app.final_decision} />
          </div>
        </div>
        {app.score && (
          <Card className="w-full sm:w-72">
            <CardTitle icon={<Calculator className="h-4 w-4" aria-hidden />}>
              <TipLabel text="Chance of bad" tip="pBad" />
            </CardTitle>
            <div className="mt-3">
              <Meter value={app.score.p_bad} max={1} label="Chance of bad" display={pct(app.score.p_bad, 1)} tone={app.recommendation === "decline" ? "red" : app.recommendation === "refer" ? "amber" : "green"} />
            </div>
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              Approve below 16.7% · refer to 25% · decline above. <span className="font-mono">{app.score.model_version}</span>
            </p>
          </Card>
        )}
      </header>

      <StatusStepper status={app.status} auto={app.final?.auto === true} />

      {error && (
        <Callout variant="error" title="That did not go through" role="alert">
          {error}
        </Callout>
      )}
      {app.error && (
        <Callout variant="error" title="Scoring failed" role="alert">
          {app.error}. You can retry below.
        </Callout>
      )}

      {(app.status === "queued" || app.status === "failed") && (
        <Card tone="teal">
          <CardTitle icon={<Play className="h-4 w-4" aria-hidden />}>What happens when you score it</CardTitle>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700 dark:text-slate-300">
            <li>The model estimates the chance of a bad outcome. Sex, age, nationality and telephone are not inputs.</li>
            <li>Code applies the 5-to-1 cost policy. Low risk is approved automatically; everything else waits for you.</li>
            <li>For a recommended decline, code derives up to four reasons, fills the notice and runs eight checks on it.</li>
          </ul>
          <button type="button" disabled={busy} onClick={() => call(() => api.start(id))} className={`${button} mt-4 bg-teal-600 text-white hover:bg-teal-700`}>
            <Play className="h-4 w-4" aria-hidden /> {app.status === "failed" ? "Retry scoring" : "Score this application"}
          </button>
        </Card>
      )}

      {app.score && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardTitle icon={<ListChecks className="h-4 w-4" aria-hidden />}>
              <TipLabel text="Why the model leans this way" tip="reasonCode" />
            </CardTitle>
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              Each bar is a field&apos;s push on the log-odds of a bad outcome, compared with the average approved training
              applicant. Red pushes toward decline. These are model attributions, not causes.
            </p>
            <div className="mt-3">
              <ContributionBars contributions={app.score.contributions} reasons={app.reasons} labels={labels} />
            </div>
          </Card>

          <Card>
            <CardTitle icon={<ShieldCheck className="h-4 w-4" aria-hidden />}>
              <TipLabel text="Notice verification" tip="verifier" />
            </CardTitle>
            {app.verification ? (
              <>
                <p className={`mt-2 text-sm font-semibold ${verified ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400"}`}>
                  {verified ? "All eight checks passed. The notice may be sent." : "Verification failed. This notice cannot be sent."}
                </p>
                <div className="mt-3">
                  <VerifierChecklist checks={app.verification.checks} />
                </div>
              </>
            ) : app.recommendation === "refer" ? (
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
                Borderline case: no notice is drafted unless you decide to decline. If you do, reasons and checks run first.
              </p>
            ) : app.recommendation === "decline" ? (
              <Callout variant="warning" className="mt-2">
                No adverse reasons could be derived, so no notice can be sent. Approve with a comment, or escalate offline.
              </Callout>
            ) : (
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Approved: no adverse-action notice is needed.</p>
            )}
          </Card>
        </div>
      )}

      {app.notice && app.notice_text && (
        <Card>
          <CardTitle icon={<FileText className="h-4 w-4" aria-hidden />}>
            <TipLabel text="Draft adverse-action notice" tip="adverseAction" />
          </CardTitle>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            Written by code from the reviewed template; no AI wrote any of it. Template {app.notice.template_version}, reason
            catalogue {app.notice.catalogue_version}.
          </p>
          <pre className="mt-3 whitespace-pre-wrap rounded-lg bg-slate-50 p-4 font-sans text-sm leading-relaxed text-slate-800 dark:bg-slate-950 dark:text-slate-200">
            {app.notice_text}
          </pre>
          {reviewing && (
            <div className="mt-4 space-y-2">
              <p className="text-sm font-semibold text-slate-900 dark:text-white">Choose the wording for each reason</p>
              {app.notice.reasons.map((r) => (
                <div key={r.code} className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-3">
                  <label htmlFor={`v-${r.code}`} className="w-12 font-mono text-xs font-semibold">
                    {r.code}
                  </label>
                  <select
                    id={`v-${r.code}`}
                    value={variants[r.code] ?? r.variant}
                    onChange={(e) => setVariants({ ...variants, [r.code]: e.target.value })}
                    className="flex-1 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
                  >
                    {Object.entries(app.variant_options[r.code] ?? {}).map(([name, text]) => (
                      <option key={name} value={name}>
                        {name}: {text}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
              <button type="button" disabled={busy || !variantsChanged} onClick={() => act("set_variants", { variants })} className={`${button} border border-slate-300 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800`}>
                Apply wording and re-verify
              </button>
            </div>
          )}
        </Card>
      )}

      {reviewing && (
        <Card tone="amber">
          <CardTitle icon={<UserCheck className="h-4 w-4" aria-hidden />}>Your decision</CardTitle>
          <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">
            The model recommends <strong>{app.recommendation}</strong>. You decide. The recommendation is kept on record
            whatever you choose.
          </p>
          <label htmlFor="comment" className="mt-3 block text-xs font-medium text-slate-700 dark:text-slate-300">
            Comment {override ? "(required to approve against the recommendation)" : "(optional)"}
          </label>
          <textarea id="comment" value={comment} onChange={(e) => setComment(e.target.value)} rows={2} maxLength={1000} className="mt-1 w-full rounded-lg border border-slate-300 bg-white p-2 text-sm dark:border-slate-700 dark:bg-slate-900" />
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {app.notice && (
              <div>
                <button type="button" disabled={busy || !verified || variantsChanged} onClick={() => act("confirm_decline")} className={`${button} w-full justify-center bg-red-600 text-white hover:bg-red-700`}>
                  Send the decline notice
                </button>
                <p className="mt-1 text-xs text-slate-500">
                  {variantsChanged ? "Apply your wording change first; it must be re-verified." : "Records a decline and the exact verified notice."}
                </p>
              </div>
            )}
            {app.recommendation === "refer" && !app.notice && (
              <div>
                <button type="button" disabled={busy} onClick={() => act("prepare_decline")} className={`${button} w-full justify-center border border-red-300 text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950`}>
                  Prepare a decline notice
                </button>
                <p className="mt-1 text-xs text-slate-500">Derives reasons and drafts a notice for you to check. Nothing is sent yet.</p>
              </div>
            )}
            <div>
              <button type="button" disabled={busy || (override && !comment.trim())} onClick={() => act("approve")} className={`${button} w-full justify-center bg-emerald-600 text-white hover:bg-emerald-700`}>
                {override ? "Approve (override)" : "Approve"}
              </button>
              <p className="mt-1 text-xs text-slate-500">
                {override ? "Overrides the model. Your comment is stored with the decision." : "Records an approval. No notice is needed."}
              </p>
            </div>
          </div>
        </Card>
      )}

      {app.final && (
        <Card tone={app.final.decision === "approved" ? "emerald" : "red"}>
          <CardTitle icon={<UserCheck className="h-4 w-4" aria-hidden />}>Decision recorded</CardTitle>
          <p className="mt-2 text-sm text-slate-800 dark:text-slate-200">
            <strong className="capitalize">{app.final.decision}</strong> by {app.final.auto ? "the cost policy (auto-approval, no review)" : app.final.actor} on {fmtTime(app.final.at)}.
            {app.final.overrode_recommendation && " This overrode the model's decline recommendation."}
          </p>
          {app.final.comment && <p className="mt-1 text-sm italic text-slate-600 dark:text-slate-300">“{app.final.comment}”</p>}
          {app.final.notice_sha256 && <p className="mt-1 font-mono text-[11px] text-slate-500">notice sha256 {app.final.notice_sha256.slice(0, 16)}…</p>}
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardTitle icon={<History className="h-4 w-4" aria-hidden />}>Audit trail</CardTitle>
          <div className="mt-3">
            {app.events.length ? <Timeline events={app.events} /> : <p className="text-sm text-slate-500">Nothing has happened yet.</p>}
          </div>
        </Card>
        <Card>
          <CardTitle icon={<Bot className="h-4 w-4" aria-hidden />}>Ask the analyst about this case</CardTitle>
          <div className="mt-3">
            <AnalystChat page="application" caseId={app.id} compact suggestions={[`Why is ${app.id} recommended for ${app.recommendation ?? "review"}?`, "What did each verifier check do here?"]} />
          </div>
        </Card>
      </div>

      <Card>
        <CardTitle>The application</CardTitle>
        <div className="mt-3">
          <FieldsTable fields={app.fields} />
        </div>
      </Card>
    </div>
  );
}
