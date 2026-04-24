"""Shared configuration and utilities for GCP resource validation and cleanup."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def parse_config_file(path: str) -> dict[str, str]:
    """Parse a KEY=VALUE config file, ignoring comments and blank lines."""
    config: dict[str, str] = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                value = value.strip().strip('"').strip("'")
                config[key.strip()] = value
    return config


def load_components_json(path: str) -> set[str]:
    """Load selected components from a decision JSON file."""
    with open(path) as f:
        data = json.load(f)
    return set(data.get("selected", []))


def detect_components(args: argparse.Namespace) -> set[str]:
    """Infer active components from provided CLI arguments."""
    components: set[str] = set()
    if args.service_name:
        components.add("cloud_run")
    if args.cluster_name:
        components.add("alloydb")
    if components:
        components.add("iam")
    return components


def derive_defaults(args: argparse.Namespace) -> None:
    """Fill in derived resource names from provided arguments."""
    if args.service_name:
        if not args.repo_name:
            args.repo_name = args.service_name
        if not args.secret_name and args.cluster_name:
            args.secret_name = f"{args.service_name}-db-pass"
        if not args.sa_name:
            args.sa_name = f"{args.service_name}-sa"
    if args.sa_name and args.project_id:
        args.sa_email = f"{args.sa_name}@{args.project_id}.iam.gserviceaccount.com"
    else:
        args.sa_email = None


def add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add shared CLI arguments for resource identification."""
    parser.add_argument("--project-id", help="GCP project ID")
    parser.add_argument("--region", default="us-central1", help="GCP region (default: us-central1)")
    parser.add_argument("--service-name", help="Cloud Run service name")
    parser.add_argument("--cluster-name", help="AlloyDB cluster name")
    parser.add_argument("--instance-name", help="AlloyDB primary instance name")
    parser.add_argument("--network-name", help="VPC network name")
    parser.add_argument("--repo-name", help="Artifact Registry repo (defaults to service-name)")
    parser.add_argument("--secret-name", help="Secret Manager secret (defaults to {service-name}-db-pass)")
    parser.add_argument("--sa-name", help="Service account name (defaults to {service-name}-sa)")
    parser.add_argument("--config", help="Path to KEY=VALUE config file")
    parser.add_argument("--components-json", help="Path to selected-components.json")


def resolve_args(parser: argparse.ArgumentParser) -> argparse.Namespace:
    """Parse CLI args, merge config file values, derive defaults."""
    args = parser.parse_args()

    if args.config:
        config = parse_config_file(args.config)
        mapping = {
            "PROJECT_ID": "project_id",
            "REGION": "region",
            "SERVICE_NAME": "service_name",
            "CLUSTER_NAME": "cluster_name",
            "INSTANCE_NAME": "instance_name",
            "NETWORK_NAME": "network_name",
            "REPO_NAME": "repo_name",
            "SECRET_NAME": "secret_name",
            "SA_NAME": "sa_name",
        }
        for env_key, attr in mapping.items():
            if env_key in config and not getattr(args, attr, None):
                setattr(args, attr, config[env_key])

    if not args.project_id:
        parser.error("--project-id is required (or PROJECT_ID in config file)")

    derive_defaults(args)
    return args


def run_gcloud(cmd: list[str], quiet: bool = True) -> tuple[bool, str]:
    """Run a gcloud command. Returns (success, output_or_error)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "command timed out"
    except FileNotFoundError:
        return False, "gcloud CLI not found"
