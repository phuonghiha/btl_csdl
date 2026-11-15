from contextlib import contextmanager
from queue import Empty, Full, LifoQueue
from typing import Any, Iterator
import pymysql
from pymysql.cursors import DictCursor
from .config import get_settings

_POOL: LifoQueue[pymysql.connections.Connection] = LifoQueue(maxsize=12)


def _connect(autocommit: bool = True) -> pymysql.connections.Connection:
    cfg = get_settings()
    return pymysql.connect(
        host=cfg.mysql_host,
        port=cfg.mysql_port,
        user=cfg.mysql_user,
        password=cfg.mysql_password,
        database=cfg.mysql_database,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=autocommit,
        connect_timeout=5,
    )


def _acquire_conn(autocommit: bool) -> pymysql.connections.Connection:
    while True:
        try:
            conn = _POOL.get_nowait()
        except Empty:
            return _connect(autocommit=autocommit)
        try:
            if conn.open:
                conn.ping(reconnect=False)
                conn.autocommit(autocommit)
                return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass


def _release_conn(conn: pymysql.connections.Connection) -> None:
    try:
        if not conn.open:
            return
        conn.autocommit(True)
        _POOL.put_nowait(conn)
    except Full:
        try:
            conn.close()
        except Exception:
            pass
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


@contextmanager
def get_cursor(autocommit: bool = True) -> Iterator[DictCursor]:
    """Yield a DictCursor from a pooled MySQL connection."""
    conn: pymysql.connections.Connection | None = _acquire_conn(autocommit=autocommit)
    try:
        with conn.cursor() as cur:
            yield cur
        if not autocommit:
            conn.commit()
    except Exception:
        if conn is not None:
            if not autocommit:
                try:
                    conn.rollback()
                except Exception:
                    pass
            try:
                conn.close()
            except Exception:
                pass
            conn = None
        raise
    finally:
        if conn is not None:
            _release_conn(conn)


def fetch_all(sql: str, params: tuple[Any, ...] | list[Any] = ()) -> list[dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def fetch_one(sql: str, params: tuple[Any, ...] | list[Any] = ()) -> dict[str, Any] | None:
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def call_proc_with_out(
    proc_name: str,
    in_params: tuple[Any, ...],
    out_names: list[str],
) -> dict[str, Any]:
    """Call a MySQL stored procedure that declares OUT parameters via session variables."""
    placeholders = ["%s"] * len(in_params) + [f"@{name}" for name in out_names]
    call_sql = f"CALL {proc_name}({', '.join(placeholders)})"
    with get_cursor(autocommit=True) as cur:
        cur.execute(call_sql, in_params)
        if not out_names:
            return {}
        select_exprs = ", ".join(f"@{name} AS {name}" for name in out_names)
        cur.execute(f"SELECT {select_exprs}")
        return cur.fetchone() or {}
