# Database migration rehearsal and recovery

This runbook is the operational gate for schema work tracked by [#322](https://github.com/Second-Origin/PARTHA/issues/322),
and for backup/restore rehearsal tracked by [#323](https://github.com/Second-Origin/PARTHA/issues/323).
It documents a reproducible rehearsal, not a promise that all historical data can be downgraded safely.

## Current support and evidence

PARTHA uses one linear Alembic chain, from `0001_initial` through current head
`0014_lineage_constraints`. SQLite is the local-development default and is the local
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

To exercise the deployment dialect, use a **dedicated rehearsal PostgreSQL server only**, running
PostgreSQL 13 or newer (cleanup issues `DROP DATABASE ... WITH (FORCE)`, added in PostgreSQL 13; on an
older server the disposable database is left behind and must be dropped manually). The server URL must be
supplied through the environment, and the explicit confirmation prevents accidental use:

```bash
export PARTHA_MIGRATION_REHEARSAL_PG_URL='postgresql+psycopg://…/postgres'
export PARTHA_MIGRATION_REHEARSAL_CONFIRM=disposable
python scripts/rehearse_migrations.py --postgres
```

The command creates only a randomly named `partha_migration_rehearsal_<uuid>` database and removes that
same database in cleanup, even when the rehearsal itself fails. If cleanup fails independently (for example
the rehearsal server drops the connection mid-teardown), the command prints a `WARNING` naming the orphaned
database so an operator can drop it manually; that name is a random identifier and never contains
connection details. It does not accept a target database name. Do not set these variables to a production,
staging, or shared server; the confirmation is an operator assertion, not an access-control boundary. A CI
job can set them only for an isolated service container, as the existing backend job does.

## Backup and restore rehearsal (#323)

`scripts/rehearse_backup_restore.py` proves the same two things a real recovery needs proven, on
disposable targets it creates and removes itself -- it cannot be pointed at an existing application
database or storage directory, and is safe to run repeatedly:

1. a database backup can be restored into a clean environment with every row, foreign key, and the sealed
   ri.v1 snapshot's `canonical_graph_hash` intact; and
2. the paired `STORAGE_PATH` repository files restore alongside it, byte-for-byte (verified by content
   hash, not just file presence).

```bash
python scripts/rehearse_backup_restore.py
```

The default target is SQLite: backup and restore are each a plain file copy, matching how SQLite itself
defines a consistent backup. This always runs, with no extra tooling.

To exercise the deployment mechanism (`pg_dump`/`pg_restore`), use the same dedicated rehearsal server and
confirmation gate as the migration rehearsal above -- and note this mode additionally requires the
`pg_dump`/`pg_restore` **client binaries** on `PATH` (not just a Python Postgres driver):

```bash
export PARTHA_MIGRATION_REHEARSAL_PG_URL='postgresql+psycopg://…/postgres'
export PARTHA_MIGRATION_REHEARSAL_CONFIRM=disposable
python scripts/rehearse_backup_restore.py --postgres
```

Each run prints the wall-clock seed and restore duration; treat these only as a rehearsal-scale sanity
number, not a production capacity-planning figure -- disposable-target file copies and a single-row seed do
not reflect production database size or network/disk throughput.

**Known gaps, not covered by this rehearsal:**

- Encryption at rest and backup retention windows are the hosting provider's responsibility (Render-managed
  PostgreSQL), not application code -- see "Retention, encryption, access, and deletion" below for the
  expected policy, which cannot itself be rehearsed by a local script.
- This rehearses a clean, quiescent restore, not a restore under concurrent production write load, and not
  point-in-time recovery to a timestamp between two backups.
- Filesystem backup here is a directory copy of the local storage backend. A different storage backend
  (e.g. object storage) would need its own rehearsal.
- Not currently wired into CI (unlike the migration rehearsal above): `pg_dump`/`pg_restore` binary
  availability on the CI runner has not been confirmed. Confirm it, then add a CI step mirroring "Rehearse
  migrations on isolated PostgreSQL" before relying on this running unattended.

## Retention, encryption, access, and deletion expectations

Recorded as the expected policy for the production deployment described in `PARTHA_LIVE_HOSTING_PLAN.md`
(one Render-managed PostgreSQL database plus a persistent disk for repository storage). This is a policy
record, not a claim that every item has been independently verified against the live Render dashboard --
confirm each one there before the first real backup is relied upon.

- **Retention:** managed automated backups, retained per the Render PostgreSQL plan's stated window.
  Confirm the exact window in the Render dashboard for the provisioned plan before depending on it; do not
  assume a specific number of days without checking, since provider retention policy can change.
- **Encryption:** encryption in transit (TLS) for all client connections, and encryption at rest as
  provided by the hosting platform for its managed PostgreSQL and persistent disk offerings. This is a
  platform guarantee, not something PARTHA's application code implements or can rehearse.
- **Access:** database credentials live only in Render's environment configuration (`DATABASE_URL`), never
  committed to source control or logged; access to backups and the ability to trigger a restore is limited
  to the same operators who hold platform/dashboard access, not exposed through any PARTHA application
  surface.
- **Deletion:** a restored backup used for drilling (rehearsal or an actual incident) must itself be
  deleted once validation is complete -- it is a second copy of real user data for as long as it exists.
  Account-level deletion (a user exercising their own account-deletion right) is a separate, already-shipped
  concern (`AccountDeletionService`, #290): it is a live-database cascade at request time, not a backup
  operation, and is out of scope here. A restored *backup* containing an account that has since been
  deleted in production is expected during the drill window; do not treat that as a bug in account
  deletion, and destroy the drill copy promptly once the drill is done.

## Production preflight and recovery decision

Before applying a migration to a non-disposable database:

1. Confirm the live revision with `alembic current`, the intended head with `alembic heads`, and that the
   deployment code and migration artifact are the reviewed release.
2. Take and verify a restorable database backup using the platform-approved mechanism, and rehearse the
   restore procedure itself with `python scripts/rehearse_backup_restore.py --postgres` (see above) if it
   has not been rehearsed recently. Record the backup location, timestamp, source revision, restore owner,
   and tested restore result outside logs and source control.
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

This is a gate checklist only. It does not authorize or implement Repository Lineage. PR #328 records
the approved architecture contract, and this rehearsal must be rerun against the eventual #299 migration
before that implementation PR merges.

- [ ] Re-run this rehearsal on the then-current chain and on a representative disposable copy/fixture of the
  immediately preceding supported baseline.
- [ ] Review the proposed revision for table rewrites, backfill duration, lock modes, indexes, transaction
  boundaries, concurrent imports, and the PostgreSQL/SQLite differences actually supported by the change.
- [ ] Define which fields and rows a downgrade would discard; prove a downgrade only if it is safe for the
  representative data, otherwise test the backup/restore recovery path.
- [ ] Re-run `python scripts/rehearse_backup_restore.py --postgres` (see "Backup and restore rehearsal"
  above) against the then-current schema before merging the implementation PR, to confirm the #299 schema
  change doesn't break the backup/restore integrity checks.
- [ ] Confirm no lineage models, revisions, APIs, services, frontend fields, or backfill code are included in
  this operational-gate work.
