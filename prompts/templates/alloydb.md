# AlloyDB Setup Prompt

You are a GCP database engineer. Set up AlloyDB for PostgreSQL for the following project.

## Project Context

{{PROJECT_SPEC}}

## Requirements

### 1. VPC Network Setup
Ensure a VPC network with Private Services Access:
```bash
# Create VPC (if not using default)
gcloud compute networks create {{NETWORK_NAME}} --subnet-mode=auto

# Allocate IP range for Private Services Access
gcloud compute addresses create alloydb-psa-range \
  --global \
  --purpose=VPC_PEERING \
  --prefix-length=16 \
  --network={{NETWORK_NAME}}

# Create private connection
gcloud services vpc-peerings connect \
  --service=servicenetworking.googleapis.com \
  --ranges=alloydb-psa-range \
  --network={{NETWORK_NAME}}
```

### 2. AlloyDB Cluster
```bash
gcloud alloydb clusters create {{CLUSTER_NAME}} \
  --region={{REGION}} \
  --network={{NETWORK_NAME}} \
  --password={{DB_PASSWORD}}
```

### 3. Primary Instance
```bash
gcloud alloydb instances create {{INSTANCE_NAME}} \
  --cluster={{CLUSTER_NAME}} \
  --region={{REGION}} \
  --instance-type=PRIMARY \
  --cpu-count={{CPU_COUNT}} \
  --availability-type={{AVAILABILITY_TYPE}} \
  --database-flags=alloydb.iam_authentication=on
```

### 4. Database and User Setup
Connect via Auth Proxy and create the application database:
```sql
CREATE DATABASE {{DB_NAME}};
CREATE USER {{DB_USER}} WITH PASSWORD '{{DB_PASSWORD}}';
GRANT ALL PRIVILEGES ON DATABASE {{DB_NAME}} TO {{DB_USER}};
```

### 5. Secret Manager for Credentials
```bash
echo -n "{{DB_PASSWORD}}" | gcloud secrets create {{SECRET_NAME}} \
  --data-file=- \
  --replication-policy=automatic
```

## Output

Produce a database setup script (`setup-alloydb.sh`) that:
1. Creates the VPC network and Private Services Access (if needed)
2. Creates the AlloyDB cluster and primary instance
3. Stores credentials in Secret Manager
4. Documents the instance connection URI

## Constraints
- Use IAM authentication where possible (prefer over password auth)
- Enable `alloydb.iam_authentication` database flag
- Use ZONAL availability for dev/staging, REGIONAL for production
- Minimum CPU: 2 (AlloyDB requirement)
- Store passwords in Secret Manager, never in env vars or code
