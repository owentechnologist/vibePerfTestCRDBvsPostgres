"""
Test Runner - Orchestrates all 10 performance tests.

Coordinates test execution across both CockroachDB and Azure PostgreSQL,
managing parallel and sequential execution patterns for optimal performance.
"""

import asyncio
import time
from typing import Dict, Any, List
from datetime import datetime

from src.database import DatabasePool
from src.tests.test_01_select_one import Test01SelectOne
from src.tests.test_02_point_lookup import Test02PointLookup
from src.tests.test_03_pgbench import Test03PgBench
from src.tests.test_04_rollup import Test04Rollup
from src.tests.test_05_window import Test05Window
from src.tests.test_06_join import Test06Join
from src.tests.test_07_phantom_read import Test07PhantomRead
from src.tests.test_08_nonrepeatable_read import Test08NonRepeatableRead
from src.tests.test_09_phantom_read_default import Test09PhantomReadDefault
from src.tests.test_10_nonrepeatable_read_default import Test10NonRepeatableReadDefault


class TestRunner:
    """
    Orchestrates execution of all 10 performance tests.

    Manages test execution order, parallelization, and result aggregation
    across multiple database instances.
    """

    def __init__(self, crdb_pool: DatabasePool = None, pg_pool: DatabasePool = None):
        """
        Initialize test runner.

        Args:
            crdb_pool: CockroachDB connection pool (optional)
            pg_pool: Azure PostgreSQL connection pool (optional)
        """
        self.crdb_pool = crdb_pool
        self.pg_pool = pg_pool

        # Test execution metadata
        self.start_time = None
        self.end_time = None
        self.total_duration = 0.0

    async def run_all_tests(self) -> Dict[str, Any]:
        """
        Run all 10 tests on both databases.

        Execution strategy:
        - Tests 1-2: Parallel execution (lightweight, no contention)
        - Test 3: Sequential execution (write-heavy, avoid noise)
        - Tests 4-10: Sequential execution (OLAP and isolation tests)

        Returns:
            Dictionary with all test results and metadata
        """
        print("\n" + "=" * 70)
        print("BENCHMARK TEST RUNNER")
        print("=" * 70)

        self.start_time = time.time()
        start_datetime = datetime.now()

        # Collect database metadata
        print("\nCollecting database metadata...")
        crdb_metadata = await self._get_database_metadata(self.crdb_pool, "CockroachDB")
        pg_metadata = await self._get_database_metadata(self.pg_pool, "Azure PostgreSQL")

        # Initialize results structure
        results = {
            'benchmark_info': {
                'start_time': start_datetime.isoformat(),
                'runner_version': '1.0.0',
                'test_count': 10,
            },
            'databases': {
                'cockroachdb': crdb_metadata,
                'azure_postgresql': pg_metadata,
            },
            'test_results': {
                'cockroachdb': {},
                'azure_postgresql': {},
            },
            'execution_summary': {},
        }

        # Phase 1: Run Tests 1-2 in parallel (lightweight tests)
        print("\n" + "=" * 70)
        print("PHASE 1: Parallel Execution (Tests 1-2)")
        print("=" * 70)

        await self._run_parallel_tests(results)

        # Phase 2: Run Test 3 sequentially (write-heavy TPC-B)
        print("\n" + "=" * 70)
        print("PHASE 2: Sequential Execution - Test 3 (TPC-B)")
        print("=" * 70)

        await self._run_test_3(results)

        # Phase 3: Run Tests 4-10 sequentially (OLAP and isolation tests)
        print("\n" + "=" * 70)
        print("PHASE 3: Sequential Execution - Tests 4-10 (OLAP + Isolation)")
        print("=" * 70)

        await self._run_sequential_tests(results)

        # Finalize results
        self.end_time = time.time()
        self.total_duration = self.end_time - self.start_time

        results['benchmark_info']['end_time'] = datetime.now().isoformat()
        results['benchmark_info']['total_duration_seconds'] = self.total_duration

        # Generate execution summary
        results['execution_summary'] = self._generate_summary(results)

        # Print final summary
        self._print_final_summary(results)

        return results

    async def _get_database_metadata(self, pool: DatabasePool, db_name: str) -> Dict[str, Any]:
        """
        Collect metadata about the database.

        Args:
            pool: Database connection pool (can be None)
            db_name: Database name for display

        Returns:
            Dictionary with database metadata
        """
        if pool is None:
            print(f"  [{db_name}] Not configured - will skip tests")
            return {
                'name': db_name,
                'type': db_name,
                'version': 'NOT TESTED',
                'configured': False,
            }

        print(f"  [{db_name}] Fetching version and configuration...")

        metadata = {
            'name': pool.config.name,
            'type': db_name,
            'configured': True,
        }

        try:
            version = await pool.get_version()
            metadata['version'] = version
            print(f"  [{db_name}] Version: {version}")
        except Exception as e:
            metadata['version'] = f"Error: {e}"
            print(f"  [{db_name}] Version: Error - {e}")

        return metadata

    async def _run_parallel_tests(self, results: Dict[str, Any]):
        """
        Run Tests 1-2 in parallel on configured databases.

        Args:
            results: Results dictionary to update
        """
        print("\nExecuting Tests 1-2 in parallel across configured databases...")
        print("  - Test 1: SELECT 1 latency baseline")
        print("  - Test 2: Primary key point lookup")

        # Create test instances and tasks
        tasks = []
        task_map = []  # Track which task maps to which db/test

        if self.crdb_pool:
            crdb_test1 = Test01SelectOne(self.crdb_pool, iterations=10_000)
            crdb_test2 = Test02PointLookup(self.crdb_pool, iterations=50_000, concurrency=8)
            tasks.extend([crdb_test1.run(), crdb_test2.run()])
            task_map.extend([('cockroachdb', 'test_01'), ('cockroachdb', 'test_02')])
        else:
            self._store_not_tested(results, 'cockroachdb', 'test_01', 'SELECT 1')
            self._store_not_tested(results, 'cockroachdb', 'test_02', 'Point Lookup')

        if self.pg_pool:
            pg_test1 = Test01SelectOne(self.pg_pool, iterations=10_000)
            pg_test2 = Test02PointLookup(self.pg_pool, iterations=50_000, concurrency=8)
            tasks.extend([pg_test1.run(), pg_test2.run()])
            task_map.extend([('azure_postgresql', 'test_01'), ('azure_postgresql', 'test_02')])
        else:
            self._store_not_tested(results, 'azure_postgresql', 'test_01', 'SELECT 1')
            self._store_not_tested(results, 'azure_postgresql', 'test_02', 'Point Lookup')

        # Run configured tests in parallel
        if tasks:
            print(f"\n[Running {len(tasks)} tests concurrently...]")
            task_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Store results
            for (db_key, test_key), result in zip(task_map, task_results):
                self._store_result(results, db_key, test_key, result)

        print("\n✅ Phase 1 complete (Tests 1-2)")

    async def _run_test_3(self, results: Dict[str, Any]):
        """
        Run Test 3 (TPC-B) sequentially on configured databases.

        Args:
            results: Results dictionary to update
        """
        print("\nExecuting Test 3 (TPC-B) sequentially...")
        print("  - Write-heavy workload, avoid cross-DB contention")

        # Run on CockroachDB first
        if self.crdb_pool:
            print("\n[CRDB] Running Test 3: TPC-B workload...")
            crdb_test3 = Test03PgBench(self.crdb_pool, duration_seconds=300, concurrency=16)
            crdb_result3 = await crdb_test3.run()
            self._store_result(results, 'cockroachdb', 'test_03', crdb_result3)
        else:
            print("\n[CRDB] Skipped Test 3 (not configured)")
            self._store_not_tested(results, 'cockroachdb', 'test_03', 'TPC-B')

        # Then run on Azure PostgreSQL
        if self.pg_pool:
            print("\n[PG] Running Test 3: TPC-B workload...")
            pg_test3 = Test03PgBench(self.pg_pool, duration_seconds=300, concurrency=16)
            pg_result3 = await pg_test3.run()
            self._store_result(results, 'azure_postgresql', 'test_03', pg_result3)
        else:
            print("\n[PG] Skipped Test 3 (not configured)")
            self._store_not_tested(results, 'azure_postgresql', 'test_03', 'TPC-B')

        print("\n✅ Phase 2 complete (Test 3)")

    async def _run_sequential_tests(self, results: Dict[str, Any]):
        """
        Run Tests 4-10 sequentially on both databases.

        Args:
            results: Results dictionary to update
        """
        print("\nExecuting Tests 4-10 sequentially on both databases...")
        print("  - Test 4: ROLLUP aggregation")
        print("  - Test 5: Window functions")
        print("  - Test 6: Cross-table JOIN")
        print("  - Test 7: Phantom read isolation (SERIALIZABLE)")
        print("  - Test 8: Non-repeatable read isolation (REPEATABLE READ)")
        print("  - Test 9: Phantom read with default isolation")
        print("  - Test 10: Non-repeatable read with default isolation")

        # Test 4: ROLLUP aggregation
        print("\n" + "-" * 70)
        print("Test 4: ROLLUP Aggregation")
        print("-" * 70)

        if self.crdb_pool:
            print("\n[CRDB] Running Test 4...")
            crdb_test4 = Test04Rollup(self.crdb_pool, num_runs=3, timeout_seconds=600)
            crdb_result4 = await crdb_test4.run()
            self._store_result(results, 'cockroachdb', 'test_04', crdb_result4)
        else:
            print("\n[CRDB] Skipped Test 4 (not configured)")
            self._store_not_tested(results, 'cockroachdb', 'test_04', 'ROLLUP')

        if self.pg_pool:
            print("\n[PG] Running Test 4...")
            pg_test4 = Test04Rollup(self.pg_pool, num_runs=3, timeout_seconds=600)
            pg_result4 = await pg_test4.run()
            self._store_result(results, 'azure_postgresql', 'test_04', pg_result4)
        else:
            print("\n[PG] Skipped Test 4 (not configured)")
            self._store_not_tested(results, 'azure_postgresql', 'test_04', 'ROLLUP')

        # Test 5: Window functions
        print("\n" + "-" * 70)
        print("Test 5: Window Functions")
        print("-" * 70)

        if self.crdb_pool:
            print("\n[CRDB] Running Test 5...")
            crdb_test5 = Test05Window(self.crdb_pool, num_runs=3, timeout_seconds=600)
            crdb_result5 = await crdb_test5.run()
            self._store_result(results, 'cockroachdb', 'test_05', crdb_result5)
        else:
            print("\n[CRDB] Skipped Test 5 (not configured)")
            self._store_not_tested(results, 'cockroachdb', 'test_05', 'Window Functions')

        if self.pg_pool:
            print("\n[PG] Running Test 5...")
            pg_test5 = Test05Window(self.pg_pool, num_runs=3, timeout_seconds=600)
            pg_result5 = await pg_test5.run()
            self._store_result(results, 'azure_postgresql', 'test_05', pg_result5)
        else:
            print("\n[PG] Skipped Test 5 (not configured)")
            self._store_not_tested(results, 'azure_postgresql', 'test_05', 'Window Functions')

        # Test 6: Cross-table JOIN
        print("\n" + "-" * 70)
        print("Test 6: Cross-Table JOIN")
        print("-" * 70)

        if self.crdb_pool:
            print("\n[CRDB] Running Test 6...")
            crdb_test6 = Test06Join(self.crdb_pool, num_runs=2, timeout_seconds=600)
            crdb_result6 = await crdb_test6.run()
            self._store_result(results, 'cockroachdb', 'test_06', crdb_result6)
        else:
            print("\n[CRDB] Skipped Test 6 (not configured)")
            self._store_not_tested(results, 'cockroachdb', 'test_06', 'Cross-Table JOIN')

        if self.pg_pool:
            print("\n[PG] Running Test 6...")
            pg_test6 = Test06Join(self.pg_pool, num_runs=2, timeout_seconds=600)
            pg_result6 = await pg_test6.run()
            self._store_result(results, 'azure_postgresql', 'test_06', pg_result6)
        else:
            print("\n[PG] Skipped Test 6 (not configured)")
            self._store_not_tested(results, 'azure_postgresql', 'test_06', 'Cross-Table JOIN')

        # Test 7: Phantom read isolation
        print("\n" + "-" * 70)
        print("Test 7: Phantom Read Isolation")
        print("-" * 70)

        if self.crdb_pool:
            print("\n[CRDB] Running Test 7...")
            crdb_test7 = Test07PhantomRead(self.crdb_pool, timeout_seconds=60)
            crdb_result7 = await crdb_test7.run()
            self._store_result(results, 'cockroachdb', 'test_07', crdb_result7)
        else:
            print("\n[CRDB] Skipped Test 7 (not configured)")
            self._store_not_tested(results, 'cockroachdb', 'test_07', 'Phantom Read Isolation')

        if self.pg_pool:
            print("\n[PG] Running Test 7...")
            pg_test7 = Test07PhantomRead(self.pg_pool, timeout_seconds=60)
            pg_result7 = await pg_test7.run()
            self._store_result(results, 'azure_postgresql', 'test_07', pg_result7)
        else:
            print("\n[PG] Skipped Test 7 (not configured)")
            self._store_not_tested(results, 'azure_postgresql', 'test_07', 'Phantom Read Isolation')

        # Test 8: Non-repeatable read isolation
        print("\n" + "-" * 70)
        print("Test 8: Non-Repeatable Read Isolation")
        print("-" * 70)

        if self.crdb_pool:
            print("\n[CRDB] Running Test 8...")
            crdb_test8 = Test08NonRepeatableRead(self.crdb_pool, timeout_seconds=60)
            crdb_result8 = await crdb_test8.run()
            self._store_result(results, 'cockroachdb', 'test_08', crdb_result8)
        else:
            print("\n[CRDB] Skipped Test 8 (not configured)")
            self._store_not_tested(results, 'cockroachdb', 'test_08', 'Non-Repeatable Read Isolation')

        if self.pg_pool:
            print("\n[PG] Running Test 8...")
            pg_test8 = Test08NonRepeatableRead(self.pg_pool, timeout_seconds=60)
            pg_result8 = await pg_test8.run()
            self._store_result(results, 'azure_postgresql', 'test_08', pg_result8)
        else:
            print("\n[PG] Skipped Test 8 (not configured)")
            self._store_not_tested(results, 'azure_postgresql', 'test_08', 'Non-Repeatable Read Isolation')

        # Test 9: Phantom read with default isolation
        print("\n" + "-" * 70)
        print("Test 9: Phantom Read (Default Isolation)")
        print("-" * 70)

        if self.crdb_pool:
            print("\n[CRDB] Running Test 9...")
            crdb_test9 = Test09PhantomReadDefault(self.crdb_pool, timeout_seconds=60)
            crdb_result9 = await crdb_test9.run()
            self._store_result(results, 'cockroachdb', 'test_09', crdb_result9)
        else:
            print("\n[CRDB] Skipped Test 9 (not configured)")
            self._store_not_tested(results, 'cockroachdb', 'test_09', 'Phantom Read Default Isolation')

        if self.pg_pool:
            print("\n[PG] Running Test 9...")
            pg_test9 = Test09PhantomReadDefault(self.pg_pool, timeout_seconds=60)
            pg_result9 = await pg_test9.run()
            self._store_result(results, 'azure_postgresql', 'test_09', pg_result9)
        else:
            print("\n[PG] Skipped Test 9 (not configured)")
            self._store_not_tested(results, 'azure_postgresql', 'test_09', 'Phantom Read Default Isolation')

        # Test 10: Non-repeatable read with default isolation
        print("\n" + "-" * 70)
        print("Test 10: Non-Repeatable Read (Default Isolation)")
        print("-" * 70)

        if self.crdb_pool:
            print("\n[CRDB] Running Test 10...")
            crdb_test10 = Test10NonRepeatableReadDefault(self.crdb_pool, timeout_seconds=60)
            crdb_result10 = await crdb_test10.run()
            self._store_result(results, 'cockroachdb', 'test_10', crdb_result10)
        else:
            print("\n[CRDB] Skipped Test 10 (not configured)")
            self._store_not_tested(results, 'cockroachdb', 'test_10', 'Non-Repeatable Read Default Isolation')

        if self.pg_pool:
            print("\n[PG] Running Test 10...")
            pg_test10 = Test10NonRepeatableReadDefault(self.pg_pool, timeout_seconds=60)
            pg_result10 = await pg_test10.run()
            self._store_result(results, 'azure_postgresql', 'test_10', pg_result10)
        else:
            print("\n[PG] Skipped Test 10 (not configured)")
            self._store_not_tested(results, 'azure_postgresql', 'test_10', 'Non-Repeatable Read Default Isolation')

        print("\n✅ Phase 3 complete (Tests 4-10)")

    def _store_result(self, results: Dict[str, Any], db_key: str, test_key: str, result):
        """
        Store a test result in the results dictionary.

        Args:
            results: Results dictionary
            db_key: Database key ('cockroachdb' or 'azure_postgresql')
            test_key: Test key (e.g., 'test_01')
            result: Test result (TestResult object or Exception)
        """
        if isinstance(result, Exception):
            # Handle exception during test execution
            results['test_results'][db_key][test_key] = {
                'status': 'ERROR',
                'error': str(result),
                'error_type': type(result).__name__,
            }
        else:
            # Store TestResult as dictionary
            results['test_results'][db_key][test_key] = {
                'status': result.status,
                'test_name': result.test_name,
                'duration_seconds': result.duration_seconds,
                'percentiles': result.percentiles,
                'throughput': result.throughput,
                'custom_metrics': result.custom_metrics,
                'error_count': result.error_count,
                'timeout_count': result.timeout_count,
                'retry_count': result.retry_count,
                'error_message': result.error_message,
            }

    def _store_not_tested(self, results: Dict[str, Any], db_key: str, test_key: str, test_name: str):
        """
        Store a NOT TESTED result for unconfigured database.

        Args:
            results: Results dictionary
            db_key: Database key ('cockroachdb' or 'azure_postgresql')
            test_key: Test key (e.g., 'test_01')
            test_name: Human-readable test name
        """
        results['test_results'][db_key][test_key] = {
            'status': 'NOT TESTED',
            'test_name': test_name,
            'duration_seconds': 0.0,
            'percentiles': {},
            'throughput': {},
            'custom_metrics': {},
            'error_count': 0,
            'timeout_count': 0,
            'retry_count': 0,
            'error_message': 'Database not configured',
        }

    def _generate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate execution summary statistics.

        Args:
            results: Results dictionary

        Returns:
            Summary dictionary
        """
        summary = {
            'total_duration_seconds': self.total_duration,
            'total_tests': 10,
            'tests_per_database': 10,
            'databases_tested': 2,
        }

        # Count successes, failures, timeouts per database
        for db_key in ['cockroachdb', 'azure_postgresql']:
            db_results = results['test_results'][db_key]

            success_count = sum(1 for r in db_results.values() if r.get('status') == 'SUCCESS')
            failure_count = sum(1 for r in db_results.values() if r.get('status') == 'FAILED')
            timeout_count = sum(1 for r in db_results.values() if r.get('status') == 'TIMEOUT')
            error_count = sum(1 for r in db_results.values() if r.get('status') == 'ERROR')
            not_tested_count = sum(1 for r in db_results.values() if r.get('status') == 'NOT TESTED')

            summary[f'{db_key}_success'] = success_count
            summary[f'{db_key}_failures'] = failure_count
            summary[f'{db_key}_timeouts'] = timeout_count
            summary[f'{db_key}_errors'] = error_count
            summary[f'{db_key}_not_tested'] = not_tested_count

        return summary

    def _print_final_summary(self, results: Dict[str, Any]):
        """
        Print final execution summary to console.

        Args:
            results: Results dictionary
        """
        print("\n" + "=" * 70)
        print("BENCHMARK EXECUTION SUMMARY")
        print("=" * 70)

        summary = results['execution_summary']

        print(f"\nTotal Duration: {summary['total_duration_seconds']:.2f}s")
        print(f"Tests Executed: {summary['total_tests']} tests × {summary['databases_tested']} databases = {summary['total_tests'] * summary['databases_tested']} total")

        # CockroachDB summary
        print(f"\nCockroachDB Results:")
        if summary['cockroachdb_not_tested'] == 10:
            print(f"  ⊘  NOT TESTED (database not configured)")
        else:
            print(f"  ✅ Success: {summary['cockroachdb_success']}")
            print(f"  ❌ Failed:  {summary['cockroachdb_failures']}")
            print(f"  ⏱️  Timeout: {summary['cockroachdb_timeouts']}")
            print(f"  ⚠️  Error:   {summary['cockroachdb_errors']}")
            if summary['cockroachdb_not_tested'] > 0:
                print(f"  ⊘  Not Tested: {summary['cockroachdb_not_tested']}")

        # Azure PostgreSQL summary
        print(f"\nAzure PostgreSQL Results:")
        if summary['azure_postgresql_not_tested'] == 10:
            print(f"  ⊘  NOT TESTED (database not configured)")
        else:
            print(f"  ✅ Success: {summary['azure_postgresql_success']}")
            print(f"  ❌ Failed:  {summary['azure_postgresql_failures']}")
            print(f"  ⏱️  Timeout: {summary['azure_postgresql_timeouts']}")
            print(f"  ⚠️  Error:   {summary['azure_postgresql_errors']}")
            if summary['azure_postgresql_not_tested'] > 0:
                print(f"  ⊘  Not Tested: {summary['azure_postgresql_not_tested']}")

        print("\n" + "=" * 70)
        print("✅ Benchmark execution complete!")
        print("=" * 70 + "\n")


async def test_runner():
    """Test the TestRunner with mock pools."""
    print("=" * 70)
    print("Test Runner - Implementation Test")
    print("=" * 70)

    # Mock pool for testing
    class MockConnection:
        async def fetchval(self, query, *args):
            await asyncio.sleep(0.001)
            if 'version' in query.lower():
                return "MockDB v1.0.0"
            return 1

        async def fetchrow(self, query, *args):
            await asyncio.sleep(0.001)
            return {'aid': 1, 'abalance': 0}

        async def fetch(self, query, *args):
            await asyncio.sleep(0.1)
            return [{'id': 1}] * 10

        async def execute(self, query, *args):
            await asyncio.sleep(0.001)
            return None

    class MockPool:
        def __init__(self, name):
            self.config = type('Config', (), {'name': name})()

        class pool:
            @staticmethod
            async def acquire():
                return MockConnection()

            @staticmethod
            async def release(conn):
                pass

        def acquire(self):
            return MockContextManager(self.pool)

        async def get_version(self):
            return "MockDB v1.0.0"

    class MockContextManager:
        def __init__(self, pool):
            self.pool = pool
            self.conn = None

        async def __aenter__(self):
            self.conn = await self.pool.acquire()
            return self.conn

        async def __aexit__(self, *args):
            await self.pool.release(self.conn)

    # Create mock pools
    crdb_pool = MockPool("MockCRDB")
    pg_pool = MockPool("MockPG")

    # Create and run test runner with reduced scale
    print("\n✅ Creating TestRunner with mock pools...")
    runner = TestRunner(crdb_pool, pg_pool)

    print("✅ TestRunner instantiated")
    print(f"   CockroachDB pool: {crdb_pool.config.name}")
    print(f"   PostgreSQL pool: {pg_pool.config.name}")

    # Note: Full run would take too long for testing
    # This just validates instantiation and structure
    print("\n✅ TestRunner ready for execution")
    print("   (Skipping full test run for brevity)")

    print("\n" + "=" * 70)


if __name__ == '__main__':
    asyncio.run(test_runner())
