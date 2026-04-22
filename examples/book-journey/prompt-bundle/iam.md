# IAM Configuration Prompt

You are a GCP IAM security engineer. Configure IAM roles and bindings for the following project.

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

Set up IAM with least-privilege principles:

### 1. Service Accounts
Create dedicated service accounts for each workload:
```bash
gcloud iam service-accounts create {{SA_NAME}} \
  --display-name="{{SA_DISPLAY_NAME}}" \
  --project={{PROJECT_ID}}
```

### 2. Project-Level Role Bindings
Grant only the roles each service account needs:
```bash
gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:{{SA_EMAIL}} \
  --role={{ROLE}}
```

### 3. Service Account Impersonation
If any principal needs to deploy as or act as a service account:
```bash
gcloud iam service-accounts add-iam-policy-binding {{SA_EMAIL}} \
  --member={{DEPLOYER_MEMBER}} \
  --role=roles/iam.serviceAccountUser
```

### 4. Access Patterns to Configure

For each access pattern in the project, determine:
- **Who** needs access (user, SA, group, allUsers)
- **What** they need access to (project, service, resource)
- **Which role** provides least-privilege access

## Output

Produce an IAM setup script (`setup-iam.sh`) that:
1. Creates all required service accounts
2. Grants project-level role bindings
3. Configures service account impersonation where needed
4. Documents each binding with inline comments explaining why

## Constraints
- Never grant `roles/owner` or `roles/editor` to service accounts
- Prefer resource-level bindings over project-level where possible
- Use IAM conditions for time-limited or scoped access
- Document the purpose of every binding
