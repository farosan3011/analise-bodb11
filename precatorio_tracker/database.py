import sqlite3
import json
import os
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "precatorios.db"


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS precatorios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                depre TEXT NOT NULL,
                cidade TEXT NOT NULL,
                criado_em TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(depre, cidade)
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                precatorio_id INTEGER NOT NULL REFERENCES precatorios(id),
                capturado_em TEXT DEFAULT (datetime('now','localtime')),
                posicao INTEGER,
                valor TEXT,
                status TEXT,
                dados_brutos TEXT
            );
        """)


def upsert_precatorio(depre: str, cidade: str) -> int:
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO precatorios (depre, cidade) VALUES (?, ?)",
            (depre, cidade),
        )
        row = conn.execute(
            "SELECT id FROM precatorios WHERE depre = ? AND cidade = ?",
            (depre, cidade),
        ).fetchone()
        return row["id"]


def save_snapshot(precatorio_id: int, dados: dict):
    with _connect() as conn:
        conn.execute(
            """INSERT INTO snapshots (precatorio_id, posicao, valor, status, dados_brutos)
               VALUES (?, ?, ?, ?, ?)""",
            (
                precatorio_id,
                dados.get("posicao"),
                dados.get("valor"),
                dados.get("status"),
                json.dumps(dados, ensure_ascii=False),
            ),
        )


def get_history(depre: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT s.capturado_em, s.posicao, s.valor, s.status, s.dados_brutos,
                      p.depre, p.cidade
               FROM snapshots s
               JOIN precatorios p ON p.id = s.precatorio_id
               WHERE p.depre = ?
               ORDER BY s.capturado_em DESC""",
            (depre,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_all() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT p.depre, p.cidade, p.criado_em,
                      s.posicao AS ultima_posicao,
                      s.status AS ultimo_status,
                      s.capturado_em AS ultima_captura
               FROM precatorios p
               LEFT JOIN snapshots s ON s.id = (
                   SELECT id FROM snapshots
                   WHERE precatorio_id = p.id
                   ORDER BY capturado_em DESC
                   LIMIT 1
               )
               ORDER BY p.cidade, p.depre"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_tracked() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT depre, cidade FROM precatorios ORDER BY cidade, depre"
        ).fetchall()
        return [dict(r) for r in rows]
