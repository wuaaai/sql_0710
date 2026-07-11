"""达梦数据库执行模块。"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, List, Tuple

from config import DamengConfig

try:
    import dmPython
except ImportError:  # pragma: no cover
    dmPython = None


class DamengExecutor:
    """负责连接达梦数据库并执行查询。"""

    def __init__(self, config: DamengConfig):
        """保存达梦连接配置。"""
        self._config = config

    @contextmanager
    def connect(self):
        """创建一个数据库连接上下文，离开作用域时自动关闭连接。"""
        if dmPython is None:
            raise ImportError("dmPython is required for Dameng access.")
        conn = self._open_connection()
        try:
            self._apply_schema(conn)
            yield conn
        finally:
            conn.close()

    def query(self, sql: str, params: Tuple[Any, ...] | None = None) -> List[Dict[str, Any]]:
        """执行一条查询 SQL，并把结果转成字典列表。"""
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, params or [])
            columns = [item[0] for item in cur.description] if cur.description else []
            rows = cur.fetchall()
            return [dict(zip(columns, row)) for row in rows]

    def _open_connection(self):
        """尝试用几种不同连接参数格式连接达梦。"""
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
        """如果配置了 schema，就在当前连接里切换到对应 schema。"""
        schema = (self._config.schema or "").strip()
        if not schema:
            return

        cur = conn.cursor()
        try:
            cur.execute(f"SET SCHEMA {schema}")
        except Exception:
            pass
