# AlloyDB Setup Prompt

You are a GCP database engineer. Set up AlloyDB for PostgreSQL for the following project.

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

### 1. VPC Network Setup
Ensure a VPC network with Private Services Access:
```bash
# Create VPC (if not using default)
gcloud compute networks create {{NETWORK_NAME}} --subnet-mode=auto

# Allocate IP range for Private Services Access
gcloud compute addresses create alloydb-psa-range \
  --global \
  --purpose=VPC_PEERING \
  --prefix-length=16 \
  --network={{NETWORK_NAME}}

# Create private connection
gcloud services vpc-peerings connect \
  --service=servicenetworking.googleapis.com \
  --ranges=alloydb-psa-range \
  --network={{NETWORK_NAME}}
```

### 2. AlloyDB Cluster
```bash
gcloud alloydb clusters create {{CLUSTER_NAME}} \
  --region={{REGION}} \
  --network={{NETWORK_NAME}} \
  --password={{DB_PASSWORD}}
```

### 3. Primary Instance
```bash
gcloud alloydb instances create {{INSTANCE_NAME}} \
  --cluster={{CLUSTER_NAME}} \
  --region={{REGION}} \
  --instance-type=PRIMARY \
  --cpu-count={{CPU_COUNT}} \
  --availability-type={{AVAILABILITY_TYPE}} \
  --database-flags=alloydb.iam_authentication=on
```

### 4. Database and User Setup
Connect via Auth Proxy and create the application database:
```sql
CREATE DATABASE {{DB_NAME}};
CREATE USER {{DB_USER}} WITH PASSWORD '{{DB_PASSWORD}}';
GRANT ALL PRIVILEGES ON DATABASE {{DB_NAME}} TO {{DB_USER}};
```

### 5. Secret Manager for Credentials
```bash
echo -n "{{DB_PASSWORD}}" | gcloud secrets create {{SECRET_NAME}} \
  --data-file=- \
  --replication-policy=automatic
```

## Output

Produce a database setup script (`setup-alloydb.sh`) that:
1. Creates the VPC network and Private Services Access (if needed)
2. Creates the AlloyDB cluster and primary instance
3. Stores credentials in Secret Manager
4. Documents the instance connection URI

## Constraints
- Use IAM authentication where possible (prefer over password auth)
- Enable `alloydb.iam_authentication` database flag
- Use ZONAL availability for dev/staging, REGIONAL for production
- Minimum CPU: 2 (AlloyDB requirement)
- Store passwords in Secret Manager, never in env vars or code
