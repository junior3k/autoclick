"""Validação do botoes.json: aponta erros, typos e PNGs sem regra (modo 'validar')."""
from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, cast

from .regras import ACOES_VALIDAS, AO_VER_VALIDOS, ESCOLHAS_VALIDAS
from .condicoes import AO_ESTOURAR_VALIDOS

CAMPOS_REGRA = (
    "acao", "vezes", "intervalo", "destino", "offset", "confirmar_cinza", "queda_saturacao",
    "tentativas", "espera_confirmacao", "auto_detect", "escolha", "grupo", "reiniciar_loop",
    "requer", "ignorar_se", "etapa", "ao_ver", "reconectar_com",
)
CHAVES_TOPO = ("_janela", "_fluxo", "_comentario")


@dataclass
class Problema:
    nivel: str  # "erro" | "aviso"
    msg: str

    def __str__(self) -> str:
        return ("✖ " if self.nivel == "erro" else "⚠ ") + self.msg


def _sugerir(valor: str, opcoes: list[str] | tuple[str, ...]) -> str:
    p = difflib.get_close_matches(valor, list(opcoes), n=1, cutoff=0.6)
    return f" Quis dizer '{p[0]}'?" if p else ""


def _par(v: Any) -> bool:
    return isinstance(v, list) and len(cast(list[Any], v)) == 2 and all(
        isinstance(x, (int, float)) and not isinstance(x, bool) for x in cast(list[Any], v))


