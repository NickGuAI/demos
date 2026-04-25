#!/usr/bin/env python3
"""
Global GCP resource scanner for isolated projects.

Discovers all resources in a GCP project by type — no resource names needed.
Designed for isolated projects where everything found can be inventoried or
cleaned up.

Usage:
    # Scan all resources:
    python3 scripts/scan_project_resources.py --project-id my-project --region us-central1

    # Cleanup (dry-run by default):
    python3 scripts/scan_project_resources.py --project-id my-project --region us-central1 --cleanup

    # Actually delete:
    python3 scripts/scan_project_resources.py --project-id my-project --region us-central1 --cleanup --confirm
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def _run_gcloud(cmd: list[str]) -> tuple[bool, str]:
    """Run a gcloud command. Returns (success, stdout)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.returncode == 0, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "command timed out"
    except FileNotFoundError:
        return False, "gcloud CLI not found"


def _list_resources(cmd: list[str]) -> list[str]:
    """Run a gcloud list command, return list of resource names/identifiers."""
    ok, output = _run_gcloud(cmd)
    if ok and output:
        return [line.strip() for line in output.splitlines() if line.strip()]
    return []


# ---------------------------------------------------------------------------
# Resource type definitions, ordered by cleanup dependency.
# ---------------------------------------------------------------------------

# Each entry: (label, list_cmd_builder, delete_cmd_builder)
# Builders take (project_id, region) and return gcloud arg lists.
# AlloyDB is handled separately due to instance-per-cluster nesting.

RESOURCE_TYPES = [
    (
        "Cloud Run services",
        lambda p, r: [
            "gcloud", "run", "services", "list",
            f"--project={p}", f"--region={r}", "--format=value(name)",
        ],
        lambda name, p, r: [
            "gcloud", "run", "services", "delete", name,
            f"--project={p}", f"--region={r}", "--quiet",
        ],
    ),
    (
        "Artifact Registry repos",
        lambda p, r: [
            "gcloud", "artifacts", "repositories", "list",
            f"--project={p}", f"--location={r}", "--format=value(REPOSITORY)",
        ],
        lambda name, p, r: [
            "gcloud", "artifacts", "repositories", "delete", name,
            f"--project={p}", f"--location={r}", "--quiet",
        ],
    ),
    (
        "Secrets",
        lambda p, r: [
            "gcloud", "secrets", "list",
            f"--project={p}", "--format=value(name)",
        ],
        lambda name, p, r: [
            "gcloud", "secrets", "delete", name,
            f"--project={p}", "--quiet",
        ],
    ),
    # AlloyDB is a sentinel — handled by special-case logic below.
    None,  # placeholder for AlloyDB position in cleanup order
    (
        "Service accounts (user-created)",
        lambda p, r: [
            "gcloud", "iam", "service-accounts", "list",
            f"--project={p}", "--format=value(email)",
            "--filter=email!~(developer|appspot|cloudbuild|compute)",
        ],
        lambda name, p, r: [
            "gcloud", "iam", "service-accounts", "delete", name,
            f"--project={p}", "--quiet",
        ],
    ),
    (
        "Compute addresses (PSA)",
        lambda p, r: [
            "gcloud", "compute", "addresses", "list",
            f"--project={p}", "--global", "--format=value(name)",
        ],
        lambda name, p, r: [
            "gcloud", "compute", "addresses", "delete", name,
            f"--project={p}", "--global", "--quiet",
        ],
    ),
    (
        "VPC networks (non-default)",
        lambda p, r: [
            "gcloud", "compute", "networks", "list",
            f"--project={p}", "--format=value(name)", "--filter=name!=default",
        ],
        lambda name, p, r: [
            "gcloud", "compute", "networks", "delete", name,
            f"--project={p}", "--quiet",
        ],
    ),
]


def _discover_alloydb(project_id: str, region: str) -> dict[str, list[str]]:
    """Discover AlloyDB clusters and their instances. Returns {cluster: [instances]}."""
    clusters = _list_resources([
        "gcloud", "alloydb", "clusters", "list",
        f"--project={project_id}", f"--region={region}", "--format=value(name)",
    ])
    result: dict[str, list[str]] = {}
    for cluster in clusters:
        instances = _list_resources([
            "gcloud", "alloydb", "instances", "list",
            f"--project={project_id}", f"--region={region}",
            f"--cluster={cluster}", "--format=value(name)",
        ])
        result[cluster] = instances
    return result


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

