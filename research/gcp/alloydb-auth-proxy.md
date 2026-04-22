# AlloyDB Auth Proxy

> Source: https://docs.cloud.google.com/alloydb/docs/auth-proxy/connect
> Archived: 2026-04-21

## Overview

The AlloyDB Auth Proxy provides secure, encrypted (mTLS 1.3) connections to AlloyDB instances. It handles authentication via IAM automatically, removing the need for IP allowlists or SSL certificate management.

## Installation

```bash
# Linux (amd64)
wget https://storage.googleapis.com/alloydb-auth-proxy/v1.14.2/alloydb-auth-proxy.linux.amd64 \
  -O alloydb-auth-proxy
chmod +x alloydb-auth-proxy

# macOS (arm64)
curl -o alloydb-auth-proxy \
  https://storage.googleapis.com/alloydb-auth-proxy/v1.14.2/alloydb-auth-proxy.darwin.arm64
chmod +x alloydb-auth-proxy

# Docker
docker pull gcr.io/alloydb-connectors/alloydb-auth-proxy:latest
```

## Instance URI Format

```
projects/PROJECT_ID/locations/REGION/clusters/CLUSTER_ID/instances/INSTANCE_ID
```

List all instance URIs:
```bash
gcloud alloydb instances list --cluster=CLUSTER --region=REGION \
  --format="value(name)"
```

## IAM Requirements

The principal running the Auth Proxy needs:

| Role | Purpose |
|------|---------|
| `roles/alloydb.client` | Connect to AlloyDB instances |
| `roles/serviceusage.serviceUsageConsumer` | Service usage verification |

## Key Flags

| Flag | Description |
|------|-------------|
| `--credentials-file=PATH` | SA JSON key file |
| `--port=PORT` | Local listener port (default: 5432) |
| `--address=ADDR` | Local listener address (default: 127.0.0.1) |
| `--auto-iam-authn` | Enable automatic IAM database authentication |
| `--psc` | Connect via Private Service Connect |
| `--public-ip` | Use instance's public IP |

## Usage Examples

### Basic
```bash
./alloydb-auth-proxy \
  "projects/myproject/locations/us-central1/clusters/mycluster/instances/myprimary"
```

### With service account key
```bash
./alloydb-auth-proxy \
  "projects/myproject/locations/us-central1/clusters/mycluster/instances/myprimary" \
  --credentials-file=sa-key.json
```

### Custom port
```bash
./alloydb-auth-proxy \
  "projects/myproject/locations/us-central1/clusters/mycluster/instances/myprimary?port=5000"
```

### With IAM auto-auth
```bash
./alloydb-auth-proxy \
  "projects/myproject/locations/us-central1/clusters/mycluster/instances/myprimary" \
  --auto-iam-authn
```

## Cloud Run Sidecar Deployment

Deploy the Auth Proxy as a sidecar container in Cloud Run:

```yaml
# service.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: my-service
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/container-dependencies: '{"app":["alloydb-auth-proxy"]}'
    spec:
      containers:
        - name: app
          image: IMAGE
          env:
            - name: DB_HOST
              value: "127.0.0.1"
            - name: DB_PORT
              value: "5432"
        - name: alloydb-auth-proxy
          image: gcr.io/alloydb-connectors/alloydb-auth-proxy:latest
          args:
            - "projects/PROJECT/locations/REGION/clusters/CLUSTER/instances/INSTANCE"
            - "--port=5432"
            - "--auto-iam-authn"
```

## Client Connection (via proxy)

Application connects to `localhost:5432` as if it were a local PostgreSQL:

```python
# Python (SQLAlchemy)
engine = sqlalchemy.create_engine(
    "postgresql+pg8000://user:pass@127.0.0.1:5432/dbname"
)
```

```javascript
// Node.js
const pool = new Pool({
  host: '127.0.0.1',
  port: 5432,
  user: process.env.DB_USER,
  password: process.env.DB_PASS,
  database: process.env.DB_NAME,
});
```

## Network Requirements

- Outbound access to port 5433 (AlloyDB instances)
- Outbound access to port 443 (HTTPS for auth)
- Network visibility to AlloyDB VPC (VPN/Interconnect if external)
- Compute Engine: `cloud-platform` access scope required
