# pyright: basic
"""Log em arquivo com rotação (logs/autoclick.log): guarda o que aparece no console.

Só a biblioteca padrão. O processo "dono" (a janela, ou o terminal quando você roda direto)
grava; os processos filhos da janela não gravam (a janela repassa a saída deles), assim
não há dois processos disputando o mesmo arquivo (o que falha no Windows).
"""
from __future__ import annotations

import io
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Any, Optional

_logger: Optional[logging.Logger] = None


def iniciar(pasta: str = "logs", nome: str = "autoclick.log", maximo: int = 1_000_000,
            copias: int = 3) -> Optional[logging.Logger]:
    """Liga o log em arquivo (idempotente). Devolve o logger, ou None se não deu para abrir."""
    global _logger
    if _logger is not None:
        return _logger
    try:
        os.makedirs(pasta, exist_ok=True)
        h = RotatingFileHandler(os.path.join(pasta, nome), maxBytes=maximo, backupCount=copias,
                                encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
        lg = logging.getLogger("autoclick.arquivo")
        lg.setLevel(logging.INFO)
        lg.propagate = False
        lg.addHandler(h)
        _logger = lg
    except OSError:
        _logger = None
    return _logger


def escrever(texto: str, nivel: int = logging.INFO) -> None:
    """Grava `texto` (uma ou várias linhas) no log, se ligado."""
    if _logger is None:
        return
    for linha in texto.splitlines():
        if linha.strip():
            _logger.log(nivel, linha.rstrip())


def fechar() -> None:
    global _logger
    if _logger is not None:
        for h in list(_logger.handlers):
            h.close()
            _logger.removeHandler(h)
    _logger = None


class _Tee(io.TextIOBase):
    """Escreve no fluxo original e também no log (por linhas completas)."""

    def __init__(self, original: Any, nivel: int) -> None:
        self.original, self.nivel, self._resto = original, nivel, ""

    def write(self, s: str) -> int:
        if self.original is not None:
            try:
                self.original.write(s)
            except Exception:
                pass
        self._resto += s
        *linhas, self._resto = self._resto.split("\n")
        for ln in linhas:
            escrever(ln, self.nivel)
        return len(s)

    def flush(self) -> None:
        if self.original is not None:
            try:
                self.original.flush()
            except Exception:
                pass

    def isatty(self) -> bool:
        return bool(self.original is not None and getattr(self.original, "isatty", lambda: False)())

    @property
    def encoding(self) -> str:  # type: ignore[override]
        return str(getattr(self.original, "encoding", "utf-8") or "utf-8")


def capturar_saida() -> None:
    """Faz print()/erros também irem para o arquivo de log."""
    if iniciar() is None or isinstance(sys.stdout, _Tee):
        return
    sys.stdout = _Tee(sys.stdout, logging.INFO)  # type: ignore[assignment]
    sys.stderr = _Tee(sys.stderr, logging.ERROR)  # type: ignore[assignment]


def sou_filho() -> bool:
    """True quando a janela iniciou este processo (ela é quem grava o log)."""
    return os.environ.get("AUTOCLICK_FILHO") == "1"
