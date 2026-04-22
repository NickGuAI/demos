#!/usr/bin/env python3
"""
GCP Augmentation Prompt Generator (model-driven)

Takes a project spec (markdown) and:
1. Sends it to `claude -p` along with the GCP component catalog
2. Claude analyzes the spec and returns structured JSON with selected components
3. Renders the matching prompt templates for those components

Usage:
    python3 scripts/generate_gcp_prompts.py examples/book-journey/project.md

    # Custom output directory:
    python3 scripts/generate_gcp_prompts.py spec.md --output-dir ./my-output

    # Also emit the decision JSON:
    python3 scripts/generate_gcp_prompts.py spec.md --emit-decision

    # Use static fallback (skip claude, keyword matching only):
    python3 scripts/generate_gcp_prompts.py spec.md --static
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = REPO_ROOT / "rules" / "gcp-component-decision.yaml"
TEMPLATES_DIR = REPO_ROOT / "prompts" / "templates"
RESEARCH_DIR = REPO_ROOT / "research" / "gcp"

VALID_COMPONENTS = {"cloud_run", "iam", "alloydb"}

# ---------------------------------------------------------------------------
# Catalog loading
# ---------------------------------------------------------------------------

def load_catalog(catalog_path: Path = CATALOG_PATH) -> dict:
    """Load the component catalog YAML."""
    with open(catalog_path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Model-driven component selection via `claude -p`
# ---------------------------------------------------------------------------

DECISION_SYSTEM_PROMPT = """\
You are a GCP infrastructure analyst. Given a project specification and a \
catalog of available GCP components, determine which components the project \
needs for deployment.

Respond with ONLY a JSON object (no markdown fencing, no commentary) matching \
this exact schema:

{
  "selected": ["cloud_run", "iam", "alloydb"],
  "reasoning": {
    "cloud_run": "one sentence why selected or null if not",
    "iam": "one sentence why selected or null if not",
    "alloydb": "one sentence why selected or null if not"
  },
  "supporting": ["artifact_registry", "vpc_network", "service_account", "secret_manager"]
}

Rules:
- "selected" contains only the components the project actually needs.
  Valid values: cloud_run, iam, alloydb
- "reasoning" has an entry for every component — explain why it's needed or \
  set to null if it's not.
- "supporting" lists transitive infrastructure required by the selected \
  components (artifact_registry for cloud_run, vpc_network + secret_manager \
  for alloydb, service_account whenever any component is selected).
- If alloydb is selected, iam must also be selected (AlloyDB requires IAM \
  for service account connectivity).
- Do NOT select components the project doesn't need. A static site with no \
  database does not need alloydb. A pure database setup does not need cloud_run.
"""


def build_decision_prompt(spec_text: str, catalog: dict) -> str:
    """Build the prompt that asks Claude to analyze the spec.

    Embeds the system instructions directly in the prompt since
    `claude -p` does not support a separate --system flag.
    """
    catalog_section = yaml.dump(
        {"components": catalog.get("components", {}),
         "supporting": catalog.get("supporting", {})},
        default_flow_style=False,
    )

    return f"""\
{DECISION_SYSTEM_PROMPT}

---

## GCP Component Catalog

{catalog_section}

## Project Specification

{spec_text}

## Task

