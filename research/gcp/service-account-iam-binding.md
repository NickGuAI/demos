# gcloud iam service-accounts add-iam-policy-binding

> Source: https://docs.cloud.google.com/sdk/gcloud/reference/iam/service-accounts/add-iam-policy-binding
> Archived: 2026-04-21

## Command

```
gcloud iam service-accounts add-iam-policy-binding SA_EMAIL \
  --member=MEMBER \
  --role=ROLE
```

Grants a role on a service account resource to a principal. This controls who can **act as** or **manage** a service account, not what the service account itself can do.

## Required Arguments

| Argument | Description |
|----------|-------------|
| `SA_EMAIL` | Service account email (e.g., `my-sa@proj.iam.gserviceaccount.com`) |
| `--member=MEMBER` | Principal to grant the role to |
| `--role=ROLE` | IAM role to grant on this SA |

## Key Roles

| Role | Description |
|------|-------------|
| `roles/iam.serviceAccountUser` | Allows acting as (impersonating) the SA |
| `roles/iam.serviceAccountTokenCreator` | Can create tokens for the SA |
| `roles/iam.serviceAccountAdmin` | Full admin over the SA resource |

## Examples

### Allow a user to deploy Cloud Run with a specific SA
```bash
gcloud iam service-accounts add-iam-policy-binding \
  cloud-run-sa@my-project.iam.gserviceaccount.com \
  --member=user:deployer@company.com \
  --role=roles/iam.serviceAccountUser
```

### Allow Cloud Build to act as the Cloud Run SA
```bash
gcloud iam service-accounts add-iam-policy-binding \
  cloud-run-sa@my-project.iam.gserviceaccount.com \
  --member=serviceAccount:PROJECT_NUMBER@cloudbuild.gserviceaccount.com \
  --role=roles/iam.serviceAccountUser
```

### Allow one SA to create tokens for another
```bash
gcloud iam service-accounts add-iam-policy-binding \
  target-sa@my-project.iam.gserviceaccount.com \
  --member=serviceAccount:caller-sa@my-project.iam.gserviceaccount.com \
  --role=roles/iam.serviceAccountTokenCreator
```

## Notes

- This is about permissions **on** the SA, not permissions **of** the SA
- To grant permissions **to** the SA, use `gcloud projects add-iam-policy-binding`
- `roles/iam.serviceAccountUser` is needed by anyone deploying a Cloud Run service with `--service-account`
- Without this binding, `gcloud run deploy --service-account=X` will fail with permission denied
