# AlloyDB IAM Roles and Permissions

> Source: https://docs.cloud.google.com/iam/docs/roles-permissions/alloydb
> Archived: 2026-04-21

## Predefined Roles

### AlloyDB Admin (`roles/alloydb.admin`)
Full administrative access to all AlloyDB resources.
- `alloydb.clusters.*` (create, delete, get, list, update, restore)
- `alloydb.instances.*` (create, delete, get, list, update, restart, failover)
- `alloydb.backups.*` (create, delete, get, list, update)
- `alloydb.users.*` (create, delete, get, list, update)
- `alloydb.databases.*`
- `alloydb.locations.*`
- `alloydb.operations.*`
- **Use when**: Full infrastructure management (create/destroy clusters, instances, backups)

### AlloyDB Editor (`roles/alloydb.editor`)
Read/write access to AlloyDB resources (cannot create/delete clusters).
- Most `alloydb.*` permissions except destructive cluster operations
- **Use when**: Day-to-day operational management

### AlloyDB Viewer (`roles/alloydb.viewer`)
Read-only access.
- `alloydb.clusters.get`, `alloydb.clusters.list`
- `alloydb.instances.get`, `alloydb.instances.list`
- `alloydb.backups.get`, `alloydb.backups.list`
- **Use when**: Monitoring, dashboards, read-only visibility

### AlloyDB Client (`roles/alloydb.client`)
Application-level database connectivity.
- `alloydb.instances.connect`
- **Use when**: Service accounts that connect to AlloyDB via Auth Proxy
- **Required for**: Auth Proxy connections

### AlloyDB Database User (`roles/alloydb.databaseUser`)
IAM-based database login.
- `alloydb.users.login`
- **Use when**: Service accounts or users authenticating to AlloyDB with IAM credentials
- **Required for**: IAM database authentication

## Role Selection Guide

```
┌──────────────────────────────────────────────────────┐
│           Which AlloyDB IAM role do I need?           │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Managing clusters/instances/backups?                 │
│    ├── Full CRUD ──────────→ roles/alloydb.admin     │
│    └── Operational only ───→ roles/alloydb.editor    │
│                                                      │
│  Connecting to a database?                           │
│    ├── Via Auth Proxy ─────→ roles/alloydb.client    │
│    ├── Via IAM auth ───────→ roles/alloydb.databaseUser │
│    └── Both (recommended) ─→ both roles              │
│                                                      │
│  Read-only monitoring?                               │
│    └── Dashboard/alerts ───→ roles/alloydb.viewer    │
│                                                      │
└──────────────────────────────────────────────────────┘
```

## Common Combinations for Cloud Run + AlloyDB

| Service Account Role | Combination | Purpose |
|---------------------|-------------|---------|
| Cloud Run app SA | `alloydb.client` + `serviceusage.serviceUsageConsumer` | Connect via VPC/Auth Proxy with password |
| Cloud Run app SA | `alloydb.client` + `alloydb.databaseUser` + `serviceusage.serviceUsageConsumer` | Connect via Auth Proxy with IAM auth |
| Deploy SA | `alloydb.admin` + `run.admin` | Full infra management |
| Monitoring SA | `alloydb.viewer` + `run.viewer` | Read-only dashboards |
