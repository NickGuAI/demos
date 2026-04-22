# Cloud Run + IAM + AlloyDB Full-Stack Deployment Prompt

You are a GCP infrastructure engineer. Deploy a full-stack application on Cloud Run with AlloyDB and proper IAM for the following project.

## Project Context

{{PROJECT_SPEC}}

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
