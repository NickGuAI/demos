# gcloud run services add-iam-policy-binding

> Source: https://docs.cloud.google.com/sdk/gcloud/reference/run/services/add-iam-policy-binding
> Archived: 2026-04-21

## Command

```
gcloud run services add-iam-policy-binding SERVICE \
  --member=MEMBER \
  --role=ROLE \
  [--region=REGION]
```

Adds an IAM policy binding to a Cloud Run service without removing existing bindings.

## Required Arguments

| Argument | Description |
|----------|-------------|
| `SERVICE` | Name of the Cloud Run service |
| `--member=MEMBER` | Principal to grant the role to |
| `--role=ROLE` | IAM role to assign |

## Member Formats

| Type | Format |
|------|--------|
| All users (public) | `allUsers` |
| All authenticated | `allAuthenticatedUsers` |
| User account | `user:email@example.com` |
| Service account | `serviceAccount:sa@project.iam.gserviceaccount.com` |
| Group | `group:group@example.com` |
| Domain | `domain:example.com` |

## Common Roles for Cloud Run Services

| Role | Description |
|------|-------------|
| `roles/run.invoker` | Can invoke/call the service |
| `roles/run.admin` | Full control of the service |
| `roles/run.viewer` | Read-only access to service config |

## Examples

### Grant public access
```bash
gcloud run services add-iam-policy-binding my-service \
  --member=allUsers \
  --role=roles/run.invoker \
  --region=us-central1
```

### Grant service-to-service access
```bash
gcloud run services add-iam-policy-binding backend-service \
  --member=serviceAccount:frontend-sa@my-project.iam.gserviceaccount.com \
  --role=roles/run.invoker \
  --region=us-central1
```

### Grant specific user access
```bash
gcloud run services add-iam-policy-binding my-service \
  --member=user:developer@company.com \
  --role=roles/run.invoker \
  --region=us-central1
```

## Notes

- This is additive; existing bindings are preserved
- `--allow-unauthenticated` on `gcloud run deploy` is equivalent to binding `allUsers` to `roles/run.invoker`
- Service-to-service auth: the calling service's SA needs `roles/run.invoker` on the target service
