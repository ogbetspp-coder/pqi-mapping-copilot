"""CLI entrypoint for PQI Mapping Copilot."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pqi_copilot.common import build_arg_parser, file_sha256, write_json
from pqi_copilot.generate.bundle import generate_minimal_bundle
from pqi_copilot.governance.store import approve_run, list_library, run_dir
from pqi_copilot.ig.ig_loader import build_and_save_catalog, list_profiles, load_catalog, show_profile
from pqi_copilot.pipeline import ensure_catalog, propose_run, update_manifest_with_outputs
from pqi_copilot.report.render import render_report_files
from pqi_copilot.validate.validator import validate_bundle_minimal

try:
    import typer  # type: ignore

    TYPER_AVAILABLE = True
except Exception:
    typer = None
    TYPER_AVAILABLE = False


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _handle_ig(args: Any) -> int:
    if args.ig_command == "index":
        catalog = build_and_save_catalog()
        _print(
            {
                "catalog": "artifacts/library/ig_catalog.json",
                "source": catalog.get("source"),
                "profiles": len(catalog.get("profiles", [])),
                "valueSets": len(catalog.get("valueSets", {})),
                "codeSystems": len(catalog.get("codeSystems", {})),
                "conceptMaps": len(catalog.get("conceptMaps", {})),
            }
        )
        return 0

    catalog = load_catalog()

    if args.ig_command == "list-profiles":
        matches = list_profiles(catalog, contains=args.contains)
        _print(
            {
                "count": len(matches),
                "profiles": [
                    {
                        "url": p.get("url"),
                        "name": p.get("name"),
                        "resourceType": p.get("resourceType"),
                    }
                    for p in matches
                ],
            }
        )
        return 0

    if args.ig_command == "show-profile":
        profile = show_profile(catalog, args.profile_url)
        if not profile:
            _print({"error": f"Profile not found: {args.profile_url}"})
            return 2
        _print(profile)
        return 0

    _print({"error": f"Unknown ig command: {args.ig_command}"})
    return 2


def _handle_propose(args: Any) -> int:
    ensure_catalog()
    result = propose_run(Path(args.input_dir))
    _print(result)
    return 0


def _handle_report(args: Any) -> int:
    paths = render_report_files(args.run_id)
    _print({"run_id": args.run_id, "report": paths})
    return 0


def _handle_approve(args: Any) -> int:
    overrides_path = Path(args.overrides) if getattr(args, "overrides", None) else None
    result = approve_run(args.run_id, Path(args.rules), args.mapping_name, overrides_path=overrides_path)

    update_manifest_with_outputs(
        run_id=args.run_id,
        approved_mapping_version_id=result.get("version_id"),
    )

    _print(
        {
            "run_id": args.run_id,
            "mapping_name": args.mapping_name,
            "version": result.get("version"),
            "version_id": result.get("version_id"),
            "reused": result.get("reused"),
            "path": result.get("path"),
            "decisions_required": len(result.get("approved", {}).get("decisions_required", [])),
            "overrides_applied": len(result.get("approved", {}).get("overrides_applied", [])),
        }
    )
    return 0


def _handle_library(args: Any) -> int:
    if args.library_command != "list":
        _print({"error": f"Unknown library command: {args.library_command}"})
        return 2
    _print(list_library())
    return 0


def _handle_generate(args: Any) -> int:
    generated = generate_minimal_bundle(args.run_id, mapping_name=args.mapping_name)
    base = run_dir(args.run_id) / "outputs"
    bundle_path = base / "bundle.json"
    gen_manifest_path = base / "generation_manifest.json"
    write_json(bundle_path, generated["bundle"])
    write_json(gen_manifest_path, generated["generation_manifest"])

    validation = validate_bundle_minimal(generated["bundle"])
    validation_path = base / "bundle_validation.json"
    write_json(validation_path, validation)

    output_hashes = {
        str(bundle_path): file_sha256(bundle_path),
        str(gen_manifest_path): file_sha256(gen_manifest_path),
        str(validation_path): file_sha256(validation_path),
    }

    update_manifest_with_outputs(
        run_id=args.run_id,
        approved_mapping_version_id=generated["generation_manifest"].get("mapping_version"),
        output_hashes=output_hashes,
    )

    _print(
        {
            "run_id": args.run_id,
            "bundle": str(bundle_path),
            "generation_manifest": str(gen_manifest_path),
            "validation": validation,
            "output_hashes": output_hashes,
        }
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "ig":
        return _handle_ig(args)
    if args.command == "propose":
        return _handle_propose(args)
    if args.command == "report":
        return _handle_report(args)
    if args.command == "approve":
        return _handle_approve(args)
    if args.command == "library":
        return _handle_library(args)
    if args.command == "generate":
        return _handle_generate(args)

    parser.print_help()
    return 2


if TYPER_AVAILABLE:
    app = typer.Typer(help="PQI Mapping Copilot CLI")
    ig_app = typer.Typer(help="IG catalog utilities")
    library_app = typer.Typer(help="Library operations")
    app.add_typer(ig_app, name="ig")
    app.add_typer(library_app, name="library")

    @ig_app.command("index")
    def ig_index() -> None:
        _handle_ig(type("Args", (), {"ig_command": "index"}))

    @ig_app.command("list-profiles")
    def ig_list_profiles(contains: str = "") -> None:
        _handle_ig(type("Args", (), {"ig_command": "list-profiles", "contains": contains}))

    @ig_app.command("show-profile")
    def ig_show_profile(profile_url: str) -> None:
        _handle_ig(type("Args", (), {"ig_command": "show-profile", "profile_url": profile_url}))

    @app.command("propose")
    def propose(input_dir: str) -> None:
        _handle_propose(type("Args", (), {"input_dir": input_dir}))

    @app.command("report")
    def report(run_id: str) -> None:
        _handle_report(type("Args", (), {"run_id": run_id}))

    @app.command("approve")
    def approve(
        run_id: str,
        rules: str,
        mapping_name: str = "batch-lot-analysis",
        overrides: str | None = None,
    ) -> None:
        _handle_approve(
            type(
                "Args",
                (),
                {"run_id": run_id, "rules": rules, "mapping_name": mapping_name, "overrides": overrides},
            )
        )

    @library_app.command("list")
    def library_list() -> None:
        _handle_library(type("Args", (), {"library_command": "list"}))

    @app.command("generate")
    def generate(run_id: str, mapping_name: str = "batch-lot-analysis") -> None:
        _handle_generate(type("Args", (), {"run_id": run_id, "mapping_name": mapping_name}))


if __name__ == "__main__":
    raise SystemExit(main())
