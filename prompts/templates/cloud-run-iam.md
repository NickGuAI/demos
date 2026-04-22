# Cloud Run + IAM Deployment Prompt

You are a GCP engineer. Set up Cloud Run with proper IAM configuration for the following project.

## Project Context

{{PROJECT_SPEC}}

## Requirements

### 1. Service Account
Create a dedicated Cloud Run service account:
```bash
gcloud iam service-accounts create {{SERVICE_NAME}}-sa \
  --display-name="{{SERVICE_NAME}} Cloud Run SA"
```

### 2. IAM Bindings

#### Project-level roles for the Cloud Run SA:
```bash
# Allow the SA to be used by Cloud Run
gcloud iam service-accounts add-iam-policy-binding \
  {{SERVICE_NAME}}-sa@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --member={{DEPLOYER_MEMBER}} \
  --role=roles/iam.serviceAccountUser
```

#### Service-level access (choose based on requirements):
```bash
# Public access (if needed):
gcloud run services add-iam-policy-binding {{SERVICE_NAME}} \
  --member=allUsers \
  --role=roles/run.invoker \
  --region={{REGION}}

# Service-to-service access (if needed):
gcloud run services add-iam-policy-binding {{SERVICE_NAME}} \
  --member=serviceAccount:{{CALLER_SA}} \
  --role=roles/run.invoker \
  --region={{REGION}}
```

### 3. Container Image
```bash
gcloud artifacts repositories create {{REPO_NAME}} \
  --repository-format=docker \
  --location={{REGION}}

gcloud builds submit \
  --tag us-docker.pkg.dev/{{PROJECT_ID}}/{{REPO_NAME}}/{{SERVICE_NAME}}
```

### 4. Cloud Run Deployment
```bash
gcloud run deploy {{SERVICE_NAME}} \
  --image=us-docker.pkg.dev/{{PROJECT_ID}}/{{REPO_NAME}}/{{SERVICE_NAME}}:latest \
  --region={{REGION}} \
  --service-account={{SERVICE_NAME}}-sa@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --port={{PORT}} \
  --memory={{MEMORY}} \
  --cpu={{CPU}} \
  --min-instances={{MIN_INSTANCES}} \
  --max-instances={{MAX_INSTANCES}} \
  --set-env-vars={{ENV_VARS}} \
  {{ACCESS_FLAG}}
```

## Output

Produce a deployment script (`deploy.sh`) that:
1. Creates the service account
2. Applies all IAM bindings
3. Builds and pushes the container image
4. Deploys to Cloud Run with the dedicated SA
5. Verifies the deployment and IAM configuration

## Constraints
- Never use the default Compute Engine SA for Cloud Run
- Document every IAM binding with its purpose
- Use `--allow-unauthenticated` only for public-facing services
- For internal services, grant `roles/run.invoker` only to specific SAs
