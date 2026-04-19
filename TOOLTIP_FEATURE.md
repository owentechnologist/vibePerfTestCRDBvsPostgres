# HTML Dashboard Tooltip Feature

## Overview

Added interactive hover tooltips to the HTML benchmark dashboard. Each test result row now displays detailed information about the query, expected results, and business impact when hovering over the test name.

## Features

### 1. Query Display
- Shows the exact SQL query used in each test
- Queries are truncated to ~200 characters for readability
- Displayed in monospace code blocks for clarity

### 2. Test Description
- Explains what the test measures
- Describes test parameters (iterations, concurrency, timeout)
- Provides context for interpreting results

### 3. Sample Results
- Shows expected output format
- Indicates number of rows returned
- Helps understand what the test is validating

### 4. Business Impact (Isolation Tests Only)
- **Test 7 & 8**: Explains SERIALIZABLE and REPEATABLE READ isolation guarantees
- **Test 9 & 10**: Highlights critical differences in default isolation behavior between databases
- Includes real-world scenarios and risk examples
- Provides actionable recommendations

## Implementation

### Files Created

**`src/output/test_metadata.py`**
- Central repository for all test metadata
- `get_test_metadata()`: Returns complete test information
- `get_test_tooltip()`: Generates HTML tooltip content
- Includes queries for all 10 tests
- Contains business impact explanations for isolation tests (Tests 7-10)

### Files Modified

**`src/output/html_generator.py`**
- Added import: `from src.output.test_metadata import get_test_tooltip`
- Updated `test_configs` to include Tests 9-10
- Modified `_build_comparison_table()` to generate and include tooltip text for each row
- Added `tooltip` field to all row dictionaries

**`templates/dashboard_template.html`**
- Added CSS styles for tooltip display:
  - `.tooltip-row`: Marks rows with tooltip functionality
  - `.tooltip-text`: Styled tooltip container with dark theme
  - `.info-icon`: Visual indicator (ℹ️) next to test names
- Updated table rows to include tooltip containers
- Added JavaScript for dynamic tooltip positioning
- Tooltips follow mouse cursor for better UX

## Usage

### Viewing Tooltips

1. Open the generated HTML dashboard (`outputs/benchmark_report.html`)
2. Hover over any test name in the "Detailed Test Results" table
3. An information icon (ℹ️) indicates tooltip availability
4. Tooltip appears near the cursor showing:
   - SQL query
   - Test description
   - Sample results
   - Business impact (for isolation tests)

### Example Tooltip Content

**Test 1: SELECT 1**
```
Query: SELECT 1;

Description: Measures minimum round-trip latency with zero data access. 
Tests network overhead and query processing speed.

Result: Returns: 1
```

**Test 9: Phantom Read (DEFAULT)**
```
Query: -- Connection A:
BEGIN;  -- Using default isolation level
SELECT COUNT(*) FROM isolation_test WHERE test_value = $1;
...

Description: Tests whether default isolation level prevents phantom reads.

Result: CockroachDB PASS: Consistent counts (SERIALIZABLE default) | 
PostgreSQL FAIL: Count changes (READ COMMITTED default)

Business Impact:
⚙️  DEFAULT Isolation Level - Database Differences

CockroachDB (SERIALIZABLE default):
✅ PASS: Phantom reads prevented automatically
✅ Developers get strong consistency without explicit configuration
...

PostgreSQL (READ COMMITTED default):
❌ FAIL (DEFAULT SETTINGS): Phantom reads occur
⚠️  Weaker consistency without explicit isolation level configuration
...

Recommendation: Always set explicit isolation levels in PostgreSQL for 
critical business logic.
```

## Technical Details

### Tooltip Positioning

- Uses JavaScript to dynamically position tooltips near mouse cursor
- Fixed positioning prevents overflow issues
- Follows mouse movement for better readability
- Max width: 600px to prevent unwieldy tooltips

### Styling

- Dark theme (`#2c3e50` background) for better contrast
- Code blocks with subtle background highlighting
- Section headers in light blue (`#4fc3f7`)
- Smooth fade-in transition (0.3s)
- Box shadow for depth

### HTML Safety

- Uses Jinja2's `| safe` filter to render HTML in tooltips
- Content is generated server-side, not user input
- No XSS risk as all content comes from `test_metadata.py`

## Benefits

1. **Self-Documenting Reports**: Users can understand what each test does without referring to external documentation
2. **Business Context**: Decision-makers can understand real-world impact of isolation test results
3. **Query Transparency**: DBAs and developers can see exact queries being benchmarked
4. **Educational**: Helps users learn about database isolation levels and their implications

## Maintenance

To add or update tooltip content:

1. Edit `src/output/test_metadata.py`
2. Update the `get_test_metadata()` dictionary for the relevant test
3. Available fields:
   - `name`: Test display name
   - `query`: SQL query (auto-truncated to 200 chars in tooltip)
   - `description`: What the test measures
   - `sample_result`: Expected output format
   - `business_impact`: Detailed explanation (isolation tests only)

## Future Enhancements

Potential improvements:
- Collapsible query sections for very long queries
- Copy-to-clipboard button for queries
- Links to relevant documentation
- Test-specific charts within tooltips
- Comparison of expected vs actual results
