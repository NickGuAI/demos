#!/usr/bin/env python3
"""
GCP Augmentation Prompt Generator

Takes a project spec (markdown) and:
1. Matches signals against gcp-component-decision.yaml
2. Selects required GCP components
3. Emits a prompt bundle for those components

Usage:
    python3 scripts/generate_gcp_prompts.py examples/book-journey/project.md

    # Custom output directory:
    python3 scripts/generate_gcp_prompts.py spec.md --output-dir ./my-output

    # Also emit the decision JSON:
    python3 scripts/generate_gcp_prompts.py spec.md --emit-decision
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = REPO_ROOT / "rules" / "gcp-component-decision.yaml"
TEMPLATES_DIR = REPO_ROOT / "prompts" / "templates"


def load_rules(rules_path: Path) -> dict:
    """Load the component decision rules from YAML."""
    with open(rules_path) as f:
        return yaml.safe_load(f)


def match_signals(spec_text: str, rules: dict) -> dict:
    """Match project spec text against decision rules.

    Returns:
        {
            "selected": ["cloud_run", "iam", ...],
            "matches": {
                "cloud_run": [{"group": "web_service", "keyword": "server", "context": "..."}],
                ...
            },
            "transitive": ["iam"],
            "supporting": ["artifact_registry", "service_account", ...]
        }
    """
    spec_lower = spec_text.lower()
    spec_lines = spec_text.split("\n")
    components = rules.get("components", {})

    selected = []
    matches = {}

    for comp_name, comp_def in components.items():
        comp_matches = []
        for signal_group in comp_def.get("signals", []):
            group_name = signal_group["group"]
            for keyword in signal_group.get("keywords", []):
                kw_lower = keyword.lower()
                if kw_lower in spec_lower:
                    # Find the line containing this keyword for context
                    context = ""
                    for line in spec_lines:
                        if kw_lower in line.lower():
                            context = line.strip()
                            break
                    comp_matches.append({
                        "group": group_name,
                        "keyword": keyword,
                        "context": context[:120],
                    })
        if comp_matches:
            selected.append(comp_name)
            matches[comp_name] = comp_matches

    # Resolve transitive dependencies
    transitive = []
    for comp_name in list(selected):
        for dep in components.get(comp_name, {}).get("transitive_requires", []):
            if dep not in selected:
                selected.append(dep)
                transitive.append(dep)
                matches[dep] = [{"group": "transitive", "keyword": f"required by {comp_name}", "context": ""}]

    # Resolve supporting infrastructure
    supporting_defs = rules.get("supporting", {})
    supporting = []
    for sup_name, sup_def in supporting_defs.items():
        trigger = sup_def.get("when", "")
        if trigger == "any" and selected:
            supporting.append(sup_name)
        elif trigger in selected:
            supporting.append(sup_name)

    # Deduplicate supporting
    supporting = sorted(set(supporting))

    return {
        "selected": sorted(selected),
        "matches": matches,
        "transitive": transitive,
        "supporting": supporting,
    }


def select_template(selected: list[str], rules: dict) -> str | None:
    """Pick the best-fit template from the template matrix."""
    matrix = rules.get("template_matrix", {})
    key = "+".join(sorted(selected))
    if key in matrix:
        return matrix[key]

    # Fallback: try the full-stack template if it covers all selected
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


def generate(spec_path: str, output_dir: str | None = None, emit_decision: bool = False) -> dict:
    """Main generation pipeline.

    Returns the decision result dict. Side-effects: writes files to output_dir.
    """
    spec_path = Path(spec_path)
    if not spec_path.exists():
        print(f"Error: spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    spec_text = spec_path.read_text()
    rules = load_rules(RULES_PATH)

    # Step 1: Match signals and select components
    decision = match_signals(spec_text, rules)
    selected = decision["selected"]

    if not selected:
        print("No GCP components detected in the project spec.")
        print("Signals checked:")
        for comp_name, comp_def in rules["components"].items():
            keywords = []
            for sg in comp_def.get("signals", []):
                keywords.extend(sg.get("keywords", []))
            print(f"  {comp_name}: {', '.join(keywords[:5])}...")
        sys.exit(0)

    # Step 2: Select template
    template_file = select_template(selected, rules)

    # Step 3: Set up output
    if output_dir is None:
        output_dir = Path(spec_path).parent / "prompt-bundle"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 4: Emit decision file
    if emit_decision:
        decision_path = output_dir.parent / "selected-components.json"
        with open(decision_path, "w") as f:
            json.dump(decision, f, indent=2)
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
    print(f"Project: {spec_path.name}")
    print(f"Selected components: {', '.join(selected)}")
    if decision["transitive"]:
        print(f"Transitive deps: {', '.join(decision['transitive'])}")
    print(f"Supporting infra: {', '.join(decision['supporting'])}")
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
    args = parser.parse_args()
    generate(args.spec, args.output_dir, args.emit_decision)


if __name__ == "__main__":
    main()
