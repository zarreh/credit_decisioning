export type Status = "queued" | "scoring" | "needs_review" | "recorded" | "failed";
export type BandName = "approve" | "refer" | "decline";

export interface Summary {
  id: string;
  status: Status;
  revision: number;
  purpose: string;
  credit_amount: number;
  duration_months: number;
  p_bad: number | null;
  recommendation: BandName | null;
  final_decision: "approved" | "declined" | null;
  verification_passed: boolean | null;
  updated_at: string;
}

export interface Field {
  name: string;
  label: string;
  value: string | number;
  used_by_model: boolean;
}

export interface Reason {
  code: string;
  attribute: string;
  contribution: number;
}

export interface Check {
  name: string;
  passed: boolean;
  detail: string;
}

export interface Verification {
  passed: boolean;
  checks: Check[];
  notice_sha256: string;
}

export interface NoticeReason {
  code: string;
  variant: "standard" | "plain";
  text: string;
}

export interface Notice {
  reasons: NoticeReason[];
  template_version: string;
  catalogue_version: string;
}

export interface EventRow {
  seq: number;
  kind: string;
  actor: string;
  detail: Record<string, unknown>;
  at: string;
}

export interface Final {
  decision: "approved" | "declined";
  actor: string;
  auto?: boolean;
  comment?: string | null;
  overrode_recommendation?: boolean;
  notice_sha256?: string;
  at: string;
}

export interface Detail extends Summary {
  fields: Field[];
  score: { p_bad: number; band: BandName; model_version: string; contributions: Record<string, number> } | null;
  reasons: Reason[];
  notice: Notice | null;
  notice_text: string | null;
  verification: Verification | null;
  variant_options: Record<string, Record<string, string>>;
  final: Final | null;
  error: string | null;
  events: EventRow[];
}

export interface Interval {
  estimate: number;
  ci95: [number, number];
  undefined_replicates?: number;
  repeat_range?: [number, number];
}

export interface FairnessRow {
  group: string;
  n: number;
  n_bad: number;
  status: "ok" | "insufficient_n";
  approval_rate?: number;
  false_positive_rate?: number;
  false_negative_rate?: number;
  calibration_gap?: number;
  expected_cost?: number;
  adverse_impact_ratio?: number | null;
  ci95?: Record<string, [number, number]>;
}

export interface Evidence {
  provenance: Record<string, string | number>;
  policy: {
    cost_approve_bad: number;
    cost_decline_good: number;
    threshold: number;
    refer_ceiling: number;
    band_counts: Record<BandName, number>;
  };
  baselines: { approve_everyone: number; decline_everyone: number };
  champion: Record<"auroc" | "brier" | "ece" | "expected_cost", Interval>;
  challenger: Record<"auroc" | "brier" | "ece" | "expected_cost", Interval>;
  challenger_minus_champion: Record<"auroc" | "expected_cost", Interval>;
  reliability: { bin: number; n: number; mean_predicted: number; observed: number }[];
  fairness: Record<"sex" | "foreign_worker" | "age_band", FairnessRow[]>;
  proxy_audit: Record<string, { auroc: Interval; classes: Record<string, number>; method: string }>;
  serving_model: { version: string; reference_kind: string; reference_n: number; calibration_slope: number };
}

export interface MutatorResult {
  defect: string;
  intended_checks: string[];
  applicable: number;
  killed: number;
  skipped: number;
  kill_rate: number | null;
}

export interface VerifierReport {
  run_date: string;
  scorer: string;
  label_source: string;
  model_version: string;
  verifier: { genuine_notices: number; false_rejects: number; mutators: Record<string, MutatorResult> };
  meta_mutation: Record<string, string>;
  analyst: { scorer: string; n: number; passed: number; cases: Record<string, { job: string; passed: boolean }> };
  gate_problems: string[];
}

export interface Claim {
  value: number;
  source_id: string;
  field: string;
}

export interface Grounding {
  verified: boolean;
  problems: string[];
  numbers_checked: number;
  repairs?: number;
}

export interface Draft {
  id: number;
  kind: string;
  title: string;
  body: string;
  status: string;
  created_at: string;
}
