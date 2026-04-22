# Cloud Run Deployment Prompt

You are a GCP infrastructure engineer. Set up a Cloud Run deployment for the following project.

## Project Context

{{PROJECT_SPEC}}

## Requirements

Deploy this project as a Cloud Run service with:

### 1. Container Image
- Build a Dockerfile for the application
- Push to Artifact Registry: `us-docker.pkg.dev/{{PROJECT_ID}}/{{REPO_NAME}}/{{SERVICE_NAME}}`
- Use multi-stage build to minimize image size

### 2. Cloud Run Service
```bash
gcloud run deploy {{SERVICE_NAME}} \
  --image=us-docker.pkg.dev/{{PROJECT_ID}}/{{REPO_NAME}}/{{SERVICE_NAME}}:latest \
  --region={{REGION}} \
  --port={{PORT}} \
  --memory={{MEMORY}} \
  --cpu={{CPU}} \
  --min-instances={{MIN_INSTANCES}} \
  --max-instances={{MAX_INSTANCES}} \
  --set-env-vars={{ENV_VARS}} \
  {{ACCESS_FLAG}}
```

### 3. Service Account
Create a dedicated service account with least-privilege roles:
```bash
gcloud iam service-accounts create {{SERVICE_NAME}}-sa \
  --display-name="{{SERVICE_NAME}} Cloud Run SA"
```

### 4. Artifact Registry Repository
```bash
gcloud artifacts repositories create {{REPO_NAME}} \
  --repository-format=docker \
  --location={{REGION}}
```

## Output

Produce a deployment script (`deploy.sh`) that:
1. Builds and pushes the container image
2. Creates the service account if it doesn't exist
3. Deploys to Cloud Run with the configuration above
4. Outputs the service URL

## Constraints
- Use `gen2` execution environment for full Linux support
- Set appropriate health check if the app has a `/health` endpoint
- Configure concurrency based on the app's threading model
