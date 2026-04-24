#!/usr/bin/env python3
"""
Tests for validate_resources.py and cleanup_resources.py.

Run:
    python3 -m pytest tests/test_resource_scripts.py -v
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from gcp_resource_config import (
    derive_defaults,
    detect_components,
    load_components_json,
    parse_config_file,
)
from validate_resources import build_checks
from cleanup_resources import build_cleanup_steps


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------

def test_parse_config_file():
    """Config file parses KEY=VALUE pairs, ignoring comments."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write('# GCP config\n')
        f.write('PROJECT_ID="my-project"\n')
        f.write("REGION=us-west1\n")
        f.write("SERVICE_NAME='book-journey'\n")
        f.write("\n")
        f.write("# AlloyDB\n")
        f.write("CLUSTER_NAME=my-cluster\n")
        f.name
    config = parse_config_file(f.name)
    assert config["PROJECT_ID"] == "my-project"
    assert config["REGION"] == "us-west1"
    assert config["SERVICE_NAME"] == "book-journey"
    assert config["CLUSTER_NAME"] == "my-cluster"


def test_parse_config_strips_quotes():
    """Both single and double quotes are stripped from values."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write('A="double"\n')
        f.write("B='single'\n")
        f.write("C=none\n")
    config = parse_config_file(f.name)
    assert config["A"] == "double"
    assert config["B"] == "single"
    assert config["C"] == "none"


# ---------------------------------------------------------------------------
# Components detection
# ---------------------------------------------------------------------------

def test_load_components_json():
    """Components loaded from decision JSON."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"selected": ["cloud_run", "alloydb"], "reasoning": {}}, f)
    components = load_components_json(f.name)
    assert components == {"cloud_run", "alloydb"}


def test_detect_components_cloud_run_only():
    """Service name alone implies cloud_run + iam."""
    args = argparse.Namespace(service_name="my-svc", cluster_name=None)
    assert detect_components(args) == {"cloud_run", "iam"}


def test_detect_components_alloydb():
    """Cluster name implies alloydb + iam."""
    args = argparse.Namespace(service_name=None, cluster_name="my-cluster")
    assert detect_components(args) == {"alloydb", "iam"}


def test_detect_components_full_stack():
    """Both service and cluster implies all three."""
    args = argparse.Namespace(service_name="svc", cluster_name="cluster")
    assert detect_components(args) == {"cloud_run", "alloydb", "iam"}


def test_detect_components_empty():
    """No args means no components."""
    args = argparse.Namespace(service_name=None, cluster_name=None)
    assert detect_components(args) == set()


# ---------------------------------------------------------------------------
# Derive defaults
# ---------------------------------------------------------------------------

