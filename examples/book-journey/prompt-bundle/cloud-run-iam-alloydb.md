# Cloud Run + IAM + AlloyDB Full-Stack Deployment Prompt

You are a GCP infrastructure engineer. Deploy a full-stack application on Cloud Run with AlloyDB and proper IAM for the following project.

## Project Context

# Book Journey (MVP)

## Overview

A multi-user reading journal where users add short "journey checkpoints" to pre-seeded books. Each book has a public landing page showing its details and all readers' checkpoints.

Books are loaded from `assets/books.json` (users cannot add or edit books). Each book contains: `id`, `title`, `author`, `year_published`, `synopsis`, `total_chapters`, `genre`.

---

## Authentication (Username Only)

- App entry shows a username field and a "Continue" action.
- Username rules: required, 3-20 characters, letters/numbers/underscores only, case-sensitive, unique.
- If validation fails: show an error and remain on the login screen.
- On valid submit:
  - If username does not exist: create account and log in.
  - If username already exists: log that user in.
- After login, user lands on Browse Books.
- Session persists across page refreshes.

---

## Browse Books

- Shows a list of all books with: title, author, year published, genre, and a synopsis preview.
- Each book links to its Book Landing Page.
- Search input filters by substring match on title or author (case-insensitive).
- Top navigation includes links to "Browse" and "My Journey".

---

## My Journey

- Lists all books where the logged-in user has at least one checkpoint.
- Shows: title, author, year published for each book.
- Each entry links to the Book Landing Page.
- Empty state: "You haven't started any journeys yet."

---

## Book Landing Page

**Book Details** (at top):
- Title, author, year published, genre, full synopsis
- Total chapters displayed as "Chapters: N"

**Your Journey Section**:
- If user has checkpoints: show count and "Add Checkpoint" action.
- If user has no checkpoints: indicate not started and show "Add First Checkpoint" action.

**Reader Checkpoints Section**:
- All checkpoints from all users for this book.
- Each shows: username, chapter number, note text, mood (if present).
- Ordered by chapter number ascending.
- Current user's checkpoints are visually distinguished.

---

## Checkpoints (Add Only)

Each checkpoint contains: chapter number, note text, mood (optional).

**Validation**:
- Chapter: integer between 1 and `total_chapters` (inclusive).
- Note: required, 1-280 characters after trimming leading/trailing whitespace.
- Mood options: Curious, Confused, Excited, Calm, Sad, Delighted (or none).

**On save**:
- If validation fails: show errors, do not save.
- If valid: save checkpoint, return to Book Landing Page. The checkpoint appears in Reader Checkpoints sorted by chapter. If first checkpoint for this book, it appears in My Journey.

Users cannot edit or delete checkpoints.

### Seed Data & Initialization
Initialize the application with the following data. Ensure all usernames and checkpoint details are preserved exactly:

**Existing User Accounts:**
- `reader_taken`: Existing account, no checkpoints.
- `reader_alex`: Existing account with checkpoints.
- `reader_bella`: Existing account with checkpoints.

**Negative Constraints (Do Not Create):**
- `journey_sara`: This account should NOT exist initially.

**Initial Checkpoints for "The Silent Library" (ID found in `assets/books.json`):**
1. **User:** `reader_alex`
   - **Chapter:** 5
   - **Note:** "First twist caught me off guard."
   - **Mood:** Curious
2. **User:** `reader_alex`
   - **Chapter:** 12
   - **Note:** "Starting to suspect the librarian."
   - **Mood:** Confused
3. **User:** `reader_bella`
   - **Chapter:** 3
   - **Note:** "Loving the eerie atmosphere."
   - **Mood:** Excited

All other books should start with zero checkpoints. All other potential usernames should be considered non-existent until created by the login flow.

## Explicit Instruction Regarding Seed Data Validation
You must create a `startup.sh` script that starts the server on the provided port. This script MUST ALSO programmatically inject the seed data into the application database. Absolute dates specified in the data should be used as-is.


## Architecture

```
                           ┌─────────────────────────────────────┐
                           │          GCP Project                │
                           │                                     │
┌──────────┐    HTTPS      │  ┌──────────────┐                  │
│  Client  │ ─────────────→│  │  Cloud Run   │                  │
│          │               │  │  Service     │                  │
└──────────┘               │  │              │                  │
                           │  │  SA: app-sa  │                  │
                           │  └──────┬───────┘                  │
                           │         │                          │
                           │    VPC Direct Egress               │
                           │         │                          │
                           │  ┌──────▼───────┐                  │
                           │  │  VPC Network │                  │
                           │  └──────┬───────┘                  │
                           │         │ Private IP               │
                           │  ┌──────▼───────┐                  │
                           │  │   AlloyDB    │                  │
                           │  │   Primary    │                  │
                           │  └──────────────┘                  │
                           │                                     │
                           │  ┌──────────────┐                  │
                           │  │ Secret Mgr   │ DB credentials   │
                           │  └──────────────┘                  │
                           │                                     │
                           │  ┌──────────────┐                  │
                           │  │ Artifact Reg │ Container images │
                           │  └──────────────┘                  │
                           └─────────────────────────────────────┘

IAM Bindings:
  app-sa ──→ roles/alloydb.client
  app-sa ──→ roles/serviceusage.serviceUsageConsumer
  app-sa ──→ roles/secretmanager.secretAccessor
  service ──→ roles/run.invoker (to allUsers or specific SAs)
```

