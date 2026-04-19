# Quick Start Guide

Get up and running with the PostgreSQL Performance Benchmark in 5 minutes.

## Prerequisites

- **Python 3.10+** (check with `python3 --version`)
- **Git** (to clone or manage the repository)
- Access to **CockroachDB Cloud** (for deployment automation)
- Access to **Azure PostgreSQL Flexible Server** (for comparison)

## Step 1: Environment Setup

Create a virtual environment and install all dependencies:

```bash
# Run the automated setup script
./setup.sh
```

This will:
- ✅ Check Python version (3.10+ required)
- ✅ Create virtual environment at `./venv`
- ✅ Install all dependencies from `requirements.txt`
- ✅ Verify installation

**Manual setup (alternative):**
```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Verify Installation

Run the verification script to ensure everything is set up correctly:

```bash
# Activate virtual environment if not already active
source venv/bin/activate

# Run verification
python verify_setup.py
```

Expected output:
```
✅ PASS     Python Version
✅ PASS     Dependencies
✅ PASS     Custom Modules
✅ PASS     Class Instantiation
✅ PASS     File Structure
```

## Step 3: Authenticate with CockroachDB Cloud

Authenticate using the interactive browser-based login:

```bash
ccloud auth login
```

This will:
- Open a browser window for authentication
- Securely store your session credentials
- Allow you to use ccloud CLI and deploy_crdb.py

**Note:** Your session may expire after some time. If you see authentication errors, simply run `ccloud auth login` again.

## Step 4: Install ccloud CLI

### macOS
```bash
brew install cockroachdb/tap/ccloud
```

### Linux
```bash
curl https://binaries.cockroachdb.com/ccloud/install.sh | bash
```

### Verify
```bash
ccloud version
```

## Step 5: Deploy CockroachDB Cluster

Deploy a cluster in Azure:

```bash
# Review configuration (optional)
cat cluster_config.yaml

# Deploy cluster
python deploy_crdb.py --config cluster_config.yaml
```

This will:
- Authenticate with CockroachDB Cloud
- Create 3-node cluster in Azure (Standard_D8s_v3)
- Wait for cluster to be ready (~10-15 minutes)
- Save connection string to `crdb_connection.txt`

**Expected output:**
```
✅ Authenticated with CockroachDB Cloud
Creating cluster 'perftest-crdb-2026q2'...
✅ Cluster creation initiated
⏳ Waiting for cluster to be ready...
✅ Cluster is ready!
✅ Connection string retrieved
   Saved to: crdb_connection.txt
```

## Step 6: Set Up Azure PostgreSQL

You'll need to provision Azure PostgreSQL Flexible Server separately:

**Recommended configuration** (to match CockroachDB):
- **Tier**: General Purpose
- **Compute**: 8 vCores
- **Storage**: 500 GiB
- **Region**: East US (or same as CockroachDB)
- **PostgreSQL version**: 14 or higher

**Get connection string:**
```
postgresql://username:password@servername.postgres.database.azure.com:5432/perftest?sslmode=require
```

## Step 7: Run Benchmark

```bash
# Activate virtual environment
source venv/bin/activate

# Run full benchmark (data loading + all 8 tests)
python benchmark.py \
  --crdb $(cat crdb_connection.txt) \
  --pg "postgresql://user:pass@azurepg.postgres.database.azure.com:5432/perftest?sslmode=require"
```

**With existing data (skip loading):**
```bash
python benchmark.py \
  --crdb $(cat crdb_connection.txt) \
  --pg "postgresql://...postgres.database.azure.com:5432/perftest?sslmode=require" \
  --skip-load
```

## Step 8: View Results

After the benchmark completes, you'll have three output files:

```bash
# View HTML dashboard (recommended)
open outputs/benchmark_report.html

# View plain text summary
cat outputs/benchmark_summary.txt

# Inspect raw JSON data
python -m json.tool outputs/benchmark_results.json | less
```

## Step 9: Cleanup

**Delete CockroachDB cluster** (to avoid charges):

```bash
# Get cluster ID from deployment output or:
CLUSTER_ID=$(python deploy_crdb.py --config cluster_config.yaml --cleanup --cluster-id YOUR_CLUSTER_ID)

# Or if you saved it during deployment:
python deploy_crdb.py --cleanup --cluster-id abc-123-def
```

**Delete Azure PostgreSQL** through Azure Portal or CLI.

---

## Common Issues

### "asyncpg not found"

**Solution:** Activate virtual environment
```bash
source venv/bin/activate
```

### "ccloud: command not found"

**Solution:** Install ccloud CLI (see Step 4)

### "Not authenticated with CockroachDB Cloud"

**Solution:** Authenticate using ccloud CLI (see Step 3)
```bash
ccloud auth login
```

### "Connection refused"

**Solution:** Check connection strings have correct format:
```
postgresql://user:pass@host:port/database?sslmode=require
```

### Benchmark takes too long

**Solution:** Use reduced scale for testing:
```bash
python benchmark.py --crdb <conn> --pg <conn> --reduced-scale
```

---

## Quick Commands Reference

```bash
# Setup
./setup.sh                                    # Initial setup
source venv/bin/activate                      # Activate venv
python verify_setup.py                        # Verify installation

# Deploy CockroachDB
python deploy_crdb.py --config cluster_config.yaml

# Run benchmark
python benchmark.py --crdb <conn> --pg <conn>

# Cleanup
python deploy_crdb.py --cleanup --cluster-id <id>
deactivate                                    # Deactivate venv
```

---

## Next Steps

- **Read full documentation**: See `DEPLOYMENT.md` for detailed deployment options
- **Customize cluster config**: Edit `cluster_config.yaml` for different instance types/regions
- **Review benchmark spec**: See `benchmark_skill.md` for test details
- **Automate workflows**: Use `--auto-cleanup` and `--run-benchmark` flags for CI/CD

---

## Getting Help

- **CockroachDB Docs**: https://www.cockroachlabs.com/docs/
- **Issues**: Report at project repository
- **Questions**: See inline documentation in each module

Happy benchmarking! 🚀
