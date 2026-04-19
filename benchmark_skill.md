# Skill: PostgreSQL-Compatible Database Performance Benchmark

## Purpose
Build a performance testing application that benchmarks two PostgreSQL-compatible databases side by side and displays results in a unified comparison dashboard.

**Database A**: CockroachDB Advanced — Azure, Single Region, 8 vCPU × 3 Nodes  
**Database B**: Azure Database for PostgreSQL – Flexible Server — Azure, Single Region, 8 vCPU × 3 Nodes  
**Data Scale**: 20 tables × 5,000,000 rows each  
**Test Window**: Minimum 5 minutes, maximum 30 minutes (excluding data load)

---

## Step 1: Gather Connection Information

Before building anything, prompt the user for:
1. CockroachDB connection string (psql-compatible): `postgresql://user:pass@host:26257/dbname?sslmode=require`
2. Azure PostgreSQL Flexible Server connection string: `postgresql://user:pass@host:5432/dbname?sslmode=require`
3. Whether to skip data loading if tables already exist (`--skip-load`)
4. Preferred output directory for reports

---

## Step 2: Application Architecture

Build a **Python benchmark script** (`benchmark.py`) that:
- Accepts `--crdb` and `--pg` connection string arguments
- Optionally accepts `--skip-load`, `--output-dir`
- Connects to both databases concurrently using `asyncpg` (async) or `psycopg2` with thread pools
- Runs all tests and captures raw timing samples
- Generates three output files on completion (see Step 8)
- Prints live progress to stdout during execution

Also generate a **self-contained HTML dashboard** (`benchmark_report.html`) with side-by-side results, inline CSS/JS, Chart.js charts (via CDN or embedded).

**Concurrency model**: Use `asyncio` + `asyncpg` for async query execution. Maintain separate connection pools for each database, sized to match the concurrency level of each test.

---

## Step 3: Schema Setup

Execute on **BOTH** databases. Use `IF NOT EXISTS` so re-runs are safe.

### pgbench-Compatible Tables (TPC-B)

```sql
CREATE TABLE IF NOT EXISTS pgbench_branches (
  bid      SERIAL PRIMARY KEY,
  bbalance INT  NOT NULL DEFAULT 0,
  filler   CHAR(88) NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS pgbench_tellers (
  tid      SERIAL PRIMARY KEY,
  bid      INT  NOT NULL,
  tbalance INT  NOT NULL DEFAULT 0,
  filler   CHAR(84) NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS pgbench_accounts (
  aid      BIGSERIAL PRIMARY KEY,
  bid      INT  NOT NULL,
  abalance INT  NOT NULL DEFAULT 0,
  filler   CHAR(84) NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS pgbench_history (
  tid    INT       NOT NULL,
  bid    INT       NOT NULL,
  aid    BIGINT    NOT NULL,
  delta  INT       NOT NULL,
  mtime  TIMESTAMP NOT NULL DEFAULT NOW(),
  filler CHAR(22)  DEFAULT NULL
);
```

### Analytical / OLAP Tables (bench_events_1 through bench_events_16)

Repeat for N = 1 to 16:

```sql
CREATE TABLE IF NOT EXISTS bench_events_{N} (
  id          BIGSERIAL    PRIMARY KEY,
  customer_id BIGINT       NOT NULL,
  session_id  UUID         NOT NULL DEFAULT gen_random_uuid(),
  event_type  VARCHAR(50)  NOT NULL,
  region      VARCHAR(20)  NOT NULL,
  amount      NUMERIC(12,2) NOT NULL DEFAULT 0.00,
  quantity    INT          NOT NULL DEFAULT 1,
  status      VARCHAR(20)  NOT NULL DEFAULT 'completed',
  tags        TEXT[],
  metadata    JSONB,
  created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bench_events_{N}_customer ON bench_events_{N}(customer_id);
CREATE INDEX IF NOT EXISTS idx_bench_events_{N}_created  ON bench_events_{N}(created_at);
CREATE INDEX IF NOT EXISTS idx_bench_events_{N}_region   ON bench_events_{N}(region);
```

> **Azure PostgreSQL note**: `gen_random_uuid()` requires `CREATE EXTENSION IF NOT EXISTS pgcrypto;` — run this first on the Azure PG database.

### Isolation Test Table

```sql
CREATE TABLE IF NOT EXISTS isolation_test (
  id         BIGSERIAL PRIMARY KEY,
  test_value VARCHAR(100) NOT NULL,
  data       TEXT NOT NULL
);
```

