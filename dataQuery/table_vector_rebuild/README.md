# Table Vector Rebuild

This folder contains a standalone rebuild tool for the text2sql table vector store.

## What it builds

The rebuilt vector store is split into three pgvector tables:

- `vec_table_profile`: table selection profiles
- `vec_subject_binding`: table-subject bindings
- `vec_metric_alias`: metric and column aliases

## Data source

- Vector store: PostgreSQL + pgvector
- Source database: Dameng on `localhost:5236`
- Metadata files: generated locally inside this project

## Quick start

1. Install dependencies from `requirements.txt`
2. Update environment variables if needed
3. Generate metadata from Dameng
4. Run rebuild

```bash
python run_rebuild.py generate-metadata
python run_rebuild.py init
python run_rebuild.py build-all --version v1
```

## Environment variables

- `VECTOR_EMBEDDING_URL`
- `VECTOR_DIM`
- `PGVECTOR_HOST`
- `PGVECTOR_PORT`
- `PGVECTOR_DB`
- `PGVECTOR_USER`
- `PGVECTOR_PASSWORD`
- `DM_HOST`
- `DM_PORT`
- `DM_USER`
- `DM_PASSWORD`
- `DM_SCHEMA`
- `DM_TABLE_INFO_PATH`
- `DM_SCHEMA_META_PATH`

## Notes

- The script writes metadata to the local `metadata/` directory by default.
- Dameng access uses the `dmPython` driver.
- The rebuild process is versioned. Re-running the same version will replace data for that version.
- `table_description.py` is no longer required. Table profile text is generated automatically from schema metadata and `table_info.json`.
