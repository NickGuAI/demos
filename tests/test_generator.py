#!/usr/bin/env python3
"""
Tests for the GCP augmentation prompt generator.

Run:
    python3 -m pytest tests/test_generator.py -v
    # or:
    python3 tests/test_generator.py
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from generate_gcp_prompts import (
    build_decision_prompt,
    detect_components_static,
    generate,
    load_catalog,
    parse_decision_json,
    resolve_supporting,
    select_template,
)


# ---------------------------------------------------------------------------
# Catalog loading
# ---------------------------------------------------------------------------

def test_catalog_loads():
    """Catalog YAML loads and has expected structure."""
    catalog = load_catalog(REPO_ROOT / "rules" / "gcp-component-decision.yaml")
    assert "components" in catalog
    assert "cloud_run" in catalog["components"]
    assert "iam" in catalog["components"]
    assert "alloydb" in catalog["components"]
    assert "template_matrix" in catalog
    assert "supporting" in catalog
    print("PASS: test_catalog_loads")


def test_catalog_components_have_descriptions():
    """Every component in the catalog has a description and use_when."""
    catalog = load_catalog(REPO_ROOT / "rules" / "gcp-component-decision.yaml")
    for name, comp in catalog["components"].items():
        assert "description" in comp, f"{name} missing description"
        assert "use_when" in comp, f"{name} missing use_when"
    print("PASS: test_catalog_components_have_descriptions")


# ---------------------------------------------------------------------------
# parse_decision_json
# ---------------------------------------------------------------------------

def test_parse_clean_json():
    """Parses a clean JSON response from Claude."""
    raw = json.dumps({
        "selected": ["cloud_run", "iam"],
        "reasoning": {"cloud_run": "web app", "iam": "needs SA", "alloydb": None},
        "supporting": ["artifact_registry", "service_account"],
    })
    result = parse_decision_json(raw)
    assert result["selected"] == ["cloud_run", "iam"]
    assert result["reasoning"]["alloydb"] is None
    print("PASS: test_parse_clean_json")


def test_parse_fenced_json():
    """Strips markdown fences from Claude response."""
    raw = '```json\n{"selected": ["alloydb", "iam"], "reasoning": {}}\n```'
    result = parse_decision_json(raw)
    assert "alloydb" in result["selected"]
    assert "iam" in result["selected"]
    print("PASS: test_parse_fenced_json")


def test_parse_enforces_alloydb_iam_transitive():
    """AlloyDB without IAM gets IAM added transitively."""
    raw = json.dumps({
        "selected": ["alloydb"],
        "reasoning": {"alloydb": "needs db", "iam": None, "cloud_run": None},
    })
    result = parse_decision_json(raw)
    assert "iam" in result["selected"], "IAM should be added transitively for AlloyDB"
    assert result["reasoning"]["iam"] is not None
    print("PASS: test_parse_enforces_alloydb_iam_transitive")


def test_parse_filters_invalid_components():
    """Unknown component names are stripped from selected."""
    raw = json.dumps({
        "selected": ["cloud_run", "bigquery", "iam"],
        "reasoning": {},
    })
    result = parse_decision_json(raw)
    assert "bigquery" not in result["selected"]
    assert result["selected"] == ["cloud_run", "iam"]
    print("PASS: test_parse_filters_invalid_components")


def test_parse_adds_supporting_when_missing():
    """Supporting infra is derived when Claude omits it."""
    raw = json.dumps({
        "selected": ["cloud_run", "alloydb", "iam"],
        "reasoning": {},
    })
    result = parse_decision_json(raw)
    assert "supporting" in result
    assert "artifact_registry" in result["supporting"]
    assert "vpc_network" in result["supporting"]
    assert "service_account" in result["supporting"]
    assert "secret_manager" in result["supporting"]
    print("PASS: test_parse_adds_supporting_when_missing")


def test_parse_rejects_invalid_json():
    """Raises on garbage input."""
    try:
        parse_decision_json("this is not json")
        assert False, "Should have raised"
    except (json.JSONDecodeError, ValueError):
        pass
    print("PASS: test_parse_rejects_invalid_json")


def test_parse_rejects_missing_selected():
    """Raises when selected field is missing."""
    try:
        parse_decision_json('{"reasoning": {}}')
        assert False, "Should have raised"
    except ValueError:
        pass
    print("PASS: test_parse_rejects_missing_selected")


# ---------------------------------------------------------------------------
# resolve_supporting
# ---------------------------------------------------------------------------

def test_resolve_supporting_cloud_run():
    """Cloud Run needs artifact_registry + service_account."""
    result = resolve_supporting(["cloud_run"])
    assert "artifact_registry" in result
    assert "service_account" in result
    assert "vpc_network" not in result
    print("PASS: test_resolve_supporting_cloud_run")


def test_resolve_supporting_alloydb():
    """AlloyDB needs vpc_network + secret_manager + service_account."""
    result = resolve_supporting(["alloydb"])
    assert "vpc_network" in result
    assert "secret_manager" in result
    assert "service_account" in result
    print("PASS: test_resolve_supporting_alloydb")


def test_resolve_supporting_empty():
    """No components means no supporting infra."""
    assert resolve_supporting([]) == []
    print("PASS: test_resolve_supporting_empty")


def test_resolve_supporting_full_stack():
    """All components selected → all supporting infra."""
    result = resolve_supporting(["alloydb", "cloud_run", "iam"])
    assert len(result) == 4  # artifact_registry, secret_manager, service_account, vpc_network
    print("PASS: test_resolve_supporting_full_stack")


# ---------------------------------------------------------------------------
# build_decision_prompt
# ---------------------------------------------------------------------------

def test_build_prompt_includes_spec_and_catalog():
    """Decision prompt contains both the spec and the catalog."""
    catalog = load_catalog()
    prompt = build_decision_prompt("My test project spec.", catalog)
    assert "My test project spec." in prompt
    assert "cloud_run" in prompt
    assert "alloydb" in prompt
    assert "GCP Component Catalog" in prompt
    print("PASS: test_build_prompt_includes_spec_and_catalog")


# ---------------------------------------------------------------------------
# Static fallback (detect_components_static)
# ---------------------------------------------------------------------------

def test_static_cloud_run_only():
    """Static: web service signals select cloud_run."""
    result = detect_components_static("Deploy a simple web application.")
    assert "cloud_run" in result["selected"]
    assert "alloydb" not in result["selected"]
    assert result["method"] == "static"
    print("PASS: test_static_cloud_run_only")


def test_static_alloydb_implies_iam():
    """Static: database signals select alloydb + transitive iam."""
    result = detect_components_static("Set up a PostgreSQL database.")
    assert "alloydb" in result["selected"]
    assert "iam" in result["selected"]
    print("PASS: test_static_alloydb_implies_iam")


def test_static_iam_only():
    """Static: IAM signals select iam."""
    result = detect_components_static("Configure IAM roles and service accounts.")
    assert "iam" in result["selected"]
    print("PASS: test_static_iam_only")


def test_static_full_stack():
    """Static: Book Journey spec selects all three."""
    spec = (REPO_ROOT / "examples" / "book-journey" / "project.md").read_text()
    result = detect_components_static(spec)
    assert "cloud_run" in result["selected"]
    assert "alloydb" in result["selected"]
    assert "iam" in result["selected"]
    print("PASS: test_static_full_stack")


def test_static_no_signals():
    """Static: irrelevant spec selects nothing."""
    result = detect_components_static("Paint the fence blue.")
    assert len(result["selected"]) == 0
    print("PASS: test_static_no_signals")


# ---------------------------------------------------------------------------
# Template selection (preserved from v1)
# ---------------------------------------------------------------------------

def test_template_selection():
    """Template matrix returns correct templates for all combinations."""
    catalog = load_catalog()
    assert select_template(["cloud_run"], catalog) == "cloud-run.md"
    assert select_template(["iam"], catalog) == "iam.md"
    assert select_template(["alloydb"], catalog) == "alloydb.md"
    assert select_template(["cloud_run", "iam"], catalog) == "cloud-run-iam.md"
    assert select_template(["alloydb", "cloud_run"], catalog) == "cloud-run-alloydb.md"
    assert select_template(["alloydb", "cloud_run", "iam"], catalog) == "cloud-run-iam-alloydb.md"
    print("PASS: test_template_selection")


# ---------------------------------------------------------------------------
# End-to-end (uses --static to avoid requiring claude CLI)
# ---------------------------------------------------------------------------

def test_generate_end_to_end_static():
    """Full pipeline with --static produces files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_path = REPO_ROOT / "examples" / "book-journey" / "project.md"
        output_dir = Path(tmpdir) / "bundle"
        decision = generate(
            str(spec_path), str(output_dir), emit_decision=True, use_static=True,
        )

        assert len(decision["selected"]) >= 3
        assert decision["method"] == "static"

        # Prompt files written
        files = list(output_dir.glob("*.md"))
        assert len(files) >= 3, f"Expected >=3 prompt files, got {len(files)}"

        # Decision JSON written
        decision_file = Path(tmpdir) / "selected-components.json"
        assert decision_file.exists()
        data = json.loads(decision_file.read_text())
        assert "selected" in data
        assert "method" in data

        # Templates contain project spec
        for f in files:
            content = f.read_text()
            assert "Book Journey" in content, f"{f.name} missing project spec"

        print("PASS: test_generate_end_to_end_static")


