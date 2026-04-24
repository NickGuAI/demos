#!/usr/bin/env python3
"""
Clean up GCP resources created from generated deployment prompts.

Deletes resources in reverse dependency order: Cloud Run first, then secrets,
AlloyDB instances/cluster, service accounts, networking last.

Dry-run by default -- pass --confirm to actually delete.

Usage:
    # Dry run (shows what would be deleted):
    python3 scripts/cleanup_resources.py \
        --project-id my-project \
        --service-name book-journey \
        --cluster-name book-journey-cluster \
        --instance-name book-journey-primary

    # Actually delete:
    python3 scripts/cleanup_resources.py --config resources.env --confirm
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


def build_cleanup_steps(
    args: argparse.Namespace, components: set[str]
) -> list[tuple[str, list[str]]]:
    """Build ordered list of (description, gcloud_delete_command) pairs.

    Order: Cloud Run -> Artifact Registry -> Secrets -> AlloyDB instances ->
    AlloyDB cluster -> Service account -> PSA range -> VPC network.
    """
    steps: list[tuple[str, list[str]]] = []
    p = args.project_id
    r = args.region

    # --- Phase 1: Cloud Run service (depends on everything) ---
    if "cloud_run" in components and args.service_name:
        steps.append((
            f"Delete Cloud Run service '{args.service_name}'",
            ["gcloud", "run", "services", "delete", args.service_name,
             f"--region={r}", f"--project={p}", "--quiet"],
        ))

    # --- Phase 2: Artifact Registry ---
    if "cloud_run" in components and args.repo_name:
        steps.append((
            f"Delete Artifact Registry repo '{args.repo_name}'",
            ["gcloud", "artifacts", "repositories", "delete", args.repo_name,
             f"--location={r}", f"--project={p}", "--quiet"],
        ))

    # --- Phase 3: Secrets ---
    if "alloydb" in components and args.secret_name:
        steps.append((
            f"Delete secret '{args.secret_name}'",
            ["gcloud", "secrets", "delete", args.secret_name,
             f"--project={p}", "--quiet"],
        ))

    # --- Phase 4: AlloyDB instance (before cluster) ---
    if "alloydb" in components and args.instance_name and args.cluster_name:
        steps.append((
            f"Delete AlloyDB instance '{args.instance_name}'",
            ["gcloud", "alloydb", "instances", "delete", args.instance_name,
             f"--cluster={args.cluster_name}", f"--region={r}",
             f"--project={p}", "--quiet"],
        ))

    # --- Phase 5: AlloyDB cluster ---
    if "alloydb" in components and args.cluster_name:
        steps.append((
            f"Delete AlloyDB cluster '{args.cluster_name}'",
            ["gcloud", "alloydb", "clusters", "delete", args.cluster_name,
             f"--region={r}", f"--project={p}", "--quiet"],
        ))

    # --- Phase 6: Service account ---
    if "iam" in components and args.sa_email:
        steps.append((
            f"Delete service account '{args.sa_name}'",
            ["gcloud", "iam", "service-accounts", "delete", args.sa_email,
             f"--project={p}", "--quiet"],
        ))

    # --- Phase 7: PSA range ---
    if "alloydb" in components:
        steps.append((
            "Delete PSA range 'alloydb-psa-range'",
            ["gcloud", "compute", "addresses", "delete", "alloydb-psa-range",
             "--global", f"--project={p}", "--quiet"],
        ))

    # --- Phase 8: VPC network (only if non-default) ---
    if "alloydb" in components and args.network_name and args.network_name != "default":
        steps.append((
            f"Delete VPC network '{args.network_name}'",
            ["gcloud", "compute", "networks", "delete", args.network_name,
             f"--project={p}", "--quiet"],
        ))

    return steps


def cleanup(args: argparse.Namespace, components: set[str], confirm: bool) -> bool:
    """Run cleanup steps. Returns True if all succeed (or dry-run)."""
    steps = build_cleanup_steps(args, components)
    if not steps:
        print("No resources to clean up. Provide --service-name and/or --cluster-name.")
        return False

    mode = "DELETING" if confirm else "DRY RUN"
    print(f"[{mode}] {len(steps)} resources in project '{args.project_id}':\n")

    if not confirm:
        for i, (desc, cmd) in enumerate(steps, 1):
            print(f"  {i}. {desc}")
            print(f"     $ {' '.join(cmd)}")
        print(f"\nPass --confirm to execute these {len(steps)} deletions.")
        return True

    succeeded = 0
    failed = 0
    for i, (desc, cmd) in enumerate(steps, 1):
        print(f"  [{i}/{len(steps)}] {desc}...", end=" ", flush=True)
        ok, output = run_gcloud(cmd)
        if ok:
            print("done")
            succeeded += 1
        else:
            print(f"FAILED")
            if output:
                print(f"           {output[:120]}")
            failed += 1

    print(f"\n{succeeded}/{len(steps)} resources deleted", end="")
    if failed:
        print(f", {failed} failed")
    else:
        print(" - cleanup complete")

    return failed == 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean up GCP resources created from deployment prompts."
    )
    add_common_args(parser)
    parser.add_argument(
        "--confirm", action="store_true",
        help="Actually delete resources (default is dry-run)",
    )
    args = resolve_args(parser)

    if args.components_json:
        components = load_components_json(args.components_json)
    else:
        components = detect_components(args)

    success = cleanup(args, components, confirm=args.confirm)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
