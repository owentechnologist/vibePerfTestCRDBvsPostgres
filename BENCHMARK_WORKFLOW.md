# Performance Benchmark Workflow

Complete workflow for running CockroachDB vs Azure PostgreSQL performance benchmarks.

## Overview

This guide covers the complete process from cluster deployment through benchmark execution and analysis.

## Prerequisites

- Python 3.8+
- `psycopg2-binary` package (`pip install psycopg2-binary`)
- CockroachDB Cloud account (for CRDB cluster)
- Azure account with PostgreSQL Flexible Server (for comparison)
- Network access to both database clusters

## Workflow Options

### Option A: Deploy CockroachDB via Web UI (Recommended for Azure)

**Use this option when:**
- Deploying ADVANCED cluster on Azure with single region and 3 nodes
- The `ccloud` CLI doesn't support your desired configuration

**Steps:**

#### 1. Deploy CockroachDB Cluster via Web UI

Follow the detailed guide: **[CRDB_WEB_UI_DEPLOYMENT.md](./CRDB_WEB_UI_DEPLOYMENT.md)**

**Quick summary:**
1. Go to https://cockroachlabs.cloud/
2. Create new cluster:
   - Plan: **ADVANCED**
   - Cloud: **Azure**
   - Region: **westus2** (or your preferred region)
   - Nodes: **3**
   - vCPUs per node: **8**
   - Storage per node: **500 GiB**
3. Wait for cluster to be ready (~15-20 minutes)
4. Get connection string from web console

#### 2. Get Connection String

Use the helper script to automatically generate the connection string with correct CA certificate paths:

```bash
python3 get_crdb_connection.py
```

The script will:
- List your available clusters
- Prompt for cluster name, database, and username
- Use `ccloud` CLI to generate the connection string with CA cert path
- Prompt for your SQL password
- Save to `crdb_connection.txt` with secure permissions

**Alternative - Manual approach:**
```bash
# Get connection string from ccloud CLI
ccloud cluster connection-string <cluster-name> \
  --database perftest \
  --sql-user perftest_user \
  --os MAC  # Or LINUX, WINDOWS

# Then manually add password and save to file
```

#### 3. Validate Connection

```bash
python3 validate_crdb_connection.py crdb_connection.txt
```

Expected output:
```
✅ Connection validated successfully!
✅ User has necessary permissions for benchmarking
```

#### 4. Run Benchmarks

```bash
python3 benchmark.py \
  --crdb "$(cat crdb_connection.txt)" \
  --pg "postgresql://user:pass@azure-pg-host:5432/perftest" \
  --output-dir ./outputs
```

#### 5. Review Results

Results are saved in `./outputs/` directory:
- `comparison_summary_<timestamp>.json` - Detailed metrics
- Console output shows performance comparison

#### 6. Cleanup (Important!)

Delete the cluster to avoid charges:

**Via Web UI:**
1. Go to https://cockroachlabs.cloud/
2. Select your cluster
3. Settings → Delete cluster

**Via CLI:**
```bash
# List clusters to get ID
ccloud cluster list

# Delete cluster
ccloud cluster delete <cluster-id> --yes
```

---

### Option B: Deploy CockroachDB via CLI (GCP/AWS)

**Use this option when:**
- Using GCP or AWS cloud providers
- Using STANDARD plan (single region, 3 nodes)

**Steps:**

#### 1. Configure Cluster Settings

Edit `cluster_config.yaml`:

```yaml
cockroachdb:
  cluster_name: "perftest-crdb-2026q2"
  cloud_provider: "gcp"  # or "aws"
  plan: "standard"
  regions:
    - "us-east1"  # GCP region
  nodes:
    provisioned_vcpus: 24
    storage_gib_limit: 1500
  database:
    name: "perftest"
    sql_user: "perftest_user"
```

#### 2. Deploy Cluster

```bash
python3 deploy_crdb.py --config cluster_config.yaml
```

