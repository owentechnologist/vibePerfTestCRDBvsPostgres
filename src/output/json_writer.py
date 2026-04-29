"""
JSON Writer - Export benchmark results as JSON.

Provides raw data export for programmatic analysis and archiving.
Handles special cases like NaN, Infinity, and nested structures.
"""

import json
import math
from pathlib import Path
from typing import Dict, Any


def write_json_results(results: Dict[str, Any], output_path: str) -> None:
    """
    Write benchmark results to JSON file.

    Handles special float values (NaN, Infinity) by converting to null/strings.

    Args:
        results: Results dictionary from TestRunner
        output_path: Path to output JSON file

    Raises:
        IOError: If file cannot be written
        ValueError: If results cannot be serialized
    """
    print(f"\nWriting JSON results to: {output_path}")

    # Create output directory if needed
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Clean results for JSON serialization
    cleaned_results = _clean_for_json(results)

    # Write JSON with pretty formatting
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(cleaned_results, f, indent=2, sort_keys=False)

        # Validate by reading back
        with open(output_path, 'r', encoding='utf-8') as f:
            json.load(f)

        file_size = output_file.stat().st_size
        print(f"✅ JSON written successfully ({file_size:,} bytes)")

    except (IOError, OSError) as e:
        print(f"❌ Failed to write JSON: {e}")
        raise
    except json.JSONDecodeError as e:
        print(f"❌ JSON validation failed: {e}")
        raise ValueError(f"Invalid JSON generated: {e}")


def _clean_for_json(obj: Any) -> Any:
    """
    Recursively clean an object for JSON serialization.

    Converts special float values and handles nested structures.

    Args:
        obj: Object to clean

    Returns:
        Cleaned object safe for JSON serialization
    """
    if obj is None:
        return None

    if isinstance(obj, bool):
        # Handle booleans before numbers (bool is subclass of int)
        return obj

    if isinstance(obj, (int, str)):
        return obj

    if isinstance(obj, float):
        # Handle special float values
        if math.isnan(obj):
            return None
        if math.isinf(obj):
            return "Infinity" if obj > 0 else "-Infinity"
        return obj

    if isinstance(obj, dict):
        # Recursively clean dictionary
        return {key: _clean_for_json(value) for key, value in obj.items()}

    if isinstance(obj, (list, tuple)):
        # Recursively clean list/tuple
        return [_clean_for_json(item) for item in obj]

    # For other types, convert to string
    return str(obj)


def validate_json_file(file_path: str) -> bool:
    """
    Validate that a JSON file is well-formed.

    Args:
        file_path: Path to JSON file

    Returns:
        True if valid, False otherwise
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            json.load(f)
        return True
    except (IOError, json.JSONDecodeError):
        return False


def load_json_results(file_path: str) -> Dict[str, Any]:
    """
    Load benchmark results from JSON file.

    Args:
        file_path: Path to JSON file

    Returns:
        Results dictionary

    Raises:
        IOError: If file cannot be read
        json.JSONDecodeError: If JSON is invalid
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# Test function
def test_json_writer():
    """Test JSON writer with sample data."""
    print("=" * 70)
    print("JSON Writer - Test")
    print("=" * 70)

    # Sample results structure
    sample_results = {
        'benchmark_info': {
            'start_time': '2026-04-14T10:00:00',
            'end_time': '2026-04-14T10:30:00',
            'total_duration_seconds': 1800.5,
            'runner_version': '1.0.0',
        },
        'databases': {
            'cockroachdb': {
                'name': 'test_crdb',
                'version': 'CockroachDB v23.2.0',
            },
            'azure_postgresql': {
                'name': 'test_pg',
                'version': 'PostgreSQL 15.5',
            },
        },
        'test_results': {
            'cockroachdb': {
                'test_01': {
                    'status': 'SUCCESS',
                    'duration_seconds': 12.5,
                    'percentiles': {
                        'p50': 1.23,
                        'p95': 2.45,
                        'p99': 3.67,
                    },
                },
            },
        },
        'special_values': {
            'nan_value': float('nan'),
            'inf_value': float('inf'),
            'neg_inf_value': float('-inf'),
            'normal_value': 42.0,
        },
    }

    # Write JSON
    test_output = '/tmp/test_benchmark_results.json'
    write_json_results(sample_results, test_output)

    # Validate
    print("\nValidating JSON file...")
    if validate_json_file(test_output):
        print("✅ JSON file is valid")
    else:
        print("❌ JSON file is invalid")

    # Load back
    print("\nLoading JSON file...")
    loaded_results = load_json_results(test_output)

    # Check special values were converted
    print("\nChecking special value handling:")
    print(f"  NaN → {loaded_results['special_values']['nan_value']}")
    print(f"  Inf → {loaded_results['special_values']['inf_value']}")
    print(f"  -Inf → {loaded_results['special_values']['neg_inf_value']}")
    print(f"  Normal → {loaded_results['special_values']['normal_value']}")

    assert loaded_results['special_values']['nan_value'] is None
    assert loaded_results['special_values']['inf_value'] == "Infinity"
    assert loaded_results['special_values']['neg_inf_value'] == "-Infinity"
    assert loaded_results['special_values']['normal_value'] == 42.0

    print("\n✅ All JSON writer tests passed!")
    print("=" * 70)


if __name__ == '__main__':
    test_json_writer()
