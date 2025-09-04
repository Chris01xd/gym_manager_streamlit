# app/lib/db.py
import os
from contextlib import contextmanager
from dotenv import load_dotenv

import psycopg
from psycopg.rows import dict_row

# Carga variables de .env (PGHOST, PGPORT, etc.)
load_dotenv()

def get_conn():
    return psycopg.connect(
        host=os.getenv("PGHOST"),
        port=os.getenv("PGPORT"),
        dbname=os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        row_factory=dict_row,  # resultados como diccionarios
    )

@contextmanager
def db_cursor(commit=False):
    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                yield cur
                if commit:
                    conn.commit()
            except Exception:
                conn.rollback()
                raise

def query(sql, params=None):
    with db_cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()

def execute(sql, params=None):
    with db_cursor(commit=True) as cur:
        cur.execute(sql, params or ())
        return cur.rowcount

def call_sp(sp_name, params=(), commit=True):
    placeholders = ",".join(["%s"]*len(params))
    sql = f"SELECT * FROM {sp_name}({placeholders})" if params else f"SELECT * FROM {sp_name}()"
    with db_cursor(commit=commit) as cur:
        cur.execute(sql, params)
        try:
            return cur.fetchall()
        except Exception:
            return []
