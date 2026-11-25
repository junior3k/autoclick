"""Perfis por jogo: um arquivo JSON com as opções que você repetiria na linha de comando.

Exemplo (perfis/roblox.json):
    {"modo": "imagem", "janela": "Roblox", "pasta": "botoes", "config": "botoes.json",
     "intervalo": 1.0, "variacao": 0.15, "log": "log.csv", "relatorio": "relatorio.md"}

Valem as mesmas opções do terminal (com ou sem o "--", "-" ou "_"). O que você digita
na linha de comando sempre vence o perfil; o perfil vence os padrões.
"""
from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Optional, cast


def localizar_perfil(nome: str, arquivo: Optional[str] = None) -> Path:
    if arquivo:
        p = Path(arquivo)
        if not p.is_file():
            sys.exit(f"Perfil '{arquivo}' não encontrado.")
        return p
    candidatos = [Path(nome), Path(f"{nome}.json"), Path("perfis") / f"{nome}.json"]
    for c in candidatos:
        if c.is_file():
            return c
    from .jogos import perfil_em_jogos
    mov = perfil_em_jogos(nome)
    if mov is not None:
        return mov
    sys.exit(f"Perfil '{nome}' não encontrado (procurei em: "
             + ", ".join(str(c) for c in candidatos) + ").")


def normalizar_chave(chave: str) -> str:
    return chave.strip().lstrip("-").replace("-", "_").lower()


def carregar_perfil(caminho: Path, validos: Iterable[str]) -> dict[str, Any]:
    """Lê o perfil e devolve {dest_do_argparse: valor}, recusando chaves desconhecidas."""
    try:
        bruto: Any = json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"{caminho}: JSON inválido (linha {e.lineno}: {e.msg}).")
    if not isinstance(bruto, dict):
        sys.exit(f"{caminho}: o perfil deve ser um objeto JSON.")
    validos_l = sorted(set(validos))
    out: dict[str, Any] = {}
    erros: list[str] = []
    for k, v in cast(dict[str, Any], bruto).items():
        if k.startswith("_"):
            continue
        dest = normalizar_chave(k)
        if dest not in validos_l:
            sug = difflib.get_close_matches(dest, validos_l, n=1, cutoff=0.6)
            erros.append(f"opção desconhecida '{k}'" + (f" (quis dizer '{sug[0]}'?)" if sug else ""))
            continue
        out[dest] = v
    if erros:
        sys.exit(f"{caminho}: " + "; ".join(erros) + ".")
    return out
