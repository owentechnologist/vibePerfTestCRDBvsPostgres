# CockroachDB Cluster Deployment via Web UI

This guide explains how to deploy a CockroachDB cluster using the web UI for configurations not supported by the `ccloud` CLI (such as single-region Azure ADVANCED clusters with 3 nodes).

## Why Use the Web UI?

The `ccloud` CLI enforces Azure ADVANCED clusters to use multi-region deployment with >1 node per region. For a single-region, 3-node cluster on Azure, you must use the CockroachDB Cloud web console.

## Deployment Steps

### 1. Access CockroachDB Cloud Console

Navigate to: **https://cockroachlabs.cloud/**

Log in with your CockroachDB Cloud credentials.

### 2. Create New Cluster

1. Click **"Create Cluster"** button
2. Select **"Advanced"** plan type

### 3. Configure Cloud Provider & Region

1. **Cloud Provider**: Select **Azure**
2. **Region**: Select **West US 2** (westus2)
3. **Multi-region**: Leave **disabled** (single region deployment)

### 4. Configure Cluster Capacity

For benchmark specifications (matching Azure PostgreSQL):

- **Nodes**: **3**
- **vCPUs per node**: **8**
- **Storage per node**: **500 GiB**

**Total cluster capacity:**
- 3 nodes × 8 vCPUs = **24 vCPUs total**
- 3 nodes × 500 GiB = **1,500 GiB total storage**

### 5. Configure Cluster Settings

- **Cluster name**: `perftest-crdb-2026q2` (or your preferred name)
- **CockroachDB version**: Latest stable (or specific version if required)
- **Hardware**: Ensure "Standard" storage tier is selected

### 6. Configure Network & Security

- **IP Allowlist**: Add your IP address or CIDR range
  - For testing: `0.0.0.0/0` (allows all IPs - **use with caution**)
  - For production: Specify your exact IP or VPC CIDR

- **Private connectivity**: Optional (not required for benchmarking)

### 7. Review & Create

1. Review all settings
2. Confirm pricing estimate (~$2.50-3.50/hour for this configuration)
3. Click **"Create cluster"**

### 8. Wait for Cluster Provisioning

- Cluster creation typically takes **15-20 minutes**
- Status will show as "Creating..." then "Ready"
- You can monitor progress in the cluster details page

## Post-Deployment: Get Connection String

### Option A: Using Helper Script (Recommended)

The easiest way to get a connection string with proper CA certificate configuration:

```bash
python3 get_crdb_connection.py
```

This script will:
- List your clusters
- Prompt for cluster name, database, and username
- Generate connection string using `ccloud` CLI with correct CA cert path
- Prompt for password
- Save to `crdb_connection.txt` with secure permissions

See [GET_CONNECTION_STRING.md](./GET_CONNECTION_STRING.md) for detailed documentation.

### Option B: Via Web Console

1. Navigate to your cluster in the web console
2. Click **"Connect"** button
3. Select **"General connection string"**
4. Choose:
   - **Database**: `perftest` (create if needed)
   - **User**: `perftest_user` (create if needed)
   - **SQL client**: PostgreSQL-compatible driver
5. Copy the connection string

**Example connection string format:**
```
postgresql://perftest_user:<password>@<cluster-host>:26257/perftest?sslmode=verify-full
```

### Option B: Via CLI (after web deployment)

Once the cluster is deployed via web UI, you can use `ccloud` CLI to get connection info:

```bash
# List clusters to get cluster ID
ccloud cluster list

# Get connection string
ccloud cluster connection-string <cluster-id> \
  --database perftest \
  --user perftest_user
```

## Create Database and User

If not created during setup, connect to the cluster and run:

```sql
-- Create database
CREATE DATABASE perftest;

-- Create user
CREATE USER perftest_user WITH PASSWORD 'your-secure-password';

-- Grant permissions
GRANT ALL ON DATABASE perftest TO perftest_user;
```

## Save Connection String

Save the connection string to a file for use with benchmark scripts:

```bash
# Create connection string file
cat > crdb_connection.txt << 'EOF'
postgresql://perftest_user:<password>@<cluster-host>:26257/perftest?sslmode=verify-full
EOF
```

## Verify Connection

Use the validation script to test connectivity:

```bash
python3 validate_crdb_connection.py crdb_connection.txt
```

## Next Steps

Once the cluster is deployed and connection string is obtained:

1. **Validate connection**: Run the connection validation script
2. **Run benchmarks**: Use the connection string with `benchmark.py`
3. **Monitor performance**: Check CockroachDB Cloud console for metrics
4. **Cleanup**: Delete the cluster when done to avoid charges

## Cost Management

**Important**: This cluster configuration costs approximately **$2.50-3.50 per hour**.

To minimize costs:
- Deploy only when ready to run benchmarks
- Delete the cluster immediately after benchmarks complete
- Use the web console or CLI to delete:
  ```bash
  ccloud cluster delete <cluster-id> --yes
  ```

## Troubleshooting

### Connection Fails

- Verify IP allowlist includes your current IP
- Check that SSL mode is set correctly (`sslmode=verify-full` or `sslmode=require`)
- Ensure database and user exist
- Verify password is correct

### Performance Issues

- Check cluster status in web console
- Verify all nodes are healthy
- Review SQL insights for slow queries
- Check storage usage hasn't exceeded capacity

### Region Not Available

If westus2 is not available:
- Try alternative Azure regions: `eastus`, `centralus`, `westus3`
- Ensure region supports ADVANCED plan clusters

## Reference Configuration

This deployment matches the configuration in `cluster_config.yaml`:

```yaml
cockroachdb:
  cluster_name: "perftest-crdb-2026q2"
  cloud_provider: "azure"
  plan: "advanced"
  regions:
    - "westus2"
  nodes:
    vcpus: 8
    storage_gib: 500
  database:
    name: "perftest"
    sql_user: "perftest_user"
```

## Additional Resources

- CockroachDB Cloud Documentation: https://www.cockroachlabs.com/docs/cockroachcloud/
- Connection String Format: https://www.cockroachlabs.com/docs/stable/connection-parameters
- Pricing: https://www.cockroachlabs.com/pricing/
