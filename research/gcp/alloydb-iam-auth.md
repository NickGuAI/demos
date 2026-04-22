# AlloyDB IAM Authentication

> Source: https://docs.cloud.google.com/alloydb/docs/connect-iam
> Archived: 2026-04-21

## Overview

IAM authentication lets users and service accounts connect to AlloyDB using Google Cloud IAM credentials (OAuth 2.0 tokens) instead of database passwords.

## How It Works

1. Principal obtains an OAuth 2.0 access token from Google Cloud
2. Token is used as the PostgreSQL password
3. AlloyDB validates the token against IAM
4. Connection is established if the IAM principal has the correct roles

## Authentication Methods

### Manual (psql)
```bash
PGPASSWORD=$(gcloud auth print-access-token) psql \
  -h INSTANCE_ADDRESS \
  -U USERNAME \
  -d DATABASE
```

### Automatic via Auth Proxy
```bash
./alloydb-auth-proxy INSTANCE_URI --auto-iam-authn
# Then connect without a password:
psql -h 127.0.0.1 -U USERNAME -d DATABASE
```

### Language Connectors
Use AlloyDB language connectors (Go, Java, Python) which handle token refresh automatically.

## Username Format

| Account Type | Database Username |
|-------------|-------------------|
| IAM user | Full email: `user@example.com` |
| Service account | Email minus `.gserviceaccount.com`: `my-sa@my-project.iam` |

## Token Scoping (Optional)

Restrict token scope for enhanced security:
```bash
gcloud auth application-default login \
  --scopes=https://www.googleapis.com/auth/alloydb.login,\
https://www.googleapis.com/auth/cloud-platform,\
https://www.googleapis.com/auth/userinfo.email,\
openid
```

## Required IAM Roles

| Role | Purpose |
|------|---------|
| `roles/alloydb.databaseUser` | Allows IAM-based database login |
| `roles/serviceusage.serviceUsageConsumer` | Service usage verification |

## Prerequisites

- Instance must have `alloydb.iam_authentication=on` database flag
- IAM database user must be created in AlloyDB (see manage-iam-users.md)
- Principal must have the required IAM roles above

## Troubleshooting

| Error | Cause |
|-------|-------|
| "Invalid credentials" | Token expired or wrong scope |
| "Caller does not have required permission" | Missing `alloydb.databaseUser` role |
| "IAM principal does not match database user" | Username format mismatch |
| "Insufficient scopes" | Need `alloydb.login` or `cloud-platform` scope |

Check: Cloud Logging > AlloyDB instance > Alert severity