Analyze the project specification above against the GCP component catalog. \
Determine which components are needed. Respond with ONLY the JSON object, \
nothing else."""


def call_claude(prompt: str) -> str:
    """Call `claude -p` and return stdout."""
    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude -p failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


def resolve_supporting(selected: list[str]) -> list[str]:
    """Derive supporting infra from selected components."""
    supporting = set()
    if selected:
        supporting.add("service_account")
    if "cloud_run" in selected:
        supporting.add("artifact_registry")
    if "alloydb" in selected:
        supporting.update(["vpc_network", "secret_manager"])
    return sorted(supporting)


def _validate_decision(data: dict) -> dict:
    """Validate and normalize a parsed decision dict."""
    if "selected" not in data or not isinstance(data["selected"], list):
        raise ValueError("Missing or invalid 'selected' field in Claude response")

    # Normalize: only keep valid component names
    data["selected"] = sorted(
        c for c in data["selected"] if c in VALID_COMPONENTS
    )

    # Enforce transitive: alloydb requires iam
    if "alloydb" in data["selected"] and "iam" not in data["selected"]:
        data["selected"] = sorted(data["selected"] + ["iam"])
        if "reasoning" in data:
            data["reasoning"]["iam"] = "Required transitively by alloydb for service account connectivity."

    # Ensure supporting is present
    if "supporting" not in data:
        data["supporting"] = resolve_supporting(data["selected"])

    return data


def parse_decision_json(raw: str) -> dict:
    """Parse Claude's JSON response, extracting the JSON object robustly.

    Handles: bare JSON, markdown-fenced JSON, JSON with surrounding prose.
    """
    # Strategy 1: try to find a ```json ... ``` fenced block
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
    if fence_match:
        candidate = fence_match.group(1).strip()
        try:
            data = json.loads(candidate)
            return _validate_decision(data)
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 2: find the first { ... } block with balanced braces
    start = raw.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(raw)):
            if raw[i] == "{":
                depth += 1
            elif raw[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = raw[start : i + 1]
                    try:
                        data = json.loads(candidate)
                        return _validate_decision(data)
                    except (json.JSONDecodeError, ValueError):
                        pass
                    break

    # Strategy 3: try the whole string
    data = json.loads(raw.strip())
    return _validate_decision(data)


def detect_components_with_claude(spec_text: str, catalog: dict) -> dict:
    """Use claude -p to analyze spec and select components."""
    prompt = build_decision_prompt(spec_text, catalog)
    raw_response = call_claude(prompt)
    decision = parse_decision_json(raw_response)
    decision["method"] = "claude"
    decision["raw_response"] = raw_response
    return decision


# ---------------------------------------------------------------------------
# Static fallback (keyword matching — for offline / testing)
# ---------------------------------------------------------------------------

STATIC_SIGNALS = {
    "cloud_run": [
        "web application", "web app", "rest api", "http", "api endpoint",
        "backend service", "server", "frontend", "landing page", "deploy",
        "container", "docker", "serverless", "cloud run", "microservice",
    ],
    "iam": [
        "authentication", "authorization", "permission", "role",
        "access control", "service account", "iam", "policy binding",
    ],
    "alloydb": [
        "database", "postgresql", "postgres", "sql", "relational",
        "alloydb", "crud", "query", "transaction", "migration", "schema",
        "table", "persistent storage", "data store", "user data",
    ],
}


def detect_components_static(spec_text: str) -> dict:
    """Keyword-based fallback when claude is unavailable."""
    spec_lower = spec_text.lower()
    selected = []
    reasoning = {}

    for comp, keywords in STATIC_SIGNALS.items():
        matched = [kw for kw in keywords if kw in spec_lower]
        if matched:
            selected.append(comp)
            reasoning[comp] = f"Matched keywords: {', '.join(matched[:3])}"
        else:
            reasoning[comp] = None

    selected = sorted(selected)

    # Transitive: alloydb requires iam
    if "alloydb" in selected and "iam" not in selected:
        selected = sorted(selected + ["iam"])
        reasoning["iam"] = "Required transitively by alloydb."

    return {
        "selected": selected,
        "reasoning": reasoning,
        "supporting": resolve_supporting(selected),
        "method": "static",
    }


# ---------------------------------------------------------------------------
# Template selection and rendering (preserved from v1)
# ---------------------------------------------------------------------------

def select_template(selected: list[str], catalog: dict) -> str | None:
    """Pick the best-fit template from the template matrix."""
    matrix = catalog.get("template_matrix", {})
    key = "+".join(sorted(selected))
    if key in matrix:
        return matrix[key]

    # Fallback: try the most comprehensive template that covers all selected
    for matrix_key in sorted(matrix.keys(), key=lambda k: -k.count("+")):
        matrix_components = set(matrix_key.split("+"))
        if set(selected).issubset(matrix_components):
            return matrix[matrix_key]

    return None


def render_template(template_path: Path, spec_text: str) -> str:
    """Render a prompt template by injecting the project spec."""
    with open(template_path) as f:
        template = f.read()
    return template.replace("{{PROJECT_SPEC}}", spec_text)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def generate(
    spec_path: str,
    output_dir: str | None = None,
    emit_decision: bool = False,
    use_static: bool = False,
) -> dict:
    """Main generation pipeline.

    Returns the decision result dict. Side-effects: writes files to output_dir.
    """
    spec_path = Path(spec_path)
    if not spec_path.exists():
        print(f"Error: spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    spec_text = spec_path.read_text()
    catalog = load_catalog()

    # Step 1: Component detection
    if use_static:
        decision = detect_components_static(spec_text)
    else:
        if not shutil.which("claude"):
            print(
                "Warning: claude CLI not found, falling back to static detection.",
                file=sys.stderr,
            )
            decision = detect_components_static(spec_text)
        else:
            try:
                decision = detect_components_with_claude(spec_text, catalog)
            except Exception as e:
                print(
                    f"Warning: claude -p failed ({e}), falling back to static detection.",
                    file=sys.stderr,
                )
                decision = detect_components_static(spec_text)

    selected = decision["selected"]

    if not selected:
        print("No GCP components detected in the project spec.")
        sys.exit(0)

    # Step 2: Select template
    template_file = select_template(selected, catalog)

    # Step 3: Set up output
    if output_dir is None:
        output_dir = Path(spec_path).parent / "prompt-bundle"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 4: Emit decision file
    if emit_decision:
        decision_out = {k: v for k, v in decision.items() if k != "raw_response"}
        decision_path = output_dir.parent / "selected-components.json"
        with open(decision_path, "w") as f:
            json.dump(decision_out, f, indent=2)
        print(f"Decision: {decision_path}")

    # Step 5: Render and write prompts
    written = []

    # Write the composite template
    if template_file:
        tpl_path = TEMPLATES_DIR / template_file
        if tpl_path.exists():
            rendered = render_template(tpl_path, spec_text)
            out_file = output_dir / template_file
            out_file.write_text(rendered)
            written.append(str(out_file))

    # Also write individual component templates
    for comp in selected:
        comp_tpl_file = f"{comp.replace('_', '-')}.md"
        comp_tpl_path = TEMPLATES_DIR / comp_tpl_file
        if comp_tpl_path.exists():
            rendered = render_template(comp_tpl_path, spec_text)
            out_file = output_dir / comp_tpl_file
            if str(out_file) not in written:
                out_file.write_text(rendered)
                written.append(str(out_file))

    # Step 6: Print summary
    method = decision.get("method", "unknown")
    print(f"Project: {spec_path.name}")
    print(f"Detection: {method}")
    print(f"Selected components: {', '.join(selected)}")
    if decision.get("reasoning"):
        for comp, reason in decision["reasoning"].items():
            if reason:
                print(f"  {comp}: {reason}")
    print(f"Supporting infra: {', '.join(decision.get('supporting', []))}")
    print(f"Template: {template_file}")
    print(f"Prompts written to: {output_dir}/")
    for f in written:
        print(f"  - {Path(f).name}")

    return decision


def main():
    parser = argparse.ArgumentParser(
        description="Generate GCP augmentation prompts from a project spec."
    )
    parser.add_argument("spec", help="Path to the project spec markdown file")
    parser.add_argument("--output-dir", help="Output directory for prompt bundle")
    parser.add_argument(
        "--emit-decision",
        action="store_true",
        help="Also emit the component decision JSON",
    )
    parser.add_argument(
        "--static",
        action="store_true",
        help="Use static keyword matching instead of claude -p",
    )
    args = parser.parse_args()
    generate(args.spec, args.output_dir, args.emit_decision, args.static)


if __name__ == "__main__":
    main()
