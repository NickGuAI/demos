# GCP Augmentation Prompt Generator

Generate GCP deployment prompts from project specs. Takes a markdown project specification, determines which GCP components are needed (Cloud Run, IAM, AlloyDB), and emits a composable prompt bundle for updating those components.

## How It Works

```
┌─────────────────┐     ┌────────────────────┐     ┌──────────────────┐
│  Project Spec   │────→│  Decision Engine   │────→│  Prompt Bundle   │
│  (markdown)     │     │                    │     │  (per-component  │
│                 │     │  rules/gcp-        │     │   templates +    │
│  e.g. "web app  │     │  component-        │     │   composite)     │
│  with database" │     │  decision.yaml     │     │                  │
└─────────────────┘     └────────────────────┘     └──────────────────┘
                              │
                              ▼
                        ┌────────────────────┐
                        │  Selected:         │
                        │  - cloud_run       │
                        │  - iam             │
                        │  - alloydb         │
                        │  Supporting:       │
                        │  - vpc_network     │
                        │  - secret_manager  │
                        │  - service_account │
                        └────────────────────┘
```

## Quick Start

```bash
# Generate prompts for a project spec
python3 scripts/generate_gcp_prompts.py path/to/project-spec.md

# Also emit the decision JSON
python3 scripts/generate_gcp_prompts.py path/to/project-spec.md --emit-decision

# Custom output directory
python3 scripts/generate_gcp_prompts.py spec.md --output-dir ./my-output
```

## Worked Example: Book Journey

```bash
python3 scripts/generate_gcp_prompts.py examples/book-journey/project.md --emit-decision
```

Output:
- `examples/book-journey/selected-components.json` - decision artifact
- `examples/book-journey/prompt-bundle/cloud-run-iam-alloydb.md` - composite prompt
- `examples/book-journey/prompt-bundle/cloud-run.md` - Cloud Run-only prompt
- `examples/book-journey/prompt-bundle/iam.md` - IAM-only prompt
- `examples/book-journey/prompt-bundle/alloydb.md` - AlloyDB-only prompt
- `examples/book-journey/augmented-spec.md` - full GCP deployment specification

## Input / Output Contract

**Input**: A markdown file describing a project. The generator scans for keyword signals (case-insensitive substring match) that map to GCP components.

**Output**:
1. **Decision JSON** (`--emit-decision`): Which components were selected and why
2. **Prompt bundle**: One composite template + individual component templates, each with the project spec injected

### Signal Examples

| Signal Keywords | Component Selected |
|----------------|-------------------|
| "web application", "REST API", "server", "deploy" | Cloud Run |
| "authentication", "IAM", "service account", "roles" | IAM |
| "database", "PostgreSQL", "SQL", "user data" | AlloyDB |

## Project Structure

```
demos/
├── README.md                           # This file
├── research/gcp/                       # Archived GCP official docs
│   ├── cloud-run-deploy.md
│   ├── cloud-run-iam-binding.md
│   ├── project-iam-binding.md
│   ├── service-account-iam-binding.md
│   ├── alloydb-instances-create.md
│   ├── alloydb-cloud-run-integration.md
│   ├── alloydb-auth-proxy.md
│   ├── alloydb-iam-auth.md
│   ├── alloydb-manage-iam-users.md
│   └── alloydb-iam-roles.md
├── rules/
│   └── gcp-component-decision.yaml     # Decision rules (human-editable)
├── prompts/templates/                   # Reusable prompt templates
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
    └── test_generator.py               # Smoke tests (10 tests)
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

## Editing the Rules

The decision rules in `rules/gcp-component-decision.yaml` are human-editable YAML. To add a new signal:

```yaml
components:
  cloud_run:
    signals:
      - group: "my_new_group"
        keywords:
          - "my new keyword"
```

## Running Tests

```bash
python3 tests/test_generator.py
```

Requires: Python 3.8+ and PyYAML (`pip3 install pyyaml`).

## Research Archive

The `research/gcp/` directory contains archived extracts from official Google Cloud documentation for:
- `gcloud run deploy`
- `gcloud run services add-iam-policy-binding`
- `gcloud projects add-iam-policy-binding`
- `gcloud iam service-accounts add-iam-policy-binding`
- `gcloud alloydb instances create`
- AlloyDB + Cloud Run integration guide
- AlloyDB Auth Proxy connection guide
- AlloyDB IAM authentication
- AlloyDB IAM user management
- AlloyDB IAM roles and permissions

These are point-in-time snapshots (2026-04-21) for offline reference. Always check the official docs for the latest information.
