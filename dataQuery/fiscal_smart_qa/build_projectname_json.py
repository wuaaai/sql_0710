"""从达梦收支表抽取项目名称，并生成 projectname.json。

这个模块既可以单独执行，也可以在智能问数向量库重建时被调用。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Set

from config import load_config
from dameng_executor import DamengExecutor
from metadata import load_metadata


OUTPUT_PATH = Path(__file__).resolve().parent / "projectname.json"
TABLE_CONFIG_PATH = Path(__file__).resolve().parent / "projectname_tables.json"


def main() -> None:
    """执行抽取流程，并把项目名称保存为 JSON 文件。"""
    config = load_config()
    metadata_bundle = load_metadata(config.metadata)
    executor = DamengExecutor(config.dameng)
    build_projectname_file(metadata_bundle, executor, OUTPUT_PATH)
    print(f"projectname.json generated: {OUTPUT_PATH}")


def build_projectname_file(metadata_bundle, executor: DamengExecutor, output_path: Path | None = None) -> Path:
    """构建 projectname.json 文件，供其他构建流程复用。"""
    final_output_path = output_path or OUTPUT_PATH

    project_names = extract_project_names(metadata_bundle, executor)
    payload = {
        "count": len(project_names),
        "project_names": project_names,
    }
    final_output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"project name count: {len(project_names)}")
    return final_output_path


def extract_project_names(metadata_bundle, executor: DamengExecutor) -> List[str]:
    """从配置文件指定的表中提取项目名称。"""
    table_names = load_projectname_tables_config(metadata_bundle)
    all_names: Set[str] = set()

    for table_name in table_names:
        subject_column = _guess_subject_name_column(metadata_bundle, table_name)
        if not subject_column:
            continue

        sql = (
            f'SELECT DISTINCT "{subject_column}" AS PROJECT_NAME '
            f'FROM "{executor._config.schema}"."{table_name}" '
            f'WHERE "{subject_column}" IS NOT NULL '
            f"AND TRIM(\"{subject_column}\") <> ''"
        )
        try:
            rows = executor.query(sql)
        except Exception as exc:
            print(f"skip table {table_name}: {exc}")
            continue

        for row in rows:
            name = str(row.get("PROJECT_NAME", "") or "").strip()
            if name:
                all_names.add(name)

    return sorted(all_names, key=len, reverse=True)


def load_projectname_tables_config(metadata_bundle) -> List[str]:
    """读取 projectname_tables.json，获得参与抽取项目名称的表列表。"""
    if not TABLE_CONFIG_PATH.exists():
        return []

    try:
        payload = json.loads(TABLE_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

    raw_tables = payload.get("tables", []) if isinstance(payload, dict) else []
    table_names: List[str] = []
    seen = set()
    for item in raw_tables:
        table_name = str(item or "").strip()
        if not table_name:
            continue
        if table_name not in metadata_bundle.table_info:
            print(f"skip unknown projectname table: {table_name}")
            continue
        if table_name in seen:
            continue
        seen.add(table_name)
        table_names.append(table_name)
    return table_names


def _guess_subject_name_column(metadata_bundle, table_name: str) -> str:
    """根据元数据推断项目名称字段。"""
    _, table_info = metadata_bundle.get_table_info_by_en(table_name)
    schema = metadata_bundle.get_table_schema(table_name) or {}
    fields = schema.get("fields", {})

    preferred_columns = ["AI_XM_NAME", "XM_NAME", "AI_KM_NAME", "KM_NAME", "SUBJECT_NAME"]
    for column_name in preferred_columns:
        if column_name in fields:
            return column_name

    for comment in table_info.get("project_name", []):
        column_name = str(comment.get("column_name", "")).strip()
        if column_name and column_name in fields:
            return column_name

    return ""


if __name__ == "__main__":
    main()
