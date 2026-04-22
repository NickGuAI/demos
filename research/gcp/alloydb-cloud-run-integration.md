# AlloyDB + Cloud Run Integration

> Source: https://docs.cloud.google.com/alloydb/docs/quickstart/integrate-cloud-run
> Archived: 2026-04-21

## Overview

Cloud Run services connect to AlloyDB via the instance's private IP through VPC networking. AlloyDB does not expose public IPs by default, so Cloud Run must have VPC egress configured.

## Prerequisites

- GCP project with billing enabled
- An AlloyDB cluster and primary instance
- Required IAM roles: Compute Network Admin, AlloyDB Admin, Cloud Run Admin
- APIs enabled: Compute Engine, Cloud Run, AlloyDB, Service Networking, Cloud Build, Artifact Registry

## Architecture

```
┌─────────────┐     HTTPS      ┌─────────────────┐    Private IP    ┌─────────────┐
│   Client     │ ──────────────→│   Cloud Run      │ ───────────────→│   AlloyDB    │
│  (browser)   │                │   Service        │   (VPC egress)  │   Instance   │
└─────────────┘                └─────────────────┘                  └─────────────┘
                                       │
                                       │ VPC Direct Egress
                                       ▼
                               ┌─────────────────┐
                               │   VPC Network    │
                               │  (default or     │
                               │   custom)        │
                               └─────────────────┘
```

## Steps

### 1. Create database
Using AlloyDB Studio or `psql` via Auth Proxy:
```sql
CREATE DATABASE mydb;
```

### 2. Configure Cloud Run VPC egress
In deploy command or console:
- Select "Connect to a VPC for outbound traffic"
- Choose "Send traffic directly to a VPC"
- Select the same network/subnet as your AlloyDB cluster

### 3. Set environment variables on Cloud Run

| Env Var | Value | Notes |
|---------|-------|-------|
| `DB_NAME` | database name | e.g., `mydb` |
| `DB_USER` | database user | e.g., `postgres` |
| `DB_PASS` | database password | use Secret Manager in production |
| `DB_PORT` | `5432` | standard PostgreSQL port |
| `INSTANCE_HOST` | private IP of AlloyDB | no port suffix |

### 4. Build and push container image
```bash
gcloud builds submit --tag us-docker.pkg.dev/PROJECT/REPO/IMAGE
```

### 5. Deploy to Cloud Run
```bash
gcloud run deploy SERVICE_NAME \
  --image=us-docker.pkg.dev/PROJECT/REPO/IMAGE \
  --region=REGION \
  --allow-unauthenticated \
  --set-env-vars=DB_NAME=mydb,DB_USER=postgres,DB_PORT=5432,INSTANCE_HOST=PRIVATE_IP \
  --set-secrets=DB_PASS=db-password:latest \
  --vpc-egress=private-ranges-only \
  --network=NETWORK \
  --subnet=SUBNET
```

## Connection Method: Direct VPC vs Auth Proxy Sidecar

### Direct VPC (recommended for simplicity)
- Cloud Run connects directly to AlloyDB private IP
- Requires VPC Direct Egress or Serverless VPC Access connector
- Application uses standard PostgreSQL connection string

### Auth Proxy Sidecar
- Runs AlloyDB Auth Proxy as a Cloud Run sidecar container
- Handles TLS encryption and IAM-based authentication
- Application connects to `localhost:5432`
- See: alloydb-auth-proxy.md

## Important Notes

- AlloyDB and Cloud Run must be in the same region (or connected via VPC peering)
- Use Secret Manager for database passwords; never put them in env vars directly
- The AlloyDB private IP is stable for the lifetime of the instance
- VPC Direct Egress is the newer, simpler alternative to VPC connectors
