# gcloud run deploy

> Source: https://docs.cloud.google.com/sdk/gcloud/reference/run/deploy
> Archived: 2026-04-21

## Command

```
gcloud run deploy [SERVICE] --image=IMAGE [flags]
```

Deploys a container to Cloud Run as a managed service.

## Key Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--image=IMAGE` | Container image to deploy (required) | - |
| `--region=REGION` | GCP region | prompt / config |
| `--platform=managed` | Target platform | `managed` |
| `--service-account=SA` | Service account email for the revision | project default compute SA |
| `--port=PORT` | Container port to receive requests | `8080` |
| `--memory=MEMORY` | Memory limit per instance (e.g., `512Mi`, `1Gi`) | `512Mi` |
| `--cpu=CPU` | CPU limit per instance (e.g., `1`, `2`) | `1` |
| `--min-instances=N` | Minimum number of instances | `0` |
| `--max-instances=N` | Maximum number of instances | `100` |
| `--set-env-vars=K=V,...` | Environment variables | - |
| `--set-secrets=K=SECRET:VERSION` | Mount secrets from Secret Manager | - |
| `--vpc-connector=CONNECTOR` | VPC connector for outbound traffic | - |
| `--vpc-egress=SETTING` | VPC egress setting (`all-traffic` or `private-ranges-only`) | `private-ranges-only` |
| `--allow-unauthenticated` | Allow public (unauthenticated) access | denied |
| `--ingress=SETTING` | Ingress restriction (`all`, `internal`, `internal-and-cloud-load-balancing`) | `all` |
| `--add-cloudsql-instances=INST` | Cloud SQL instances to connect | - |
| `--timeout=DURATION` | Request timeout | `300s` |
| `--concurrency=N` | Max concurrent requests per instance | `80` |
| `--cpu-throttling` / `--no-cpu-throttling` | Throttle CPU when no requests | throttled |
| `--execution-environment=ENV` | `gen1` or `gen2` | `gen1` |
| `--tag=TAG` | Traffic tag for this revision | - |

## Examples

### Basic deploy
```bash
gcloud run deploy my-service \
  --image=gcr.io/my-project/my-image:latest \
  --region=us-central1 \
  --allow-unauthenticated
```

### Deploy with service account and env vars
```bash
gcloud run deploy my-service \
  --image=us-docker.pkg.dev/my-project/repo/image:v1 \
  --region=us-central1 \
  --service-account=my-sa@my-project.iam.gserviceaccount.com \
  --set-env-vars=DB_HOST=10.0.0.5,DB_PORT=5432 \
  --memory=1Gi \
  --cpu=2 \
  --min-instances=1 \
  --max-instances=10
```

### Deploy with VPC connector (for AlloyDB/private resources)
```bash
gcloud run deploy my-service \
  --image=gcr.io/my-project/my-image \
  --region=us-central1 \
  --vpc-connector=my-vpc-connector \
  --vpc-egress=private-ranges-only \
  --set-env-vars=INSTANCE_HOST=10.x.x.x,DB_PORT=5432
```

### Deploy with secrets
```bash
gcloud run deploy my-service \
  --image=gcr.io/my-project/my-image \
  --set-secrets=DB_PASS=db-password:latest
```

## Notes

- `--allow-unauthenticated` sets an IAM binding granting `roles/run.invoker` to `allUsers`
- VPC connector is required for reaching private-IP resources (AlloyDB, Memorystore, etc.)
- `--set-secrets` requires the service account to have `roles/secretmanager.secretAccessor`
- Second-gen execution environment (`gen2`) supports full Linux syscalls, network file systems
- Container must listen on the port specified by `--port` (or `PORT` env var)
