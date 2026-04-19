# CockroachDB Cloud Connection Setup

Complete guide for connecting to CockroachDB Cloud clusters with proper TLS/CA certificate configuration.

## Quick Start

After deploying your CockroachDB cluster via the web UI:

```bash
# 1. Generate connection string (prompts for cluster info)
python3 get_crdb_connection.py

# 2. Validate connection
python3 validate_crdb_connection.py crdb_connection.txt

# 3. Run benchmarks
python3 benchmark.py \
  --crdb "$(cat crdb_connection.txt)" \
  --pg "$(cat pg_connection.txt)" \
  --output-dir ./outputs
```

## Why CA Certificates Matter

**CockroachDB Cloud enforces TLS on all connections** for security:

1. **TLS encryption** - All data in transit is encrypted
2. **Server authentication** - CA certificate verifies you're connecting to the real cluster
3. **SSL mode `verify-full`** - Strongest security, verifies both certificate and hostname

**Without the CA certificate:**
- Connections will fail with SSL errors
- `sslmode=disable` is not allowed on CockroachDB Cloud
- Applications cannot verify cluster identity

## Connection String Format

The complete connection string format:

```
postgresql://[user]:[password]@[host]:26257/[database]?sslmode=verify-full&sslrootcert=[ca-cert-path]
```

**Example:**
```
postgresql://perftest_user:MyPass123@cluster-abc.g8z.cockroachlabs.cloud:26257/perftest?sslmode=verify-full&sslrootcert=/Users/user/.postgresql/root.crt
```

## ccloud CLI Certificate Management

The `ccloud cluster connection-string` command automatically:

✅ Generates a complete PostgreSQL connection string
✅ Includes the correct CA certificate path for your OS
✅ Works with clusters deployed via web UI (just needs cluster name)
✅ No manual certificate download required

**Command:**
```bash
ccloud cluster connection-string <cluster-name> \
  --database perftest \
  --sql-user perftest_user \
  --os MAC  # Automatically detects: MAC, LINUX, or WINDOWS
```

**What you need:**
- Cluster name or ID (from web UI)
- Database name (created in SQL console)
- SQL username (created in SQL console)
- SQL password (set when creating user)

## Using the Helper Script

The `get_crdb_connection.py` script automates the entire process:

### What It Does

1. **Checks prerequisites** - Verifies `ccloud` CLI is installed and authenticated
2. **Lists clusters** - Shows your available CockroachDB Cloud clusters
3. **Prompts for info** - Asks for cluster name, database, and username
4. **Generates connection string** - Uses `ccloud` CLI with OS-specific CA cert paths
5. **Prompts for password** - Securely prompts for SQL password (hidden input)
6. **Saves to file** - Creates `crdb_connection.txt` with 600 permissions
7. **Offers validation** - Can run validation script to test connection

### Usage

```bash
python3 get_crdb_connection.py
```

**Example session:**
```
CockroachDB Cloud Connection String Generator
======================================================================

CHECKING CCLOUD CLI
======================================================================
✅ ccloud CLI found: ccloud 0.8.18
✅ Authenticated as: user@example.com

AVAILABLE CLUSTERS
======================================================================
Name                           ID                        State      Cloud
perftest-crdb-2026q2          abc-123-def               READY      AZURE

CLUSTER CONNECTION INFORMATION
======================================================================
Cluster name/ID: perftest-crdb-2026q2
Database name [perftest]:
SQL username [perftest_user]:

✅ Information collected:
   Cluster: perftest-crdb-2026q2
   Database: perftest
   User: perftest_user

GENERATING CONNECTION STRING
======================================================================
Detected OS: MAC
✅ Connection string generated successfully

SQL USER PASSWORD
======================================================================
Password: ********

SAVING CONNECTION STRING
======================================================================
✅ Connection string saved to: crdb_connection.txt
   Permissions: 600 (read/write for owner only)

CONNECTION VALIDATION
======================================================================
Validate connection? [y/N]: y

✅ Connection validated successfully!

COMPLETE
======================================================================
✅ Connection string is ready for use!
```

## CA Certificate Locations

The `ccloud` CLI uses OS-specific default locations:

