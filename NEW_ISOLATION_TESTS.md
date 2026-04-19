# New Isolation Tests - Default Isolation Level Comparison

## Overview

Added **Test 9** and **Test 10** to demonstrate the difference in default isolation level behavior between CockroachDB and PostgreSQL.

## Motivation

Tests 7 and 8 explicitly set isolation levels (`SERIALIZABLE` and `REPEATABLE READ`), which both databases support. This masked an important difference:

- **CockroachDB default**: SERIALIZABLE
- **PostgreSQL default**: READ COMMITTED

The new tests demonstrate this difference by running the same isolation scenarios **without** explicitly setting isolation levels.

---

## Test 9: Phantom Read with Default Isolation

**File**: `src/tests/test_09_phantom_read_default.py`

### What It Tests

Checks whether a database prevents phantom reads using its **default isolation level**.

### Scenario

1. Connection A begins transaction (no explicit isolation level)
2. Connection A counts rows matching a test value (count = 0)
3. Connection B inserts a new row with that test value
4. Connection A counts again
5. Connection A commits

### Expected Behavior

| Database | Default Level | Expected Result |
|----------|--------------|-----------------|
| **CockroachDB** | SERIALIZABLE | ✅ PASS: No phantom read (counts remain 0 → 0) |
| **PostgreSQL** | READ COMMITTED | ❌ FAIL (DEFAULT SETTINGS): Phantom read occurs (counts change 0 → 1) |

### Key Difference

- CockroachDB: **PASS** - Prevents phantom reads by default
- PostgreSQL: **FAIL (DEFAULT SETTINGS)** - Does not prevent phantom reads by default (per SQL standard for READ COMMITTED)

---

## Test 10: Non-Repeatable Read with Default Isolation

**File**: `src/tests/test_10_nonrepeatable_read_default.py`

### What It Tests

Checks whether a database prevents non-repeatable reads using its **default isolation level**.

### Scenario

1. Setup: Insert test row with `data = 'initial_value'`
2. Connection A begins transaction (no explicit isolation level)
3. Connection A reads the row (`data = 'initial_value'`)
4. Connection B updates the row to `data = 'updated_value'`
5. Connection A reads the row again
6. Connection A commits

### Expected Behavior

| Database | Default Level | Expected Result |
|----------|--------------|-----------------|
| **CockroachDB** | SERIALIZABLE | ✅ PASS: Consistent reads ('initial_value' → 'initial_value') |
| **PostgreSQL** | READ COMMITTED | ❌ FAIL (DEFAULT SETTINGS): Non-repeatable read ('initial_value' → 'updated_value') |

### Key Difference

- CockroachDB: **PASS** - Prevents non-repeatable reads by default
- PostgreSQL: **FAIL (DEFAULT SETTINGS)** - Does not prevent non-repeatable reads by default (per SQL standard for READ COMMITTED)

---

## Implementation Details

### Test Classes

Both tests inherit from `IsolationTest` base class and follow the same pattern as Tests 7 and 8, with key differences:

1. **No explicit isolation level**: Use `BEGIN` instead of `BEGIN TRANSACTION ISOLATION LEVEL X`
2. **Database-aware validation**: Pass/fail logic accounts for different default behaviors
3. **Clear output**: Test output indicates which isolation level is being used by default

### Integration

**Modified Files**:
- `src/test_runner.py`:
  - Added imports for new test classes
  - Increased test count from 8 to 10
  - Added Test 9 and Test 10 execution in sequential phase
  - Updated documentation strings

- `src/output/text_summary.py`:
  - Added test names for Tests 9 and 10
  - Updated isolation test category to include `test_09` and `test_10`
  - Updated test iteration from `range(1, 9)` to `range(1, 11)`
  - Updated test counts from 8 to 10

### Test Names

```python
'test_09': 'Test 9: Phantom Read (Default Isolation)'
'test_10': 'Test 10: Non-Repeatable Read (Default Isolation)'
```

---

## Running the Tests

### Run Full Benchmark (All 10 Tests)

```bash
python benchmark.py \
  --crdb "postgresql://user:pass@crdb-host:26257/dbname?sslmode=require" \
  --pg "postgresql://user:pass@pg-host:5432/dbname?sslmode=require" \
  --output-dir ./outputs
```

### Run Only New Tests

Currently, the test runner executes all tests. To run only Tests 9-10, you would need to modify the test runner or create a standalone script.

---

## Expected Output

### CockroachDB (Test 9)

