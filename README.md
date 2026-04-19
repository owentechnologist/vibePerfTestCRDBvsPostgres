# PostgreSQL Performance Benchmark Tool

Comprehensive performance benchmark comparing **CockroachDB Advanced** and **Azure Database for PostgreSQL Flexible Server** across OLTP, OLAP, and isolation test scenarios.

## Overview

This tool benchmarks two PostgreSQL-compatible databases side-by-side using:
- **8 performance tests** covering OLTP latency, throughput, OLAP queries, and transaction isolation
- **20 tables** with 5 million rows each (100M total rows)
- **Async architecture** using Python asyncio + asyncpg for maximum performance
- **3 output formats**: JSON (raw data), HTML dashboard (Chart.js visualizations), plain text summary

### Test Suite

1. **Test 1**: SELECT 1 latency baseline (10k iterations)
2. **Test 2**: Primary key point lookup (50k iterations, 8 concurrent workers)
3. **Test 3**: TPC-B workload (5 minutes, 16 concurrent workers)
4. **Test 4**: ROLLUP aggregation on 5M rows (3 runs)
5. **Test 5**: Window functions (RANK, NTILE, SUM OVER) (3 runs)
6. **Test 6**: Cross-table JOIN (5M × 5M rows) (2 runs)
7. **Test 7**: Phantom read isolation test (SERIALIZABLE)
8. **Test 8**: Non-repeatable read isolation test (REPEATABLE READ)

## Prerequisites

### Software Requirements

- **Python 3.10+** (3.11 or 3.12 recommended)
- **CockroachDB Cloud CLI** (`ccloud`) - for automated cluster deployment
- **Database access**:
  - CockroachDB Advanced cluster (or use `deploy_crdb.py` to create one)
  - Azure PostgreSQL Flexible Server instance

### Python Dependencies

Install from `requirements.txt`:

```bash
pip install -r requirements.txt
```

Required packages:
- `asyncpg>=0.29.0` - Async PostgreSQL driver
- `numpy>=1.24.0` - Percentile calculations
- `rich>=13.0.0` - Progress bars and terminal UI
- `jinja2>=3.1.0` - HTML template rendering
- `psutil>=5.9.0` - System monitoring
- `pyyaml>=6.0.0` - Configuration files

## Quick Start

### Option 1: Using Virtual Environment (Recommended)

```bash
# Clone repository
cd perftest2026Q2

# Run setup script
./setup.sh

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Verify installation
python verify_setup.py
```

### Option 2: Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify
python -c "import asyncpg; print('✅ asyncpg installed')"
```

## Deployment Workflows

### Automated Workflow (CockroachDB + Benchmark)

Deploy CockroachDB cluster and run benchmark automatically:

```bash
# 1. Configure CockroachDB cluster (edit cluster_config.yaml)
cat cluster_config.yaml

# 2. Authenticate with CockroachDB Cloud
ccloud auth login

# 3. Deploy cluster, run benchmark, and auto-cleanup
python deploy_crdb.py \
  --config cluster_config.yaml \
  --auto-cleanup \
  --run-benchmark \
  --pg-connection "postgresql://user:pass@azurepg.postgres.database.azure.com:5432/perftest"
```

This will:
1. Create a 3-node CockroachDB Advanced cluster in Azure (eastus)
2. Wait for cluster to be ready
3. Run the complete benchmark
4. Delete the cluster after completion

### Manual Workflow

#### Step 1: Deploy CockroachDB Cluster

```bash
# Deploy CockroachDB cluster
python deploy_crdb.py \
  --config cluster_config.yaml \
  --output-connection crdb_connection.txt

