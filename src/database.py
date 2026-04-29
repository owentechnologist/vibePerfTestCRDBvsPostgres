"""
Database connection pool management for PostgreSQL benchmark.

Provides async connection pool handling for both CockroachDB and Azure PostgreSQL
using asyncpg driver.
"""

import asyncio
import sys
from typing import Any, List, Optional, Dict

try:
    import asyncpg
except ImportError:
    print("Error: asyncpg is required. Install it with: pip install asyncpg", file=sys.stderr)
    sys.exit(1)

from src.config import DatabaseConfig


class DatabasePool:
    """
    Manages asyncpg connection pool for a database.

    Handles pool lifecycle, version detection, and provides utilities for
    query execution with proper error handling.
    """

    def __init__(self, config: DatabaseConfig):
        """
        Initialize database pool manager.

        Args:
            config: DatabaseConfig instance
        """
        self.config = config
        self.pool: Optional[asyncpg.Pool] = None
        self.version: Optional[str] = None
        self.is_cockroachdb: bool = config.database_type == 'cockroachdb'

    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        """
        Initialize each new connection from the pool.

        Sets database-specific session variables.

        Args:
            conn: Database connection
        """
        if self.is_cockroachdb:
            # Enable multiple active portals (required for asyncpg transactions)
            # This is a preview feature in CockroachDB v26.1
            await conn.execute('SET multiple_active_portals_enabled = true')

        # Note: search_path is set via server_settings in create_pool()
        # This ensures it's applied to all connections automatically

    async def create_pool(self, min_size: int = 1, max_size: int = 10) -> None:
        """
        Create asyncpg connection pool.

        Args:
            min_size: Minimum number of connections in pool
            max_size: Maximum number of connections in pool
        """
        if self.pool:
            print(f"Warning: Pool already exists for {self.config.name}")
            return

        try:
            print(f"Creating connection pool for {self.config.name}...")
            print(f"  Host: {self.config.get_host()}")
            print(f"  Port: {self.config.get_port()}")
            print(f"  Database: {self.config.get_database()}")
            print(f"  Pool size: {min_size}-{max_size}")

            # For Azure PostgreSQL, disable SSL certificate verification
            # asyncpg doesn't handle self-signed certs in the chain by default
            ssl_mode = 'prefer' if not self.is_cockroachdb else None

            # Set server settings for all connections
            # This ensures search_path is set for the entire pool
            server_settings = {
                'search_path': 'perftest,public'
            }

            # Create pool using connection string
            self.pool = await asyncpg.create_pool(
                dsn=self.config.connection_string,
                min_size=min_size,
                max_size=max_size,
                command_timeout=None,  # No timeout - allow long-running operations (data loading)
                timeout=30,  # Connection timeout
                init=self._init_connection,  # Initialize each connection
                ssl=ssl_mode,  # Use 'prefer' for Azure PG (encrypts but doesn't verify cert)
                server_settings=server_settings,  # Set search_path for all connections
            )

            print(f"✅ Connection pool created for {self.config.name}")
            if self.is_cockroachdb:
                print(f"  ✅ CockroachDB: multiple_active_portals_enabled = true")

            # Test connection and get version
            await self._initialize_connection()

        except asyncpg.PostgresError as e:
            print(f"❌ Failed to create pool for {self.config.name}: {e}")
            raise
        except Exception as e:
            print(f"❌ Unexpected error creating pool for {self.config.name}: {e}")
            raise

    async def _initialize_connection(self) -> None:
        """
        Initialize connection: test connectivity and fetch database version.

        Also handles database-specific initialization like creating extensions.
        """
        if not self.pool:
            raise RuntimeError("Pool not created. Call create_pool() first.")

        async with self.pool.acquire() as conn:
            # Get database version
            self.version = await self.get_version(conn)
            print(f"  Version: {self.version}")

            # Ensure perftest schema exists
            await self._ensure_perftest_schema(conn)

            # Azure PostgreSQL specific: ensure pgcrypto extension exists
            if not self.is_cockroachdb:
                await self._ensure_pgcrypto_extension(conn)

    async def _ensure_perftest_schema(self, conn: asyncpg.Connection) -> None:
        """
        Ensure perftest schema exists.

        This is required for both CockroachDB and Azure Flexible Server.
        - CockroachDB: creates schema in perftest database
        - Azure Flexible Server: creates schema in postgres database

        Args:
            conn: Database connection
        """
        try:
            await conn.execute('CREATE SCHEMA IF NOT EXISTS perftest;')
            print(f"  ✅ perftest schema ready")

            # Grant permissions to current user
            current_user = await conn.fetchval('SELECT current_user;')
            await conn.execute(f'GRANT ALL ON SCHEMA perftest TO {current_user};')
            await conn.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA perftest GRANT ALL ON TABLES TO {current_user};')

        except asyncpg.InsufficientPrivilegeError:
            print(f"  ⚠️  Warning: Cannot create perftest schema (insufficient privileges)")
            print(f"     Schema may need to be created manually")
        except Exception as e:
            print(f"  ⚠️  Warning: perftest schema check failed: {e}")

    async def _ensure_pgcrypto_extension(self, conn: asyncpg.Connection) -> None:
        """
        Ensure pgcrypto extension is created (for gen_random_uuid() on older PostgreSQL).

        Note: PostgreSQL 13+ has gen_random_uuid() built-in, so pgcrypto is optional.

        Args:
            conn: Database connection
        """
        try:
            await conn.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto;')
            print(f"  ✅ pgcrypto extension enabled")
        except asyncpg.InsufficientPrivilegeError:
            # This is OK on PostgreSQL 13+ which has gen_random_uuid() built-in
            print(f"  ℹ️  Note: pgcrypto extension not available (PostgreSQL 13+ has gen_random_uuid() built-in)")
        except Exception as e:
            # Check if it's an Azure-specific error about allow-listing
            if "not allow-listed" in str(e):
                print(f"  ℹ️  Note: pgcrypto not allow-listed in Azure (PostgreSQL 13+ has gen_random_uuid() built-in)")
            else:
                print(f"  ⚠️  Warning: pgcrypto extension check failed: {e}")

    async def close_pool(self) -> None:
        """Close connection pool and cleanup resources."""
        if self.pool:
            print(f"Closing connection pool for {self.config.name}...")
            await self.pool.close()
            self.pool = None
            print(f"✅ Pool closed for {self.config.name}")

    async def get_version(self, conn: Optional[asyncpg.Connection] = None) -> str:
        """
        Get database version string.

        Args:
            conn: Optional connection to use (acquires from pool if not provided)

        Returns:
            Version string
        """
        if conn:
            version = await conn.fetchval('SELECT version();')
            return version
        else:
            if not self.pool:
                raise RuntimeError("Pool not created")

            async with self.pool.acquire() as conn:
                version = await conn.fetchval('SELECT version();')
                return version

    async def execute(self, query: str, *args, timeout: Optional[float] = None) -> str:
        """
        Execute a query (DDL/DML) that doesn't return rows.

        Args:
            query: SQL query to execute
            *args: Query parameters
            timeout: Optional query timeout in seconds

        Returns:
            Status string (e.g., 'CREATE TABLE', 'INSERT 0 1000')
        """
        if not self.pool:
            raise RuntimeError("Pool not created")

        async with self.pool.acquire() as conn:
            if timeout:
                return await conn.execute(query, *args, timeout=timeout)
            else:
                return await conn.execute(query, *args)

    async def fetch(self, query: str, *args, timeout: Optional[float] = None) -> List[asyncpg.Record]:
        """
        Fetch all rows from a query.

        Args:
            query: SQL query to execute
            *args: Query parameters
            timeout: Optional query timeout in seconds

        Returns:
            List of records
        """
        if not self.pool:
            raise RuntimeError("Pool not created")

        async with self.pool.acquire() as conn:
            if timeout:
                return await conn.fetch(query, *args, timeout=timeout)
            else:
                return await conn.fetch(query, *args)

    async def fetchval(self, query: str, *args, timeout: Optional[float] = None) -> Any:
        """
        Fetch a single value from a query.

        Args:
            query: SQL query to execute
            *args: Query parameters
            timeout: Optional query timeout in seconds

        Returns:
            Single value (first column of first row)
        """
        if not self.pool:
            raise RuntimeError("Pool not created")

        async with self.pool.acquire() as conn:
            if timeout:
                return await conn.fetchval(query, *args, timeout=timeout)
            else:
                return await conn.fetchval(query, *args)

    async def fetchrow(self, query: str, *args, timeout: Optional[float] = None) -> Optional[asyncpg.Record]:
        """
        Fetch a single row from a query.

        Args:
            query: SQL query to execute
            *args: Query parameters
            timeout: Optional query timeout in seconds

        Returns:
            Single record or None
        """
        if not self.pool:
            raise RuntimeError("Pool not created")

        async with self.pool.acquire() as conn:
            if timeout:
                return await conn.fetchrow(query, *args, timeout=timeout)
            else:
                return await conn.fetchrow(query, *args)

    async def get_table_count(self, table_name: str) -> int:
        """
        Get row count for a table.

        Args:
            table_name: Name of table

        Returns:
            Row count
        """
        count = await self.fetchval(f'SELECT COUNT(*) FROM {table_name};')
        return count or 0

    async def table_exists(self, table_name: str, schema: str = 'perftest') -> bool:
        """
        Check if a table exists in the specified schema.

        Args:
            table_name: Name of table
            schema: Schema name (default: 'perftest')

        Returns:
            True if table exists, False otherwise
        """
        query = """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = $1 AND table_name = $2
            );
        """
        exists = await self.fetchval(query, schema, table_name)
        return exists or False

    async def get_isolation_level(self) -> str:
        """
        Get current transaction isolation level.

        Returns:
            Isolation level string
        """
        level = await self.fetchval('SHOW transaction_isolation;')
        return level or "unknown"

    async def get_connection_info(self) -> Dict[str, Any]:
        """
        Get database connection and configuration info.

        Returns:
            Dict with connection details
        """
        info = {
            'name': self.config.name,
            'type': self.config.database_type,
            'host': self.config.get_host(),
            'port': self.config.get_port(),
            'database': self.config.get_database(),
            'user': self.config.get_user(),
            'version': self.version,
            'pool_size': f"{self.pool.get_min_size()}-{self.pool.get_max_size()}" if self.pool else "N/A"
        }
        return info

    def acquire(self):
        """
        Acquire a connection from the pool (context manager).

        Usage:
            async with pool.acquire() as conn:
                result = await conn.fetch('SELECT ...')

        Returns:
            Connection context manager
        """
        if not self.pool:
            raise RuntimeError("Pool not created")

        return self.pool.acquire()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup pool."""
        await self.close_pool()


async def test_database_connections(crdb_config: DatabaseConfig, pg_config: DatabaseConfig) -> bool:
    """
    Test connections to both databases.

    Args:
        crdb_config: CockroachDB configuration
        pg_config: Azure PostgreSQL configuration

    Returns:
        True if both connections successful
    """
    print("=" * 70)
    print("Testing Database Connections")
    print("=" * 70)

    success = True

    # Test CockroachDB
    print("\n[1/2] Testing CockroachDB connection...")
    crdb_pool = DatabasePool(crdb_config)
    try:
        await crdb_pool.create_pool(min_size=1, max_size=2)
        info = await crdb_pool.get_connection_info()
        print(f"✅ CockroachDB connection successful")
        print(f"   Version: {info['version']}")
    except Exception as e:
        print(f"❌ CockroachDB connection failed: {e}")
        success = False
    finally:
        await crdb_pool.close_pool()

    # Test Azure PostgreSQL
    print("\n[2/2] Testing Azure PostgreSQL connection...")
    pg_pool = DatabasePool(pg_config)
    try:
        await pg_pool.create_pool(min_size=1, max_size=2)
        info = await pg_pool.get_connection_info()
        print(f"✅ Azure PostgreSQL connection successful")
        print(f"   Version: {info['version']}")
    except Exception as e:
        print(f"❌ Azure PostgreSQL connection failed: {e}")
        success = False
    finally:
        await pg_pool.close_pool()

    print("\n" + "=" * 70)
    if success:
        print("✅ All database connections successful")
    else:
        print("❌ Some database connections failed")
    print("=" * 70)

    return success


if __name__ == '__main__':
    print("Database pool module loaded successfully")
    print("\nExample usage:")
    print("  from src.database import DatabasePool")
    print("  from src.config import DatabaseConfig")
    print()
    print("  config = DatabaseConfig(...)")
    print("  pool = DatabasePool(config)")
    print("  await pool.create_pool()")
    print("  result = await pool.fetchval('SELECT 1;')")
    print("  await pool.close_pool()")
