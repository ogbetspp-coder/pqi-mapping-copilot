from __future__ import annotations

import os
from pathlib import Path

from pqi_copilot.pipeline import ensure_catalog, propose_run


def test_artifacts_root_env_relocates_outputs(tmp_path: Path) -> None:
    previous = os.environ.get("PQI_ARTIFACTS_ROOT")
    os.environ["PQI_ARTIFACTS_ROOT"] = str(tmp_path / "custom-artifacts")
    try:
        ensure_catalog()
        result = propose_run(Path("data/examples"))
    finally:
        if previous is None:
            os.environ.pop("PQI_ARTIFACTS_ROOT", None)
        else:
            os.environ["PQI_ARTIFACTS_ROOT"] = previous

    run_dir = Path(result["run_dir"])
    assert str(run_dir).startswith(str(tmp_path / "custom-artifacts" / "runs"))
    assert (run_dir / "manifest.json").exists()
