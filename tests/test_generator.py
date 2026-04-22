#!/usr/bin/env python3
"""
Tests for the GCP augmentation prompt generator.

Run:
    python3 -m pytest tests/test_generator.py -v
    # or:
    python3 tests/test_generator.py

Tests use injected fakes for the claude CLI so they do not require the
`claude` binary to be installed. This is the guardrail that prevents silent
degradation to keyword matching from returning — there is no static path
to fall back to.
"""

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from generate_gcp_prompts import (
    ClaudeCliMissingError,
    build_decision_prompt,
    detect_components,
    generate,
    load_catalog,
    parse_decision_json,
    resolve_supporting,
    select_template,
)


def make_fake_claude(response: str):
    """Return a stand-in for call_claude that yields a fixed response."""
    def fake(prompt: str) -> str:
        return response
    return fake


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
# detect_components with injected fake claude
# ---------------------------------------------------------------------------

def test_detect_components_uses_injected_caller():
    """detect_components wires the fake response through to the result."""
    fake = make_fake_claude(json.dumps({
        "selected": ["cloud_run", "alloydb", "iam"],
        "reasoning": {
            "cloud_run": "HTTP service",
            "alloydb": "relational data",
            "iam": "service account",
        },
    }))
    catalog = load_catalog()
    decision = detect_components("A web app with PostgreSQL.", catalog, claude_caller=fake)
    assert decision["selected"] == ["alloydb", "cloud_run", "iam"]
    assert decision["method"] == "claude"
    print("PASS: test_detect_components_uses_injected_caller")


def test_detect_components_propagates_claude_errors():
    """If claude_caller raises, detect_components lets the exception propagate —
    no silent degradation to keyword matching."""
    def broken_caller(prompt: str) -> str:
        raise RuntimeError("claude is down")

    catalog = load_catalog()
    try:
        detect_components("irrelevant spec", catalog, claude_caller=broken_caller)
        assert False, "Should have raised"
    except RuntimeError as e:
        assert "claude is down" in str(e)
    print("PASS: test_detect_components_propagates_claude_errors")


# ---------------------------------------------------------------------------
# Template selection
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
# Guardrail: the static fallback must stay removed
# ---------------------------------------------------------------------------

def test_no_static_fallback_symbols():
    """Regression guard: the script must not re-introduce keyword matching.

    Deleted in chore/remove-static-fallback after the a118aa2 refactor. If
    anyone resurrects STATIC_SIGNALS, detect_components_static, or a
    --static flag, this test fails so we notice before silent-degradation
    behavior ships.
    """
    import generate_gcp_prompts as mod
    for forbidden in ("STATIC_SIGNALS", "detect_components_static"):
        assert not hasattr(mod, forbidden), (
            f"{forbidden} must stay removed — claude is the only detection path. "
            f"If you need offline testing, mock call_claude via the claude_caller "
            f"argument as test_detect_components_uses_injected_caller does."
        )

    script_src = (REPO_ROOT / "scripts" / "generate_gcp_prompts.py").read_text()
    assert "--static" not in script_src, (
        "--static CLI flag must stay removed — there is no static path."
    )
    print("PASS: test_no_static_fallback_symbols")


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------

def test_generate_end_to_end_with_fake_claude():
    """Full pipeline with an injected fake claude caller produces files."""
    fake_response = json.dumps({
        "selected": ["alloydb", "cloud_run", "iam"],
        "reasoning": {
            "cloud_run": "multi-user web app serving HTTP",
            "iam": "service account connectivity for AlloyDB",
            "alloydb": "relational storage for users and checkpoints",
        },
        "supporting": ["artifact_registry", "secret_manager", "service_account", "vpc_network"],
    })

    with tempfile.TemporaryDirectory() as tmpdir:
        spec_path = REPO_ROOT / "examples" / "book-journey" / "project.md"
        output_dir = Path(tmpdir) / "bundle"
        decision = generate(
            str(spec_path),
            str(output_dir),
            emit_decision=True,
            claude_caller=make_fake_claude(fake_response),
        )

        assert decision["method"] == "claude"
        assert decision["selected"] == ["alloydb", "cloud_run", "iam"]

        # Prompt files written
        files = list(output_dir.glob("*.md"))
        assert len(files) >= 3, f"Expected >=3 prompt files, got {len(files)}"

        # Decision JSON written (no raw_response in the on-disk file)
        decision_file = Path(tmpdir) / "selected-components.json"
        assert decision_file.exists()
        data = json.loads(decision_file.read_text())
        assert data["method"] == "claude"
        assert "raw_response" not in data

        # Templates contain project spec
        for f in files:
            content = f.read_text()
            assert "Book Journey" in content, f"{f.name} missing project spec"

        print("PASS: test_generate_end_to_end_with_fake_claude")


def test_claude_cli_missing_raises():
    """If the real call_claude runs without the binary on PATH, ClaudeCliMissingError."""
    from generate_gcp_prompts import call_claude
    import shutil as _shutil

    original_which = _shutil.which
    _shutil.which = lambda name: None  # pretend claude is not installed
    try:
        try:
            call_claude("noop")
            assert False, "Should have raised ClaudeCliMissingError"
        except ClaudeCliMissingError as e:
            assert "claude" in str(e).lower()
    finally:
        _shutil.which = original_which
    print("PASS: test_claude_cli_missing_raises")


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

    # detect_components with injected fake claude
    test_detect_components_uses_injected_caller()
    test_detect_components_propagates_claude_errors()

    # Template selection
    test_template_selection()

    # Guardrail
    test_no_static_fallback_symbols()

    # End-to-end
    test_generate_end_to_end_with_fake_claude()
    test_claude_cli_missing_raises()

    print("\n--- All tests passed ---")
