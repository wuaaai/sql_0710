from __future__ import annotations

from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple

from config import DamengConfig

try:
    import dmPython
except ImportError:  # pragma: no cover
    dmPython = None


class DamengSource:
    def __init__(self, config: DamengConfig):
        self._config = config

    @property
    def schema_name(self) -> str:
        return self._config.schema

    @contextmanager
    def connect(self):
        if dmPython is None:
            raise ImportError("dmPython is required for Dameng access.")

        conn = self._open_connection()
        try:
            self._apply_schema(conn)
            yield conn
        finally:
            conn.close()

    def fetch_distinct_subject_rows(
        self,
        table_name: str,
        subject_name_column: str,
        subject_code_column: Optional[str],
    ) -> List[Tuple[str, Optional[str]]]:
        qualified_table = self._qualified_table(table_name)
        subject_name_expr = self._quote_identifier(subject_name_column)
        subject_code_expr = self._quote_identifier(subject_code_column) if subject_code_column else ""
        select_code = f", {subject_code_expr}" if subject_code_expr else ""
        order_code = f", {subject_code_expr}" if subject_code_expr else ""
        sql = (
            f"SELECT DISTINCT {subject_name_expr}{select_code} "
            f"FROM {qualified_table} "
            f"WHERE {subject_name_expr} IS NOT NULL "
            f"ORDER BY {subject_name_expr}{order_code}"
        )
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql)
            return [(row[0], row[1] if len(row) > 1 else None) for row in cur.fetchall()]

    def list_tables(self) -> List[Tuple[str, str]]:
        rows = self._fetch_first(
            sql_candidates=[
                """
                SELECT TABLE_NAME, COMMENTS
                FROM USER_TAB_COMMENTS
                ORDER BY TABLE_NAME
                """,
                """
                SELECT TABLE_NAME, COMMENTS
                FROM ALL_TAB_COMMENTS
                WHERE OWNER = ?
                ORDER BY TABLE_NAME
                """,
            ],
            params=[self._config.schema.upper()],
        )
        output: List[Tuple[str, str]] = []
        for row in rows:
            table_name = row[0]
            if not self._is_candidate_table_name(table_name):
                continue
            output.append((table_name, row[1] or row[0]))
        return output

    def fetch_column_metadata(self, table_name: str) -> List[Dict[str, object]]:
        pk_columns = set(self._fetch_primary_keys(table_name))
        comments = self.fetch_column_comments(table_name)
        rows = self._fetch_first(
            sql_candidates=[
                """
                SELECT COLUMN_NAME, DATA_TYPE, DATA_DEFAULT, NULLABLE
                FROM USER_TAB_COLUMNS
                WHERE TABLE_NAME = ?
                ORDER BY COLUMN_ID
                """,
                """
                SELECT COLUMN_NAME, DATA_TYPE, DATA_DEFAULT, NULLABLE
                FROM ALL_TAB_COLUMNS
                WHERE OWNER = ? AND TABLE_NAME = ?
                ORDER BY COLUMN_ID
                """,
            ],
            params=[table_name.upper()],
            alt_params=[self._config.schema.upper(), table_name.upper()],
        )

        columns: List[Dict[str, object]] = []
        for row in rows:
            nullable_raw = row[3] if len(row) > 3 else "Y"
            columns.append(
                {
                    "name": row[0],
                    "type": row[1],
                    "default": row[2],
                    "nullable": False if str(nullable_raw).upper() == "N" else True,
                    "primary_key": row[0] in pk_columns,
                    "autoincrement": False,
                    "comment": comments.get(row[0], row[0]),
                }
            )
        return columns

    def fetch_column_comments(self, table_name: str) -> Dict[str, str]:
        rows = self._fetch_first(
            sql_candidates=[
                """
                SELECT COLUMN_NAME, COMMENTS
                FROM USER_COL_COMMENTS
                WHERE TABLE_NAME = ?
                ORDER BY COLUMN_NAME
                """,
                """
                SELECT COLUMN_NAME, COMMENTS
                FROM ALL_COL_COMMENTS
                WHERE OWNER = ? AND TABLE_NAME = ?
                ORDER BY COLUMN_NAME
                """,
            ],
            params=[table_name.upper()],
            alt_params=[self._config.schema.upper(), table_name.upper()],
        )
        return {row[0]: row[1] or row[0] for row in rows}

    def fetch_comment_to_column_mapping(self, table_name: str) -> Dict[str, str]:
        return {comment: column for column, comment in self.fetch_column_comments(table_name).items()}

    def fetch_column_examples(self, table_name: str, column_name: str, limit: int = 5) -> List[str]:
        qualified_table = self._qualified_table(table_name)
        column_expr = self._quote_identifier(column_name)
        rows = self._fetch_first(
            sql_candidates=[
                f"""
                SELECT *
                FROM (
                    SELECT DISTINCT {column_expr}
                    FROM {qualified_table}
                    WHERE {column_expr} IS NOT NULL
                ) t
                WHERE ROWNUM <= {limit}
                """,
            ],
        )
        return [str(row[0]) for row in rows if row and row[0] is not None]

    def _fetch_primary_keys(self, table_name: str) -> List[str]:
        rows = self._fetch_first(
            sql_candidates=[
                """
                SELECT cols.COLUMN_NAME
                FROM USER_CONSTRAINTS cons
                JOIN USER_CONS_COLUMNS cols
                  ON cons.CONSTRAINT_NAME = cols.CONSTRAINT_NAME
                WHERE cons.TABLE_NAME = ?
                  AND cons.CONSTRAINT_TYPE = 'P'
                ORDER BY cols.POSITION
                """,
                """
                SELECT cols.COLUMN_NAME
                FROM ALL_CONSTRAINTS cons
                JOIN ALL_CONS_COLUMNS cols
                  ON cons.OWNER = cols.OWNER
                 AND cons.CONSTRAINT_NAME = cols.CONSTRAINT_NAME
                WHERE cons.OWNER = ?
                  AND cons.TABLE_NAME = ?
                  AND cons.CONSTRAINT_TYPE = 'P'
                ORDER BY cols.POSITION
                """,
            ],
            params=[table_name.upper()],
            alt_params=[self._config.schema.upper(), table_name.upper()],
        )
        return [row[0] for row in rows]

    def _fetch_first(
        self,
        sql_candidates: List[str],
        params: Optional[List[object]] = None,
        alt_params: Optional[List[object]] = None,
    ):
        last_error = None
        for index, sql in enumerate(sql_candidates):
            call_params = []
            if index == 0:
                call_params = params or []
            else:
                call_params = alt_params if alt_params is not None else params or []
            try:
                with self.connect() as conn:
                    cur = conn.cursor()
                    cur.execute(sql, call_params)
                    return cur.fetchall()
            except Exception as exc:  # pragma: no cover
                last_error = exc
        raise RuntimeError(f"Dameng query failed: {last_error}")

    def _open_connection(self):
        attempts = [
            {"user": self._config.user, "password": self._config.password, "server": self._config.host, "port": self._config.port},
            {"user": self._config.user, "password": self._config.password, "server": f"{self._config.host}:{self._config.port}"},
            {"user": self._config.user, "password": self._config.password, "server": self._config.host, "port": str(self._config.port)},
        ]
        last_error = None
        for kwargs in attempts:
            try:
                return dmPython.connect(**kwargs)
            except Exception as exc:  # pragma: no cover
                last_error = exc
        raise RuntimeError(f"Unable to connect to Dameng: {last_error}")

    def _apply_schema(self, conn) -> None:
        schema = (self._config.schema or "").strip()
        if not schema:
            return
        cur = conn.cursor()
        try:
            cur.execute(f"SET SCHEMA {schema}")
        except Exception:
            pass

    def _qualified_table(self, table_name: str) -> str:
        schema = (self._config.schema or "").strip()
        table_expr = self._quote_identifier(table_name)
        if not schema:
            return table_expr
        return f"{self._quote_identifier(schema)}.{table_expr}"

    def _quote_identifier(self, name: Optional[str]) -> str:
        if not name:
            return ""
        escaped = str(name).replace('"', '""')
        return f'"{escaped}"'

    def _is_candidate_table_name(self, table_name: Optional[str]) -> bool:
        if not table_name:
            return False
        name = str(table_name).strip()
        if not name:
            return False
        if name.startswith("#"):
            return False
        if name.startswith("##"):
            return False
        if name.startswith("SYS_"):
            return False
        return True
