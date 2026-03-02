from __future__ import annotations

import os

from pqi_copilot.ig.ig_loader import ENV_IG_SOURCE, discover_ig_resources


def test_discovery_prefers_repo_pinned_package() -> None:
    resources, source = discover_ig_resources()
    assert source.endswith("ig/pqi-package.tgz")
    assert any(r[1].get("resourceType") == "StructureDefinition" for r in resources)


def test_discovery_respects_env_override() -> None:
    prev = os.environ.get(ENV_IG_SOURCE)
    os.environ[ENV_IG_SOURCE] = "assets/pqi/package.tgz"
    try:
        resources, source = discover_ig_resources()
    finally:
        if prev is None:
            os.environ.pop(ENV_IG_SOURCE, None)
        else:
            os.environ[ENV_IG_SOURCE] = prev

    assert source.endswith("assets/pqi/package.tgz")
    assert any(r[1].get("resourceType") == "StructureDefinition" for r in resources)
