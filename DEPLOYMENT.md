# CockroachDB Deployment Guide

This guide covers automated deployment of CockroachDB Advanced clusters in Azure for performance benchmarking.

## Prerequisites

### 1. Install ccloud CLI

**macOS:**
```bash
brew install cockroachdb/tap/ccloud
```

**Linux:**
```bash
curl https://binaries.cockroachdb.com/ccloud/install.sh | bash
```

**Windows:**
Download from: https://www.cockroachlabs.com/docs/cockroachcloud/install-ccloud

Verify installation:
```bash
ccloud version
```

### 2. Authenticate with CockroachDB Cloud

Before deploying clusters, authenticate using the ccloud CLI:

```bash
ccloud auth login
```

This will:
- Open a browser window for interactive authentication
- Securely store your session credentials
- Allow you to use all ccloud commands and deploy_crdb.py

**Note:** Your authentication session may expire after some time. If you encounter authentication errors, simply run `ccloud auth login` again to refresh your session.

### 3. Install Python Dependencies

```bash
pip install pyyaml
```

## Configuration

### Cluster Configuration File

Edit `cluster_config.yaml` to customize your cluster:

```yaml
cockroachdb:
  cluster_name: "perftest-crdb-2026q2"
  cloud_provider: "azure"
  plan: "advanced"

  nodes:
    count: 3                        # Number of nodes
    instance_type: "Standard_D8s_v3" # Azure VM size
    storage_gib: 500                # Storage per node

  regions:
    - "eastus"                      # Primary region

  database:
    name: "perftest"
    sql_user: "perftest_user"
```

**Important configuration options:**

- **instance_type**: Choose based on your benchmark requirements
  - `Standard_D4s_v3`: 4 vCPU, 16 GB RAM (smaller workloads)
  - `Standard_D8s_v3`: 8 vCPU, 32 GB RAM ⭐ **(recommended for benchmark)**
  - `Standard_D16s_v3`: 16 vCPU, 64 GB RAM (larger workloads)

- **plan**: Cluster tier
  - `basic`: Single-node, development only
  - `standard`: Multi-node, production-ready
  - `advanced`: Multi-node with advanced features ⭐ **(recommended)**

- **regions**: Azure regions
  - `eastus`: East US
  - `westus2`: West US 2
  - `northeurope`: North Europe
  - `southeastasia`: Southeast Asia

## Deployment Workflows

### Workflow 1: Basic Deployment (Manual Cleanup)

**Step 1: Deploy cluster**
```bash
python deploy_crdb.py --config cluster_config.yaml
```

This will:
- Authenticate with CockroachDB Cloud API
- Create the cluster
- Wait for it to be ready (up to 15 minutes)
- Extract and save connection string to `crdb_connection.txt`

**Step 2: Run benchmark**
```bash
python benchmark.py \
  --crdb $(cat crdb_connection.txt) \
  --pg "postgresql://user:pass@azurepg.postgres.database.azure.com:5432/perftest" \
  --output-dir ./outputs
```

**Step 3: Cleanup (when done)**
```bash
# Get cluster ID from deployment output or:
CLUSTER_ID=$(cat crdb_connection.txt | grep -oP '@\K[^.]+' | head -1)

python deploy_crdb.py --cleanup --cluster-id $CLUSTER_ID
```

### Workflow 2: Auto-Cleanup (Ephemeral Testing)

Best for one-time benchmarks where you want automatic cleanup:

```bash
python deploy_crdb.py \
  --config cluster_config.yaml \
  --auto-cleanup
```

The cluster will be deleted automatically after you exit the script (Ctrl+C or when it completes).

### Workflow 3: Fully Automated (Deploy + Benchmark + Cleanup)

**⚠️ COMING SOON** - This feature requires `benchmark.py` to be implemented first.

```bash
python deploy_crdb.py \
  --config cluster_config.yaml \
  --run-benchmark \
  --pg-connection "postgresql://user:pass@azurepg.postgres.database.azure.com:5432/perftest" \
  --auto-cleanup
```

This will:
1. Deploy CockroachDB cluster
2. Wait for ready state
3. Automatically run benchmark.py
4. Delete cluster after completion

## Troubleshooting

### Error: "ccloud: command not found"

**Solution:** Install ccloud CLI (see Prerequisites above)

```bash
# Verify installation
which ccloud
ccloud version
```

### Error: "Not authenticated with CockroachDB Cloud"

**Solution:** Authenticate using the ccloud CLI

```bash
ccloud auth login
```

This will open a browser window for interactive authentication.

### Error: "Authentication failed"

**Possible causes:**
1. Session expired
2. Network connectivity issues
3. Browser authentication not completed

**Solution:**
1. Run `ccloud auth login` to refresh your session
2. Ensure browser window completes authentication
3. Verify network access to `cockroachlabs.cloud`

### Error: "Cluster creation failed: quota exceeded"

**Solution:** You've hit your account quota limits.

1. Check your quota: https://cockroachlabs.cloud/settings/billing
2. Delete unused clusters
3. Request quota increase (if on paid plan)
4. Use smaller instance type or fewer nodes

### Error: "Cluster creation timed out"

**Default timeout:** 15 minutes (900 seconds)

**Solution 1:** Increase timeout
```bash
python deploy_crdb.py --config cluster_config.yaml --timeout 1800
```