**Total**: 4 pgbench tables + 16 bench_events tables + 1 isolation_test = 21 tables  
(The 20 primary tables for 5M-row loading are: pgbench_accounts + bench_events_1 through bench_events_16 + pgbench_tellers + pgbench_branches = 19; round out to 20 by including bench_events tables 1–16 + pgbench_accounts + pgbench_tellers + pgbench_branches + pgbench_history)

---

## Step 4: Data Loading

**Check before loading**: `SELECT COUNT(*) FROM pgbench_accounts` — skip if rows already exist.

### pgbench Tables
- `pgbench_branches`: 50,000 rows (scale factor 50,000)
- `pgbench_tellers`: 500,000 rows (10 × scale factor)
- `pgbench_accounts`: 5,000,000 rows (100 × scale factor)
- `pgbench_history`: starts empty (populated by test)

### bench_events_{N} Tables (N = 1–16)
Load 5,000,000 rows per table using batch inserts of 10,000 rows. Use 6 concurrent worker coroutines.

Generate each row with:
```python
event_types = ['purchase', 'refund', 'view', 'click', 'signup', 'login', 'checkout', 'search']
regions     = ['eastus', 'westus', 'northeurope', 'southeastasia', 'australiaeast']
statuses    = ['completed', 'pending', 'failed', 'cancelled']

customer_id = random.randint(1, 500_000)
event_type  = random.choice(event_types)
region      = random.choice(regions)
amount      = round(random.uniform(0.01, 9999.99), 2)
quantity    = random.randint(1, 100)
status      = random.choice(statuses)
created_at  = now - timedelta(days=random.randint(0, 730))  # past 2 years
```

### isolation_test Table
Insert 10,000 rows with `value` uniformly distributed between 1 and 1,000.

**Show a progress bar** during loading. Estimated load time: 15–25 minutes (excluded from test window timing).

---

## Step 5: Test Definitions

Run all 8 tests against both databases. Capture wall-clock latency for every individual operation. Compute p50, p95, p99 from raw samples.

---

### Test 1: Simple Latency Baseline — `SELECT 1`
**Purpose**: Round-trip latency with zero data access.

```sql
SELECT 1;
```

- Iterations: 10,000 (serial, single connection)
- Measure: p50 / p95 / p99 latency (ms), throughput (QPS)
- Target duration: ~60 seconds per database

---

### Test 2: Primary Key Point Lookup
**Purpose**: Single-row indexed fetch.

```sql
SELECT aid, abalance FROM pgbench_accounts WHERE aid = $1;
-- Use random aid in [1, 5_000_000]
```

- Iterations: 50,000
- Concurrency: 8 workers
- Measure: p50 / p95 / p99 latency (ms), QPS
- Target duration: ~90 seconds per database

---

### Test 3: Standard pgbench TPC-B Workload
**Purpose**: Industry-standard OLTP mixed read/write workload.

Execute the standard TPC-B-like transaction:
```sql
BEGIN;
UPDATE pgbench_accounts SET abalance = abalance + {delta} WHERE aid = {aid};
SELECT abalance FROM pgbench_accounts WHERE aid = {aid};
UPDATE pgbench_tellers  SET tbalance = tbalance + {delta} WHERE tid = {tid};
UPDATE pgbench_branches SET bbalance = bbalance + {delta} WHERE bid = {bid};
INSERT INTO pgbench_history (tid, bid, aid, delta, mtime)
  VALUES ({tid}, {bid}, {aid}, {delta}, NOW());
COMMIT;
```

Random values:
- `aid` ∈ [1, 5,000,000]
- `tid` ∈ [1, 500,000]
- `bid` ∈ [1, 50,000]
- `delta` ∈ [-5000, 5000]

- **Duration: 5 minutes (300 seconds) per database** — sequential (one DB at a time to avoid contention noise)
- Concurrency: 16 workers
- If `pgbench` binary is on PATH, prefer: `pgbench -c 16 -j 4 -T 300 <connection_string>` and capture its output
- Measure: TPS, p50/p95/p99 transaction latency (ms), total transactions completed, error count, **retry count** (SQLSTATE 40001 serialization errors — retry up to 3× with exponential backoff and count them)

---

### Test 4: Rollup Aggregation Query
**Purpose**: GROUP BY ROLLUP over 5M rows — tests the planner and aggregation engine.