def validar_config(config: str, pasta: str, janela_cli: Optional[str] = None) -> list[Problema]:
    out: list[Problema] = []
    p = Path(config)
    if not p.is_file():
        return [Problema("aviso", f"'{config}' não existe (sem regras: tudo será clicado).")]
    try:
        bruto: Any = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [Problema("erro", f"{config}: JSON inválido na linha {e.lineno}, coluna "
                         f"{e.colno}: {e.msg}")]
    if not isinstance(bruto, dict):
        return [Problema("erro", f"{config}: deve ser um objeto JSON {{...}}.")]
    dados = cast(dict[str, Any], bruto)

    pngs: set[str] = set()
    pd = Path(pasta)
    if pd.is_dir():
        pngs = {f.stem for f in pd.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg")}
    else:
        out.append(Problema("aviso", f"a pasta de imagens '{pasta}' não existe."))

    regras = {k: v for k, v in dados.items() if not k.startswith("_")}
    for k in dados:
        if k.startswith("_") and k not in CHAVES_TOPO and _sugerir(k, CHAVES_TOPO):
            out.append(Problema("aviso", f"chave '{k}' é tratada como comentário."
                                + _sugerir(k, CHAVES_TOPO)))
    nomes = set(regras)
    ancoras_ref: set[str] = set()
    janela = dados.get("_janela") or janela_cli

    # etapas declaradas em _fluxo
    etapas: set[str] = set()
    fluxo: Any = dados.get("_fluxo")
    if fluxo is not None:
        if not isinstance(fluxo, list):
            out.append(Problema("erro", '"_fluxo" deve ser uma lista de etapas.'))
        else:
            for i, e in enumerate(cast(list[Any], fluxo), 1):
                if not isinstance(e, dict):
                    out.append(Problema("erro", f'"_fluxo" etapa #{i} deve ser um objeto.'))
                    continue
                ed = cast(dict[str, Any], e)
                nome_e = ed.get("etapa")
                if not isinstance(nome_e, str) or not nome_e:
                    out.append(Problema("erro", f'"_fluxo" etapa #{i}: falta "etapa".'))
                    continue
                etapas.add(nome_e)
                q: Any = ed.get("quando")
                lq = [q] if isinstance(q, str) else cast(list[Any], q) if isinstance(q, list) else []
                if not lq:
                    out.append(Problema("erro", f'etapa "{nome_e}": falta "quando".'))
                for n in lq:
                    if str(n) not in nomes and str(n) not in pngs:
                        out.append(Problema("erro", f'etapa "{nome_e}": "{n}" não é um botão '
                                            "conhecido." + _sugerir(str(n), sorted(nomes | pngs))))
                ao = str(ed.get("ao_estourar", "avisar"))
                if ao not in AO_ESTOURAR_VALIDOS:
                    out.append(Problema("erro", f'etapa "{nome_e}": ao_estourar "{ao}" inválido.'
                                        + _sugerir(ao, AO_ESTOURAR_VALIDOS)))

    for nome, r in regras.items():
        if not isinstance(r, dict):
            out.append(Problema("erro", f"'{nome}': a regra deve ser um objeto."))
            continue
        d = cast(dict[str, Any], r)
        if pngs and nome not in pngs:
            out.append(Problema("erro", f"'{nome}': regra sem imagem '{nome}.png' em "
                                f"'{pasta}'." + _sugerir(nome, sorted(pngs))))
        for campo in d:
            if campo not in CAMPOS_REGRA:
                out.append(Problema("aviso", f"'{nome}': campo desconhecido '{campo}'."
                                    + _sugerir(campo, CAMPOS_REGRA)))
        acao = str(d.get("acao", "clicar")).lower()
        if acao not in ACOES_VALIDAS:
            out.append(Problema("erro", f"'{nome}': acao '{acao}' inválida (use "
                                f"{', '.join(ACOES_VALIDAS)})." + _sugerir(acao, ACOES_VALIDAS)))
        if "escolha" in d and d["escolha"] not in ESCOLHAS_VALIDAS:
            out.append(Problema("erro", f"'{nome}': escolha deve ser {', '.join(ESCOLHAS_VALIDAS)}."))
        if "ao_ver" in d and str(d["ao_ver"]) not in AO_VER_VALIDOS:
            out.append(Problema("erro", f"'{nome}': ao_ver deve ser {', '.join(AO_VER_VALIDOS)}."))
        rc = d.get("reconectar_com")
        if rc is not None and (not isinstance(rc, str) or rc not in dados):
            out.append(Problema("erro", f"'{nome}': reconectar_com '{rc}' não é uma regra/botão "
                                "existente." + (_sugerir(rc, list(regras)) if isinstance(rc, str) else "")))
        if str(d.get("ao_ver", "")) == "reconectar" and not rc:
            out.append(Problema("aviso", f"'{nome}': ao_ver 'reconectar' sem 'reconectar_com': só "
                                "reinicia a partida; nenhum botão será clicado para reconectar."))
        for campo, minimo in (("vezes", 0), ("tentativas", 1)):
            v = d.get(campo)
            if v is not None and (not isinstance(v, int) or isinstance(v, bool) or v < minimo):
                out.append(Problema("erro", f"'{nome}': '{campo}' deve ser inteiro >= {minimo}."))
        for campo in ("intervalo", "espera_confirmacao"):
            v = d.get(campo)
            if v is not None and (not isinstance(v, (int, float)) or v < 0):
                out.append(Problema("erro", f"'{nome}': '{campo}' deve ser um número >= 0."))
        qs = d.get("queda_saturacao")
        if qs is not None and not (isinstance(qs, (int, float)) and 0 < qs <= 1):
            out.append(Problema("erro", f"'{nome}': queda_saturacao deve estar entre 0 e 1."))
        if "offset" in d and not _par(d["offset"]):
            out.append(Problema("erro", f"'{nome}': offset deve ser [dx, dy]."))
        # destino
        dest: Any = d.get("destino")
        if acao == "arrastar" and dest is None:
            out.append(Problema("erro", f"'{nome}': 'arrastar' precisa de 'destino'."))
        if dest is not None:
            if isinstance(dest, list):
                if not _par(dest):
                    out.append(Problema("erro", f"'{nome}': destino [x, y] inválido."))
            elif isinstance(dest, dict):
                dd = cast(dict[str, Any], dest)
                if "janela" in dd:
                    ok = _par(dd["janela"]) and all(
                        0 <= x <= 1 for x in cast(list[float], dd["janela"]))
                    if not ok:
                        out.append(Problema("erro", f"'{nome}': destino.janela deve ser "
                                            "[fx, fy] entre 0 e 1."))
                    if not janela:
                        out.append(Problema("erro", f"'{nome}': destino relativo à janela exige "
                                            '"_janela" no json ou --janela.'))
                elif "ancora" in dd:
                    a = str(dd["ancora"])
                    ancoras_ref.add(a)
                    if pngs and a not in pngs:
                        out.append(Problema("erro", f"'{nome}': âncora '{a}' sem PNG em '{pasta}'."
                                            + _sugerir(a, sorted(pngs))))
                    if "offset" in dd and not _par(dd["offset"]):
                        out.append(Problema("erro", f"'{nome}': destino.offset deve ser [dx, dy]."))
                    if a in regras and isinstance(regras[a], dict) and \
                            str(cast(dict[str, Any], regras[a]).get("acao", "")) == "clicar":
                        out.append(Problema("aviso", f"'{nome}': a âncora '{a}' está como "
                                            "'clicar'; use \"acao\": \"ancora\"."))
                else:
                    out.append(Problema("erro", f"'{nome}': destino deve ter 'janela' ou 'ancora'."))
            else:
                out.append(Problema("erro", f"'{nome}': destino inválido."))
        # condições
        for campo in ("requer", "ignorar_se"):
            v: Any = d.get(campo)
            lista = [v] if isinstance(v, str) else cast(list[Any], v) if isinstance(v, list) else []
            for n in lista:
                if str(n) == nome:
                    out.append(Problema("erro", f"'{nome}': '{campo}' aponta para si mesmo."))
                elif str(n) not in nomes and str(n) not in pngs:
                    out.append(Problema("erro", f"'{nome}': {campo} '{n}' não existe."
                                        + _sugerir(str(n), sorted(nomes | pngs))))
        et = d.get("etapa")
        if et is not None and str(et) not in etapas:
            out.append(Problema("erro", f"'{nome}': etapa '{et}' não está em \"_fluxo\"."
                                + _sugerir(str(et), sorted(etapas))))

    for png in sorted(pngs - nomes - ancoras_ref):
        out.append(Problema("aviso", f"imagem '{png}' sem regra no json (será clicada sempre; "
                            'use "acao": "ancora" se for só referência).'))
    return out


def relatorio(problemas: list[Problema], config: str) -> str:
    if not problemas:
        return f"✔ {config}: nenhum problema encontrado."
    erros = sum(1 for p in problemas if p.nivel == "erro")
    linhas = [f"{config}: {erros} erro(s), {len(problemas) - erros} aviso(s)"]
    linhas += [f"  {p}" for p in problemas]
    return "\n".join(linhas)
