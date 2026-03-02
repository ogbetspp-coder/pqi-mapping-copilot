from __future__ import annotations

import json
from pathlib import Path

from pqi_copilot.common import file_sha256
from pqi_copilot.pipeline import propose_run


def test_golden_hashes_example_dataset() -> None:
    expected = json.loads(Path("tests/golden/pqi_copilot_expected_hashes.json").read_text(encoding="utf-8"))
    result = propose_run(Path("data/examples"))

    assert result["run_id"] == expected["run_id"]

    run_dir = Path(result["run_dir"])
    actual = {
        "mapping_proposals": file_sha256(run_dir / "mapping_proposals.json"),
        "domain_classification": file_sha256(run_dir / "domain_classification.json"),
        "relationship_proposals": file_sha256(run_dir / "relationship_proposals.json"),
        "manifest": file_sha256(run_dir / "manifest.json"),
    }

    assert actual == expected["hashes"]
