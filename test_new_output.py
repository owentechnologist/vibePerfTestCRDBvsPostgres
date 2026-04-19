#!/usr/bin/env python3
"""
Test the new output format showing p50, p99, p99.99 for all tests.
"""

from src.output.text_summary import generate_text_summary

# Create sample results for CockroachDB-only testing
sample_results = {
    'benchmark_info': {
        'start_time': '2026-04-16T12:00:00',
        'end_time': '2026-04-16T12:15:00',
        'total_duration_seconds': 900.0,
    },
    'databases': {
        'cockroachdb': {
            'name': 'CockroachDB',
            'type': 'CockroachDB',
            'version': 'CockroachDB CCL v26.1.2',
            'configured': True,
        },
        'azure_postgresql': {
            'name': 'Azure PostgreSQL',
            'type': 'Azure PostgreSQL',
            'version': 'NOT TESTED',
            'configured': False,
        },
    },
    'test_results': {
        'cockroachdb': {
            'test_01': {
                'status': 'SUCCESS',
                'duration_seconds': 100.0,
                'percentiles': {
                    'p50': 48.24,
                    'p95': 55.81,
                    'p99': 66.89,
                    'p99_99': 285.93,
                    'min': 46.28,
                    'max': 285.93,
                    'mean': 49.75,
                    'std': 7.69,
                    'count': 10000
                },
                'custom_metrics': {
                    'query': 'SELECT 1',
                    'description': 'Simple latency baseline'
                }
            },
            'test_02': {
                'status': 'SUCCESS',
                'duration_seconds': 150.0,
                'percentiles': {
                    'p50': 50.23,
                    'p95': 58.12,
                    'p99': 73.59,
                    'p99_99': 686.95,
                    'min': 46.11,
                    'max': 686.95,
                    'mean': 51.96,
                    'std': 11.89,
                    'count': 50000
                },
                'custom_metrics': {
                    'query': 'SELECT aid, abalance FROM pgbench_accounts WHERE aid = $1'
                }
            },
            'test_03': {
                'status': 'SUCCESS',
                'duration_seconds': 300.0,
                'custom_metrics': {
                    'tps': 52.18,
                    'successful_transactions': 15654,
                    'failed_transactions': 0,
                    'description': 'TPC-B workload'
                }
            },
            'test_04': {
                'status': 'SUCCESS',
                'duration_seconds': 0.31,
                'custom_metrics': {
                    'query_type': 'ROLLUP aggregation',
                    'runs': 3,
                    'min_time_seconds': 0.096,
                    'median_time_seconds': 0.099,
                    'max_time_seconds': 0.114,
                    'mean_time_seconds': 0.103
                }
            },
            'test_05': {
                'status': 'SUCCESS',
                'duration_seconds': 13.30,
                'custom_metrics': {
                    'query_type': 'Window functions',
                    'runs': 3,
                    'min_time_seconds': 4.174,
                    'median_time_seconds': 4.183,
                    'max_time_seconds': 4.943,
                    'mean_time_seconds': 4.433
                }
            },
            'test_06': {
                'status': 'SUCCESS',
                'duration_seconds': 5.95,
                'custom_metrics': {
                    'query_type': 'Cross-table JOIN',
                    'runs': 2,
                    'min_time_seconds': 2.845,
                    'median_time_seconds': 3.105,
                    'max_time_seconds': 3.105,
                    'mean_time_seconds': 2.975
                }
            },
            'test_07': {
                'status': 'SUCCESS',
                'duration_seconds': 0.35,
                'custom_metrics': {
                    'test': 'phantom_read',
                    'isolation_level': 'SERIALIZABLE',
                    'status': 'PASS',
                    'behavior': 'No phantom read detected',
                    'serialization_error': False,
                    'description': 'SERIALIZABLE isolation prevented phantom read'
                }
            },
            'test_08': {
                'status': 'SUCCESS',
                'duration_seconds': 0.10,
                'custom_metrics': {
                    'test': 'nonrepeatable_read',
                    'isolation_level': 'REPEATABLE READ',
                    'status': 'PASS',
                    'behavior': 'No non-repeatable read detected',
                    'serialization_error': False,
                    'description': 'REPEATABLE READ isolation prevented non-repeatable read'
                }
            },
        },
        'azure_postgresql': {}
    },
    'execution_summary': {
        'cockroachdb_success': 8,
        'cockroachdb_failures': 0,
        'cockroachdb_not_tested': 0,
        'azure_postgresql_not_tested': 8,
    }
}

# Generate and print the summary
print("\n" + "=" * 70)
print("TESTING NEW OUTPUT FORMAT")
print("=" * 70)

summary = generate_text_summary(sample_results)
print(summary)

print("\n" + "=" * 70)
print("✅ New output format test complete!")
print("=" * 70)
