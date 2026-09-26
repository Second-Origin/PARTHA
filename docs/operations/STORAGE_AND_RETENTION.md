# Storage and retention

What PARTHA keeps on disk, what it discards on its own, and what is left to you.

## What grows

| Where | What | Grows with |
|---|---|---|
| `STORAGE_PATH/repositories/<id>/` | the extracted source of each imported repository | each imported repository or revision |
| the database (`ri_*` tables) | the analysis of each repository revision: files, symbols, relationships, evidence | each analysed revision (tens of MB for a repository the size of PARTHA itself) |

## What is discarded automatically

- **A failed or cancelled analysis** keeps its snapshot row (so the failure stays explainable) but its partial facts are deleted as soon as it fails. A cancelled run on a large repository used to leave tens of megabytes behind.
- **Facts left by earlier failures** (from before this behaviour, or by a rejected seal) are discarded a few at a time by the worker's periodic sweep.
- Deleting a repository in the app removes its source directory and its analysis.

## What is left to you

- **Which old revisions to keep.** Each re-import of a source is a new repository with its own analysis, and the older one remains so its history can be viewed. Delete the ones you no longer need in the app; PARTHA does not expire completed analyses on its own, because that would silently remove history.
- **Returning space to the operating system.** SQLite reuses freed pages for new analyses but never shrinks the file until it is vacuumed.

## The cleanup script

```bash
cd apps/backend
python scripts/cleanup_storage.py                     # report only
python scripts/cleanup_storage.py --apply             # sweep failed-analysis facts, remove orphaned directories
python scripts/cleanup_storage.py --apply --vacuum    # also shrink the SQLite file
```

It reports by default and deletes only with `--apply`. It never touches a completed analysis or a repository that still exists. Stop PARTHA before `--vacuum` (it rewrites the whole file and needs free disk of about the database's size). On PostgreSQL, autovacuum reclaims space and `--vacuum` does nothing.
