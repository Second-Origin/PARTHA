# Database migration rehearsal and recovery

This runbook is the operational gate for schema work tracked by [#322](https://github.com/Second-Origin/PARTHA/issues/322).
It documents a reproducible rehearsal, not a promise that all historical data can be downgraded safely.

## Current support and evidence

PARTHA uses one linear Alembic chain, from `0001_initial` through current head
`0010_account_deletion`. SQLite is the local-development default and is the local
maintainer rehearsal target. PostgreSQL is the supported deployment and CI dialect: the Backend CI job runs
this rehearsal command against its isolated PostgreSQL 16 service after the backend tests. Repository files
are outside the database, under `STORAGE_PATH`; a database restore does not recreate missing repository
storage.

Every current revision has a `downgrade()` function. That only proves a schema reversal can be attempted:
some revisions drop tables, indexes, or columns. In particular, `0005_revision_snapshots` deliberately
discards snapshot data on downgrade. A downgrade is therefore **not** a production rollback guarantee.

## Rehearse before a schema release

From `apps/backend`, with the backend dependencies installed:

```bash
python scripts/rehearse_migrations.py
```

The default command has no database-URL argument and creates two temporary SQLite files itself. It proves:

1. an empty database upgrades to the current head;
2. that same empty target can downgrade to base and upgrade to head again; and
3. a representative `0004_ai_provider_configs` database containing an old-format GitHub import upgrades
   to head with its revision identity backfilled and its legacy metadata retained.

The command removes its own temporary targets. It never opens the local `.local/partha.db`, a configured
application `DATABASE_URL`, or a production/shared database. Failures name the failed phase and error class
without printing a database URL or credentials.

To exercise the deployment dialect, use a **dedicated rehearsal PostgreSQL server only**. The server URL
must be supplied through the environment, and the explicit confirmation prevents accidental use:

```bash
export PARTHA_MIGRATION_REHEARSAL_PG_URL='postgresql+psycopg://…/postgres'
export PARTHA_MIGRATION_REHEARSAL_CONFIRM=disposable
python scripts/rehearse_migrations.py --postgres
```

The command creates only a randomly named `partha_migration_rehearsal_<uuid>` database and removes that
same database in cleanup. It does not accept a target database name. Do not set these variables to a
production, staging, or shared server; the confirmation is an operator assertion, not an access-control
boundary. A CI job can set them only for an isolated service container, as the existing backend job does.

## Production preflight and recovery decision

Before applying a migration to a non-disposable database:

1. Confirm the live revision with `alembic current`, the intended head with `alembic heads`, and that the
   deployment code and migration artifact are the reviewed release.
2. Take and verify a restorable database backup using the platform-approved mechanism (for PostgreSQL,
   normally `pg_dump` plus a separate restore verification). Record the backup location, timestamp,
   source revision, restore owner, and tested restore result outside logs and source control.
3. Back up or otherwise preserve the matching `STORAGE_PATH` data. Database and repository-storage recovery
   must use a compatible point in time.
4. Quiesce writers and background workers, announce the maintenance window, and ensure one migration owner.
   DDL, index creation, table rewrites (including SQLite batch operations), and data backfills can wait on
   locks or run longer than normal request timeouts. Monitor locks, database capacity, and migration logs.
5. Run `alembic upgrade head` once. Do not use application startup auto-creation or `alembic stamp` as a
   substitute for a reviewed production migration.

If the migration fails before committing, stop writers, retain the error and exact revision, and assess the
schema with the database operator. Do not repeatedly retry or run an unreviewed downgrade. If a migration
has committed, is data-bearing, or its downgrade would discard data, choose restore: keep writes quiesced,
restore the verified database backup and compatible `STORAGE_PATH` snapshot to an isolated recovery target,
validate application integrity there, then perform the approved cutover. Point-in-time recovery and final
traffic cutover remain the database/platform operator's responsibility.

Use a downgrade only when the specific revision's review explicitly says it is data-preserving for the
actual live data and it has been rehearsed against an equivalent disposable backup. Otherwise restore is
the rollback path.

## Future Repository Lineage (#299) migration review checklist

This is a gate checklist only. It does not authorize or implement Repository Lineage. PR #328 still requires
Parth's explicit re-review/approval, and #322 must be complete before any future #299 implementation PR merges.

- [ ] Re-run this rehearsal on the then-current chain and on a representative disposable copy/fixture of the
  immediately preceding supported baseline.
- [ ] Review the proposed revision for table rewrites, backfill duration, lock modes, indexes, transaction
  boundaries, concurrent imports, and the PostgreSQL/SQLite differences actually supported by the change.
- [ ] Define which fields and rows a downgrade would discard; prove a downgrade only if it is safe for the
  representative data, otherwise test the backup/restore recovery path.
- [ ] Verify backup and matching `STORAGE_PATH` recovery ownership, retention, and a restore drill before
  merging the implementation PR.
- [ ] Confirm no lineage models, revisions, APIs, services, frontend fields, or backfill code are included in
  this operational-gate work.