The script will:
- Create the cluster
- Wait for it to be ready
- Save connection string to `crdb_connection.txt`

#### 3. Validate Connection

```bash
python3 validate_crdb_connection.py crdb_connection.txt
```

#### 4. Run Benchmarks

```bash
python3 benchmark.py \
  --crdb "$(cat crdb_connection.txt)" \
  --pg "postgresql://user:pass@azure-pg-host:5432/perftest" \
  --output-dir ./outputs
```

#### 5. Cleanup

```bash
# Get cluster ID from deployment output or list
ccloud cluster list

# Delete cluster
python3 deploy_crdb.py --cleanup --cluster-id <cluster-id>
```

---

## Azure PostgreSQL Setup

### Deploy Azure PostgreSQL Flexible Server

Use the Azure Portal or CLI:

```bash
az postgres flexible-server create \
  --name perftest-pg-2026q2 \
  --resource-group <resource-group> \
  --location westus2 \
  --admin-user perftest_user \
  --admin-password <password> \
  --sku-name Standard_D8ds_v4 \
  --tier GeneralPurpose \
  --storage-size 512 \
  --version 14
```

### Get PostgreSQL Connection String

```bash
az postgres flexible-server show-connection-string \
  --server-name perftest-pg-2026q2 \
  --database-name perftest \
  --admin-user perftest_user
```

Save to file:
```bash
cat > pg_connection.txt << 'EOF'
postgresql://perftest_user:<password>@perftest-pg-2026q2.postgres.database.azure.com:5432/perftest?sslmode=require
EOF
```

---

## Running Benchmarks

### Standard Benchmark Run

```bash
python3 benchmark.py \
  --crdb "$(cat crdb_connection.txt)" \
  --pg "$(cat pg_connection.txt)" \
  --output-dir ./outputs
```

### Custom Configuration

```bash
python3 benchmark.py \
  --crdb "$(cat crdb_connection.txt)" \
  --pg "$(cat pg_connection.txt)" \
  --tables 20 \
  --rows-per-table 5000000 \
  --workers 16 \
  --output-dir ./outputs
```

### Benchmark Parameters

- `--tables`: Number of tables to create (default: 20)
- `--rows-per-table`: Rows per table (default: 5,000,000)
- `--workers`: Concurrent workers for load testing (default: 16)
- `--output-dir`: Directory for results (default: ./outputs)

---

## Understanding Results

### Output Files

The benchmark creates:

1. **JSON Results**: `outputs/comparison_summary_<timestamp>.json`
   - Detailed metrics for all operations
   - Percentile latencies (p50, p95, p99)
   - Throughput measurements
   - Table sizes and row counts

2. **Console Output**: Real-time progress and summary

### Key Metrics

**Schema Creation:**
- Time to create all tables and indexes

**Data Loading:**
- Bulk INSERT performance
- Rows inserted per second

**Query Performance:**
- SELECT (point queries, range scans, aggregations)
- INSERT (single row, batch)
- UPDATE (single row, batch)
- DELETE (single row, batch)

**Latencies:**
- p50 (median)
- p95 (95th percentile)
- p99 (99th percentile)

### Sample Output

```
======================================================================
FINAL COMPARISON SUMMARY
======================================================================

Schema Creation:
  CockroachDB:  45.2s
  PostgreSQL:   38.1s
  Winner:       PostgreSQL (15.7% faster)

Data Loading (100M rows):
  CockroachDB:  892.3s (112K rows/sec)
  PostgreSQL:   654.2s (153K rows/sec)
  Winner:       PostgreSQL (26.7% faster)

Point SELECT (p95 latency):
  CockroachDB:  12.3ms
  PostgreSQL:   8.7ms
  Winner:       PostgreSQL (29.3% faster)

...
```

---

## Troubleshooting

### Connection Issues

**CockroachDB:**
```bash
# Validate connection
python3 validate_crdb_connection.py crdb_connection.txt

# Check cluster status
ccloud cluster list
ccloud cluster status <cluster-id>
```

