# Output Format Update - p50, p99, p99.99 Performance Metrics

## Overview

Updated the benchmark output to display comprehensive performance metrics including p50, p99, and p99.99 percentiles for all 8 tests when running against CockroachDB only.

## Changes Made

### 1. Enhanced Metrics Collection (`src/metrics.py`)

**Added p99.99 percentile tracking:**
- Updated `PercentileStats` dataclass to include `p99_99` field
- Modified `compute_percentiles()` to calculate p99.99 (99.99th percentile)
- Updated test output to display p99.99 alongside other percentiles

### 2. New Output Format (`src/output/text_summary.py`)

**Created CockroachDB-only detailed output:**
- Detects when only CockroachDB is configured (no Azure PostgreSQL)
- Displays a clean performance table with all 8 tests
- Shows appropriate metrics for each test type:
  - **OLTP Tests (1-2)**: p50, p99, p99.99 latency in milliseconds
  - **TPC-B Test (3)**: Transactions per second (TPS), success/failed counts
  - **OLAP Tests (4-6)**: Median, min, max execution times in seconds
  - **Isolation Tests (7-8)**: Pass/Fail status with behavior description

### 3. Fixed isolation_test Table Schema

**Corrected database schema:**
- Old schema: `id`, `value`, `label`
- New schema: `id`, `test_value`, `data`
- Tests 7 and 8 now run successfully without column errors

## Example Output

When running tests against CockroachDB only:

```
======================================================================
COCKROACHDB PERFORMANCE RESULTS
======================================================================

Performance Metrics:
----------------------------------------------------------------------
Test                                Status     p50          p99          p99.99
----------------------------------------------------------------------
Test 1: SELECT 1                    ✓ PASS          48.24ms      66.89ms     285.93ms
Test 2: Point Lookup                ✓ PASS          50.23ms      73.59ms     686.95ms
Test 3: TPC-B Workload              ✓ PASS           52.2 TPS  (success: 15654, failed: 0)
Test 4: ROLLUP Aggregation          ✓ PASS           0.10s        0.10s        0.11s
                                               (median)   (min)        (max)
Test 5: Window Functions            ✓ PASS           4.18s        4.17s        4.94s
                                               (median)   (min)        (max)
Test 6: Cross-Table JOIN            ✓ PASS           3.10s        2.85s        3.10s
                                               (median)   (min)        (max)
Test 7: Phantom Read                ✓ PASS     No phantom read detected
Test 8: Non-Repeatable Read         ✓ PASS     No non-repeatable read detected
----------------------------------------------------------------------
```

## Usage

The enhanced output automatically appears when running benchmark against CockroachDB only:

```bash
# Run benchmark against CockroachDB only
python benchmark.py --crdb "$(cat crdb_connection.txt)" --output-dir ./outputs

# The text summary will automatically show the new format
cat outputs/benchmark_summary.txt
```

## Backwards Compatibility

- When testing both CockroachDB and Azure PostgreSQL, the original comparison format is used
- JSON output (`benchmark_results.json`) includes all metrics including p99.99
- HTML dashboard continues to work with existing format

## Files Modified

1. `src/metrics.py` - Added p99.99 tracking
2. `src/output/text_summary.py` - New CockroachDB-only output format
3. `src/schema.py` - Fixed isolation_test table schema
4. `fix_isolation_table.py` - Script to update database schema

## Testing

Run the test script to verify the new output format:

```bash
python test_new_output.py
```

This displays sample output with all 8 tests showing the new metrics format.