```
Test 9: Phantom Read (Default Isolation)
----------------------------------------------------------------------

[CRDB] Running Test 9...

Executing phantom read test (DEFAULT isolation level)...
  Isolation level: DEFAULT
  Expected behavior:
    - CockroachDB (default SERIALIZABLE): PASS if no phantom read

  [Conn A] BEGIN (using default isolation level)
  [Conn A] Initial count: 0
  [Conn B] BEGIN; INSERT; COMMIT
  [Conn B] Inserted 1 row with test_value = 'phantom_default_test_1776419367'
  [Conn A] Second count...
  [Conn A] Second count: 0
  [Conn A] COMMIT

  ✅ PASS: No phantom read (counts: 0 → 0)
  [Cleanup] Deleted test rows: DELETE 1
```

### PostgreSQL (Test 9)

```
Test 9: Phantom Read (Default Isolation)
----------------------------------------------------------------------

[PG] Running Test 9...

Executing phantom read test (DEFAULT isolation level)...
  Isolation level: DEFAULT
  Expected behavior:
    - PostgreSQL (default READ COMMITTED): FAIL if phantom read occurs

  [Conn A] BEGIN (using default isolation level)
  [Conn A] Initial count: 0
  [Conn B] BEGIN; INSERT; COMMIT
  [Conn B] Inserted 1 row with test_value = 'phantom_default_test_1776419367'
  [Conn A] Second count...
  [Conn A] Second count: 1
  [Conn A] COMMIT

  ❌ FAIL (DEFAULT SETTINGS): Phantom read occurred (counts: 0 → 1)
  [Cleanup] Deleted test rows: DELETE 1
```

---

## Interpretation Guide

### Test Results Reflect Default Safety Guarantees

These tests evaluate whether default isolation settings prevent common read anomalies:

- **CockroachDB PASS**: Enforces SERIALIZABLE by default - prevents phantom reads and non-repeatable reads
- **PostgreSQL FAIL (DEFAULT SETTINGS)**: Uses READ COMMITTED by default - does not prevent these anomalies

### What This Demonstrates

1. **CockroachDB's stronger default guarantees**: Developers get SERIALIZABLE isolation without asking for it
2. **PostgreSQL's standard compliance vs. safety trade-off**: READ COMMITTED is the ANSI SQL default but requires explicit configuration for stronger guarantees
3. **Why Test 7 and Test 8 both passed**: Both databases support stronger isolation when explicitly requested
4. **The FAIL status is intentional**: It highlights that PostgreSQL applications need explicit isolation level configuration for anomaly prevention

### Implications for Applications

- **CockroachDB**: Simpler application code - no need to set isolation levels for strong consistency
- **PostgreSQL**: Applications must explicitly request `REPEATABLE READ` or `SERIALIZABLE` for strong guarantees, or accept the risk of read anomalies

---

## Comparison Matrix

| Test | Isolation Level | CockroachDB | PostgreSQL |
|------|----------------|-------------|------------|
| Test 7 | SERIALIZABLE (explicit) | ✅ PASS - No phantom read | ✅ PASS - No phantom read |
| Test 8 | REPEATABLE READ (explicit) | ✅ PASS - Consistent reads | ✅ PASS - Consistent reads |
| **Test 9** | **DEFAULT** | ✅ **PASS** - No phantom read | ❌ **FAIL (DEFAULT SETTINGS)** - Phantom read occurs |
| **Test 10** | **DEFAULT** | ✅ **PASS** - Consistent reads | ❌ **FAIL (DEFAULT SETTINGS)** - Non-repeatable read occurs |

---

## Technical Notes

### PostgreSQL Isolation Levels

PostgreSQL implements:
- `READ UNCOMMITTED` → treated as READ COMMITTED
- `READ COMMITTED` → default, allows non-repeatable reads and phantom reads
- `REPEATABLE READ` → uses snapshot isolation (actually prevents phantoms too)
- `SERIALIZABLE` → true serializability via SSI (Serializable Snapshot Isolation)

### CockroachDB Isolation Levels

CockroachDB only supports:
- `SERIALIZABLE` → default and only option
- Requests for weaker levels are upgraded to SERIALIZABLE

### Why This Matters

The choice of default isolation level represents a **fundamental design philosophy**:

- **CockroachDB**: "Correctness by default" - strongest guarantees without developer intervention → **PASS**
- **PostgreSQL**: "Performance by default" - weaker guarantees for better read concurrency → **FAIL (DEFAULT SETTINGS)**

The FAIL status for PostgreSQL is not a bug - it's a **feature flag** highlighting that applications must explicitly configure stronger isolation if they need to prevent read anomalies. This makes the safety trade-off visible in the benchmark results.
