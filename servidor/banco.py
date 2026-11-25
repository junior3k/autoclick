# pyright: basic
"""SQLite fino e seguro para threads."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

ESQUEMA = """
CREATE TABLE IF NOT EXISTS instalacoes (
    id TEXT PRIMARY KEY,
    primeira TEXT NOT NULL,
    visto TEXT NOT NULL,
    versao TEXT,
    so TEXT,
    canal TEXT
);
CREATE TABLE IF NOT EXISTS versoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    versao TEXT NOT NULL,
    artefato TEXT NOT NULL,
    canal TEXT NOT NULL,
    arquivo TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    tamanho INTEGER NOT NULL,
    assinatura TEXT NOT NULL,
    notas TEXT NOT NULL DEFAULT '',
    minima TEXT NOT NULL DEFAULT '0',
    percentual INTEGER NOT NULL DEFAULT 100,
    publicada TEXT NOT NULL,
    UNIQUE (versao, artefato)
);
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    t TEXT NOT NULL,
    tipo TEXT NOT NULL,
    amigo TEXT,
    detalhe TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS relatorios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instalacao TEXT,
    criado TEXT NOT NULL,
    arquivo TEXT NOT NULL,
    resumo TEXT NOT NULL DEFAULT '',
    tamanho INTEGER NOT NULL
);
"""


class Banco:
    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._con = sqlite3.connect(str(self.caminho), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        with self._lock:
            self._con.execute("PRAGMA journal_mode=WAL")
            self._con.execute("PRAGMA foreign_keys=ON")
            self._con.executescript(ESQUEMA)
            try:  # bancos criados antes da remoção dos convites
                self._con.execute("ALTER TABLE relatorios ADD COLUMN instalacao TEXT")
            except sqlite3.OperationalError:
                pass
            self._con.commit()

    def executar(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        with self._lock:
            cur = self._con.execute(sql, params)
            self._con.commit()
            return int(cur.lastrowid or 0)

    def um(self, sql: str, params: tuple[Any, ...] = ()) -> Optional[dict[str, Any]]:
        with self._lock:
            r = self._con.execute(sql, params).fetchone()
        return dict(r) if r is not None else None

    def todos(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._con.execute(sql, params).fetchall()]

    def copiar_para(self, destino: Path) -> None:
        """Cópia consistente do banco (API de backup do SQLite) mesmo com o servidor em uso."""
        with self._lock:
            dst = sqlite3.connect(str(destino))
            try:
                self._con.backup(dst)
            finally:
                dst.close()

    def fechar(self) -> None:
        with self._lock:
            self._con.close()