def test_generate_end_to_end_claude():
    """Full pipeline with claude -p (skipped if claude not available)."""
    if not shutil.which("claude"):
        print("SKIP: test_generate_end_to_end_claude (claude CLI not found)")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        spec_path = REPO_ROOT / "examples" / "book-journey" / "project.md"
        output_dir = Path(tmpdir) / "bundle"
        decision = generate(
            str(spec_path), str(output_dir), emit_decision=True, use_static=False,
        )

        assert len(decision["selected"]) >= 1
        assert decision["method"] == "claude"

        # Prompt files written
        files = list(output_dir.glob("*.md"))
        assert len(files) >= 1

        # Decision JSON written
        decision_file = Path(tmpdir) / "selected-components.json"
        assert decision_file.exists()

        print("PASS: test_generate_end_to_end_claude")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Catalog
    test_catalog_loads()
    test_catalog_components_have_descriptions()

    # JSON parsing
    test_parse_clean_json()
    test_parse_fenced_json()
    test_parse_enforces_alloydb_iam_transitive()
    test_parse_filters_invalid_components()
    test_parse_adds_supporting_when_missing()
    test_parse_rejects_invalid_json()
    test_parse_rejects_missing_selected()

    # Supporting infra
    test_resolve_supporting_cloud_run()
    test_resolve_supporting_alloydb()
    test_resolve_supporting_empty()
    test_resolve_supporting_full_stack()

    # Prompt building
    test_build_prompt_includes_spec_and_catalog()

    # Static detection
    test_static_cloud_run_only()
    test_static_alloydb_implies_iam()
    test_static_iam_only()
    test_static_full_stack()
    test_static_no_signals()

    # Template selection
    test_template_selection()

    # End-to-end
    test_generate_end_to_end_static()
    test_generate_end_to_end_claude()

    print("\n--- All tests passed ---")
