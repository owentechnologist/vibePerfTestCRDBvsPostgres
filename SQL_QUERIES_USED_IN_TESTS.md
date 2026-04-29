# SQL Queries Used in Performance Tests

This document catalogs all SQL queries used across the CockroachDB vs Azure PostgreSQL performance testing suite.

---

## Query Categories

### OLTP Queries
- Test 1: SELECT 1
- Test 2: Point Lookup
- Test 3: pgbench TPC-B

### OLAP Queries
- Test 4: ROLLUP Aggregation
- Test 5: Window Functions
- Test 6: Cross-Table JOIN

### Isolation Tests
- Test 7: Phantom Read (SERIALIZABLE)
- Test 8: Non-Repeatable Read (REPEATABLE READ)
- Test 9: Phantom Read (DEFAULT)
- Test 10: Non-Repeatable Read (DEFAULT)

**Databases Tested:**
- CockroachDB Advanced (distributed SQL)
- Azure Database For PostgreSQL FLEXIBLE SERVER (standalone PostgreSQL)
- Azure Database For PostgreSQL Elastic Clusters (Citus - distributed PostgreSQL)

**Note:** For Citus-specific schema adjustments and distribution strategies, see the [Azure PostgreSQL Elastic Cluster (Citus) Adjustments](#azure-postgresql-elastic-cluster-citus-adjustments) section.

---

## Test 1: SELECT 1 - Latency Baseline

**Purpose:** Measure round-trip latency with zero data access.

```sql
SELECT 1
```

**Configuration:**
- Iterations: 10,000
- Concurrency: Serial (single connection)
- Metrics: p50, p95, p99, p99.9, p99.99 latency (ms), QPS

---

## Test 2: Point Lookup

**Purpose:** Single-row indexed fetch performance on a large table.

```sql
SELECT aid, abalance FROM pgbench_accounts WHERE aid = $1
```

**Configuration:**
- Table: `pgbench_accounts` (5M rows)
- Iterations: 50,000
- Concurrency: 8 workers
- Metrics: p50, p95, p99, p99.9, p99.99 latency (ms), QPS

---

## Test 3: pgbench TPC-B Workload

**Purpose:** Industry-standard OLTP mixed read/write workload.

**Multi-statement transaction:**

```sql
-- 1. Update account balance
UPDATE pgbench_accounts SET abalance = abalance + $1 WHERE aid = $2;

-- 2. Read account balance
SELECT abalance FROM pgbench_accounts WHERE aid = $1;

-- 3. Update teller balance
UPDATE pgbench_tellers SET tbalance = tbalance + $1 WHERE tid = $2;

-- 4. Update branch balance
UPDATE pgbench_branches SET bbalance = bbalance + $1 WHERE bid = $2;

-- 5. Insert history record
INSERT INTO pgbench_history (tid, bid, aid, delta, mtime) 
VALUES ($1, $2, $3, $4, NOW());
```

**Configuration:**
- Duration: 5 minutes (300 seconds)
- Concurrency: 16 workers
- Max retries: 3 (exponential backoff for serialization errors)
- Metrics: TPS, p50/p95/p99/p99.9/p99.99 transaction latency (ms), error count, retry count

---

## Test 4: ROLLUP Aggregation

**Purpose:** GROUP BY ROLLUP over 5M rows - tests planner and aggregation engine.

**Note:** CockroachDB v26.1 doesn't support native `GROUP BY ROLLUP` syntax. This query manually constructs rollup levels with `UNION ALL`.

```sql
WITH base AS (
    SELECT
        date_trunc('month', created_at) AS month,
        region,
        status,
        amount
    FROM bench_events_1
)
-- Level 1: month, region, status (finest granularity)
SELECT
    month,
    region,
    status,
    COUNT(*)                          AS event_count,
    SUM(amount)                       AS total_amount,
    AVG(amount)                       AS avg_amount,
    MIN(amount)                       AS min_amount,
    MAX(amount)                       AS max_amount
FROM base
GROUP BY month, region, status

UNION ALL

-- Level 2: month, region subtotals
SELECT
    month,
    region,
    NULL AS status,
    COUNT(*),
    SUM(amount),
    AVG(amount),
    MIN(amount),
    MAX(amount)
FROM base
GROUP BY month, region

UNION ALL

-- Level 3: month subtotals
SELECT
    month,
    NULL AS region,
    NULL AS status,
    COUNT(*),
    SUM(amount),
    AVG(amount),
    MIN(amount),
    MAX(amount)
FROM base
GROUP BY month

UNION ALL

-- Level 4: grand total
SELECT
    NULL AS month,
    NULL AS region,
    NULL AS status,
    COUNT(*),
    SUM(amount),
    AVG(amount),
    MIN(amount),
    MAX(amount)
FROM base

ORDER BY month NULLS LAST, region NULLS LAST, status NULLS LAST;
```

**Configuration:**
- Table: `bench_events_1` (5M rows)
- Runs: 3 (report min, median, max execution time)
- Timeout: 10 minutes per run
- Metrics: Execution time per run, median time, rows returned

---

## Test 5: Window Functions

**Purpose:** Complex analytical queries with window functions - tests ranking, bucketing, and cumulative aggregations.

```sql
SELECT
    customer_id,
    event_type,
    region,
    created_at,
    amount,
    RANK() OVER (PARTITION BY region ORDER BY amount DESC) AS amount_rank,
    NTILE(10) OVER (PARTITION BY region ORDER BY created_at) AS time_decile,
    SUM(amount) OVER (PARTITION BY customer_id ORDER BY created_at
                      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total,
    AVG(amount) OVER (PARTITION BY event_type ORDER BY created_at
                      ROWS BETWEEN 10 PRECEDING AND CURRENT ROW) AS moving_avg,
    ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY created_at DESC) AS recency_order
FROM bench_events_2
WHERE created_at >= NOW() - INTERVAL '90 days'
  AND status = 'completed'
ORDER BY region, amount_rank
LIMIT 10000;
```

**Window functions used:**
- `RANK()` - Ranking within partitions
- `NTILE()` - Bucketing into deciles
- `SUM() OVER` - Running totals
- `AVG() OVER` - Moving averages
- `ROW_NUMBER()` - Row numbering within partitions

**Configuration:**
- Table: `bench_events_2` (5M rows)
- Runs: 3
- Timeout: 10 minutes per run
- Metrics: Execution time per run, median time, rows returned

---

## Test 6: Cross-Table JOIN

**Purpose:** Multi-table join performance on large datasets.

```sql
SELECT
    e1.region,
    e1.event_type AS event_type_1,
    e2.event_type AS event_type_2,
    COUNT(*) AS match_count,
    SUM(e1.amount) AS total_amount_1,
    SUM(e2.amount) AS total_amount_2,
    AVG(e1.amount) AS avg_amount_1,
    AVG(e2.amount) AS avg_amount_2,
    MAX(e1.created_at) AS latest_event_1,
    MAX(e2.created_at) AS latest_event_2
FROM bench_events_1 e1
INNER JOIN bench_events_2 e2
    ON e1.customer_id = e2.customer_id
    AND e1.region = e2.region
WHERE e1.status = 'completed'
  AND e2.status = 'completed'
  AND e1.created_at >= NOW() - INTERVAL '180 days'
  AND e2.created_at >= NOW() - INTERVAL '180 days'
GROUP BY e1.region, e1.event_type, e2.event_type
HAVING COUNT(*) > 100
ORDER BY match_count DESC, e1.region
LIMIT 500;
```

**Configuration:**
- Tables: `bench_events_1` (5M rows) ⨝ `bench_events_2` (5M rows)
- Join condition: `customer_id` + `region`
- Aggregations: COUNT, SUM, AVG, MAX
- Runs: 2
- Timeout: 10 minutes per run
- Metrics: Execution time per run, median time, rows returned

---

## Test 7: Phantom Read Isolation Test (SERIALIZABLE)

**Purpose:** Validate SERIALIZABLE isolation level prevents phantom reads.

**Connection A:**
```sql
BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;

-- First count
SELECT COUNT(*) FROM isolation_test WHERE test_value = $1;

-- Second count (after concurrent insert)
SELECT COUNT(*) FROM isolation_test WHERE test_value = $1;

COMMIT;
```

**Connection B (concurrent):**
```sql
BEGIN;
INSERT INTO isolation_test (test_value, data) VALUES ($1, $2);
COMMIT;
```

**Expected behavior:**
- Serialization error (SQLSTATE 40001), OR
- Consistent counts (no phantom reads)

**Configuration:**
- Isolation level: SERIALIZABLE
- Timeout: 60 seconds
- Metrics: PASS/FAIL, actual isolation behavior, error details

---

## Test 8: Non-Repeatable Read Isolation Test (REPEATABLE READ)

**Purpose:** Validate REPEATABLE READ isolation level prevents non-repeatable reads.

**Connection A:**
```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;

-- First read
SELECT data FROM isolation_test WHERE id = $1;

-- Second read (after concurrent update)
SELECT data FROM isolation_test WHERE id = $1;

COMMIT;
```

**Connection B (concurrent):**
```sql
BEGIN;
UPDATE isolation_test SET data = $1 WHERE id = $2;
COMMIT;
```

**Expected behavior:**
- Serialization error, OR
- Consistent reads (same value both times)

**Configuration:**
- Isolation level: REPEATABLE READ
- Timeout: 60 seconds
- Metrics: PASS/FAIL, actual isolation behavior, error details

---

## Test 9: Phantom Read with Default Isolation Level

**Purpose:** Verify whether default isolation level prevents phantom reads.

**Connection A:**
```sql
BEGIN;  -- Using default isolation level

-- First count
SELECT COUNT(*) FROM isolation_test WHERE test_value = $1;

-- Second count (after concurrent insert)
SELECT COUNT(*) FROM isolation_test WHERE test_value = $1;

COMMIT;
```

**Connection B (concurrent):**
```sql
BEGIN;
INSERT INTO isolation_test (test_value, data) VALUES ($1, $2);
COMMIT;
```

**Expected behavior:**
- **CockroachDB (default SERIALIZABLE):** PASS - prevents phantom reads
- **PostgreSQL (default READ COMMITTED):** FAIL - allows phantom reads

**Pass criteria:** Phantom reads must be prevented.

**Configuration:**
- Isolation level: DEFAULT
- Timeout: 60 seconds
- Purpose: Flag when default isolation is insufficient for data consistency requirements

---

## Test 10: Non-Repeatable Read with Default Isolation Level

**Purpose:** Verify whether default isolation level prevents non-repeatable reads.

**Connection A:**
```sql
BEGIN;  -- Using default isolation level

-- First read
SELECT data FROM isolation_test WHERE id = $1;

-- Second read (after concurrent update)
SELECT data FROM isolation_test WHERE id = $1;

COMMIT;
```

**Connection B (concurrent):**
```sql
BEGIN;
UPDATE isolation_test SET data = $1 WHERE id = $2;
COMMIT;
```

**Expected behavior:**
- **CockroachDB (default SERIALIZABLE):** PASS - prevents non-repeatable reads
- **PostgreSQL (default READ COMMITTED):** FAIL - allows non-repeatable reads

**Pass criteria:** Non-repeatable reads must be prevented.

**Configuration:**
- Isolation level: DEFAULT
- Timeout: 60 seconds
- Purpose: Flag when default isolation is insufficient for data consistency requirements

---

## Supporting Queries (Setup/Configuration)

### CockroachDB-Specific Configuration

```sql
-- Enable multiple active portals (CockroachDB v26.1 preview feature)
-- Required for multiple queries within the same transaction
SET multiple_active_portals_enabled = true;
```

### Cleanup Queries

```sql
-- Cleanup by test value
DELETE FROM isolation_test WHERE test_value = $1;

-- Cleanup by row ID
DELETE FROM isolation_test WHERE id = $1;

-- Insert test row with RETURNING
INSERT INTO isolation_test (test_value, data) 
VALUES ($1, $2) 
RETURNING id;
```

---

## Azure PostgreSQL Elastic Cluster (Citus) Adjustments

When running these tests against **Azure PostgreSQL Flexible Server (Citus)**, the following schema and configuration adjustments are required for distributed execution across worker nodes.

### Extension Enablement (Required First)

```sql
-- MUST run before creating distributed tables
CREATE EXTENSION IF NOT EXISTS citus;
```

### Table Distribution Strategy

Citus requires explicit table distribution across worker nodes. Unlike CockroachDB's automatic sharding, each table must be explicitly distributed with an appropriate shard key.

#### Distributed Tables (Hash-Sharded)

```sql
-- OLAP event tables: Distribute on customer_id (high cardinality, even distribution)
SELECT create_distributed_table('bench_events_1', 'customer_id');
SELECT create_distributed_table('bench_events_2', 'customer_id');
SELECT create_distributed_table('bench_events_3', 'customer_id');
SELECT create_distributed_table('bench_events_4', 'customer_id');
SELECT create_distributed_table('bench_events_5', 'customer_id');
SELECT create_distributed_table('bench_events_6', 'customer_id');
SELECT create_distributed_table('bench_events_7', 'customer_id');
SELECT create_distributed_table('bench_events_8', 'customer_id');
SELECT create_distributed_table('bench_events_9', 'customer_id');
SELECT create_distributed_table('bench_events_10', 'customer_id');
SELECT create_distributed_table('bench_events_11', 'customer_id');
SELECT create_distributed_table('bench_events_12', 'customer_id');
SELECT create_distributed_table('bench_events_13', 'customer_id');
SELECT create_distributed_table('bench_events_14', 'customer_id');
SELECT create_distributed_table('bench_events_15', 'customer_id');
SELECT create_distributed_table('bench_events_16', 'customer_id');

-- pgbench tables: Distribute on primary key
SELECT create_distributed_table('pgbench_accounts', 'aid');
SELECT create_distributed_table('pgbench_history', 'aid');  -- Co-located with accounts

-- Isolation test table
SELECT create_distributed_table('isolation_test', 'id');
```

**Default shard count:** 32 shards per distributed table

#### Reference Tables (Replicated)

Small tables (< 1M rows) that are frequently joined are replicated to all worker nodes for fast local joins:

```sql
-- Small tables: Replicate to all workers
SELECT create_reference_table('pgbench_branches');   -- 50K rows
SELECT create_reference_table('pgbench_tellers');    -- 500K rows
```

### Distribution Column Rationale

| Table | Distribution Column | Type | Rationale |
|-------|---------------------|------|-----------|
| `bench_events_1..16` | `customer_id` | Distributed | High cardinality (~1M unique values), OLAP queries filter on it, enables co-located joins across event tables |
| `pgbench_accounts` | `aid` | Distributed | Primary key (5M unique values), point lookups in Test 2 route to single shard |
| `pgbench_history` | `aid` | Distributed | Co-locate with `pgbench_accounts` for TPC-B transactions (Test 3) |
| `pgbench_branches` | N/A | **Reference** | Small (50K rows), frequently joined in TPC-B, replicate everywhere |
| `pgbench_tellers` | N/A | **Reference** | Small (500K rows), frequently joined in TPC-B, replicate everywhere |
| `isolation_test` | `id` | Distributed | Primary key, isolation tests use single-row operations |

### Co-Location Benefits

**pgbench TPC-B Transaction (Test 3):**
- `pgbench_accounts` and `pgbench_history` are co-located on `aid`
- Transactions touching the same `aid` execute on a single shard
- Branches and tellers are replicated, so joins are local
- Result: **TPC-B transactions can execute entirely on one worker node**

**OLAP Joins (Test 6):**
- All `bench_events_*` tables distributed on `customer_id`
- Joins on `customer_id` execute locally without data shuffle
- Result: **Cross-table joins are parallelized across workers**

### Query Routing Behavior

#### Single-Shard Routing (Fast)
```sql
-- Test 2: Routes to single shard based on aid
SELECT aid, abalance FROM pgbench_accounts WHERE aid = $1;
-- Execution: Coordinator → Single Worker Shard → Return

-- Test 7-10: Isolation tests route to single shard
SELECT data FROM isolation_test WHERE id = $1;
```

#### Parallel Execution (OLAP Fast Path)
```sql
-- Test 4: ROLLUP aggregation parallelized across all workers
-- Each worker aggregates its local shards, coordinator merges results

-- Test 5: Window functions execute on workers in parallel
-- Partitioning by region distributes work evenly

-- Test 6: Co-located join executes on workers
-- JOIN on customer_id uses local shards, no network shuffle
```

#### Coordinator Overhead (Expected)
```sql
-- Test 1: SELECT 1 has coordinator routing overhead
-- CockroachDB: Direct to gateway node
-- Citus: Coordinator → Worker → Coordinator
-- Result: 10-20% higher latency expected
```

### Transaction Isolation Limitations

**Important:** Citus does **not** provide distributed snapshot isolation for multi-shard transactions.

| Scenario | CockroachDB | Citus |
|----------|-------------|-------|
| Single-shard transaction | ✅ Full SERIALIZABLE | ✅ Full SERIALIZABLE |
| Multi-shard read snapshot | ✅ Consistent snapshot | ❌ No cross-shard snapshot |
| Multi-shard write | ✅ SERIALIZABLE | ⚠️ Atomic, no isolation guarantees |

**Impact on Tests:**
- **Tests 7-8 (SERIALIZABLE/REPEATABLE READ):** Expected to PASS when operations touch single shard
- **Tests 9-10 (Default isolation):** May show **PARTIAL** results if operations span multiple shards
- **Test 3 (TPC-B):** Works correctly because transactions are co-located (single shard)

### Verification Queries

```sql
-- Verify all tables are distributed
SELECT
    logicalrelid::regclass AS table_name,
    partmethod AS distribution_type,
    partkey AS distribution_column
FROM pg_dist_partition
ORDER BY logicalrelid::regclass::text;

-- Expected output shows:
-- 18 distributed tables (bench_events_1..16 + pgbench_accounts + pgbench_history + isolation_test)
-- 2 reference tables (pgbench_branches + pgbench_tellers)

-- Check shard count per table
SELECT
    logicalrelid::regclass AS table_name,
    count(*) AS shard_count
FROM pg_dist_shard
GROUP BY logicalrelid
ORDER BY logicalrelid::regclass::text;

-- Expected: 32 shards per distributed table, 1 shard per reference table

-- View shard distribution across workers
SELECT
    nodename,
    count(*) as shard_count
FROM pg_dist_placement p
JOIN pg_dist_node n ON p.groupid = n.groupid
WHERE n.noderole = 'worker'
GROUP BY nodename
ORDER BY shard_count DESC;

-- Expected: Approximately equal shard counts across workers
```

### Performance Expectations: Citus vs CockroachDB

Based on Citus architecture and distribution strategy:

| Test | Expected Citus Performance | Reason |
|------|---------------------------|--------|
| **Test 1: SELECT 1** | 10-20% slower | Coordinator routing overhead |
| **Test 2: Point Lookup** | 20-30% slower | Single-shard through coordinator |
| **Test 3: TPC-B Workload** | 15-25% faster | Parallel workers, PostgreSQL maturity, co-located transactions |
| **Test 4: ROLLUP Aggregation** | **2-3x faster** | Parallel aggregation on workers |
| **Test 5: Window Functions** | **2-3x faster** | PostgreSQL's optimized window function execution |
| **Test 6: JOIN** | 20-40% faster | Co-located join on `customer_id` |
| **Test 7-8: Isolation (SERIALIZABLE)** | ✅ PASS | Single-shard transactions |
| **Test 9-10: Isolation (DEFAULT)** | 🟡 PARTIAL | Multi-shard limitations documented |

**Key Takeaways:**
- ✅ **Citus wins on OLAP** (aggregations, analytics) - 2-3x faster due to parallel execution
- ⚠️ **CockroachDB wins on OLTP latency** - 20-30% lower latency for point operations
- 🟡 **Citus has weaker isolation** - Multi-shard transactions lack snapshot isolation
- ✅ **Citus wins on bulk loading** - 5-10x faster due to parallel COPY across workers

### Configuration Settings

```sql
-- View current shard count (default: 32)
SHOW citus.shard_count;

-- Enable multiple active portals (if needed for complex transactions)
SET citus.multi_shard_commit_protocol = '2pc';

-- Check Citus version
SELECT * FROM citus_version();

-- View worker nodes
SELECT * FROM pg_dist_node;
```


