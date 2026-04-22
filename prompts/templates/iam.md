# IAM Configuration Prompt

You are a GCP IAM security engineer. Configure IAM roles and bindings for the following project.

## Project Context

{{PROJECT_SPEC}}

## Requirements

Set up IAM with least-privilege principles:

### 1. Service Accounts
Create dedicated service accounts for each workload:
```bash
gcloud iam service-accounts create {{SA_NAME}} \
  --display-name="{{SA_DISPLAY_NAME}}" \
  --project={{PROJECT_ID}}
```

### 2. Project-Level Role Bindings
Grant only the roles each service account needs:
```bash
gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:{{SA_EMAIL}} \
  --role={{ROLE}}
```

### 3. Service Account Impersonation
If any principal needs to deploy as or act as a service account:
```bash
gcloud iam service-accounts add-iam-policy-binding {{SA_EMAIL}} \
  --member={{DEPLOYER_MEMBER}} \
  --role=roles/iam.serviceAccountUser
```

### 4. Access Patterns to Configure

For each access pattern in the project, determine:
- **Who** needs access (user, SA, group, allUsers)
- **What** they need access to (project, service, resource)
- **Which role** provides least-privilege access

## Output

Produce an IAM setup script (`setup-iam.sh`) that:
1. Creates all required service accounts
2. Grants project-level role bindings
3. Configures service account impersonation where needed
4. Documents each binding with inline comments explaining why

## Constraints
- Never grant `roles/owner` or `roles/editor` to service accounts
- Prefer resource-level bindings over project-level where possible
- Use IAM conditions for time-limited or scoped access
- Document the purpose of every binding
