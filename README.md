# GCP Augmentation Prompt Generator

Generate GCP deployment prompts from project specs. Takes a markdown project specification, uses `claude -p` to analyze which GCP components are needed (Cloud Run, IAM, AlloyDB), and emits a composable prompt bundle for updating those components.

## How It Works

```
┌─────────────────┐     ┌────────────────────┐     ┌──────────────────┐
│  Project Spec   │────→│  claude -p          │────→│  Prompt Bundle   │
│  (markdown)     │     │                    │     │  (per-component  │
│                 │     │  Reads spec +      │     │   templates +    │
│  e.g. "web app  │     │  component catalog │     │   composite)     │
│  with database" │     │  Returns JSON      │     │                  │
└─────────────────┘     └────────────────────┘     └──────────────────┘
                              │
                              ▼
                        ┌────────────────────┐
                        │  Decision JSON:    │
                        │  selected:         │
                        │   - cloud_run      │
                        │   - iam            │
                        │   - alloydb        │
                        │  reasoning:        │
                        │   cloud_run: "..." │
                        │   alloydb:   "..." │
                        └────────────────────┘
```

The decision step is **model-driven**: Claude reads the full project spec and the component catalog (`rules/gcp-component-decision.yaml`), then returns a structured JSON decision with per-component reasoning. This replaces static keyword matching — the model understands context, intent, and implicit requirements.

A `--static` flag provides a keyword-based fallback for offline use or CI.

## Quick Start

```bash
# Generate prompts (uses claude -p for component detection)
python3 scripts/generate_gcp_prompts.py path/to/project-spec.md

# Also emit the decision JSON
python3 scripts/generate_gcp_prompts.py path/to/project-spec.md --emit-decision

# Custom output directory
python3 scripts/generate_gcp_prompts.py spec.md --output-dir ./my-output

# Offline / CI mode (static keyword matching, no claude call)
python3 scripts/generate_gcp_prompts.py spec.md --static
```

Requires: Python 3.8+, PyYAML (`pip3 install pyyaml`), and `claude` CLI (for model-driven mode).

## Worked Example: Book Journey

```bash
python3 scripts/generate_gcp_prompts.py examples/book-journey/project.md --emit-decision
```

Output:
- `examples/book-journey/selected-components.json` - decision artifact (includes reasoning)
- `examples/book-journey/prompt-bundle/cloud-run-iam-alloydb.md` - composite prompt
- `examples/book-journey/prompt-bundle/cloud-run.md` - Cloud Run-only prompt
- `examples/book-journey/prompt-bundle/iam.md` - IAM-only prompt
- `examples/book-journey/prompt-bundle/alloydb.md` - AlloyDB-only prompt
- `examples/book-journey/augmented-spec.md` - full GCP deployment specification

## Input / Output Contract

**Input**: A markdown file describing a project.

**Output**:
1. **Decision JSON** (`--emit-decision`): Which components were selected, why (per-component reasoning from Claude), and which detection method was used
2. **Prompt bundle**: One composite template + individual component templates, each with the project spec injected

### Detection Modes

| Mode | Flag | How it works |
|------|------|-------------|
| Model-driven (default) | _(none)_ | `claude -p` reads spec + catalog, returns structured JSON |
| Static fallback | `--static` | Keyword matching against hardcoded signal lists |
| Auto-fallback | _(none)_ | If `claude` CLI is missing or fails, falls back to static |

## Project Structure

```
demos/
├── README.md                           # This file
├── research/gcp/                       # Archived GCP official docs (10 files)
├── rules/
│   └── gcp-component-decision.yaml     # Component catalog (read by Claude)
├── prompts/templates/                   # Reusable prompt templates (6 files)
│   ├── cloud-run.md
│   ├── iam.md
│   ├── alloydb.md
│   ├── cloud-run-iam.md
│   ├── cloud-run-alloydb.md
│   └── cloud-run-iam-alloydb.md
├── scripts/
│   └── generate_gcp_prompts.py         # Generator CLI
├── examples/book-journey/              # Worked example
│   ├── project.md                      # Input: project spec
│   ├── selected-components.json        # Output: decision artifact
│   ├── prompt-bundle/                  # Output: generated prompts
│   └── augmented-spec.md              # Hand-crafted deployment spec
└── tests/
    └── test_generator.py               # 22 tests
```

## Component Coverage

| Combination | Template | Use Case |
|------------|----------|----------|
| Cloud Run only | `cloud-run.md` | Static site, simple API |
| IAM only | `iam.md` | Service account setup, access control |
| AlloyDB only | `alloydb.md` | Database infrastructure |
| Cloud Run + IAM | `cloud-run-iam.md` | Authenticated API service |
| Cloud Run + AlloyDB | `cloud-run-alloydb.md` | Web app with database |
| Cloud Run + IAM + AlloyDB | `cloud-run-iam-alloydb.md` | Full-stack application |

## Editing the Catalog

The component catalog in `rules/gcp-component-decision.yaml` describes what each component is and when to use it. Claude reads this as context when making decisions. Edit the `description`, `use_when`, and `not_needed_when` fields to steer the model's judgment:

```yaml
components:
  cloud_run:
    description: "Serverless container deployment on Cloud Run"
    use_when: >
      The project is a web application, API service, ...
    not_needed_when: >
      The project is purely a database setup, ...
```

## Running Tests

```bash
python3 tests/test_generator.py
```

22 tests covering: catalog loading, JSON parsing (clean/fenced/invalid), transitive dependency enforcement, supporting infra resolution, prompt construction, static detection, template selection, and end-to-end generation (both static and claude modes).

## Research Archive

The `research/gcp/` directory contains archived extracts from official Google Cloud documentation (2026-04-21 snapshots) for offline reference. Always check the official docs for the latest information.