## Requirements

### Phase 1: Networking
```bash
# VPC (skip if using default network)
gcloud compute networks create {{NETWORK_NAME}} --subnet-mode=auto

# Private Services Access for AlloyDB
gcloud compute addresses create alloydb-psa-range \
  --global --purpose=VPC_PEERING --prefix-length=16 \
  --network={{NETWORK_NAME}}

gcloud services vpc-peerings connect \
  --service=servicenetworking.googleapis.com \
  --ranges=alloydb-psa-range --network={{NETWORK_NAME}}
```

### Phase 2: AlloyDB
```bash
# Cluster
gcloud alloydb clusters create {{CLUSTER_NAME}} \
  --region={{REGION}} --network={{NETWORK_NAME}} \
  --password={{DB_PASSWORD}}

# Primary instance
gcloud alloydb instances create {{INSTANCE_NAME}} \
  --cluster={{CLUSTER_NAME}} --region={{REGION}} \
  --instance-type=PRIMARY --cpu-count={{CPU_COUNT}} \
  --database-flags=alloydb.iam_authentication=on

# Create application database (via Auth Proxy)
# CREATE DATABASE {{DB_NAME}};
```

### Phase 3: IAM
```bash
# Service account
gcloud iam service-accounts create {{SERVICE_NAME}}-sa \
  --display-name="{{SERVICE_NAME}} Cloud Run SA"

SA_EMAIL="{{SERVICE_NAME}}-sa@{{PROJECT_ID}}.iam.gserviceaccount.com"

# AlloyDB connectivity
gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:$SA_EMAIL \
  --role=roles/alloydb.client

gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:$SA_EMAIL \
  --role=roles/serviceusage.serviceUsageConsumer

# Secret Manager
gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:$SA_EMAIL \
  --role=roles/secretmanager.secretAccessor

# (Optional) IAM database authentication
gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:$SA_EMAIL \
  --role=roles/alloydb.databaseUser

# Deployer can act as this SA
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
  --member={{DEPLOYER_MEMBER}} \
  --role=roles/iam.serviceAccountUser
```

### Phase 4: Secrets
```bash
echo -n "{{DB_PASSWORD}}" | gcloud secrets create {{SERVICE_NAME}}-db-pass \
  --data-file=- --replication-policy=automatic
```

### Phase 5: Container Build
```bash
gcloud artifacts repositories create {{REPO_NAME}} \
  --repository-format=docker --location={{REGION}}

gcloud builds submit \
  --tag us-docker.pkg.dev/{{PROJECT_ID}}/{{REPO_NAME}}/{{SERVICE_NAME}}:latest
```

### Phase 6: Cloud Run Deploy
```bash
gcloud run deploy {{SERVICE_NAME}} \
  --image=us-docker.pkg.dev/{{PROJECT_ID}}/{{REPO_NAME}}/{{SERVICE_NAME}}:latest \
  --region={{REGION}} \
  --service-account={{SERVICE_NAME}}-sa@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --port={{PORT}} \
  --memory={{MEMORY}} \
  --cpu={{CPU}} \
  --min-instances={{MIN_INSTANCES}} \
  --max-instances={{MAX_INSTANCES}} \
  --set-env-vars=DB_NAME={{DB_NAME}},DB_USER={{DB_USER}},DB_PORT=5432,INSTANCE_HOST={{ALLOYDB_IP}} \
  --set-secrets=DB_PASS={{SERVICE_NAME}}-db-pass:latest \
  --network={{NETWORK_NAME}} \
  --subnet={{SUBNET_NAME}} \
  --vpc-egress=private-ranges-only \
  {{ACCESS_FLAG}}
```

### Phase 7: Service IAM (post-deploy)
```bash
# Public access (if applicable):
gcloud run services add-iam-policy-binding {{SERVICE_NAME}} \
  --member=allUsers \
  --role=roles/run.invoker \
  --region={{REGION}}
```

## Output

Produce a complete deployment package:
1. `deploy.sh` - Orchestrates all phases above
2. `teardown.sh` - Reverses all resources for cleanup
3. `verify.sh` - Checks deployment health and IAM correctness
4. Documentation of all IAM bindings and their justifications

## Constraints
- Same region for Cloud Run and AlloyDB
- Dedicated SA (never default Compute Engine SA)
- All secrets in Secret Manager
- VPC Direct Egress for Cloud Run → AlloyDB
- IAM auth enabled on AlloyDB instance
- Public access only if the project requires unauthenticated access
