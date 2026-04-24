#!/usr/bin/env python3
"""
Validate that GCP resources from generated prompts exist.

Checks each resource referenced in the deployment prompts (Cloud Run service,
AlloyDB cluster/instance, Artifact Registry, service account, secrets, etc.)
and reports which ones exist and which are missing.

Usage:
    python3 scripts/validate_resources.py \
        --project-id my-project \
        --region us-central1 \
        --service-name book-journey \
        --cluster-name book-journey-cluster \
        --instance-name book-journey-primary

    # With config file:
    python3 scripts/validate_resources.py --config resources.env

    # Auto-detect components from decision file:
    python3 scripts/validate_resources.py --config resources.env \
        --components-json examples/book-journey/selected-components.json
"""

from __future__ import annotations

import argparse
import sys

from gcp_resource_config import (
    add_common_args,
    detect_components,
    load_components_json,
    resolve_args,
    run_gcloud,
)


def build_checks(args: argparse.Namespace, components: set[str]) -> list[tuple[str, list[str]]]:
    """Build a list of (description, gcloud_command) pairs to validate."""
    checks: list[tuple[str, list[str]]] = []
    p = args.project_id
    r = args.region

    # --- Cloud Run ---
    if "cloud_run" in components and args.service_name:
        checks.append((
            f"Cloud Run service '{args.service_name}'",
            ["gcloud", "run", "services", "describe", args.service_name,
             f"--region={r}", f"--project={p}", "--format=value(status.url)"],
        ))
        checks.append((
            f"Artifact Registry repo '{args.repo_name}'",
            ["gcloud", "artifacts", "repositories", "describe", args.repo_name,
             f"--location={r}", f"--project={p}", "--format=value(name)"],
        ))

    # --- IAM ---
    if "iam" in components and args.sa_email:
        checks.append((
            f"Service account '{args.sa_name}'",
            ["gcloud", "iam", "service-accounts", "describe", args.sa_email,
             f"--project={p}", "--format=value(email)"],
        ))

    # --- AlloyDB ---
    if "alloydb" in components:
        if args.cluster_name:
            checks.append((
                f"AlloyDB cluster '{args.cluster_name}'",
                ["gcloud", "alloydb", "clusters", "describe", args.cluster_name,
                 f"--region={r}", f"--project={p}", "--format=value(name)"],
            ))
        if args.instance_name and args.cluster_name:
            checks.append((
                f"AlloyDB instance '{args.instance_name}'",
                ["gcloud", "alloydb", "instances", "describe", args.instance_name,
                 f"--cluster={args.cluster_name}", f"--region={r}",
                 f"--project={p}", "--format=value(name)"],
            ))
        if args.network_name and args.network_name != "default":
            checks.append((
                f"VPC network '{args.network_name}'",
                ["gcloud", "compute", "networks", "describe", args.network_name,
                 f"--project={p}", "--format=value(name)"],
            ))
        checks.append((
            "PSA range 'alloydb-psa-range'",
            ["gcloud", "compute", "addresses", "describe", "alloydb-psa-range",
             "--global", f"--project={p}", "--format=value(name)"],
        ))
        if args.secret_name:
            checks.append((
                f"Secret '{args.secret_name}'",
                ["gcloud", "secrets", "describe", args.secret_name,
                 f"--project={p}", "--format=value(name)"],
            ))

    return checks


def validate(args: argparse.Namespace, components: set[str]) -> bool:
    """Run all checks and print results. Returns True if all pass."""
    checks = build_checks(args, components)
    if not checks:
        print("No resources to validate. Provide --service-name and/or --cluster-name.")
        return False

    print(f"Validating {len(checks)} resources in project '{args.project_id}'...\n")

    passed = 0
    failed = 0
    results: list[tuple[str, bool, str]] = []

    for desc, cmd in checks:
        ok, output = run_gcloud(cmd)
        results.append((desc, ok, output))
        if ok:
            passed += 1
        else:
            failed += 1

    # Print results table
    max_desc = max(len(r[0]) for r in results)
    for desc, ok, output in results:
        status = "FOUND" if ok else "MISSING"
        marker = "+" if ok else "-"
        detail = ""
        if ok and output:
            detail = f"  ({output})"
        elif not ok and output:
            detail = f"  ({output[:80]})"
        print(f"  [{marker}] {desc:<{max_desc}}{detail}")

    print(f"\n{passed}/{len(checks)} resources found", end="")
    if failed:
        print(f", {failed} missing")
    else:
        print(" - all resources exist")

    return failed == 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate GCP resources from generated deployment prompts."
    )
    add_common_args(parser)
    args = resolve_args(parser)

    if args.components_json:
        components = load_components_json(args.components_json)
    else:
        components = detect_components(args)

    success = validate(args, components)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
