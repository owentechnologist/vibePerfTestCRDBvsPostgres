# Isolation Tests Fix - Multiple Active Portals

## Problem

Tests 7 and 8 (isolation tests) were failing with:

```
FeatureNotSupportedError: unimplemented: multiple active portals is in preview
HINT: set session variable multiple_active_portals_enabled to true
See: https://go.crdb.dev/issue-v/40195/v26.1
```

## Root Cause

Both isolation tests execute multiple queries within the same transaction:
- **Test 7 (Phantom Read):** Two SELECT COUNT(*) queries in SERIALIZABLE transaction
- **Test 8 (Non-Repeatable Read):** Two SELECT queries in REPEATABLE READ transaction

CockroachDB v26.1 has a limitation where multiple PostgreSQL "portals" (server-side cursors) cannot be active simultaneously within a transaction by default. This is a preview feature that requires explicit enablement.

## Solution

Added session variable setting before starting each isolation test transaction:

```python
await self.conn_a.execute("SET multiple_active_portals_enabled = true")
await self.conn_a.execute("BEGIN TRANSACTION ISOLATION LEVEL ...")
```

## Files Modified

1. **src/tests/test_07_phantom_read.py** (line ~57-59)
   - Added `SET multiple_active_portals_enabled = true` before transaction start

2. **src/tests/test_08_nonrepeatable_read.py** (line ~67-69)
   - Added `SET multiple_active_portals_enabled = true` before transaction start

## Validation Results

```
✅ Test 7 (Phantom Read): PASS
   - No phantom read detected (counts: 0 → 0)
   - SERIALIZABLE isolation working correctly
   - Duration: 0.77s

✅ Test 8 (Non-Repeatable Read): PASS
   - No non-repeatable read detected (values consistent)
   - REPEATABLE READ isolation working correctly
   - Duration: 0.81s
```

## Impact on benchmark.py

The fix is **automatically included** when running `benchmark.py` because:
- `benchmark.py` → `TestRunner.run_all_tests()` → `TestRunner._run_olap_and_isolation_tests()`
- This imports and executes `Test07PhantomRead` and `Test08NonRepeatableRead`
- The modified test files now include the fix

No changes to `benchmark.py` itself were required.

## Testing the Fix

Run the validation script:
```bash
python test_isolation_fix.py
```

Or run the full benchmark:
```bash
python benchmark.py --crdb $(cat crdb_connection.txt) --skip-load
```

## References

- CockroachDB Issue: https://go.crdb.dev/issue-v/40195/v26.1
- Feature: Multiple Active Portals (Preview in v26.1)