# Output example:
# ✅ Cluster created successfully!
# Connection string saved to: crdb_connection.txt
# Cluster ID: abc-123-def-456
```

The script will:
- Create a 3-node cluster with specified configuration
- Wait for cluster ready state (up to 15 minutes)
- Extract and save connection string
- Display cluster info and estimated cost

#### Step 2: Provision Azure PostgreSQL

Create an Azure Database for PostgreSQL Flexible Server instance:

```bash
# Using Azure CLI
az postgres flexible-server create \
  --name perftest-pg-2026q2 \
  --resource-group perftest-rg \
  --location eastus \
  --admin-user pgadmin \
  --admin-password <strong-password> \
  --sku-name Standard_D4s_v3 \
  --tier GeneralPurpose \
  --storage-size 256 \
  --version 15

# Create database
az postgres flexible-server db create \
  --resource-group perftest-rg \
  --server-name perftest-pg-2026q2 \
  --database-name perftest

# Get connection string
az postgres flexible-server show-connection-string \
  --server-name perftest-pg-2026q2
```

#### Step 3: Run Benchmark

```bash
# Full benchmark (includes data loading)
python benchmark.py \
  --crdb $(cat crdb_connection.txt) \
  --pg "postgresql://pgadmin:password@perftest-pg.postgres.database.azure.com:5432/perftest?sslmode=require" \
  --output-dir ./outputs

# Skip data loading (if data already loaded)
python benchmark.py \
  --crdb $(cat crdb_connection.txt) \
  --pg "postgresql://..." \
  --skip-load
```

#### Step 4: Cleanup (Optional)

```bash
# Delete CockroachDB cluster
python deploy_crdb.py --cleanup --cluster-id abc-123-def-456

# Delete Azure PostgreSQL (using Azure CLI)
az postgres flexible-server delete \
  --resource-group perftest-rg \
  --name perftest-pg-2026q2 \
  --yes
```

## Usage

### Basic Usage

```bash
python benchmark.py \
  --crdb "postgresql://user:pass@crdb-host:26257/perftest?sslmode=require" \
  --pg "postgresql://user:pass@pg-host:5432/perftest?sslmode=require"
```

### Command-Line Options

```
Options:
  --crdb URL              CockroachDB connection string (required)
  --pg URL                Azure PostgreSQL connection string (required)
  --skip-load             Skip data loading (assumes data already loaded)
  --output-dir DIR        Output directory (default: ./outputs)
  --verbose, -v           Enable verbose output and full error tracebacks
  -h, --help              Show help message
```

### Connection String Format

```
postgresql://username:password@host:port/database?sslmode=require
```

Examples:
```bash
# CockroachDB Cloud
postgresql://user:pass@cluster-name.eastus.cockroachlabs.cloud:26257/perftest?sslmode=require

# Azure PostgreSQL Flexible Server
postgresql://user:pass@servername.postgres.database.azure.com:5432/perftest?sslmode=require
```

**Important**: Always use `?sslmode=require` for production connections.

## Output Files

The benchmark generates three output files in the specified directory:

### 1. JSON Results (`benchmark_results.json`)

Raw data export for programmatic analysis:

```json
{
  "benchmark_info": {
    "start_time": "2026-04-14T10:00:00",
    "total_duration_seconds": 1800.5,
    "test_count": 8
  },
  "databases": {
    "cockroachdb": {"version": "v23.2.0"},
    "azure_postgresql": {"version": "15.5"}
  },
  "test_results": {
    "cockroachdb": {
      "test_01": {
        "status": "SUCCESS",
        "percentiles": {"p50": 1.23, "p95": 2.45, "p99": 3.67}
      }
    }
  }
}
```

### 2. HTML Dashboard (`benchmark_report.html`)

Interactive dashboard with Chart.js visualizations:

- **Metadata Cards**: Benchmark info, database versions, execution summary
- **Results Table**: Side-by-side comparison with winner/loser highlighting
- **Charts**:
  - OLTP Latency Comparison (p50/p95/p99)
  - OLAP Query Execution Time (median)
  - Throughput Comparison (TPS/QPS)

Open in browser: `file:///path/to/outputs/benchmark_report.html`

### 3. Text Summary (`benchmark_summary.txt`)

Concise plain text summary (< 50 lines):