**Note**: CockroachDB v26.1 doesn't support `GROUP BY ROLLUP` syntax. Use `UNION ALL` to manually construct hierarchical aggregation levels (produces identical results, works on both databases).

```sql
-- CockroachDB-compatible version using UNION ALL (also works on PostgreSQL)
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
  month, region, status,
  COUNT(*) AS event_count,
  SUM(amount) AS total_amount,
  AVG(amount) AS avg_amount,
  MIN(amount) AS min_amount,
  MAX(amount) AS max_amount
FROM base
GROUP BY month, region, status

UNION ALL

-- Level 2: month, region subtotals
SELECT month, region, NULL, COUNT(*), SUM(amount), AVG(amount), MIN(amount), MAX(amount)
FROM base
GROUP BY month, region

UNION ALL

-- Level 3: month subtotals
SELECT month, NULL, NULL, COUNT(*), SUM(amount), AVG(amount), MIN(amount), MAX(amount)
FROM base
GROUP BY month

UNION ALL

-- Level 4: grand total
SELECT NULL, NULL, NULL, COUNT(*), SUM(amount), AVG(amount), MIN(amount), MAX(amount)
FROM base

ORDER BY month NULLS LAST, region NULLS LAST, status NULLS LAST;
```

- Runs: 3 (report min / median / max)
- Concurrency: 1 (analytical)
- Measure: Execution time per run (ms), median, rows returned
- Timeout: 10 minutes — record TIMEOUT if exceeded, move on
- Target: 2–5 minutes per database

---

### Test 5: OLAP Window Function Query
**Purpose**: Analytical ranking and windowing across 5M rows with partitioning.

```sql
SELECT
  customer_id,
  region,
  COUNT(*)                                                            AS event_count,
  SUM(amount)                                                         AS total_spend,
  AVG(amount)                                                         AS avg_spend,
  RANK()    OVER (PARTITION BY region ORDER BY SUM(amount) DESC)      AS regional_rank,
  NTILE(10) OVER (PARTITION BY region ORDER BY SUM(amount) DESC)      AS spend_decile,
  SUM(SUM(amount)) OVER (PARTITION BY region)                         AS region_total,
  ROUND(
    SUM(amount) / NULLIF(SUM(SUM(amount)) OVER (PARTITION BY region), 0) * 100,
    2
  )                                                                   AS pct_of_region
FROM bench_events_1
GROUP BY customer_id, region
ORDER BY region, regional_rank
LIMIT 500;
```

- Runs: 3 (report min / median / max)
- Concurrency: 1
- Measure: Execution time per run (ms), median, rows returned
- Timeout: 10 minutes
- Target: 2–5 minutes per database

---

### Test 6: Cross-Table JOIN + Aggregation
**Purpose**: Multi-table join performance at scale.

```sql
SELECT
  e1.customer_id,
  e1.region,
  COUNT(DISTINCT e1.session_id)         AS sessions_t1,
  COUNT(DISTINCT e2.session_id)         AS sessions_t2,
  SUM(e1.amount)                        AS spend_t1,
  SUM(e2.amount)                        AS spend_t2,
  SUM(e1.amount) + SUM(e2.amount)       AS total_spend
FROM bench_events_1 e1
JOIN bench_events_2 e2
  ON e1.customer_id = e2.customer_id
WHERE e1.status   = 'completed'
  AND e2.status   = 'completed'
  AND e1.created_at >= NOW() - INTERVAL '12 months'
GROUP BY e1.customer_id, e1.region
ORDER BY total_spend DESC
LIMIT 100;
```

- Runs: 2
- Concurrency: 1
- Measure: Execution time per run (ms), rows returned
- Timeout: 10 minutes

---

### Test 7: Isolation — Phantom Read Check
**Purpose**: Verify whether SERIALIZABLE isolation prevents phantom reads.

**Setup**: Confirm `isolation_test` has rows with `test_value LIKE 'value_%'`.

**Procedure** — use **two entirely separate connections**:

1. **Connection A** opens a SERIALIZABLE transaction and reads a range:
   ```sql
   BEGIN ISOLATION LEVEL SERIALIZABLE;
   SELECT COUNT(*) AS cnt FROM isolation_test WHERE test_value LIKE 'value_%';
   -- Record as count_before; do NOT commit yet
   ```

2. **Connection B** inserts a new row and commits:
   ```sql
   INSERT INTO isolation_test (test_value, data) VALUES ('value_999', 'phantom_probe');
   COMMIT;
   ```

