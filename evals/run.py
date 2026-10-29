"""``make eval``: the model gate and the verifier gate. Exits non-zero on any failure.

Scorer: deterministic code. No API key, no network. Writes evals/report.json.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Collection, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from credit.guardrails.verifier import CHECKS, Expected, verify
from credit.notice import render_decline
from credit.pipeline.data import load, to_application
from credit.pipeline.scoring import load_model, score
from credit.schemas import Band, Notice
from evals import analyst
from evals.mutations import MUTATORS

HERE = Path(__file__).parent


def corpus() -> Iterator[tuple[Notice, Expected]]:
    """Genuine notices for every decline-band benchmark applicant, in each variant."""
    model = load_model()
    for _, row in load().iterrows():
        application = to_application(row)
        scored = score(application, model)
        if scored.score.band is not Band.DECLINE or not scored.reasons:
            continue
        expected = Expected(application, [r.code for r in scored.reasons], "declined")
        for variant in ("standard", "plain"):
            chosen = {r.code: variant for r in scored.reasons}
            yield render_decline(str(row["row_id"]), application, scored.reasons, chosen), expected  # type: ignore[arg-type]


def verifier_gate(pairs: list[tuple[Notice, Expected]], disabled: Collection[str] = ()) -> dict[str, Any]:
    false_rejects = [n.application_id for n, e in pairs if not verify(n, e, disabled=disabled).passed]
    mutators: dict[str, Any] = {}
    for m in MUTATORS:
        applicable = killed = skipped = 0
        for notice, expected in pairs:
            mutant = m.apply(notice, expected)
            if mutant is None:
                skipped += 1
                continue
            if mutant == notice:
                raise RuntimeError(f"{m.id} produced an unchanged notice: harness bug")
            applicable += 1
            failed = set(verify(mutant, expected, disabled=disabled).failed())
            killed += m.intended <= failed
        mutators[m.id] = {
            "defect": m.defect,
            "intended_checks": sorted(m.intended),
            "applicable": applicable,
            "killed": killed,
            "skipped": skipped,
            "kill_rate": killed / applicable if applicable else None,
        }
    return {"genuine_notices": len(pairs), "false_rejects": len(false_rejects), "mutators": mutators}


def verifier_passes(result: dict[str, Any], gates: dict[str, Any]) -> list[str]:
    problems = []
    if result["false_rejects"] > gates["max_false_rejects"]:
        problems.append(f"{result['false_rejects']} genuine notices rejected")
    for mid, m in result["mutators"].items():
        if m["applicable"] < gates["min_applicable_per_mutator"]:
            problems.append(f"{mid} never applied")
        elif m["kill_rate"] < gates["min_kill_rate"]:
            problems.append(f"{mid} kill rate {m['kill_rate']:.3f}")
    return problems


def model_gate(evidence: dict[str, Any], gates: dict[str, Any]) -> list[str]:
    champ, problems = evidence["champion"], []
    cost = champ["expected_cost"]["estimate"]
    if cost >= evidence["baselines"][gates["must_beat_baseline"]]:
        problems.append(f"expected cost {cost} does not beat {gates['must_beat_baseline']}")
    if cost > gates["max_expected_cost"]:
        problems.append(f"expected cost {cost} > {gates['max_expected_cost']}")
    if champ["auroc"]["estimate"] < gates["min_auroc"]:
        problems.append(f"AUROC {champ['auroc']['estimate']} < {gates['min_auroc']}")
    if champ["ece"]["estimate"] > gates["max_ece"]:
        problems.append(f"ECE {champ['ece']['estimate']} > {gates['max_ece']}")
    return problems


def main() -> int:
    gates = yaml.safe_load((HERE / "gates.yaml").read_text())
    evidence = json.loads(Path("artifacts/evidence.json").read_text())
    pairs = list(corpus())
    result = verifier_gate(pairs)
    meta = {}
    for check in CHECKS:
        disabled_result = verifier_gate(pairs, disabled={check})
        meta[check] = "detected" if verifier_passes(disabled_result, gates["verifier"]) else "MISSED"
    problems = model_gate(evidence, gates["model"]) + verifier_passes(result, gates["verifier"])
    problems += [f"disabling {c} went unnoticed" for c, v in meta.items() if v != "detected"]
    analyst_result = analyst.run()
    problems += [f"analyst case {cid} failed" for cid, r in analyst_result["cases"].items() if not r["passed"]]
    report = {
        "run_date": datetime.now(UTC).date().isoformat(),
        "scorer": "deterministic code",
        "label_source": "designed by construction (mutations of genuine notices)",
        "model_version": evidence["provenance"]["model_version"],
        "verifier": result,
        "meta_mutation": meta,
        "analyst": analyst_result,
        "gate_problems": problems,
    }
    Path("artifacts/verifier_report.json").write_text(json.dumps(report, indent=2) + "\n")
    for mid, m in result["mutators"].items():
        print(f"{mid:4} {m['defect']:40} killed {m['killed']}/{m['applicable']} skipped {m['skipped']}")
    print(f"genuine notices {result['genuine_notices']}, false rejects {result['false_rejects']}")
    print(f"meta-mutation: {meta}")
    print(f"analyst (scripted stand-in): {analyst_result['passed']}/{analyst_result['n']} cases")
    print("GATE PASSED" if not problems else "GATE FAILED:\n  " + "\n  ".join(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
