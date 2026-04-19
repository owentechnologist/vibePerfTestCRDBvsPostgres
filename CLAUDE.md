# CockroachDB Performance Testing Project

## Overview

This project contains performance testing and benchmarking tools for CockroachDB vs Azure PostgreSQL.

## CockroachDB Skills Reference

**IMPORTANT**: When working with CockroachDB-related code, schema design, queries, transactions, or troubleshooting in this project, **always consult** the CockroachDB skills repository located at:

```
/Users/owentaylor/wip/gitprojects/cockroachdb-skills
```

### Key Skill Areas

Relevant skills include:

- **Application Development**
  - `skills/application-development/designing-application-transactions/SKILL.md` - Transaction patterns, retry logic, connection pooling, autocommit behavior
  - `skills/application-development/benchmarking-transaction-patterns/SKILL.md` - Benchmarking under contention

- **Observability & Diagnostics**
  - `skills/observability-and-diagnostics/profiling-statement-fingerprints/SKILL.md`
  - `skills/observability-and-diagnostics/profiling-transaction-fingerprints/SKILL.md`
  - `skills/observability-and-diagnostics/triaging-live-sql-activity/SKILL.md`

- **Operations & Lifecycle**
  - `skills/operations-and-lifecycle/managing-cluster-settings/SKILL.md`
  - `skills/operations-and-lifecycle/reviewing-cluster-health/SKILL.md`

### When to Reference

Use the skills repository when:

1. **Designing or reviewing database interactions** - Check transaction patterns, connection pooling settings, retry logic
2. **Troubleshooting errors** - Reference error codes, transaction states, common issues
3. **Optimizing performance** - Consult best practices for query patterns, batching, pagination
4. **Implementing CockroachDB-specific features** - Follower reads, distributed transactions, multi-region patterns
5. **Validating implementation approaches** - Confirm approaches align with CockroachDB best practices

### Example Usage

Before implementing changes to database code:
1. Search relevant skills for guidance
2. Validate approach matches CockroachDB best practices
3. Apply patterns from skill references and examples

## Project-Specific Conventions

### Connection Management

- Use `autocommit = True` for validation scripts and single-statement queries (per `designing-application-transactions` skill)
- Implement exponential backoff retry logic for `40001` serialization errors
- Connection strings stored in `crdb_connection.txt` with 600 permissions

### Scripts

- `get_crdb_connection.py` - Generates CockroachDB Cloud connection strings
- `validate_crdb_connection.py` - Validates connections and cluster info
- `benchmark.py` - Performance comparison testing

All CockroachDB-related code should follow the patterns and best practices documented in the skills repository.