def _make_args(**overrides):
    defaults = dict(
        project_id="test-proj",
        region="us-central1",
        service_name=None,
        cluster_name=None,
        instance_name=None,
        network_name=None,
        repo_name=None,
        secret_name=None,
        sa_name=None,
        sa_email=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_derive_defaults_repo_from_service():
    """Repo name defaults to service name."""
    args = _make_args(service_name="my-svc")
    derive_defaults(args)
    assert args.repo_name == "my-svc"


def test_derive_defaults_secret_from_service():
    """Secret name defaults to {service}-db-pass when alloydb present."""
    args = _make_args(service_name="my-svc", cluster_name="my-cluster")
    derive_defaults(args)
    assert args.secret_name == "my-svc-db-pass"


def test_derive_defaults_no_secret_without_cluster():
    """Secret name not derived without a cluster."""
    args = _make_args(service_name="my-svc")
    derive_defaults(args)
    assert args.secret_name is None


def test_derive_defaults_sa_email():
    """SA email derived from sa_name and project_id."""
    args = _make_args(service_name="my-svc")
    derive_defaults(args)
    assert args.sa_name == "my-svc-sa"
    assert args.sa_email == "my-svc-sa@test-proj.iam.gserviceaccount.com"


# ---------------------------------------------------------------------------
# Validate: build_checks
# ---------------------------------------------------------------------------

def test_build_checks_cloud_run():
    """Cloud Run component produces service + repo + SA checks."""
    args = _make_args(service_name="svc")
    derive_defaults(args)
    checks = build_checks(args, {"cloud_run", "iam"})
    descs = [c[0] for c in checks]
    assert any("Cloud Run service" in d for d in descs)
    assert any("Artifact Registry" in d for d in descs)
    assert any("Service account" in d for d in descs)


def test_build_checks_alloydb():
    """AlloyDB component produces cluster + instance + PSA + secret checks."""
    args = _make_args(
        service_name="svc", cluster_name="c1", instance_name="i1",
        network_name="my-vpc",
    )
    derive_defaults(args)
    checks = build_checks(args, {"alloydb", "iam"})
    descs = [c[0] for c in checks]
    assert any("AlloyDB cluster" in d for d in descs)
    assert any("AlloyDB instance" in d for d in descs)
    assert any("VPC network" in d for d in descs)
    assert any("PSA range" in d for d in descs)
    assert any("Secret" in d for d in descs)


def test_build_checks_skips_default_vpc():
    """Default network is not checked (it always exists)."""
    args = _make_args(cluster_name="c1", network_name="default")
    derive_defaults(args)
    checks = build_checks(args, {"alloydb"})
    descs = [c[0] for c in checks]
    assert not any("VPC network" in d for d in descs)


def test_build_checks_empty():
    """No components = no checks."""
    args = _make_args()
    derive_defaults(args)
    assert build_checks(args, set()) == []


def test_build_checks_all_use_project_flag():
    """Every gcloud command includes --project."""
    args = _make_args(
        service_name="svc", cluster_name="c1", instance_name="i1",
    )
    derive_defaults(args)
    checks = build_checks(args, {"cloud_run", "alloydb", "iam"})
    for desc, cmd in checks:
        assert any("--project=" in c for c in cmd), f"Missing --project in: {desc}"


# ---------------------------------------------------------------------------
# Cleanup: build_cleanup_steps
# ---------------------------------------------------------------------------

def test_cleanup_order_full_stack():
    """Full-stack cleanup follows reverse dependency order."""
    args = _make_args(
        service_name="svc", cluster_name="c1", instance_name="i1",
        network_name="my-vpc",
    )
    derive_defaults(args)
    steps = build_cleanup_steps(args, {"cloud_run", "alloydb", "iam"})
    descs = [s[0] for s in steps]

    # Cloud Run must come before AlloyDB
    run_idx = next(i for i, d in enumerate(descs) if "Cloud Run" in d)
    cluster_idx = next(i for i, d in enumerate(descs) if "AlloyDB cluster" in d)
    assert run_idx < cluster_idx

    # AlloyDB instance must come before cluster
    inst_idx = next(i for i, d in enumerate(descs) if "AlloyDB instance" in d)
    assert inst_idx < cluster_idx

    # SA must come after Cloud Run (service uses it)
    sa_idx = next(i for i, d in enumerate(descs) if "service account" in d)
    assert sa_idx > run_idx

    # VPC must come last (everything depends on it)
    vpc_idx = next(i for i, d in enumerate(descs) if "VPC network" in d)
    assert vpc_idx == len(descs) - 1


def test_cleanup_skips_default_vpc():
    """Default network is never deleted."""
    args = _make_args(
        service_name="svc", cluster_name="c1", network_name="default",
    )
    derive_defaults(args)
    steps = build_cleanup_steps(args, {"cloud_run", "alloydb", "iam"})
    descs = [s[0] for s in steps]
    assert not any("VPC network" in d for d in descs)


def test_cleanup_all_use_quiet_flag():
    """Every delete command includes --quiet to skip confirmation."""
    args = _make_args(
        service_name="svc", cluster_name="c1", instance_name="i1",
    )
    derive_defaults(args)
    steps = build_cleanup_steps(args, {"cloud_run", "alloydb", "iam"})
    for desc, cmd in steps:
        assert "--quiet" in cmd, f"Missing --quiet in: {desc}"


def test_cleanup_cloud_run_only():
    """Cloud Run only cleanup: service + repo + SA."""
    args = _make_args(service_name="svc")
    derive_defaults(args)
    steps = build_cleanup_steps(args, {"cloud_run", "iam"})
    descs = [s[0] for s in steps]
    assert len(steps) == 3
    assert any("Cloud Run" in d for d in descs)
    assert any("Artifact Registry" in d for d in descs)
    assert any("service account" in d for d in descs)


def test_cleanup_empty():
    """No components = no steps."""
    args = _make_args()
    derive_defaults(args)
    assert build_cleanup_steps(args, set()) == []
