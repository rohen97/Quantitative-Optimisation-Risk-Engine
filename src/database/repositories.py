from __future__ import annotations

import sqlite3

import pandas as pd


def write_table(conn: sqlite3.Connection, table: str, frame: pd.DataFrame) -> None:
    frame.to_sql(table, conn, if_exists="replace", index=False)


def read_table(conn: sqlite3.Connection, table: str) -> pd.DataFrame:
    return pd.read_sql_query(f"SELECT * FROM {table}", conn)