```
======================================================================
BENCHMARK RESULTS SUMMARY
======================================================================

Execution Time: 2026-04-14T10:00:00 - 2026-04-14T10:30:00
Total Duration: 1800.50s

Databases:
  CockroachDB:       CockroachDB v23.2.0
  Azure PostgreSQL:  PostgreSQL 15.5

Test Results:
----------------------------------------------------------------------

OLTP Tests (Lower latency is better):

  Test 1: SELECT 1 Latency:
    CRDB p50: 1.23ms  |  PG p50: 0.95ms  |  Winner: PG (22.8% faster)

🏆 Overall Winner: Azure PostgreSQL
```

## Execution Timeline

**Total Duration**: 5-30 minutes (excluding data loading)

| Phase | Duration | Description |
|-------|----------|-------------|
| Data Loading | 10-30 min | Load 100M rows across 20 tables (skip with `--skip-load`) |
| Tests 1-2 | 1-2 min | Parallel execution (latency baseline, point lookup) |
| Test 3 | 5 min | Sequential TPC-B workload (300 seconds per database) |
| Tests 4-6 | 5-20 min | Sequential OLAP queries with 10-minute timeout |
| Tests 7-8 | < 1 min | Isolation tests (quick validation) |
| Output Gen | < 10 sec | Generate JSON, HTML, and text files |

## Troubleshooting

### Common Issues

**1. "ModuleNotFoundError: No module named 'asyncpg'"**

```bash
# Solution: Install in virtual environment
source venv/bin/activate  # If not already activated
pip install -r requirements.txt
```

**2. "Connection refused" or "SSL required"**

```bash
# Check connection string format
# Must include: ?sslmode=require

# Test connection manually
psql "postgresql://user:pass@host:port/db?sslmode=require"
```

**3. "Cluster creation timeout"**

```bash
# Increase timeout in deploy_crdb.py
# Default: 15 minutes (900 seconds)
# Check cluster status manually:
ccloud cluster status <cluster-id>
```

**4. "Out of memory during data loading"**

```bash
# Reduce batch size in src/data_loader.py
# Default: 10k rows per batch
# Or run on machine with more RAM (8GB+ recommended)
```

**5. "Test timeout on OLAP queries"**

This is expected on slower hardware or high-latency connections. Tests 4-6 have a 10-minute timeout per run.

```bash
# Normal: 2-5 minutes per OLAP query
# Slow: 5-10 minutes (times out at 10 minutes)
# Check query execution with EXPLAIN ANALYZE
```

### Debugging

Enable verbose mode for detailed output:

```bash
python benchmark.py \
  --crdb "..." \
  --pg "..." \
  --verbose
```

View logs from individual test modules:

```bash
# Test specific module
python src/tests/test_01_select_one.py
python src/tests/test_03_pgbench.py
```

## Cost Optimization

### CockroachDB

**Recommended for testing**:
- Plan: Advanced (required for performance testing)
- Nodes: 3 (minimum for production-like setup)
- Instance: Standard_D8s_v3 (8 vCPU, 32 GB RAM)
- Storage: 500 GB per node
- Region: Single region (eastus)

**Cost estimate**: ~$3-5/hour for testing cluster

**Tips**:
- Use `--auto-cleanup` to automatically delete cluster after benchmark
- Disable automated backups during testing (`enable_backup: false`)
- Use smallest viable instance type for initial testing
- Monitor with: `ccloud cluster info <cluster-id>`

### Azure PostgreSQL

**Recommended for testing**:
- Tier: General Purpose
- SKU: Standard_D4s_v3 (4 vCPU, 16 GB RAM)
- Storage: 256 GB
- Backup: Disabled or 7-day retention

**Cost estimate**: ~$200-300/month (prorated for testing duration)

**Tips**:
- Delete when not in use
- Use reserved capacity for long-term testing
- Monitor costs: `az monitor metrics list`

## Security Best Practices

### Authentication and Credentials

