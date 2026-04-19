# Getting CockroachDB Connection String

Step-by-step guide to extract the PostgreSQL-compatible connection string from CockroachDB Cloud after deploying via the web UI.

## Method 1: Using the Helper Script (Recommended)

The easiest way to get a properly formatted connection string with CA certificate paths:

```bash
python3 get_crdb_connection.py
```

**What it does:**
- ✅ Lists your available CockroachDB Cloud clusters
- ✅ Prompts for cluster name, database, and username
- ✅ Uses `ccloud` CLI to generate connection string with correct CA cert path for your OS
- ✅ Prompts for SQL password securely
- ✅ Saves to `crdb_connection.txt` with secure permissions (600)
- ✅ Offers to validate the connection

**Requirements:**
- `ccloud` CLI installed and authenticated (`ccloud auth login`)
- Cluster deployed and in 'Ready' state
- Database and SQL user created

**Example session:**
```
$ python3 get_crdb_connection.py

AVAILABLE CLUSTERS
======================================================================
Name                           ID                        State      Cloud
perftest-crdb-2026q2          abc-123-def               READY      AZURE

Cluster name/ID: perftest-crdb-2026q2
Database name [perftest]: perftest
SQL username [perftest_user]: perftest_user
Password: ********

✅ Connection string saved to: crdb_connection.txt
```

---

## Method 2: Via Web Console

### Step 1: Navigate to Your Cluster

1. Go to **https://cockroachlabs.cloud/**
2. Log in with your credentials
3. Click on your cluster name (e.g., `perftest-crdb-2026q2`)

### Step 2: Create Database and User (if not done during setup)

1. Click **"SQL"** in the left sidebar
2. Run the following SQL commands in the SQL console:

```sql
-- Create database
CREATE DATABASE perftest;

-- Create user with password
CREATE USER perftest_user WITH PASSWORD 'your-secure-password-here';

-- Grant all permissions on database
GRANT ALL ON DATABASE perftest TO perftest_user;

-- Grant default privileges (needed for tables)
ALTER DEFAULT PRIVILEGES GRANT ALL ON TABLES TO perftest_user;
```

**Important:** Save the password securely - you'll need it for the connection string.

### Step 3: Get Connection String

**Option A: Using the Connect Button**

1. Click the **"Connect"** button (top right of cluster page)
2. A modal will appear with connection options
3. Select the **"General connection string"** tab
4. Configure the connection:
   - **Database**: Select `perftest` (or your database name)
   - **User**: Select `perftest_user` (or your username)
   - **Client**: Select "General connection string" or "PostgreSQL"
5. The connection string will be displayed in this format:

```
postgresql://perftest_user:<password>@<cluster-name>-<id>.g8z.cockroachlabs.cloud:26257/perftest?sslmode=verify-full
```

6. Replace `<password>` with the actual password you set
7. Copy the complete connection string

**Option B: Manual Construction**

If the Connect button doesn't provide the exact format needed:

1. Go to cluster overview page
2. Note the **"Connection string"** or **"Host"** information:
   - Example: `perftest-crdb-2026q2-abc123.g8z.cockroachlabs.cloud`
3. Construct the connection string manually:

```
postgresql://<username>:<password>@<host>:26257/<database>?sslmode=verify-full
```

**Example:**
```
postgresql://perftest_user:MySecurePassword123@perftest-crdb-2026q2-abc123.g8z.cockroachlabs.cloud:26257/perftest?sslmode=verify-full
```

### Step 4: Save Connection String to File

Create a file with your connection string:

```bash
cat > crdb_connection.txt << 'EOF'
postgresql://perftest_user:MySecurePassword123@perftest-crdb-2026q2-abc123.g8z.cockroachlabs.cloud:26257/perftest?sslmode=verify-full
EOF
```

**Security Note:** This file contains your password. Set appropriate permissions:

```bash
chmod 600 crdb_connection.txt
```

---

## Method 2: Via ccloud CLI

If you have the `ccloud` CLI installed, you can retrieve connection information programmatically:

### Step 1: List Your Clusters

```bash
ccloud cluster list
```

Output example:
```
ID                                    Name                     Plan      Regions    Cloud    Status
abc-123-def-456                      perftest-crdb-2026q2     ADVANCED  westus2    AZURE    READY
```

Copy your cluster ID (e.g., `abc-123-def-456`)

### Step 2: Get Connection String

```bash
ccloud cluster connection-string <cluster-id> \
  --database perftest \
  --user perftest_user
```

**Note:** This command may or may not work depending on ccloud CLI version. Some versions don't fully support this command.

### Step 3: Alternative - Get Host Information

If the above doesn't work, get the host manually:

```bash
ccloud cluster info <cluster-id> --output json | jq -r '.config.serverless.routing_id'
```

Then construct the connection string:

```
postgresql://perftest_user:<password>@<cluster-host>:26257/perftest?sslmode=verify-full
```

---

## Method 3: Using SQL Shell

### Step 1: Connect via SQL Shell

From the web console:

1. Click **"SQL"** in the left sidebar
2. This opens an SQL shell connected to your cluster

Or via CLI:

```bash
ccloud cluster sql <cluster-id>
```