3. **Connection A** re-reads the same range:
   ```sql
   SELECT COUNT(*) AS cnt FROM isolation_test WHERE test_value LIKE 'value_%';
   -- Record as count_after
   COMMIT;
   ```

**Evaluation**:
| Result | Meaning |
|--------|---------|
| `count_before == count_after` | ✅ PASS — Phantom read prevented |
| `count_before != count_after` | ❌ FAIL — Phantom read occurred |
| Connection A raises serialization error (40001) | ✅ PASS — DB correctly aborted |

Record the actual isolation level via `SHOW transaction_isolation;` and include in results.

**Cleanup after test**: `DELETE FROM isolation_test WHERE data = 'phantom_probe';`

---

### Test 8: Isolation — Non-Repeatable Read Check
**Purpose**: Verify whether REPEATABLE READ isolation prevents non-repeatable reads.

**Setup**: Ensure a row with `id = 1` exists in `isolation_test`.

**Procedure** — use **two entirely separate connections**:

1. **Connection A** opens a REPEATABLE READ transaction and reads a value:
   ```sql
   BEGIN ISOLATION LEVEL REPEATABLE READ;
   SELECT data FROM isolation_test WHERE id = 1;
   -- Record as data_before; do NOT commit yet
   ```

2. **Connection B** updates the same row and commits:
   ```sql
   UPDATE isolation_test SET data = 'updated_value' WHERE id = 1;
   COMMIT;
   ```

3. **Connection A** re-reads the same row:
   ```sql
   SELECT data FROM isolation_test WHERE id = 1;
   -- Record as data_after
   COMMIT;
   ```

**Evaluation**:
| Result | Meaning |
|--------|---------|
| `data_before == data_after` | ✅ PASS — Non-repeatable read prevented |
| `data_before != data_after` | ❌ FAIL — Non-repeatable read occurred |
| Connection A raises serialization/isolation error | ✅ PASS |

> **CockroachDB note**: CockroachDB is SERIALIZABLE-only by default. If REPEATABLE READ is not supported, fall back to SERIALIZABLE and document it. As of v23.1+, READ COMMITTED is available via session setting. Always document the actual isolation level used.

---

## Step 6: Timing Plan

Target total runtime: **15–25 minutes** (excluding data loading).

| Test | Per-DB Duration | Both DBs |
|------|----------------|----------|
| Test 1: SELECT 1 (parallel) | ~60 sec | ~60 sec |
| Test 2: Point Lookup (parallel) | ~90 sec | ~90 sec |
| Test 3: pgbench TPC-B (sequential) | 5 min each | ~10 min |
| Test 4: Rollup Query (sequential) | ~2–4 min | ~4–8 min |
| Test 5: OLAP Window (sequential) | ~2–4 min | ~4–8 min |
| Test 6: Cross-Table JOIN (sequential) | ~1–3 min | ~2–6 min |
| Test 7: Phantom Read | <1 min | ~1 min |
| Test 8: Non-Repeatable Read | <1 min | ~1 min |
| **Total** | | **~23–35 min** |

Run Tests 1–2 in parallel across both databases simultaneously. Run Test 3 sequentially (one DB at a time) to avoid noise. Run Tests 4–8 sequentially. Apply 10-minute per-query timeout to Tests 4–6.

If total projected duration exceeds 30 minutes, reduce Test 2 iterations from 50,000 to 20,000 and Test 3 from 300s to 180s per DB.

---

## Step 7: Results Dashboard

### Layout (Side-by-Side HTML Table)

```
┌────────────────────────────────────────────────────────────────────────────┐
│   CockroachDB Advanced  vs  Azure PostgreSQL Flexible  │  Azure — Single   │
│   Region — 8 vCPU × 3 Nodes — 20 tables × 5M rows each                   │
├──────────────────────────┬──────────────────────┬──────────────┬───────────┤
│ Test / Metric            │  CockroachDB         │  Azure PG    │  Δ %      │
├──────────────────────────┼──────────────────────┼──────────────┼───────────┤
│ SELECT 1 — p50           │  X.XX ms 🟢          │  X.XX ms     │  -XX%     │
│ SELECT 1 — p95           │  ...                 │  ...         │  ...      │
│ SELECT 1 — p99           │  ...                 │  ...         │  ...      │
│ SELECT 1 — QPS           │  ...                 │  ...         │  ...      │
│ ...                      │  ...                 │  ...         │  ...      │
│ Phantom Read             │  ✅ PASS             │  ✅ PASS     │  —        │
│ Non-Repeatable Read      │  ✅ PASS             │  ✅ PASS     │  —        │
└──────────────────────────┴──────────────────────┴──────────────┴───────────┘
```

