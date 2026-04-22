# gcloud projects add-iam-policy-binding

> Source: https://docs.cloud.google.com/sdk/gcloud/reference/projects/add-iam-policy-binding
> Archived: 2026-04-21

## Command

```
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member=MEMBER \
  --role=ROLE \
  [--condition=CONDITION]
```

Grants a project-level IAM role to a principal.

## Required Arguments

| Argument | Description |
|----------|-------------|
| `PROJECT_ID` | GCP project ID |
| `--member=MEMBER` | Principal (user, SA, group) |
| `--role=ROLE` | IAM role to grant |

## Optional Flags

| Flag | Description |
|------|-------------|
| `--condition=CONDITION` | IAM condition expression (title, expression, description) |

## Examples

### Grant AlloyDB client role to a service account
```bash
gcloud projects add-iam-policy-binding my-project \
  --member=serviceAccount:my-sa@my-project.iam.gserviceaccount.com \
  --role=roles/alloydb.client
```

### Grant Cloud Run admin role
```bash
gcloud projects add-iam-policy-binding my-project \
  --member=user:admin@company.com \
  --role=roles/run.admin
```

### Grant with condition
```bash
gcloud projects add-iam-policy-binding my-project \
  --member=serviceAccount:deploy-sa@my-project.iam.gserviceaccount.com \
  --role=roles/run.admin \
  --condition='title=expire-2026,expression=request.time < timestamp("2026-12-31T00:00:00Z")'
```

## Common Project-Level Roles for GCP Augmentation

| Role | When to Use |
|------|-------------|
| `roles/alloydb.client` | SA connecting to AlloyDB via Auth Proxy |
| `roles/alloydb.databaseUser` | SA authenticating to AlloyDB with IAM |
| `roles/run.admin` | Managing Cloud Run services |
| `roles/iam.serviceAccountUser` | Deploying as / acting as another SA |
| `roles/secretmanager.secretAccessor` | Accessing secrets from Secret Manager |
| `roles/compute.networkUser` | Using VPC connectors |
| `roles/serviceusage.serviceUsageConsumer` | Required for AlloyDB Auth Proxy |

## Notes

- Project-level bindings apply to all resources of that type within the project
- Prefer resource-level bindings (e.g., on a specific Cloud Run service) for least privilege
- Use conditions to scope time-limited or attribute-based access