**Solution 2:** Check cluster status manually
```bash
ccloud cluster list
ccloud cluster status <cluster-id>
```

### Error: "Region not available"

**Solution:** Choose a different region in `cluster_config.yaml`

Available Azure regions:
- eastus, eastus2
- westus, westus2, westus3
- centralus, northcentralus, southcentralus
- northeurope, westeurope
- uksouth, ukwest
- southeastasia, eastasia

Check availability: https://www.cockroachlabs.com/docs/cockroachcloud/regions

### Cluster is stuck in "CREATING" state

**Solution:**
1. Wait longer (can take up to 20 minutes for large clusters)
2. Check CockroachDB Cloud Console for errors
3. If stuck >30 minutes, contact support or delete and recreate

```bash
# Delete stuck cluster
python deploy_crdb.py --cleanup --cluster-id <cluster-id>
```

## Cost Optimization

### Estimated Costs (as of 2026)

**3-node Standard_D8s_v3 cluster (benchmark config):**
- **Hourly:** ~$2-3/hour
- **Daily:** ~$48-72/day
- **Monthly:** ~$1,440-2,160/month

💡 **Tip:** Use `--auto-cleanup` for ephemeral benchmarks to minimize costs!

### Cost-Saving Strategies

1. **Use auto-cleanup for testing**
   ```bash
   python deploy_crdb.py --config cluster_config.yaml --auto-cleanup
   ```

2. **Use smaller instance types for initial development**
   - Change `instance_type` to `Standard_D4s_v3` in config
   - Reduces cost by ~50%

3. **Disable automated backups**
   ```yaml
   options:
     enable_backup: false  # Already set in template
   ```

4. **Delete clusters immediately after benchmarking**
   ```bash
   python deploy_crdb.py --cleanup --cluster-id <cluster-id>
   ```

5. **Monitor usage**
   - Check CockroachDB Cloud Console regularly
   - Set up billing alerts

## Security Best Practices

### 1. Session Security

**✅ Manage your authentication session:**
- Use `ccloud auth login` for interactive authentication
- Sessions are stored securely by the ccloud CLI
- Re-authenticate if your session expires
- Use `ccloud auth logout` when done on shared machines

**✅ Secure your workstation:**
- Lock your screen when away
- Use full-disk encryption
- Don't share authentication sessions

### 2. Connection String Security

**❌ Never commit connection strings:**
```bash
# Already in .gitignore
crdb_connection.txt
*_connection.txt
```

**✅ Generate fresh credentials per benchmark:**
- The script auto-generates connection strings
- Rotate database passwords regularly

### 3. Network Security

**✅ Use SSL/TLS connections:**
```
sslmode=require  # Already enforced in connection strings
```

**✅ IP Allowlist (optional):**
- Configure in CockroachDB Cloud Console
- Limit access to benchmark runner IP only

### 4. RBAC (Role-Based Access Control)

**✅ Use least-privilege SQL users:**
```sql
-- The script creates a dedicated perftest_user
-- Grant only necessary permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON DATABASE perftest TO perftest_user;
```

## Advanced Configuration

### Multi-Region Deployment

For multi-region testing, update `cluster_config.yaml`:

```yaml
regions:
  - "eastus"
  - "westus2"
  - "northeurope"

nodes:
  count: 9  # 3 nodes per region
```

### Custom VPC/Network

```yaml
network:
  cidr_block: "10.100.0.0/16"
  # Additional network config as needed
```

### Specific CockroachDB Version

```yaml
options:
  version: "v24.1.0"  # Pin to specific version
```

## Monitoring During Deployment

### Watch cluster creation progress

```bash
# In a separate terminal
watch -n 5 'ccloud cluster list'
```

### Check cluster status

```bash
ccloud cluster status <cluster-id>
```

### View cluster details

```bash
ccloud cluster info <cluster-id>
```

## Next Steps

After successful deployment:

1. **Verify connection**
   ```bash
   psql $(cat crdb_connection.txt) -c "SELECT version();"
   ```

2. **Run benchmark**
   ```bash
   python benchmark.py --crdb $(cat crdb_connection.txt) --pg <azure-pg-conn>
   ```

3. **Review results**
   ```bash
   open outputs/benchmark_report.html
   ```

4. **Cleanup**
   ```bash
   python deploy_crdb.py --cleanup --cluster-id <cluster-id>
   ```

## Support

- **CockroachDB Cloud Console:** https://cockroachlabs.cloud/
- **Documentation:** https://www.cockroachlabs.com/docs/cockroachcloud/
- **Support:** https://support.cockroachlabs.com/
- **Community Forum:** https://forum.cockroachlabs.com/

## Reference: ccloud CLI Commands

The `deploy_crdb.py` script wraps these commands:

```bash
# Authentication (interactive browser-based)
ccloud auth login

# List clusters
ccloud cluster list

# Create cluster
ccloud cluster create <name> \
  --cloud azure \
  --region eastus \
  --plan advanced \
  --nodes 3 \
  --instance-type Standard_D8s_v3 \
  --storage 500

# Check status
ccloud cluster status <cluster-id>

# Get connection string
ccloud cluster connection-string <cluster-id> \
  --database perftest \
  --user perftest_user

# Delete cluster
ccloud cluster delete <cluster-id> --yes
```

For full CLI reference, see: https://www.cockroachlabs.com/docs/cockroachcloud/ccloud-reference
