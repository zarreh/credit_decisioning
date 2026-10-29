"""Generate the synthetic review queue (``make queue``): 60 seeded demo applicants.

Each is a real benchmark row, resampled, with duration and amount perturbed. They have
no outcome labels and no metric is ever computed on them; they only populate the queue.
Derived from CC BY 4.0 data (see NOTICE.md); synthetic, not anonymised real people.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from credit.pipeline.data import load, to_application
from credit.pipeline.model import SEED

QUEUE_PATH = Path("data/queue.json")
QUEUE_SIZE = 60


def generate(size: int = QUEUE_SIZE, seed: int = SEED) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    frame = load()
    rows = frame.iloc[rng.choice(len(frame), size=size, replace=False)]
    out = []
    for i, (_, row) in enumerate(rows.iterrows(), start=1):
        values = to_application(row).model_dump()
        values["duration_months"] = int(np.clip(values["duration_months"] + rng.integers(-6, 7), 4, 72))
        values["credit_amount"] = int(np.clip(round(values["credit_amount"] * rng.uniform(0.8, 1.25), -1), 250, 20000))
        out.append({"id": f"APP-{i:03d}", "application": values})
    return out


def main() -> None:
    QUEUE_PATH.write_text(json.dumps(generate(), indent=2) + "\n")
    print(f"wrote {QUEUE_SIZE} synthetic applicants to {QUEUE_PATH}")


if __name__ == "__main__":
    main()
