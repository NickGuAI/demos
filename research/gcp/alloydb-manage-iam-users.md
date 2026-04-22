# Managing IAM Authentication for AlloyDB Users

> Source: https://docs.cloud.google.com/alloydb/docs/database-users/manage-iam-auth
> Archived: 2026-04-21

## Overview

IAM authentication supplements standard PostgreSQL user auth. When enabled, users can authenticate via IAM tokens or traditional passwords.

## Enabling IAM Authentication

Set the `alloydb.iam_authentication` database flag to `on`:

```bash
gcloud alloydb instances update INSTANCE_ID \
  --cluster=CLUSTER \
  --region=REGION \
  --database-flags=alloydb.iam_authentication=on
```

Or during instance creation:
```bash
gcloud alloydb instances create INSTANCE_ID \
  --cluster=CLUSTER \
  --region=REGION \
  --instance-type=PRIMARY \
  --cpu-count=2 \
  --database-flags=alloydb.iam_authentication=on
```

## Required IAM Roles (before creating DB user)

Grant these to the principal at the project level:

| Role | Purpose |
|------|---------|
| `roles/alloydb.databaseUser` | Allows database login via IAM |
| `roles/serviceusage.serviceUsageConsumer` | Required for service verification |

```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member=serviceAccount:my-sa@my-project.iam.gserviceaccount.com \
  --role=roles/alloydb.databaseUser

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member=serviceAccount:my-sa@my-project.iam.gserviceaccount.com \
  --role=roles/serviceusage.serviceUsageConsumer
```

## Creating IAM Database Users

### Via gcloud CLI
```bash
gcloud alloydb users create USERNAME \
  --cluster=CLUSTER \
  --region=REGION \
  --type=IAM_BASED
```

Username format:
- User accounts: `user@example.com`
- Service accounts: `my-sa@my-project.iam` (drop `.gserviceaccount.com`)

### Via Console
1. Navigate to AlloyDB cluster > Users
2. "Add user account" > "Cloud IAM"
3. Enter principal identifier

## Granting Database Privileges

New IAM users have no privileges by default. Grant via SQL:

```sql
-- Grant read access
GRANT SELECT ON ALL TABLES IN SCHEMA public TO "my-sa@my-project.iam";

-- Grant read/write
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "my-sa@my-project.iam";

-- Grant on specific table
GRANT ALL ON TABLE users TO "my-sa@my-project.iam";
```

Note: Email-format usernames must be double-quoted in SQL.

## Deleting IAM Users

```bash
gcloud alloydb users delete USERNAME \
  --cluster=CLUSTER \
  --region=REGION
```

## Full Setup Sequence

```
1. Enable alloydb.iam_authentication flag on instance
2. Grant roles/alloydb.databaseUser to the IAM principal
3. Grant roles/serviceusage.serviceUsageConsumer to the IAM principal
4. Create IAM database user (gcloud alloydb users create --type=IAM_BASED)
5. Grant PostgreSQL privileges (GRANT ... TO "username")
6. Connect using IAM token or Auth Proxy with --auto-iam-authn
```
