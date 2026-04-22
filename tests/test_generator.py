#!/usr/bin/env python3
"""
Smoke tests for the GCP augmentation prompt generator.

Run:
    python3 -m pytest tests/test_generator.py -v
    # or:
    python3 tests/test_generator.py
"""

import json
import sys
import tempfile
from pathlib import Path

# Add scripts to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from generate_gcp_prompts import load_rules, match_signals, select_template, generate


def test_rules_load():
    """Rules YAML loads without error and has expected structure."""
    rules = load_rules(REPO_ROOT / "rules" / "gcp-component-decision.yaml")
    assert "components" in rules
    assert "cloud_run" in rules["components"]
    assert "iam" in rules["components"]
    assert "alloydb" in rules["components"]
    assert "template_matrix" in rules
    assert "supporting" in rules
    print("PASS: test_rules_load")


def test_cloud_run_only():
    """A spec mentioning only web service signals selects cloud_run."""
    rules = load_rules(REPO_ROOT / "rules" / "gcp-component-decision.yaml")
    spec = "Deploy a simple landing page as a web application."
    result = match_signals(spec, rules)
    assert "cloud_run" in result["selected"]
    assert "alloydb" not in result["selected"]
    print("PASS: test_cloud_run_only")


def test_alloydb_only():
    """A spec mentioning only database signals selects alloydb (+ transitive iam)."""
    rules = load_rules(REPO_ROOT / "rules" / "gcp-component-decision.yaml")
    spec = "Set up a PostgreSQL database for storing analytics data."
    result = match_signals(spec, rules)
    assert "alloydb" in result["selected"]
    # AlloyDB transitively requires IAM
    assert "iam" in result["selected"]
    assert "iam" in result["transitive"]
    print("PASS: test_alloydb_only")


def test_iam_only():
    """A spec mentioning only IAM signals selects iam."""
    rules = load_rules(REPO_ROOT / "rules" / "gcp-component-decision.yaml")
    spec = "Configure IAM roles and service accounts for the data pipeline."
    result = match_signals(spec, rules)
    assert "iam" in result["selected"]
    print("PASS: test_iam_only")


def test_full_stack():
    """Book Journey spec selects all three components."""
    rules = load_rules(REPO_ROOT / "rules" / "gcp-component-decision.yaml")
    spec = (REPO_ROOT / "examples" / "book-journey" / "project.md").read_text()
    result = match_signals(spec, rules)
    assert "cloud_run" in result["selected"], f"Expected cloud_run, got {result['selected']}"
    assert "alloydb" in result["selected"], f"Expected alloydb, got {result['selected']}"
    assert "iam" in result["selected"], f"Expected iam, got {result['selected']}"
    print("PASS: test_full_stack")


def test_template_selection():
    """Template matrix returns correct templates for component combinations."""
    rules = load_rules(REPO_ROOT / "rules" / "gcp-component-decision.yaml")
    assert select_template(["cloud_run"], rules) == "cloud-run.md"
    assert select_template(["iam"], rules) == "iam.md"
    assert select_template(["alloydb"], rules) == "alloydb.md"
    assert select_template(["cloud_run", "iam"], rules) == "cloud-run-iam.md"
    assert select_template(["alloydb", "cloud_run"], rules) == "cloud-run-alloydb.md"
    assert select_template(["alloydb", "cloud_run", "iam"], rules) == "cloud-run-iam-alloydb.md"
    print("PASS: test_template_selection")


def test_supporting_infra():
    """Supporting infra is resolved correctly."""
    rules = load_rules(REPO_ROOT / "rules" / "gcp-component-decision.yaml")
    spec = (REPO_ROOT / "examples" / "book-journey" / "project.md").read_text()
    result = match_signals(spec, rules)
    assert "service_account" in result["supporting"]
    assert "vpc_network" in result["supporting"]
    assert "secret_manager" in result["supporting"]
    assert "artifact_registry" in result["supporting"]
    print("PASS: test_supporting_infra")


def test_generate_end_to_end():
    """Full generate pipeline produces files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_path = REPO_ROOT / "examples" / "book-journey" / "project.md"
        output_dir = Path(tmpdir) / "bundle"
        decision = generate(str(spec_path), str(output_dir), emit_decision=True)

        # Check decision
        assert len(decision["selected"]) >= 3

        # Check prompt files were written
        files = list(output_dir.glob("*.md"))
        assert len(files) >= 3, f"Expected at least 3 prompt files, got {len(files)}: {[f.name for f in files]}"

        # Check decision JSON was written
        decision_file = Path(tmpdir) / "selected-components.json"
        assert decision_file.exists(), "Decision JSON not written"
        data = json.loads(decision_file.read_text())
        assert "selected" in data

        # Check that rendered templates contain the project spec
        for f in files:
            content = f.read_text()
            assert "Book Journey" in content, f"{f.name} should contain project spec"

        print("PASS: test_generate_end_to_end")


def test_no_signals():
    """A spec with no matching signals produces empty selection."""
    rules = load_rules(REPO_ROOT / "rules" / "gcp-component-decision.yaml")
    spec = "Paint the fence blue."
    result = match_signals(spec, rules)
    assert len(result["selected"]) == 0
    print("PASS: test_no_signals")


def test_match_context_captured():
    """Signal matches include context from the spec."""
    rules = load_rules(REPO_ROOT / "rules" / "gcp-component-decision.yaml")
    spec = "Build a REST API for managing inventory."
    result = match_signals(spec, rules)
    assert "cloud_run" in result["selected"]
    # Check that at least one match has context
    cr_matches = result["matches"]["cloud_run"]
    contexts = [m["context"] for m in cr_matches if m["context"]]
    assert len(contexts) > 0, "Should capture context for matches"
    print("PASS: test_match_context_captured")


if __name__ == "__main__":
    test_rules_load()
    test_cloud_run_only()
    test_alloydb_only()
    test_iam_only()
    test_full_stack()
    test_template_selection()
    test_supporting_infra()
    test_generate_end_to_end()
    test_no_signals()
    test_match_context_captured()
    print("\n--- All tests passed ---")
