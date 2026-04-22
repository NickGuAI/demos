#!/usr/bin/env python3
"""
GCP Augmentation Prompt Generator (model-driven)

Takes a project spec (markdown) and:
1. Sends it to `claude -p` along with the GCP component catalog.
2. Claude analyzes the spec and returns structured JSON with selected components.
3. Renders the matching prompt templates for those components.

Usage:
    python3 scripts/generate_gcp_prompts.py examples/book-journey/project.md

    # Custom output directory:
    python3 scripts/generate_gcp_prompts.py spec.md --output-dir ./my-output

    # Also emit the decision JSON:
    python3 scripts/generate_gcp_prompts.py spec.md --emit-decision

Requires: Python 3.8+, PyYAML, and the `claude` CLI on PATH.
If `claude` is unavailable or returns an error, the script fails loudly —
there is no silent fallback. Use a mocked `call_claude` for tests (see
`tests/test_generator.py`).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

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


class ClaudeCliMissingError(RuntimeError):
    """Raised when the `claude` CLI binary is not available on PATH."""


class ClaudeInvocationError(RuntimeError):
    """Raised when `claude -p` exits non-zero or cannot be parsed."""


def call_claude(prompt: str) -> str:
    """Call `claude -p` and return stdout.

    Raises:
        ClaudeCliMissingError: if the `claude` binary is not on PATH.
        ClaudeInvocationError: if claude exits non-zero.
    """
    if not shutil.which("claude"):
        raise ClaudeCliMissingError(
            "The `claude` CLI is required for model-driven component detection "
            "but was not found on PATH. Install Claude Code (https://claude.com/claude-code) "
            "and retry."
        )
    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise ClaudeInvocationError(
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


def detect_components(
    spec_text: str,
    catalog: dict,
    claude_caller: Callable[[str], str] = call_claude,
) -> dict:
    """Use claude -p to analyze spec and select components.

    `claude_caller` is injected so tests can supply a fake that returns a
    canned JSON response without requiring the real `claude` binary. The
    default calls the real CLI; production code paths never need to pass
    anything other than the default.
    """
    prompt = build_decision_prompt(spec_text, catalog)
    raw_response = claude_caller(prompt)
    decision = parse_decision_json(raw_response)
    decision["method"] = "claude"
    decision["raw_response"] = raw_response
    return decision


# ---------------------------------------------------------------------------
# Template selection and rendering
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
    claude_caller: Callable[[str], str] = call_claude,
) -> dict:
    """Main generation pipeline.

    Returns the decision result dict. Side-effects: writes files to output_dir.

    `claude_caller` is injected for testability — production callers never
    pass it (the default hits the real claude CLI).
    """
    spec_path = Path(spec_path)
    if not spec_path.exists():
        print(f"Error: spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    spec_text = spec_path.read_text()
    catalog = load_catalog()

    # Component detection — claude is the only path. Any failure is a loud
    # error, not a silent degradation to keyword matching.
    decision = detect_components(spec_text, catalog, claude_caller=claude_caller)

    selected = decision["selected"]

    if not selected:
        print("No GCP components detected in the project spec.")
        sys.exit(0)

    # Select template
    template_file = select_template(selected, catalog)

    # Set up output
    if output_dir is None:
        output_dir = Path(spec_path).parent / "prompt-bundle"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Emit decision file
    if emit_decision:
        decision_out = {k: v for k, v in decision.items() if k != "raw_response"}
        decision_path = output_dir.parent / "selected-components.json"
        with open(decision_path, "w") as f:
            json.dump(decision_out, f, indent=2)
        print(f"Decision: {decision_path}")

    # Render and write prompts
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

    # Summary
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
        description="Generate GCP augmentation prompts from a project spec.",
    )
    parser.add_argument("spec", help="Path to the project spec markdown file")
    parser.add_argument("--output-dir", help="Output directory for prompt bundle")
    parser.add_argument(
        "--emit-decision",
        action="store_true",
        help="Also emit the component decision JSON",
    )
    args = parser.parse_args()
    try:
        generate(args.spec, args.output_dir, args.emit_decision)
    except ClaudeCliMissingError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    except ClaudeInvocationError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
