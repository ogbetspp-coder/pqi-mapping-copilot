from __future__ import annotations

import json
from pathlib import Path

from pqi_copilot.models import validate_mapping_proposal_payload
from pqi_copilot.pipeline import propose_run


def test_mapping_proposal_schema_validation() -> None:
    result = propose_run(Path("data/examples"))
    payload = json.loads((Path(result["run_dir"]) / "mapping_proposals.json").read_text(encoding="utf-8"))
    validated = validate_mapping_proposal_payload(payload)

    assert "proposals" in validated
    assert len(validated["proposals"]) > 0
    for proposal in validated["proposals"]:
        assert "source" in proposal
        assert "candidates" in proposal
        assert isinstance(proposal["candidates"], list)
