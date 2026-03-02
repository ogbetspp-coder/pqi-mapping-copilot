from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pqi_copilot.common import file_sha256
from pqi_copilot.pipeline import propose_run

CONSTRAINTS = Path("constraints.txt")
DETERMINISM_PACKAGES = [
    "rapidfuzz",
    "pandas",
    "pydantic",
    "python-dateutil",
    "jinja2",
    "typer",
]


def _parse_constraints(path: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "==" not in line:
            continue
        name, pinned = line.split("==", 1)
        versions[name.strip().lower()] = pinned.strip()
    return versions


def _skip_if_unpinned_environment() -> None:
    if not CONSTRAINTS.exists():
        return
    expected = _parse_constraints(CONSTRAINTS)
    mismatches: list[str] = []

    for pkg in DETERMINISM_PACKAGES:
        wanted = expected.get(pkg.lower())
        if not wanted:
            continue
        try:
            actual = version(pkg)
        except PackageNotFoundError:
            mismatches.append(f"{pkg}=MISSING(expected {wanted})")
            continue
        if actual != wanted:
            mismatches.append(f"{pkg}={actual}(expected {wanted})")

    if mismatches:
        try:
            import pytest  # type: ignore
        except Exception:
            return
        pytest.skip(
            "Golden hash test requires constrained dependency versions. "
            "Install with: pip install -e \".[dev,ui]\" -c constraints.txt. "
            f"Mismatches: {', '.join(mismatches)}"
        )


def test_golden_hashes_example_dataset() -> None:
    _skip_if_unpinned_environment()
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