### Step 2: Query Connection Information

```sql
-- Get cluster host information
SHOW CLUSTER SETTING server.host_based_authentication.configuration;

-- Get current database
SELECT current_database();

-- Get current user
SELECT current_user;
```

### Step 3: Construct Connection String

Use the information to build:

```
postgresql://<user>:<password>@<host>:26257/<database>?sslmode=verify-full
```

---

## Connection String Components

Understanding the connection string format:

```
postgresql://[user]:[password]@[host]:[port]/[database]?[params]
```

### Components:

| Component | Description | Example |
|-----------|-------------|---------|
| `postgresql://` | Protocol | Fixed |
| `user` | SQL username | `perftest_user` |
| `password` | User password | `MySecurePassword123` |
| `host` | Cluster hostname | `perftest-crdb-2026q2-abc.g8z.cockroachlabs.cloud` |
| `port` | CockroachDB port | `26257` (default) |
| `database` | Database name | `perftest` |
| `sslmode` | SSL verification | `verify-full` or `require` |

### SSL Modes:

- **`verify-full`**: Most secure, verifies certificate and hostname
- **`require`**: Requires SSL but doesn't verify certificate
- **`prefer`**: Uses SSL if available (not recommended for production)
- **`disable`**: No SSL (not allowed for CockroachDB Cloud)

**Recommendation:** Use `verify-full` for production benchmarks.

---

## Validating the Connection String

### Quick Test with psql

```bash
psql "postgresql://perftest_user:password@host:26257/perftest?sslmode=verify-full" -c "SELECT version();"
```

Expected output:
```
CockroachDB CCL v23.1.x ...
```

### Using the Validation Script

```bash
python3 validate_crdb_connection.py crdb_connection.txt
```

This script will:
- ✅ Validate connection string format
- ✅ Test database connectivity
- ✅ Display cluster information
- ✅ Check user permissions
- ✅ Measure connection latency

---

## Troubleshooting

### "Connection refused"

**Cause:** IP not allowlisted or cluster not ready

**Fix:**
1. Check cluster status (should be "Ready")
2. Add your IP to allowlist:
   - Web Console → Cluster → Settings → IP Allowlist
   - Add your IP or `0.0.0.0/0` for testing (less secure)
3. Wait a few minutes for changes to propagate

### "SSL error" or "Certificate verification failed"

**Cause:** SSL mode mismatch or certificate issues

**Fix:**
- Try `sslmode=require` instead of `verify-full`
- Ensure you're using the exact hostname from CockroachDB Cloud
- Update system CA certificates if using `verify-full`

### "Database does not exist"

**Cause:** Database not created

**Fix:**
```sql
CREATE DATABASE perftest;
```

### "Role does not exist"

**Cause:** User not created

**Fix:**
```sql
CREATE USER perftest_user WITH PASSWORD 'your-password';
GRANT ALL ON DATABASE perftest TO perftest_user;
```

### "Password authentication failed"

**Cause:** Wrong password in connection string

**Fix:**
- Verify password is correct
- Check for special characters that need URL encoding:
  - `@` → `%40`
  - `:` → `%3A`
  - `/` → `%2F`
  - `?` → `%3F`
  - `#` → `%23`
  - `&` → `%26`
  - `%` → `%25`

**Example with special characters:**
```bash
# Password: "Pass@word:123"
# Encoded: "Pass%40word%3A123"
postgresql://user:Pass%40word%3A123@host:26257/db?sslmode=verify-full
```

---

## Security Best Practices

### 1. Password Management

- Use strong, unique passwords (min 16 characters)
- Store connection string in secure file with restricted permissions:
  ```bash
  chmod 600 crdb_connection.txt
  ```
- Never commit connection strings to Git
- Add to `.gitignore`:
  ```
  crdb_connection.txt
  *_connection.txt
  *.password
  ```

### 2. Network Security

- Use IP allowlist, not `0.0.0.0/0` in production
- Prefer VPC peering for production workloads
- Always use SSL (`sslmode=verify-full`)

### 3. User Permissions

- Create dedicated user for benchmarking
- Grant only necessary permissions
- Don't use admin/root user

---

## Quick Reference

### Get Connection String (Web UI)
1. https://cockroachlabs.cloud/
2. Click cluster → **Connect** button
3. Select database and user
4. Copy connection string
5. Replace `<password>` with actual password

### Save to File
```bash
cat > crdb_connection.txt << 'EOF'
postgresql://user:pass@host:26257/db?sslmode=verify-full
EOF
chmod 600 crdb_connection.txt
```

### Validate
```bash
python3 validate_crdb_connection.py crdb_connection.txt
```

### Use with Benchmark
```bash
python3 benchmark.py \
  --crdb "$(cat crdb_connection.txt)" \
  --pg "$(cat pg_connection.txt)" \
  --output-dir ./outputs
```

---

## Additional Resources

- [CockroachDB Connection Parameters](https://www.cockroachlabs.com/docs/stable/connection-parameters)
- [CockroachDB Cloud Connect](https://www.cockroachlabs.com/docs/cockroachcloud/connect-to-your-cluster)
- [PostgreSQL Connection Strings](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING)
