# Cloud Run + AlloyDB Deployment Prompt

You are a GCP engineer. Deploy a Cloud Run service connected to AlloyDB for the following project.

## Project Context

{{PROJECT_SPEC}}

## Architecture

```
┌──────────┐   HTTPS    ┌──────────────┐  Private IP  ┌───────────┐
│  Client  │ ──────────→│  Cloud Run   │ ────────────→│  AlloyDB  │
│          │            │  Service     │  (VPC egress) │  Primary  │
└──────────┘            └──────────────┘              └───────────┘
                              │                            │
                              │ SA: {{SERVICE_NAME}}-sa    │
                              │ Roles:                     │
                              │  - alloydb.client          │
                              │  - serviceusage.consumer   │
                              ▼                            │
                        ┌──────────────┐                   │
                        │ Secret Mgr   │   DB credentials  │
                        │ (DB_PASS)    │───────────────────┘
                        └──────────────┘
```

## Requirements

### 1. AlloyDB Infrastructure
```bash
# VPC + Private Services Access
gcloud compute addresses create alloydb-psa-range \
  --global --purpose=VPC_PEERING --prefix-length=16 \
  --network={{NETWORK_NAME}}

gcloud services vpc-peerings connect \
  --service=servicenetworking.googleapis.com \
  --ranges=alloydb-psa-range --network={{NETWORK_NAME}}

# Cluster + Instance
gcloud alloydb clusters create {{CLUSTER_NAME}} \
  --region={{REGION}} --network={{NETWORK_NAME}} \
  --password={{DB_PASSWORD}}

gcloud alloydb instances create {{INSTANCE_NAME}} \
  --cluster={{CLUSTER_NAME}} --region={{REGION}} \
  --instance-type=PRIMARY --cpu-count={{CPU_COUNT}}
```

### 2. Service Account + IAM
```bash
gcloud iam service-accounts create {{SERVICE_NAME}}-sa \
  --display-name="{{SERVICE_NAME}} Cloud Run SA"

# AlloyDB connectivity
gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:{{SERVICE_NAME}}-sa@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --role=roles/alloydb.client

gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:{{SERVICE_NAME}}-sa@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --role=roles/serviceusage.serviceUsageConsumer

# Secret Manager access
gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:{{SERVICE_NAME}}-sa@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

### 3. Secrets
```bash
echo -n "{{DB_PASSWORD}}" | gcloud secrets create {{SERVICE_NAME}}-db-pass \
  --data-file=- --replication-policy=automatic
```

### 4. Cloud Run with VPC Egress
```bash
gcloud run deploy {{SERVICE_NAME}} \
  --image=us-docker.pkg.dev/{{PROJECT_ID}}/{{REPO_NAME}}/{{SERVICE_NAME}}:latest \
  --region={{REGION}} \
  --service-account={{SERVICE_NAME}}-sa@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --set-env-vars=DB_NAME={{DB_NAME}},DB_USER={{DB_USER}},DB_PORT=5432,INSTANCE_HOST={{ALLOYDB_IP}} \
  --set-secrets=DB_PASS={{SERVICE_NAME}}-db-pass:latest \
  --network={{NETWORK_NAME}} \
  --subnet={{SUBNET_NAME}} \
  --vpc-egress=private-ranges-only \
  --port={{PORT}} \
  --memory={{MEMORY}} \
  {{ACCESS_FLAG}}
```

## Output

Produce a full deployment script (`deploy.sh`) that:
1. Sets up VPC and Private Services Access
2. Creates AlloyDB cluster and instance
3. Creates service account with correct IAM bindings
4. Stores DB credentials in Secret Manager
5. Builds and deploys the Cloud Run service with VPC egress
6. Verifies connectivity

## Constraints
- AlloyDB and Cloud Run must be in the same region
- Use VPC Direct Egress (preferred) or VPC connector for connectivity
- Store DB password in Secret Manager, reference via `--set-secrets`
- The SA needs `alloydb.client` + `serviceusage.serviceUsageConsumer` minimum
