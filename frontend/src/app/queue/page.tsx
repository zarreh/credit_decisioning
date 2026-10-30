"use client";

import { ListChecks } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { BandBadge, DecisionBadge, StatusBadge } from "@/components/ui/Badge";
import { Callout } from "@/components/ui/Callout";
import { Card } from "@/components/ui/Card";
import { InfoTip } from "@/components/ui/InfoTip";
import { Meter } from "@/components/ui/Meter";
import { PageHeader } from "@/components/ui/PageHeader";
import { ApiError, api, pct } from "@/lib/api";
import { docsLink } from "@/lib/docs";
import { GLOSSARY } from "@/lib/glossary";
import type { Status, Summary } from "@/lib/types";

const COUNTS: { status: Status; label: string }[] = [
  { status: "queued", label: "Not scored" },
  { status: "needs_review", label: "Need a reviewer" },
  { status: "recorded", label: "Decided" },
  { status: "failed", label: "Failed" },
];

export default function QueuePage() {
  const [rows, setRows] = useState<Summary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .queue()
      .then(setRows)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : String(e)));
  }, []);

  return (
    <div>
      <PageHeader icon={ListChecks} eyebrow="Step 1 · Review queue" title="Applications waiting for a decision" docsHref={docsLink("howItWorks")}>
        <p>
          Sixty synthetic applicants derived from the benchmark. Scoring one runs the model, applies the cost policy and,
          for a recommended decline, writes and verifies the notice. Anything not auto-approved waits here for a human.
        </p>
      </PageHeader>

      {error && (
        <Callout variant="error" title="Could not load the queue" role="alert">
          {error}
        </Callout>
      )}

      {rows && (
        <>
          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {COUNTS.map((c) => (
              <Card key={c.status} className="py-4">
                <p className="text-2xl font-bold text-slate-900 dark:text-white">{rows.filter((r) => r.status === c.status).length}</p>
                <p className="text-sm text-slate-500 dark:text-slate-400">{c.label}</p>
              </Card>
            ))}
          </div>

          {rows.length === 0 ? (
            <Callout title="The queue is empty">Run `make queue-reset` on the server to rebuild it.</Callout>
          ) : (
            <Card padded={false} className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:text-slate-400">
                  <tr>
                    <th className="px-4 py-3">Application</th>
                    <th className="px-4 py-3">Request</th>
                    <th className="px-4 py-3">
                      Chance of bad <InfoTip text={GLOSSARY.pBad} />
                    </th>
                    <th className="px-4 py-3">
                      Model band <InfoTip text={GLOSSARY.band} />
                    </th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Decision</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id} className="relative border-b border-slate-100 last:border-0 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50">
                      <td className="px-4 py-3 font-mono font-medium">
                        <Link href={`/applications/${r.id}`} className="text-teal-700 after:absolute after:inset-0 dark:text-teal-400">
                          {r.id}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-slate-700 dark:text-slate-300">
                        {r.credit_amount.toLocaleString("en-US")} DM · {r.duration_months} mo · {r.purpose}
                      </td>
                      <td className="w-48 px-4 py-3">
                        {r.p_bad === null ? (
                          <span className="text-slate-400">—</span>
                        ) : (
                          <Meter
                            value={r.p_bad}
                            max={1}
                            label={`Chance of bad for ${r.id}`}
                            display={pct(r.p_bad)}
                            tone={r.recommendation === "decline" ? "red" : r.recommendation === "refer" ? "amber" : "green"}
                          />
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <BandBadge band={r.recommendation} />
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={r.status} />
                      </td>
                      <td className="px-4 py-3">
                        <DecisionBadge decision={r.final_decision} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </>
      )}
      {!rows && !error && <p className="text-sm text-slate-500">Loading the queue…</p>}
    </div>
  );
}