| OS | Default CA Certificate Path |
|----|-----------------------------|
| macOS | `~/.postgresql/root.crt` |
| Linux | `~/.postgresql/root.crt` |
| Windows | `%APPDATA%\postgresql\root.crt` |

The `--os` flag in `ccloud cluster connection-string` ensures the correct path is used.

## Manual Certificate Download (Optional)

If you need to download the CA certificate manually:

**Via ccloud CLI:**
```bash
# Downloads to current directory
ccloud cluster cert <cluster-id>
```

**Via Web Console:**
1. Navigate to your cluster
2. Click "Connect" button
3. Click "Download CA Cert"

**Via URL:**
```
https://cockroachlabs.cloud/clusters/<cluster-id>/cert
```

## Troubleshooting

### "ccloud CLI not found"

Install ccloud CLI:
```bash
# macOS
brew install cockroachdb/tap/ccloud

# Linux
curl https://binaries.cockroachdb.com/ccloud/install.sh | bash
```

### "Not authenticated with CockroachDB Cloud"

Authenticate:
```bash
ccloud auth login
# Opens browser for interactive login
```

### "Unable to find a cluster with ID or name"

Verify:
1. Cluster exists and is in 'Ready' state
2. You're authenticated to the correct organization
3. Cluster name is spelled correctly

```bash
# List all clusters
ccloud cluster list
```

### "x509: certificate signed by unknown authority"

The connection string is missing the CA certificate path or the path is incorrect.

**Fix with helper script:**
```bash
python3 get_crdb_connection.py
```

**Or manually verify CA cert path:**
```bash
ls -la ~/.postgresql/root.crt  # macOS/Linux
```

### "Connection refused"

Check:
1. Cluster is in 'Ready' state (not 'Creating')
2. IP allowlist includes your IP address
3. Firewall allows port 26257

**Add IP to allowlist:**
```bash
# Via web console
# Cluster → Settings → IP Allowlist → Add Entry

# Via ccloud CLI
ccloud cluster networking allowlist add <cluster-id> \
  --cidr <your-ip>/32 \
  --name "My IP"
```

## Security Best Practices

1. **Use `sslmode=verify-full`** - Strongest security, verifies certificate and hostname
2. **Secure file permissions** - `chmod 600 crdb_connection.txt`
3. **Never commit to git** - Add to `.gitignore`:
   ```
   crdb_connection.txt
   *_connection.txt
   *.password
   ```
4. **Use strong passwords** - Minimum 16 characters, mixed case, numbers, symbols
5. **Restrict IP allowlist** - Don't use `0.0.0.0/0` in production

## Related Documentation

- **[GET_CONNECTION_STRING.md](./GET_CONNECTION_STRING.md)** - Detailed connection string guide
- **[CRDB_WEB_UI_DEPLOYMENT.md](./CRDB_WEB_UI_DEPLOYMENT.md)** - Web UI deployment guide
- **[BENCHMARK_WORKFLOW.md](./BENCHMARK_WORKFLOW.md)** - Complete benchmark workflow
- **[validate_crdb_connection.py](./validate_crdb_connection.py)** - Connection validation tool

## Quick Reference

```bash
# Generate connection string
python3 get_crdb_connection.py

# Validate connection
python3 validate_crdb_connection.py crdb_connection.txt

# Run benchmarks
python3 benchmark.py \
  --crdb "$(cat crdb_connection.txt)" \
  --pg "$(cat pg_connection.txt)"

# List clusters
ccloud cluster list

# Get cluster info
ccloud cluster info <cluster-name>

# Manual connection string (requires password insertion)
ccloud cluster connection-string <cluster-name> \
  --database perftest \
  --sql-user perftest_user \
  --os MAC
```

## Support

**CockroachDB Documentation:**
- [Transport Layer Security (TLS)](https://www.cockroachlabs.com/docs/stable/security-reference/transport-layer-security.html)
- [Connection Parameters](https://www.cockroachlabs.com/docs/stable/connection-parameters.html)
- [CockroachDB Cloud Authentication](https://www.cockroachlabs.com/docs/cockroachcloud/authentication.html)

**Tools:**
- [ccloud CLI Documentation](https://www.cockroachlabs.com/docs/cockroachcloud/ccloud-get-started)
- [CockroachDB Cloud Console](https://cockroachlabs.cloud/)
