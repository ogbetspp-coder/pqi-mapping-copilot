from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pqi_twin.pipeline import run_pipeline
from pqi_twin.utils import stable_hash_obj
from tests.common import IG_ASSET, INPUT_DIR, REPO_ROOT


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class GoldenBundleTests(unittest.TestCase):
    def test_bundle_outputs_match_golden(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_dir = tmp_path / "out"
            governance_dir = tmp_path / "gov"

            run_pipeline(IG_ASSET, INPUT_DIR, output_dir, governance_dir)

            produced_pq5 = _load_json(output_dir / "bundles" / "bundle-pq5.json")
            produced_pq6 = _load_json(output_dir / "bundles" / "bundle-pq6.json")

            golden_pq5 = _load_json(REPO_ROOT / "tests" / "golden" / "bundle-pq5.json")
            golden_pq6 = _load_json(REPO_ROOT / "tests" / "golden" / "bundle-pq6.json")

            self.assertEqual(stable_hash_obj(produced_pq5), stable_hash_obj(golden_pq5))
            self.assertEqual(stable_hash_obj(produced_pq6), stable_hash_obj(golden_pq6))


if __name__ == "__main__":
    unittest.main()
