from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pqi_twin.pipeline import run_pipeline
from pqi_twin.utils import file_sha256
from tests.common import IG_ASSET, INPUT_DIR


def _collect_hashes(output_dir: Path) -> dict[str, str]:
    tracked = [
        output_dir / "mapping_proposals.json",
        output_dir / "terminology_scaffold.json",
        output_dir / "bundles" / "bundle-pq5.json",
        output_dir / "bundles" / "bundle-pq6.json",
        output_dir / "evidence_manifest.json",
    ]
    return {str(path.name): file_sha256(path) for path in tracked}


class DeterminismTests(unittest.TestCase):
    def test_pipeline_deterministic_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_dir = tmp_path / "out"
            governance_dir = tmp_path / "governance"

            run_pipeline(IG_ASSET, INPUT_DIR, output_dir, governance_dir)
            first_hashes = _collect_hashes(output_dir)

            run_pipeline(IG_ASSET, INPUT_DIR, output_dir, governance_dir)
            second_hashes = _collect_hashes(output_dir)

            self.assertEqual(first_hashes, second_hashes)

            evidence = json.loads((output_dir / "evidence_manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(evidence["determinismContract"]["statement"].startswith("Same inputs"))


if __name__ == "__main__":
    unittest.main()
