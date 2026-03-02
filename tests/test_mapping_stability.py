from __future__ import annotations

import unittest

from pqi_twin.domain_classifier import classify_domains
from pqi_twin.ig_loader import load_ig_catalog
from pqi_twin.mapping_recommender import recommend_mappings
from pqi_twin.profiler import profile_input_extracts
from pqi_twin.utils import stable_hash_obj
from tests.common import IG_ASSET, INPUT_DIR


def _fingerprint(mapping_set: dict) -> str:
    reduced = [
        {
            "proposalId": p["proposalId"],
            "source": p["source"],
            "target": p["target"],
            "transform": p["transform"],
            "confidence": p["confidence"],
        }
        for p in mapping_set["proposals"]
    ]
    return stable_hash_obj(reduced)


class MappingStabilityTests(unittest.TestCase):
    def test_mapping_recommendations_stable(self) -> None:
        catalog = load_ig_catalog(IG_ASSET)
        profile = profile_input_extracts(INPUT_DIR)
        domains = classify_domains(profile)

        first = recommend_mappings(catalog, profile, domains)
        second = recommend_mappings(catalog, profile, domains)

        self.assertEqual(_fingerprint(first), _fingerprint(second))
        self.assertEqual(first["summary"]["proposalCount"], second["summary"]["proposalCount"])


if __name__ == "__main__":
    unittest.main()
