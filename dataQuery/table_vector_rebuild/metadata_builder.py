from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config import MetadataConfig
from dameng_source import DamengSource


EXCLUDED_NAME_COMMENTS = {"区划名称", "部门名称"}
EXCLUDED_CODE_COMMENTS = {"区划编码", "部门编码"}


class MetadataBuilder:
    def __init__(self, source: DamengSource, config: MetadataConfig):
        self._source = source
        self._config = config

    def generate_all(self) -> Tuple[Path, Path]:
        schema_path = self.generate_schema_meta()
        table_info_path = self.generate_table_info(schema_path=schema_path)
        return schema_path, table_info_path

    def generate_schema_meta(self, output_path: Optional[Path] = None) -> Path:
        output = output_path or self._config.schema_meta_path
        output.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "db_id": self._source.schema_name,
            "schema": self._source.schema_name,
            "tables": {},
        }
        for table_name, table_comment in self._source.list_tables():
            try:
                columns = self._source.fetch_column_metadata(table_name)
            except Exception as exc:
                print(f"[skip] failed to read columns for table={table_name}: {exc}")
                continue
            fields = {}
            for column in columns:
                try:
                    examples = self._source.fetch_column_examples(table_name, column["name"], limit=5)
                except Exception as exc:
                    print(
                        f"[warn] failed to read examples for table={table_name}, "
                        f"column={column['name']}: {exc}"
                    )
                    examples = []
                fields[column["name"]] = {
                    "type": column["type"],
                    "primary_key": column["primary_key"],
                    "nullable": column["nullable"],
                    "default": column["default"],
                    "autoincrement": column["autoincrement"],
                    "comment": column["comment"],
                    "examples": examples,
                }
            payload["tables"][table_name] = {
                "comment": table_comment or table_name,
                "fields": fields,
            }

        with output.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        return output

    def generate_table_info(self, schema_path: Optional[Path] = None, output_path: Optional[Path] = None) -> Path:
        schema_file = schema_path or self._config.schema_meta_path
        output = output_path or self._config.table_info_path
        output.parent.mkdir(parents=True, exist_ok=True)

        with schema_file.open("r", encoding="utf-8") as fh:
            schema_meta = json.load(fh)

        table_info: Dict[str, dict] = {}
        for table_name, table_meta in schema_meta.get("tables", {}).items():
            table_zh = table_meta.get("comment", table_name)
            fields = table_meta.get("fields", {})
            project_key, project_name = self._detect_project_fields(fields)
            is_hj = self._detect_has_total_value(table_name, project_name)
            unit = self._detect_metric_units(fields)

            table_info[table_zh] = {
                "key_words": [],
                "project_key": project_key,
                "is_sheng": 1 if self._is_provincial_table(table_zh) else 0,
                "project_name": project_name,
                "is_hj": 1 if is_hj else 0,
                "unit": unit,
                "cate": self._infer_category(table_zh),
                "table": table_name,
            }

        with output.open("w", encoding="utf-8") as fh:
            json.dump(table_info, fh, ensure_ascii=False, indent=2)
        return output

    def _detect_project_fields(self, fields: Dict[str, dict]) -> Tuple[List[str], List[str]]:
        project_key: List[str] = []
        project_name: List[str] = []
        for field in fields.values():
            comment = (field.get("comment") or "").strip()
            if not comment:
                continue
            if "编码" in comment and comment not in EXCLUDED_CODE_COMMENTS:
                project_key.append(comment)
            if "名称" in comment and comment not in EXCLUDED_NAME_COMMENTS:
                project_name.append(comment)
        return _unique(project_key), _unique(project_name)

    def _detect_has_total_value(self, table_name: str, project_name_comments: List[str]) -> bool:
        comment_map = self._source.fetch_comment_to_column_mapping(table_name)
        for comment in project_name_comments:
            column_name = comment_map.get(comment)
            if not column_name:
                continue
            for value in self._source.fetch_column_examples(table_name, column_name, limit=20):
                if str(value).strip().replace(" ", "") == "合计":
                    return True
        return False

    def _detect_metric_units(self, fields: Dict[str, dict]) -> Dict[str, Dict[str, str]]:
        units = {"万元": {}, "%": {}}
        for column_name, field in fields.items():
            data_type = (field.get("type") or "").upper()
            comment = (field.get("comment") or "").strip()
            if not comment or not _is_numeric_type(data_type):
                continue
            if _looks_like_percentage(comment):
                units["%"][column_name] = comment
            elif _looks_like_amount(comment):
                units["万元"][column_name] = comment
        return units

    def _is_provincial_table(self, table_zh: str) -> bool:
        return any(token in table_zh for token in ("省级", "本级", "省本级"))

    def _infer_category(self, table_zh: str) -> str:
        if table_zh.startswith("经济"):
            return "经济监督"
        if table_zh.startswith("国有资产"):
            return "国资监督"
        return "预算执行"


def _is_numeric_type(data_type: str) -> bool:
    return any(token in data_type for token in ("NUMBER", "DECIMAL", "NUMERIC", "INT", "DOUBLE", "FLOAT"))


def _looks_like_percentage(comment: str) -> bool:
    return any(token in comment for token in ("%", "百分比", "比率", "同比", "增幅", "完成率"))


def _looks_like_amount(comment: str) -> bool:
    return any(token in comment for token in ("金额", "预算", "收入", "支出", "累计", "本月", "完成"))


def _unique(values: List[str]) -> List[str]:
    seen = set()
    output: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output
