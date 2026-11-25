# pyright: basic
"""“O que mudou”: as novidades da versão, mostradas uma vez depois de atualizar.

Fonte: _atualizacao/novidades.json (gravado pelo instalador com as notas que vieram do servidor)
ou, se não houver, a seção da versão no CHANGELOG.md que acompanha o programa.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

ARQ = Path("_atualizacao") / "novidades.json"


def guardar(raiz: str, versao: str, notas: str) -> None:
    """Chamado ao instalar uma atualização (o programa novo mostra na primeira abertura)."""
    try:
        p = Path(raiz) / ARQ
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"versao": versao, "notas": notas}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def secao_do_changelog(texto: str, versao: str) -> str:
    m = re.search(rf"(?ms)^##\s*\[?v?{re.escape(versao)}\]?[^\n]*\n(.*?)(?=^##\s|\Z)", texto)
    return m.group(1).strip() if m else ""


def ler(raiz: str, versao: str) -> str:
    """Texto das novidades de `versao` ("" se não houver)."""
    try:
        d = json.loads((Path(raiz) / ARQ).read_text(encoding="utf-8"))
        if isinstance(d, dict) and str(d.get("versao")) == versao and str(d.get("notas", "")).strip():
            return str(d["notas"]).strip()
    except (OSError, ValueError):
        pass
    try:
        return secao_do_changelog((Path(raiz) / "CHANGELOG.md").read_text(encoding="utf-8"), versao)
    except OSError:
        return ""


def decidir(ultima_mostrada: str, atual: str) -> str:
    """"primeira" (instalação nova: só registra), "mostrar" (mudou de versão) ou "nada"."""
    if not ultima_mostrada:
        return "primeira"
    return "nada" if ultima_mostrada == atual else "mostrar"
