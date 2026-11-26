# pyright: basic
"""Relatório de problema: junta o que ajuda a diagnosticar (e NADA mais) num .zip pequeno.

Nada é enviado sozinho: a pessoa salva o .zip e escolhe a quem mandar. O que entra:
  - as últimas linhas de logs/autoclick.log
  - o histórico de sessões (historico/sessoes.jsonl, últimas linhas)
  - até 3 capturas recentes de erro (erros/*.png)
  - sistema.txt (versão, Windows, Python, resolução)
  - a configuração da janela SEM o webhook
Nunca entram: webhook, botões, perfis, gravações.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import zipfile
from pathlib import Path
from typing import Any, Optional

from . import __version__
from .atualizacao import ErroServidor

LIMITE_BYTES = 4 * 1024 * 1024
SEGREDOS = ("webhook", "servidor_chave", "chave")


def _ultimas_linhas(p: Path, n: int) -> str:
    try:
        return "\n".join(p.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]) + "\n"
    except OSError:
        return ""


def _sistema() -> str:
    linhas = [f"autoclick {__version__}", f"python {sys.version.split()[0]}", f"so {platform.platform()}",
              f"congelado {bool(getattr(sys, 'frozen', False))}"]
    if sys.platform == "win32":
        try:
            import ctypes
            u = ctypes.windll.user32  # type: ignore[attr-defined]
            linhas.append(f"tela {u.GetSystemMetrics(0)}x{u.GetSystemMetrics(1)}")
        except Exception:
            pass
    return "\n".join(linhas) + "\n"


def _config_sem_segredos(raiz: Path) -> str:
    p = raiz / "autoclick_gui.json"
    try:
        d: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "{}"
    return json.dumps({k: v for k, v in d.items() if not any(s in k.lower() for s in SEGREDOS)},
                      ensure_ascii=False, indent=2)


def conteudo(raiz: str = ".") -> list[str]:
    """Lista legível do que será enviado (mostrada na confirmação)."""
    r = Path(raiz)
    itens = ["sistema.txt (versão, Windows, Python, resolução)"]
    if (r / "logs" / "autoclick.log").is_file():
        itens.append("logs/autoclick.log (últimas 400 linhas)")
    hist = Path(os.environ.get("AUTOCLICK_HISTORICO", str(r / "historico" / "sessoes.jsonl")))
    if hist.is_file():
        itens.append("histórico de sessões (últimas 50)")
    pasta = Path(os.environ.get("AUTOCLICK_PASTA_ERROS", str(r / "erros")))
    pngs = sorted(pasta.glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)[:3] if pasta.is_dir() else []
    itens += [f"captura de erro: {f.name}" for f in pngs]
    itens.append("configurações (sem o webhook)")
    return itens


def montar(destino: str, raiz: str = ".", motivo: str = "") -> str:
    """Cria o .zip em `destino` (≤ 4 MB). Devolve o caminho."""
    r = Path(raiz)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("sistema.txt", _sistema() + (f"motivo: {motivo}\n" if motivo else ""))
        log = _ultimas_linhas(r / "logs" / "autoclick.log", 400)
        if log:
            z.writestr("autoclick.log", log)
        hist = Path(os.environ.get("AUTOCLICK_HISTORICO", str(r / "historico" / "sessoes.jsonl")))
        if hist.is_file():
            z.writestr("sessoes.jsonl", _ultimas_linhas(hist, 50))
        z.writestr("config.json", _config_sem_segredos(r))
        pasta = Path(os.environ.get("AUTOCLICK_PASTA_ERROS", str(r / "erros")))
        usado = 0
        if pasta.is_dir():
            for f in sorted(pasta.glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)[:3]:
                if usado + f.stat().st_size < LIMITE_BYTES - 200_000:
                    z.write(f, "erros/" + f.name)
                    usado += f.stat().st_size
    if os.path.getsize(destino) > LIMITE_BYTES:
        raise ErroServidor("o relatório ficou maior que 4 MB")
    return destino