def scan(project_id: str, region: str) -> dict[str, list[str]]:
    """Discover all resources in the project. Returns {type_label: [names]}."""
    findings: dict[str, list[str]] = {}

    for entry in RESOURCE_TYPES:
        if entry is None:
            # AlloyDB slot
            alloydb = _discover_alloydb(project_id, region)
            for cluster, instances in alloydb.items():
                findings.setdefault("AlloyDB clusters", []).append(cluster)
                for inst in instances:
                    findings.setdefault("AlloyDB instances", []).append(
                        f"{inst} (cluster: {cluster})"
                    )
            continue
        label, list_cmd, _ = entry
        resources = _list_resources(list_cmd(project_id, region))
        if resources:
            findings[label] = resources

    return findings


def print_scan(findings: dict[str, list[str]]) -> None:
    """Print scan results."""
    if not findings:
        print("  No resources found.")
        return
    total = sum(len(v) for v in findings.values())
    for label, resources in findings.items():
        print(f"  {label} ({len(resources)}):")
        for r in resources:
            print(f"    - {r}")
    print(f"\n  Total: {total} resources")


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def cleanup(project_id: str, region: str, confirm: bool = False) -> bool:
    """Delete all discovered resources in dependency order.

    Returns True if all deletions succeed (or dry-run).
    """
    mode = "DELETING" if confirm else "DRY RUN"
    failed = 0

    for entry in RESOURCE_TYPES:
        if entry is None:
            # AlloyDB: instances first, then clusters
            alloydb = _discover_alloydb(project_id, region)
            if alloydb:
                print("  AlloyDB:")
            for cluster, instances in alloydb.items():
                for inst in instances:
                    ok = _do_delete(
                        f"AlloyDB instance: {inst} (cluster: {cluster})",
                        ["gcloud", "alloydb", "instances", "delete", inst,
                         f"--cluster={cluster}", f"--project={project_id}",
                         f"--region={region}", "--quiet"],
                        confirm,
                    )
                    if not ok:
                        failed += 1
                ok = _do_delete(
                    f"AlloyDB cluster: {cluster}",
                    ["gcloud", "alloydb", "clusters", "delete", cluster,
                     f"--project={project_id}", f"--region={region}", "--quiet"],
                    confirm,
                )
                if not ok:
                    failed += 1
            continue

        label, list_cmd, delete_cmd = entry
        resources = _list_resources(list_cmd(project_id, region))
        if resources:
            print(f"  {label}:")
        for name in resources:
            ok = _do_delete(
                f"{label.rstrip('s')}: {name}",
                delete_cmd(name, project_id, region),
                confirm,
            )
            if not ok:
                failed += 1

    return failed == 0


def _do_delete(label: str, cmd: list[str], confirm: bool) -> bool:
    """Execute or dry-run a single deletion. Returns True on success."""
    if not confirm:
        print(f"    [dry-run] {label}")
        return True
    print(f"    [delete]  {label}...", end=" ", flush=True)
    ok, output = _run_gcloud(cmd)
    print("done" if ok else "FAILED")
    return ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan an isolated GCP project for all deployed resources.",
    )
    parser.add_argument("--project-id", required=True, help="GCP project ID")
    parser.add_argument("--region", default="us-central1", help="GCP region (default: us-central1)")
    parser.add_argument("--cleanup", action="store_true", help="Delete discovered resources")
    parser.add_argument("--confirm", action="store_true", help="Actually delete (default is dry-run)")
    args = parser.parse_args()

    print(f"Scanning project '{args.project_id}' (region: {args.region})...\n")

    if args.cleanup:
        success = cleanup(args.project_id, args.region, confirm=args.confirm)
        if not args.confirm:
            print("\nThis was a dry run. Pass --confirm to actually delete.")
        sys.exit(0 if success else 1)
    else:
        findings = scan(args.project_id, args.region)
        print_scan(findings)


if __name__ == "__main__":
    main()
