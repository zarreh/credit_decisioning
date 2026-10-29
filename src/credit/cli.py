"""``make queue-reset``: destructive rebuild of the review queue and analyst threads."""

from __future__ import annotations

import json
from pathlib import Path

from credit.settings import get_settings
from credit.store import Store


def main() -> None:
    settings = get_settings()
    items = json.loads(Path(settings.queue_path).read_text())
    Store(settings.db_path).rebuild([(i["id"], i["application"]) for i in items])
    for suffix in ("", "-wal", "-shm"):
        Path(settings.analyst_db_path + suffix).unlink(missing_ok=True)
    print(f"queue rebuilt: {len(items)} applications; analyst threads cleared")


if __name__ == "__main__":
    main()
