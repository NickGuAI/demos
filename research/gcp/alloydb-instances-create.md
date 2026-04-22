# gcloud alloydb instances create

> Source: https://docs.cloud.google.com/sdk/gcloud/reference/alloydb/instances/create
> Archived: 2026-04-21

## Command

```
gcloud alloydb instances create INSTANCE_ID \
  --cluster=CLUSTER \
  --region=REGION \
  --instance-type=INSTANCE_TYPE \
  --cpu-count=CPU_COUNT \
  [flags]
```

Creates a new AlloyDB instance within an existing cluster.

## Required Arguments

| Argument | Description |
|----------|-------------|
| `INSTANCE_ID` | Unique instance identifier |
| `--cluster=CLUSTER` | AlloyDB cluster name |
| `--region=REGION` | GCP region |
| `--instance-type=TYPE` | `PRIMARY` or `READ_POOL` |
| `--cpu-count=N` | Number of CPUs (2, 4, 8, 16, 32, 64, 128) |

## Key Flags

| Flag | Description |
|------|-------------|
| `--availability-type=TYPE` | `REGIONAL` (HA) or `ZONAL` |
| `--database-flags=K=V,...` | PostgreSQL config flags |
| `--assign-inbound-public-ip=ENABLED` | Enable public IP (default: disabled) |
| `--read-pool-node-count=N` | Nodes for READ_POOL instances |
| `--ssl-mode=MODE` | `ENCRYPTED_ONLY` or `ALLOW_UNENCRYPTED_AND_ENCRYPTED` |

## Examples

### Create primary instance
```bash
gcloud alloydb instances create my-primary \
  --cluster=my-cluster \
  --region=us-central1 \
  --instance-type=PRIMARY \
  --cpu-count=2 \
  --availability-type=ZONAL
```

### Create primary with IAM auth enabled
```bash
gcloud alloydb instances create my-primary \
  --cluster=my-cluster \
  --region=us-central1 \
  --instance-type=PRIMARY \
  --cpu-count=2 \
  --database-flags=alloydb.iam_authentication=on
```

### Create read pool
```bash
gcloud alloydb instances create my-read-pool \
  --cluster=my-cluster \
  --region=us-central1 \
  --instance-type=READ_POOL \
  --cpu-count=2 \
  --read-pool-node-count=2
```

## Prerequisites

- An AlloyDB cluster must already exist: `gcloud alloydb clusters create`
- The cluster requires a configured VPC network with Private Services Access
- Required API: `alloydb.googleapis.com`

## Notes

- AlloyDB instances use private IPs by default; public IP is opt-in
- IAM authentication is enabled per-instance via `--database-flags=alloydb.iam_authentication=on`
- PRIMARY instances: one per cluster
- READ_POOL instances: multiple allowed, each with configurable node count
- Minimum CPU is 2; actual machine type is chosen by GCP based on CPU count
