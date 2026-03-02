from __future__ import annotations

import json
from pathlib import Path

from pqi_copilot.pipeline import propose_run


def test_propose_deterministic() -> None:
    result1 = propose_run(Path("data/examples"))
    result2 = propose_run(Path("data/examples"))

    assert result1["run_id"] == result2["run_id"]

    run_dir = Path(result1["run_dir"])
    mapping = json.loads((run_dir / "mapping_proposals.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    assert mapping.get("hash") == manifest.get("mapping_proposal_hash")
    assert manifest.get("generated_at_utc") == "deterministic"