**Azure PostgreSQL:**
```bash
# Test connection
psql "$(cat pg_connection.txt)" -c "SELECT version();"

# Check server status
az postgres flexible-server show --name perftest-pg-2026q2 --resource-group <rg>
```

### Performance Issues

1. **Verify cluster is healthy:**
   - Check CockroachDB Cloud console
   - Review Azure PostgreSQL metrics

2. **Check network latency:**
   - Run benchmarks from same region as databases
   - Use Azure VM in same region for best results

3. **Resource utilization:**
   - Monitor CPU and memory usage
   - Check for storage bottlenecks

### Common Errors

**"Connection refused":**
- Check IP allowlist/firewall rules
- Verify connection string format
- Ensure cluster is in 'Ready' state

**"Permission denied":**
- Verify user has CREATE/INSERT/UPDATE/DELETE permissions
- Run validation script to check permissions

**"SSL error":**
- Use correct SSL mode: `sslmode=verify-full` or `sslmode=require`
- Check certificate configuration

---

## Cost Management

### CockroachDB Cloud

**Approximate costs** (3-node ADVANCED cluster, 8 vCPUs per node):
- **$2.50-3.50 per hour**
- **$60-84 per day**

**To minimize costs:**
1. Deploy only when ready to benchmark
2. Delete immediately after completion
3. Use `--auto-cleanup` flag if using CLI deployment:
   ```bash
   python3 deploy_crdb.py --config cluster_config.yaml --auto-cleanup
   ```

### Azure PostgreSQL

**Approximate costs** (D8ds_v4, 8 vCPUs, 512 GiB):
- **$1.50-2.50 per hour**
- **$36-60 per day**

**To minimize costs:**
1. Use Flexible Server (not Single Server)
2. Stop when not in use (Flexible Server supports stop/start)
3. Delete after benchmarking

---

## Best Practices

### Before Running Benchmarks

1. ✅ Validate all connections
2. ✅ Verify cluster health and status
3. ✅ Run from same Azure region as databases
4. ✅ Check available disk space for results
5. ✅ Estimate runtime (2-4 hours for full benchmark)

### During Benchmarks

1. ✅ Monitor cluster metrics in cloud consoles
2. ✅ Watch for errors in console output
3. ✅ Don't interrupt unless necessary (data loading takes time)

### After Benchmarks

1. ✅ Save results to permanent storage
2. ✅ Delete clusters to stop billing
3. ✅ Review metrics and analyze performance
4. ✅ Document any anomalies or issues

---

## Quick Reference

### Deploy CRDB (Web UI)
1. https://cockroachlabs.cloud/ → Create Cluster
2. Azure, ADVANCED, westus2, 3 nodes, 8 vCPUs, 500 GiB
3. Save connection string

### Validate Connections
```bash
python3 validate_crdb_connection.py crdb_connection.txt
psql "$(cat pg_connection.txt)" -c "SELECT 1;"
```

### Run Benchmark
```bash
python3 benchmark.py \
  --crdb "$(cat crdb_connection.txt)" \
  --pg "$(cat pg_connection.txt)" \
  --output-dir ./outputs
```

### Cleanup
```bash
# CockroachDB - via web UI or:
ccloud cluster delete <cluster-id> --yes

# Azure PostgreSQL
az postgres flexible-server delete \
  --name perftest-pg-2026q2 \
  --resource-group <rg> \
  --yes
```

---

## Additional Resources

- [CockroachDB Web UI Deployment Guide](./CRDB_WEB_UI_DEPLOYMENT.md)
- [CockroachDB Cloud Docs](https://www.cockroachlabs.com/docs/cockroachcloud/)
- [Azure PostgreSQL Docs](https://docs.microsoft.com/azure/postgresql/)
- [Benchmark Script Documentation](./benchmark.py) (see docstring)
