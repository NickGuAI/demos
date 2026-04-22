# Cloud Run Deployment Prompt

You are a GCP infrastructure engineer. Set up a Cloud Run deployment for the following project.

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


## Requirements

Deploy this project as a Cloud Run service with:

### 1. Container Image
- Build a Dockerfile for the application
- Push to Artifact Registry: `us-docker.pkg.dev/{{PROJECT_ID}}/{{REPO_NAME}}/{{SERVICE_NAME}}`
- Use multi-stage build to minimize image size

### 2. Cloud Run Service
```bash
gcloud run deploy {{SERVICE_NAME}} \
  --image=us-docker.pkg.dev/{{PROJECT_ID}}/{{REPO_NAME}}/{{SERVICE_NAME}}:latest \
  --region={{REGION}} \
  --port={{PORT}} \
  --memory={{MEMORY}} \
  --cpu={{CPU}} \
  --min-instances={{MIN_INSTANCES}} \
  --max-instances={{MAX_INSTANCES}} \
  --set-env-vars={{ENV_VARS}} \
  {{ACCESS_FLAG}}
```

### 3. Service Account
Create a dedicated service account with least-privilege roles:
```bash
gcloud iam service-accounts create {{SERVICE_NAME}}-sa \
  --display-name="{{SERVICE_NAME}} Cloud Run SA"
```

### 4. Artifact Registry Repository
```bash
gcloud artifacts repositories create {{REPO_NAME}} \
  --repository-format=docker \
  --location={{REGION}}
```

## Output

Produce a deployment script (`deploy.sh`) that:
1. Builds and pushes the container image
2. Creates the service account if it doesn't exist
3. Deploys to Cloud Run with the configuration above
4. Outputs the service URL

## Constraints
- Use `gen2` execution environment for full Linux support
- Set appropriate health check if the app has a `/health` endpoint
- Configure concurrency based on the app's threading model
