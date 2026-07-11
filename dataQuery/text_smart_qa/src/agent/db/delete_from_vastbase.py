"""删除 PostgreSQL pgvector 集合中的指定来源数据。

说明：
1. 这个脚本文件名沿用了历史命名，方便兼容旧操作习惯。
2. 当前实际操作的是 PostgreSQL pgvector 中的向量表。

用法:
    python src/agent/db/delete_from_vastbase.py
"""
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", ".."))
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

import env_utils
from sqlalchemy import create_engine, text

DB_CONNECTION = env_utils.PGVECTOR_CONNECTION
COLLECTION_NAME = env_utils.PGVECTOR_COLLECTION_NAME

engine = create_engine(DB_CONNECTION)


def list_sources():
    """列出向量库中所有不重复的文件来源。"""
    with engine.connect() as conn:
        result = conn.execute(
            text(
                f"SELECT DISTINCT c_metadata::jsonb->>'source' AS source, COUNT(*) AS cnt "
                f'FROM "{COLLECTION_NAME}" '
                f"GROUP BY source ORDER BY source"
            )
        )
        rows = result.fetchall()
        if not rows:
            print("知识库为空，无数据可删。")
            return []
        print(f"\n{'='*50}")
        print(f"知识库中现有 {len(rows)} 个文件来源：")
        print(f"{'='*50}")
        for i, (source, cnt) in enumerate(rows, 1):
            print(f"  [{i}] {source} ({cnt} 条)")
        return [(source, cnt) for source, cnt in rows]


def delete_by_source(source: str) -> int:
    """删除指定来源的所有数据，返回删除条数。"""
    with engine.connect() as conn:
        result = conn.execute(
            text(
                f'DELETE FROM "{COLLECTION_NAME}" '
                f"WHERE c_metadata::jsonb->>'source' = :source"
            ),
            {"source": source},
        )
        conn.commit()
        return result.rowcount


def main():
    sources = list_sources()
    if not sources:
        return

    print(f"\n输入要删除的文件编号（多个用逗号分隔，如 1,3,5）")
    print("输入 'all' 删除全部，输入 'q' 退出")
    choice = input("\n> ").strip()

    if choice.lower() == 'q':
        print("已取消")
        return

    if choice.lower() == 'all':
        targets = list(range(len(sources)))
    else:
        try:
            targets = [int(x.strip()) - 1 for x in choice.split(",")]
        except ValueError:
            print("输入格式错误，已取消")
            return

    for idx in targets:
        if idx < 0 or idx >= len(sources):
            print(f"  [{idx + 1}] 编号无效，跳过")
            continue
        source_name, cnt = sources[idx]
        confirm = input(f"\n确认删除 '{source_name}' ({cnt} 条)? [y/N]: ").strip().lower()
        if confirm == 'y':
            deleted = delete_by_source(source_name)
            print(f"  已删除 {deleted} 条")

    print("\n操作完成。")
    # 展示剩余
    sources = list_sources()


if __name__ == "__main__":
    main()