### Visual Requirements
- **Green cell** (`#22c55e` background, dark text): the faster / better result in each row
- **Red cell** (`#ef4444` background, white text): the slower / worse result
- **Δ % column**: `((B - A) / A) × 100` — label which direction is better
- **PASS badge**: green pill; **FAIL badge**: red pill; **TIMEOUT**: orange badge
- **Summary banner** at the top: overall winner by category (OLTP, OLAP, Isolation, Latency)
- **Metadata block**: test timestamp, cluster versions (`SELECT version()`), node counts, row counts confirmed, total test duration

### Charts (Chart.js)
1. **Latency Comparison Bar Chart** — Tests 1–3: grouped bars for p50/p95/p99 per database
2. **Query Time Comparison Bar Chart** — Tests 4–6: grouped bars for median execution time
3. **TPS Over Time Line Chart** — Test 3: if pgbench output includes per-second TPS, plot the time series for both databases

### Color Identity
- CockroachDB: `#CF2132` (Cockroach Red)
- Azure PostgreSQL: `#0078D4` (Azure Blue)
- Better: `#22c55e`
- Worse: `#ef4444`
- Timeout: `#f97316`

---

## Step 8: Output Files

| File | Contents |
|------|----------|
| `benchmark_results.json` | Full raw results — all samples, all metrics, both DBs |
| `benchmark_report.html` | Self-contained dashboard — inline CSS/JS, no external deps required at view time |
| `benchmark_summary.txt` | Plain-text summary (< 50 lines) suitable for Slack or email |

---

## Step 9: Database-Specific Implementation Notes

### CockroachDB
- Default port: **26257**
- SSL: `sslmode=require` or `sslmode=verify-full`
- **SERIALIZABLE isolation by default** — note this prominently in the report
- `gen_random_uuid()` is natively supported
- `SERIAL` / `BIGSERIAL` work but generate contention at high insert rates; for this benchmark keep them for pgbench compatibility
- Serialization errors (SQLSTATE `40001`): implement automatic retry with up to 3 attempts and jittered exponential backoff; track retry counts and display them in results
- Capture version with `SELECT version();` — include in report metadata
- For hot-spot contention in pgbench (pgbench_branches / pgbench_tellers): this is **intentional** and tests the DB's contention handling — document retry behavior

### Azure PostgreSQL Flexible Server
- Default port: **5432**
- SSL enforced: `sslmode=require`
- Run `CREATE EXTENSION IF NOT EXISTS pgcrypto;` before schema creation (for `gen_random_uuid()`)
- Supports READ COMMITTED, REPEATABLE READ, and SERIALIZABLE isolation
- For ROLLUP queries: ensure `SET enable_hashagg = on;`
- Capture version with `SELECT version();`

### Retry Logic (both databases)
```python
async def execute_with_retry(conn, query, *args, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await conn.fetch(query, *args)
        except asyncpg.SerializationError:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep((2 ** attempt) + random.uniform(0, 0.1))
```

### Connection Pool Sizing
- Tests 1–2: pool size = 1 (serial) or 8 (concurrent)
- Test 3 (pgbench): pool size = 16
- Tests 4–6: pool size = 1
- Tests 7–8: exactly 2 connections per database (Connection A + Connection B)

---

## Step 10: Validation Checklist

Before presenting results, verify:
- [ ] Both databases confirmed 5,000,000 rows in each of the 20 primary tables (via `SELECT COUNT(*)`)
- [ ] All 8 tests completed or recorded as TIMEOUT
- [ ] Total test duration is between 5 and 30 minutes (assert and warn if not)
- [ ] Tests 7 and 8 used **separate** connections for Connection A and Connection B
- [ ] Latency percentiles computed from **raw sample arrays** — not approximated
- [ ] HTML report opens correctly in a browser without internet if CDN assets are embedded
- [ ] CockroachDB retry behavior and isolation level are documented in results
- [ ] Database versions and cluster config captured via `SELECT version()`
- [ ] `benchmark_results.json` is valid JSON (run `json.dumps(...)`; validate no NaN/Infinity)
- [ ] Summary banner correctly identifies the winner per category