```bash
# Authenticate with CockroachDB Cloud (interactive browser-based login)
ccloud auth login

# Your session will be stored securely by the ccloud CLI
# Re-authenticate if your session expires

# Never commit credentials to Git
# Check .gitignore includes:
#   *.txt (connection strings)
#   .env
#   cluster_config.local.yaml
```

### Connection Strings

- Always use SSL/TLS (`sslmode=require`)
- Use strong passwords (16+ characters, mixed case, symbols)
- Rotate credentials after testing
- Use environment variables for production:

```bash
export CRDB_URL="postgresql://..."
export PG_URL="postgresql://..."

python benchmark.py --crdb "$CRDB_URL" --pg "$PG_URL"
```

### Network Security

- Limit IP allowlist to benchmark runner IP
- Use private endpoints when available
- Disable public access after testing

## Architecture

### Project Structure

```
perftest2026Q2/
├── benchmark.py              # Main CLI entry point
├── deploy_crdb.py            # CockroachDB deployment automation
├── requirements.txt          # Python dependencies
├── cluster_config.yaml       # CockroachDB cluster configuration
├── README.md                 # This file
├── DEPLOYMENT.md             # Detailed deployment guide
├── src/
│   ├── config.py             # CLI args, connection config
│   ├── database.py           # Connection pool management
│   ├── schema.py             # Schema creation (21 tables)
│   ├── data_loader.py        # Async batch data loading
│   ├── test_runner.py        # Test orchestration
│   ├── retry_logic.py        # Exponential backoff
│   ├── metrics.py            # Latency tracking & percentiles
│   ├── tests/
│   │   ├── base.py           # Base test classes
│   │   ├── test_01_select_one.py
│   │   ├── test_02_point_lookup.py
│   │   ├── test_03_pgbench.py
│   │   ├── test_04_rollup.py
│   │   ├── test_05_window.py
│   │   ├── test_06_join.py
│   │   ├── test_07_phantom_read.py
│   │   └── test_08_nonrepeatable_read.py
│   └── output/
│       ├── json_writer.py    # JSON export
│       ├── html_generator.py # HTML dashboard
│       └── text_summary.py   # Text summary
├── templates/
│   └── dashboard_template.html
└── outputs/                  # Generated reports (gitignored)
```

### Technology Stack

- **Language**: Python 3.10+
- **Async Runtime**: asyncio
- **Database Driver**: asyncpg (high-performance async PostgreSQL)
- **Progress UI**: Rich library
- **Templating**: Jinja2
- **Charts**: Chart.js (loaded from CDN)
- **Data Analysis**: NumPy (percentile calculations)

### Design Decisions

1. **Async-First**: All database operations use asyncio for maximum concurrency
2. **Connection Pooling**: Sized per test (1-16 connections)
3. **Retry Logic**: Exponential backoff with jitter for CockroachDB serialization errors
4. **Memory Efficient**: Stream large results, batch data generation
5. **Standardized Results**: Common TestResult format across all tests
6. **Timeout Enforcement**: asyncio.wait_for() with 10-minute timeout for OLAP queries

## Contributing

This is a benchmarking tool for performance testing. Contributions are welcome:

1. Report issues at: https://github.com/anthropics/claude-code/issues
2. Follow existing code style
3. Add tests for new features
4. Update documentation

## License

See LICENSE file for details.

## Support

For help:
- Run: `python benchmark.py --help`
- View logs: `python benchmark.py --verbose`
- Check documentation: `README.md`, `DEPLOYMENT.md`
- Report issues: https://github.com/anthropics/claude-code/issues

## Acknowledgments

- TPC-B benchmark specification: http://www.tpc.org/tpcb/
- CockroachDB documentation: https://www.cockroachlabs.com/docs/
- Azure PostgreSQL documentation: https://learn.microsoft.com/en-us/azure/postgresql/

---

**Generated by**: Claude Code (Anthropic)
**Version**: 1.0.0
**Last Updated**: 2026-04-14
