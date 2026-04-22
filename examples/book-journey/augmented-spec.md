# Book Journey (MVP) - GCP Deployment Specification

## Decision Summary

```
┌──────────────────────────────────────────────────────────────┐
│                   Component Selection                        │
├──────────────┬──────────┬────────────────────────────────────┤
│ Component    │ Selected │ Reason                             │
├──────────────┼──────────┼────────────────────────────────────┤
│ Cloud Run    │    ✓     │ Web app, server, landing page      │
│ IAM          │    ✓     │ Authentication, public access,     │
│              │          │ service account for AlloyDB         │
│ AlloyDB      │    ✓     │ Database, user data, CRUD, SQL     │
├──────────────┼──────────┼────────────────────────────────────┤
│ SUPPORTING   │          │                                    │
├──────────────┼──────────┼────────────────────────────────────┤
│ Artifact Reg │    ✓     │ Container images (Cloud Run)       │
│ VPC Network  │    ✓     │ Private connectivity (AlloyDB)     │
│ Service Acct │    ✓     │ Least-privilege identity           │
│ Secret Mgr   │    ✓     │ Database credentials               │
└──────────────┴──────────┴────────────────────────────────────┘
```

## Architecture

```
                    ┌──────────────────────────────────────────────────┐
                    │              GCP Project: book-journey           │
                    │                                                  │
  ┌──────────┐     │   ┌────────────────┐                            │
  │  Browser  │ HTTPS   │  Cloud Run     │                            │
  │  Users    │────────→│  book-journey  │                            │
  └──────────┘     │   │  :8080         │                            │
                    │   │                │                            │
                    │   │  SA: book-     │                            │
                    │   │  journey-sa    │                            │
                    │   └───────┬────────┘                            │
                    │           │                                      │
                    │      VPC Direct Egress                           │
                    │           │                                      │
                    │   ┌───────▼────────┐                            │
                    │   │  VPC Network   │                            │
                    │   │  (default)     │                            │
                    │   └───────┬────────┘                            │
                    │           │ Private IP (10.x.x.x)               │
                    │   ┌───────▼────────┐                            │
                    │   │  AlloyDB       │                            │
                    │   │  Cluster:      │                            │
                    │   │   book-journey │                            │
                    │   │  Instance:     │                            │
                    │   │   primary      │                            │
                    │   │  DB: bookdb    │                            │
                    │   └────────────────┘                            │
                    │                                                  │
                    │   ┌────────────────┐  ┌────────────────┐       │
                    │   │ Secret Manager │  │ Artifact       │       │
                    │   │ book-journey-  │  │ Registry       │       │
                    │   │ db-pass        │  │ book-journey   │       │
                    │   └────────────────┘  └────────────────┘       │
                    └──────────────────────────────────────────────────┘
```

## GCP Configuration

### Variables
```bash
PROJECT_ID="your-gcp-project"
REGION="us-central1"
SERVICE_NAME="book-journey"
CLUSTER_NAME="book-journey-cluster"
INSTANCE_NAME="book-journey-primary"
DB_NAME="bookdb"
DB_USER="bookjourney"
NETWORK_NAME="default"
SA_EMAIL="${SERVICE_NAME}-sa@${PROJECT_ID}.iam.gserviceaccount.com"
```

### Phase 1: Enable APIs
```bash
gcloud services enable \
  run.googleapis.com \
  alloydb.googleapis.com \
  compute.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  servicenetworking.googleapis.com \
  --project=$PROJECT_ID
```

### Phase 2: Networking (VPC + Private Services Access)
```bash
# Allocate IP range for AlloyDB
gcloud compute addresses create alloydb-psa-range \
  --global \
  --purpose=VPC_PEERING \
  --prefix-length=16 \
  --network=$NETWORK_NAME \
  --project=$PROJECT_ID

# Create private connection
gcloud services vpc-peerings connect \
  --service=servicenetworking.googleapis.com \
  --ranges=alloydb-psa-range \
  --network=$NETWORK_NAME \
  --project=$PROJECT_ID
```

### Phase 3: AlloyDB
```bash
# Create cluster
gcloud alloydb clusters create $CLUSTER_NAME \
  --region=$REGION \
  --network=$NETWORK_NAME \
  --password="$(openssl rand -base64 24)" \
  --project=$PROJECT_ID

# Create primary instance (2 CPU minimum, ZONAL for MVP)
gcloud alloydb instances create $INSTANCE_NAME \
  --cluster=$CLUSTER_NAME \
  --region=$REGION \
  --instance-type=PRIMARY \
  --cpu-count=2 \
  --availability-type=ZONAL \
  --project=$PROJECT_ID

# Get the private IP
ALLOYDB_IP=$(gcloud alloydb instances describe $INSTANCE_NAME \
  --cluster=$CLUSTER_NAME --region=$REGION \
  --format="value(ipAddress)" --project=$PROJECT_ID)
```

