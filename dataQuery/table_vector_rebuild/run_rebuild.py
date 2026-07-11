from __future__ import annotations

import argparse

from builders import VectorRebuildService
from config import load_config
from dameng_source import DamengSource
from embedding_client import EmbeddingClient
from metadata_builder import MetadataBuilder
from metadata_loader import load_metadata
from pgvector_store import PGVectorStore
from pathlib import Path
import sys


WORKSPACE_DIR = Path(__file__).resolve().parents[1]
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from fiscal_smart_qa.build_projectname_json import build_projectname_file
from fiscal_smart_qa.config import load_config as load_fiscal_config
from fiscal_smart_qa.dameng_executor import DamengExecutor
from fiscal_smart_qa.metadata import load_metadata as load_fiscal_metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild text2sql table vectors with Dameng + pgvector.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Create pgvector tables and indexes.")
    subparsers.add_parser("generate-metadata", help="Generate local metadata from Dameng.")

    build_all = subparsers.add_parser("build-all", help="Rebuild all vector tables for a version.")
    build_all.add_argument("--version", required=True, help="Logical data version, for example 20260622.")

    args = parser.parse_args()
    config = load_config()
    source = DamengSource(config.dameng)

    store = PGVectorStore(config.pgvector)
    try:
        if args.command == "init":
            store.init_schema(config.embedding.dimension)
            print("pgvector schema initialized.")
            return

        if args.command == "generate-metadata":
            builder = MetadataBuilder(source=source, config=config.metadata)
            schema_path, table_info_path = builder.generate_all()
            print(f"Metadata generated. schema_meta={schema_path} table_info={table_info_path}")
            return

        metadata = load_metadata(config.metadata)
        embeddings = EmbeddingClient(config.embedding)
        rebuild = VectorRebuildService(metadata=metadata, source=source, embeddings=embeddings)

        if args.command == "build-all":
            store.init_schema(config.embedding.dimension)
            _build_projectname_json_before_rebuild()
            table_profiles = rebuild.build_table_profiles(version=args.version)
            subject_bindings = rebuild.build_subject_bindings(version=args.version)
            metric_aliases = rebuild.build_metric_aliases(version=args.version)
            store.replace_version(
                version=args.version,
                table_profiles=table_profiles,
                subject_bindings=subject_bindings,
                metric_aliases=metric_aliases,
            )
            print(
                f"Rebuild complete. version={args.version}, "
                f"table_profiles={len(table_profiles)}, "
                f"subject_bindings={len(subject_bindings)}, "
                f"metric_aliases={len(metric_aliases)}"
            )
    finally:
        store.close()


def _build_projectname_json_before_rebuild() -> None:
    """在重建智能问数向量库前，同步刷新项目名称字典。"""
    fiscal_config = load_fiscal_config()
    fiscal_metadata = load_fiscal_metadata(fiscal_config.metadata)
    fiscal_executor = DamengExecutor(fiscal_config.dameng)
    output_path = WORKSPACE_DIR / "fiscal_smart_qa" / "projectname.json"
    build_projectname_file(fiscal_metadata, fiscal_executor, output_path)
    print(f"projectname.json refreshed before vector rebuild: {output_path}")


if __name__ == "__main__":
    main()
