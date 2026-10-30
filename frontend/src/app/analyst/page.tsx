"use client";

import { Bot, FileText } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AnalystChat } from "@/components/AnalystChat";
import { Markdown } from "@/components/Markdown";
import { Badge } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { api, fmtTime } from "@/lib/api";
import { docsLink } from "@/lib/docs";
import type { Draft } from "@/lib/types";

export default function AnalystPage() {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const refresh = useCallback(() => {
    api.reports().then(setDrafts).catch(() => setDrafts([]));
  }, []);
  useEffect(refresh, [refresh]);

  return (
    <div className="space-y-6">
      <PageHeader icon={Bot} eyebrow="Step 4 · Analyst (AI, read-only)" title="Ask about the evidence, a case, or the data" docsHref={docsLink("analyst")}>
        <p>
          An AI agent with read-only tools: model metrics, fairness tables, queue cases (protected attributes removed) and
          aggregate benchmark queries with small cells suppressed. It can draft a report, but only you can save it.
        </p>
        <p>
          Code checks that every number it states appears in a tool result it retrieved; anything that does not is flagged
          in amber. It cannot score, decide or change anything.
        </p>
      </PageHeader>

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <Card>
          <CardTitle icon={<Bot className="h-4 w-4" aria-hidden />}>Conversation</CardTitle>
          <div className="mt-3">
            <AnalystChat
              page="analyst"
              suggestions={[
                "How good is the model, with uncertainty?",
                "Does the model beat declining everyone?",
                "How are applicants under 25 treated, and why?",
                "What is the bad rate by loan purpose?",
                "Draft a short model-risk report",
              ]}
            />
          </div>
        </Card>
        <Card>
          <div className="flex items-center justify-between">
            <CardTitle icon={<FileText className="h-4 w-4" aria-hidden />}>Report drafts</CardTitle>
            <button type="button" onClick={refresh} className="text-xs font-medium text-teal-700 hover:underline dark:text-teal-400">
              Refresh
            </button>
          </div>
          {drafts.length === 0 ? (
            <p className="mt-3 text-sm text-slate-500">No drafts yet. Ask the analyst to draft one; you approve before it is saved.</p>
          ) : (
            <ul className="mt-3 space-y-3">
              {drafts.map((d) => (
                <li key={d.id} className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium">{d.title}</p>
                    <Badge variant="amber">{d.status}</Badge>
                  </div>
                  <p className="text-xs text-slate-500">
                    {d.kind.replace("_", " ")} · {fmtTime(d.created_at)}
                  </p>
                  <details className="mt-1 text-sm">
                    <summary className="cursor-pointer text-xs text-teal-700 dark:text-teal-400">Read</summary>
                    <div className="mt-2 border-t border-slate-100 pt-2 dark:border-slate-800">
                      <Markdown>{d.body}</Markdown>
                    </div>
                  </details>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
