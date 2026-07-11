from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict

from config import MetadataConfig


@dataclass(frozen=True)
class LoadedMetadata:
    table_info: Dict[str, dict]
    schema_meta: Dict[str, dict]


def load_metadata(config: MetadataConfig) -> LoadedMetadata:
    with config.table_info_path.open("r", encoding="utf-8") as fh:
        table_info = json.load(fh)

    with config.schema_meta_path.open("r", encoding="utf-8") as fh:
        schema_meta = json.load(fh)

    return LoadedMetadata(table_info=table_info, schema_meta=schema_meta)
