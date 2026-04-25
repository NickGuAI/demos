#!/usr/bin/env python3
"""
Tests for dynamic resource script generation and the global scanner.

Run:
    python3 -m pytest tests/test_resource_scripts.py -v
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from generate_gcp_prompts import (
    generate_cleanup_script,
    generate_validate_script,
    generate,
    _select_sections,
    _VALIDATE_SECTIONS,
    _CLEANUP_SECTIONS,
)
from scan_project_resources import RESOURCE_TYPES, _discover_alloydb, scan


def make_fake_claude(response: str):
    def fake(prompt: str) -> str:
        return response
    return fake


# ---------------------------------------------------------------------------
# _select_sections
# ---------------------------------------------------------------------------

def test_select_sections_matches_gates():
    """Sections are included when any gate name matches active components."""
    sections = [
        (("cloud_run",), "CLOUD_RUN"),
        (("alloydb",), "ALLOYDB"),
        (("service_account", "iam"), "SA"),
    ]
    result = _select_sections(sections, ["cloud_run"], ["service_account"])
    assert result == ["CLOUD_RUN", "SA"]


def test_select_sections_empty_active():
    """No active components = no sections."""
    assert _select_sections(_VALIDATE_SECTIONS, [], []) == []


def test_select_sections_full_stack():
    """Full stack activates all sections."""
    result = _select_sections(
        _VALIDATE_SECTIONS,
        ["cloud_run", "iam", "alloydb"],
        ["artifact_registry", "vpc_network", "service_account", "secret_manager"],
    )
    assert len(result) == len(_VALIDATE_SECTIONS)


# ---------------------------------------------------------------------------
# generate_validate_script
# ---------------------------------------------------------------------------

def test_validate_script_header():
    """Validate script has shebang, component list, and usage."""
    script = generate_validate_script(["cloud_run"], ["artifact_registry", "service_account"])
    assert script.startswith("#!/usr/bin/env bash")
    assert "cloud_run" in script
    assert "artifact_registry" in script
    assert "$PROJECT_ID" in script
    assert "$REGION" in script


def test_validate_script_cloud_run_sections():
    """Cloud Run selection includes Cloud Run + Artifact Registry + SA sections."""
    script = generate_validate_script(
        ["cloud_run", "iam"],
        ["artifact_registry", "service_account"],
    )
    assert "Cloud Run Services" in script
    assert "Artifact Registry" in script
    assert "Service Accounts" in script
    assert "AlloyDB" not in script
    assert "Secrets" not in script


def test_validate_script_alloydb_sections():
    """AlloyDB selection includes AlloyDB + Secrets + VPC sections."""
    script = generate_validate_script(
        ["alloydb", "iam"],
        ["vpc_network", "service_account", "secret_manager"],
    )
    assert "AlloyDB Clusters" in script
    assert "Secrets" in script
    assert "VPC Networks" in script
    assert "Compute Addresses" in script
    assert "Cloud Run" not in script


def test_validate_script_full_stack():
    """Full stack includes all sections."""
    script = generate_validate_script(
        ["cloud_run", "iam", "alloydb"],
        ["artifact_registry", "vpc_network", "service_account", "secret_manager"],
    )
    assert "Cloud Run" in script
    assert "Artifact Registry" in script
    assert "Service Accounts" in script
    assert "AlloyDB" in script
    assert "Secrets" in script
    assert "VPC Networks" in script


def test_validate_script_uses_gcloud_list():
    """All resource discovery uses gcloud list, not describe."""
    script = generate_validate_script(
        ["cloud_run", "iam", "alloydb"],
        ["artifact_registry", "vpc_network", "service_account", "secret_manager"],
    )
    assert "gcloud run services list" in script
    assert "gcloud alloydb clusters list" in script
    assert "gcloud secrets list" in script
    assert " describe " not in script


# ---------------------------------------------------------------------------
# generate_cleanup_script
# ---------------------------------------------------------------------------

def test_cleanup_script_header():
    """Cleanup script has shebang, DRY_RUN support, and delete helper."""
    script = generate_cleanup_script(["cloud_run"], ["artifact_registry", "service_account"])
    assert script.startswith("#!/usr/bin/env bash")
    assert "DRY_RUN" in script
    assert "delete()" in script
    assert "dry-run" in script


def test_cleanup_script_order():
    """Full-stack cleanup deletes in dependency order."""
    script = generate_cleanup_script(
        ["cloud_run", "iam", "alloydb"],
        ["artifact_registry", "vpc_network", "service_account", "secret_manager"],
    )
    # Extract section headers to verify order
    lines = script.splitlines()
    section_lines = [l for l in lines if l.startswith("echo \"---")]
    labels = [l.split('"')[1].strip("--- ") for l in section_lines]

    # Cloud Run before AlloyDB
    assert labels.index("Cloud Run Services") < labels.index("AlloyDB")
    # Secrets before AlloyDB
    assert labels.index("Secrets") < labels.index("AlloyDB")
    # AlloyDB before Service Accounts
    assert labels.index("AlloyDB") < labels.index("Service Accounts")
    # Service Accounts before VPC Networks
    sa_idx = labels.index("Service Accounts")
    vpc_idx = labels.index("VPC Networks (non-default)")
    assert sa_idx < vpc_idx


def test_cleanup_script_uses_quiet():
    """All delete commands use --quiet flag."""
    script = generate_cleanup_script(
        ["cloud_run", "iam", "alloydb"],
        ["artifact_registry", "vpc_network", "service_account", "secret_manager"],
    )
    # Every "delete" gcloud line should have --quiet
    for line in script.splitlines():
        if "gcloud" in line and "delete" in line:
            assert "--quiet" in line, f"Missing --quiet: {line.strip()}"


def test_cleanup_script_dry_run_footer():
    """Cleanup script reminds about dry-run mode."""
    script = generate_cleanup_script(["cloud_run"], ["service_account"])
    assert 'DRY_RUN=false' in script


def test_cleanup_alloydb_instances_before_clusters():
    """AlloyDB cleanup deletes instances before clusters (nested loop)."""
    script = generate_cleanup_script(
        ["alloydb", "iam"],
        ["vpc_network", "service_account", "secret_manager"],
    )
    inst_pos = script.index("alloydb instances delete")
    cluster_pos = script.index("alloydb clusters delete")
    assert inst_pos < cluster_pos


def test_cleanup_vpc_addresses_before_networks():
    """PSA addresses are deleted before VPC networks."""
    script = generate_cleanup_script(
        ["alloydb", "iam"],
        ["vpc_network", "service_account", "secret_manager"],
    )
    addr_pos = script.index("Compute Addresses")
    net_pos = script.index("VPC Networks")
    assert addr_pos < net_pos


# ---------------------------------------------------------------------------
# End-to-end: generate() emits scripts
# ---------------------------------------------------------------------------

def test_generate_emits_validate_and_cleanup():
    """The generator pipeline produces validate.sh and cleanup.sh in the bundle."""
    fake_response = json.dumps({
        "selected": ["cloud_run", "iam"],
        "reasoning": {"cloud_run": "web app", "iam": "SA needed", "alloydb": None},
        "supporting": ["artifact_registry", "service_account"],
    })

    with tempfile.TemporaryDirectory() as tmpdir:
        spec_path = REPO_ROOT / "examples" / "book-journey" / "project.md"
        output_dir = Path(tmpdir) / "bundle"
        generate(
            str(spec_path),
            str(output_dir),
            claude_caller=make_fake_claude(fake_response),
        )

        validate_sh = output_dir / "validate.sh"
        cleanup_sh = output_dir / "cleanup.sh"
        assert validate_sh.exists(), "validate.sh not generated"
        assert cleanup_sh.exists(), "cleanup.sh not generated"

        # validate.sh content matches components
        v_content = validate_sh.read_text()
        assert "Cloud Run" in v_content
        assert "AlloyDB" not in v_content  # not selected

        # cleanup.sh content matches components
        c_content = cleanup_sh.read_text()
        assert "Cloud Run" in c_content
        assert "DRY_RUN" in c_content


def test_generate_full_stack_scripts():
    """Full-stack generation produces scripts with all sections."""
    fake_response = json.dumps({
        "selected": ["alloydb", "cloud_run", "iam"],
        "reasoning": {
            "cloud_run": "HTTP", "iam": "SA", "alloydb": "DB",
        },
        "supporting": ["artifact_registry", "secret_manager", "service_account", "vpc_network"],
    })

    with tempfile.TemporaryDirectory() as tmpdir:
        spec_path = REPO_ROOT / "examples" / "book-journey" / "project.md"
        output_dir = Path(tmpdir) / "bundle"
        generate(
            str(spec_path),
            str(output_dir),
            claude_caller=make_fake_claude(fake_response),
        )

        v_content = (output_dir / "validate.sh").read_text()
        c_content = (output_dir / "cleanup.sh").read_text()
        for keyword in ["Cloud Run", "AlloyDB", "Secrets", "VPC Networks"]:
            assert keyword in v_content, f"validate.sh missing {keyword}"
            assert keyword in c_content, f"cleanup.sh missing {keyword}"


# ---------------------------------------------------------------------------
# Global scanner: structure
# ---------------------------------------------------------------------------

def test_scanner_resource_types_ordered():
    """Scanner resource types are in cleanup-dependency order."""
    labels = [r[0] if r else "AlloyDB" for r in RESOURCE_TYPES]
    assert labels.index("Cloud Run services") < labels.index("AlloyDB")
    assert labels.index("Secrets") < labels.index("AlloyDB")
    assert labels.index("AlloyDB") < labels.index("Service accounts (user-created)")
    assert labels.index("Service accounts (user-created)") < labels.index("Compute addresses (PSA)")
    assert labels.index("Compute addresses (PSA)") < labels.index("VPC networks (non-default)")


def test_scanner_resource_types_have_delete():
    """Every non-AlloyDB resource type has list and delete builders."""
    for entry in RESOURCE_TYPES:
        if entry is None:
            continue
        label, list_fn, delete_fn = entry
        # Verify callables produce lists
        list_cmd = list_fn("test-project", "us-central1")
        assert isinstance(list_cmd, list)
        assert "gcloud" in list_cmd[0]
        delete_cmd = delete_fn("my-resource", "test-project", "us-central1")
        assert isinstance(delete_cmd, list)
        assert "--quiet" in delete_cmd


def test_scanner_sa_filter_excludes_system():
    """Service account listing filters out GCP-managed accounts."""
    sa_entry = [r for r in RESOURCE_TYPES if r and "Service account" in r[0]][0]
    list_cmd = sa_entry[1]("test-project", "us-central1")
    cmd_str = " ".join(list_cmd)
    assert "developer" in cmd_str
    assert "appspot" in cmd_str
    assert "cloudbuild" in cmd_str
    assert "compute" in cmd_str


def test_scanner_vpc_filter_excludes_default():
    """VPC listing filters out the default network."""
    vpc_entry = [r for r in RESOURCE_TYPES if r and "VPC" in r[0]][0]
    list_cmd = vpc_entry[1]("test-project", "us-central1")
    cmd_str = " ".join(list_cmd)
    assert "name!=default" in cmd_str