### Phase 4: Database Setup (via Auth Proxy)
```sql
CREATE DATABASE bookdb;

-- Application tables
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(20) UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE checkpoints (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  book_id VARCHAR(50) NOT NULL,
  chapter INTEGER NOT NULL,
  note TEXT NOT NULL,
  mood VARCHAR(20),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_checkpoints_book ON checkpoints(book_id);
CREATE INDEX idx_checkpoints_user ON checkpoints(user_id);
```

### Phase 5: IAM
```bash
# Create service account
gcloud iam service-accounts create ${SERVICE_NAME}-sa \
  --display-name="Book Journey Cloud Run SA" \
  --project=$PROJECT_ID

# AlloyDB connectivity (Auth Proxy / direct VPC)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:$SA_EMAIL \
  --role=roles/alloydb.client

# Service usage (required for AlloyDB)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:$SA_EMAIL \
  --role=roles/serviceusage.serviceUsageConsumer

# Secret Manager (read DB password)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:$SA_EMAIL \
  --role=roles/secretmanager.secretAccessor
```

### Phase 6: Secrets
```bash
# Store DB password
echo -n "$DB_PASSWORD" | gcloud secrets create ${SERVICE_NAME}-db-pass \
  --data-file=- \
  --replication-policy=automatic \
  --project=$PROJECT_ID
```

### Phase 7: Container Build & Push
```bash
# Create Artifact Registry repo
gcloud artifacts repositories create $SERVICE_NAME \
  --repository-format=docker \
  --location=$REGION \
  --project=$PROJECT_ID

# Build and push
gcloud builds submit \
  --tag us-docker.pkg.dev/$PROJECT_ID/$SERVICE_NAME/$SERVICE_NAME:latest \
  --project=$PROJECT_ID
```

### Phase 8: Cloud Run Deploy
```bash
gcloud run deploy $SERVICE_NAME \
  --image=us-docker.pkg.dev/$PROJECT_ID/$SERVICE_NAME/$SERVICE_NAME:latest \
  --region=$REGION \
  --service-account=$SA_EMAIL \
  --port=8080 \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=5 \
  --set-env-vars="DB_NAME=$DB_NAME,DB_USER=$DB_USER,DB_PORT=5432,INSTANCE_HOST=$ALLOYDB_IP" \
  --set-secrets="DB_PASS=${SERVICE_NAME}-db-pass:latest" \
  --network=$NETWORK_NAME \
  --subnet=default \
  --vpc-egress=private-ranges-only \
  --allow-unauthenticated \
  --project=$PROJECT_ID
```

### Phase 9: Post-Deploy Verification
```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
  --region=$REGION --format="value(status.url)" --project=$PROJECT_ID)

# Health check
curl -s "$SERVICE_URL/health" | head -1

# Verify IAM
gcloud run services get-iam-policy $SERVICE_NAME \
  --region=$REGION --project=$PROJECT_ID
```

## IAM Binding Summary

| Principal | Role | Resource | Purpose |
|-----------|------|----------|---------|
| `book-journey-sa` | `roles/alloydb.client` | Project | Connect to AlloyDB |
| `book-journey-sa` | `roles/serviceusage.serviceUsageConsumer` | Project | Required for AlloyDB |
| `book-journey-sa` | `roles/secretmanager.secretAccessor` | Project | Read DB password |
| `allUsers` | `roles/run.invoker` | Cloud Run service | Public web access |

## Design Decisions

- **AlloyDB over Cloud SQL**: AlloyDB is the target database per package scope. For an MVP this size, Cloud SQL would also work, but this spec demonstrates the AlloyDB integration pattern.
- **VPC Direct Egress over VPC Connector**: Simpler, no separate connector resource to manage.
- **Password auth over IAM auth**: Simpler for MVP. IAM auth flag is enabled on the instance for future upgrade.
- **ZONAL over REGIONAL**: MVP doesn't need HA. Switch to REGIONAL for production.
- **`--allow-unauthenticated`**: Book Journey has its own username-based auth; the Cloud Run service itself is public.
- **2 CPU / 512Mi**: Minimal AlloyDB instance + lightweight Cloud Run for an MVP reading journal.
