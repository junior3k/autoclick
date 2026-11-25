"""Conversão entre uma regra do botoes.json e os campos de texto do formulário (sem Tk)."""
from __future__ import annotations

from typing import Any, Optional, cast

ACOES = ("clicar", "arrastar", "inicio", "ancora", "marcador", "erro")
AUTO_OPCOES = ("padrão", "sim", "não")
ESCOLHAS = ("", "primeiro", "ultimo", "aleatorio")
DESTINOS = ("nenhum", "fixo", "janela", "ancora")
AO_VER = ("avisar", "parar", "reconectar")

DESCRICAO_ACAO = {
    "clicar": "Clica no botão quando ele aparece.",
    "arrastar": "Segura o botão e solta no destino (ex.: colocar uma torre).",
    "inicio": "Marca o começo de uma partida: zera os contadores. Nunca é clicado.",
    "ancora": "Imagem de referência do mapa (acompanha a câmera). Nunca é clicada.",
    "marcador": "Só serve para as condições “requer/ignorar_se/etapa”. Nunca é clicado.",
    "erro": "Tela de erro ou desconexão: avisa, para o programa ou tenta reconectar.",
}

GERENCIADAS = ("acao", "auto_detect", "vezes", "intervalo", "offset", "reiniciar_loop", "escolha",
               "grupo", "requer", "ignorar_se", "etapa", "confirmar_cinza", "queda_saturacao",
               "tentativas", "espera_confirmacao", "ao_ver", "reconectar_com", "destino")


def _lista(v: Any) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return ", ".join(str(x) for x in cast(list[Any], v))
    return ""


def regra_para_campos(r: dict[str, Any]) -> dict[str, str]:
    acao = str(r.get("acao", "clicar")).lower()
    auto = r.get("auto_detect")
    c: dict[str, str] = {
        "acao": acao,
        "auto_detect": "padrão" if auto is None else ("sim" if auto else "não"),
        "vezes": str(r.get("vezes", 1 if acao == "arrastar" else 0)),
        "intervalo": "" if r.get("intervalo") is None else f"{float(r['intervalo']):g}",
        "off_x": "0", "off_y": "0",
        "reiniciar_loop": "1" if r.get("reiniciar_loop") else "0",
        "escolha": str(r.get("escolha", "") or ""),
        "grupo": str(r.get("grupo", "") or ""),
        "requer": _lista(r.get("requer")),
        "ignorar_se": _lista(r.get("ignorar_se")),
        "etapa": str(r.get("etapa", "") or ""),
        "confirmar_cinza": "1" if r.get("confirmar_cinza", acao == "arrastar") else "0",
        "queda": f"{float(r.get('queda_saturacao', 0.5)):g}",
        "tentativas": str(r.get("tentativas", 3)),
        "espera_conf": f"{float(r.get('espera_confirmacao', 0.7)):g}",
        "ao_ver": str(r.get("ao_ver", "avisar")),
        "reconectar_com": str(r.get("reconectar_com", "") or ""),
        "dest_tipo": "nenhum", "dest_x": "", "dest_y": "", "dest_fx": "", "dest_fy": "",
        "dest_ancora": "", "dest_dx": "0", "dest_dy": "0",
    }
    off = r.get("offset")
    if isinstance(off, list) and len(cast(list[Any], off)) == 2:
        c["off_x"], c["off_y"] = str(cast(list[Any], off)[0]), str(cast(list[Any], off)[1])
    d = r.get("destino")
    if isinstance(d, list) and len(cast(list[Any], d)) == 2:
        c["dest_tipo"] = "fixo"
        c["dest_x"], c["dest_y"] = str(cast(list[Any], d)[0]), str(cast(list[Any], d)[1])
    elif isinstance(d, dict):
        dd = cast(dict[str, Any], d)
        if "janela" in dd:
            jl = cast(list[Any], dd["janela"])
            c["dest_tipo"] = "janela"
            c["dest_fx"], c["dest_fy"] = f"{float(jl[0]):g}", f"{float(jl[1]):g}"
        elif "ancora" in dd:
            c["dest_tipo"] = "ancora"
            c["dest_ancora"] = str(dd["ancora"])
            o = dd.get("offset", [0, 0])
            c["dest_dx"], c["dest_dy"] = str(cast(list[Any], o)[0]), str(cast(list[Any], o)[1])
    return c


def _int(txt: str, nome: str, erros: list[str], minimo: Optional[int] = None) -> int:
    try:
        v = int(float(txt.strip().replace(",", ".") or "0"))
    except ValueError:
        erros.append(f"“{nome}” deve ser um número inteiro.")
        return 0
    if minimo is not None and v < minimo:
        erros.append(f"“{nome}” deve ser pelo menos {minimo}.")
    return v


def _num(txt: str, nome: str, erros: list[str]) -> float:
    try:
        return float(txt.strip().replace(",", ".") or "0")
    except ValueError:
        erros.append(f"“{nome}” deve ser um número.")
        return 0.0


def _nomes(txt: str) -> list[str]:
    return [p.strip() for p in txt.replace(";", ",").split(",") if p.strip()]


def campos_para_regra(original: dict[str, Any], c: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    """Aplica os campos sobre a regra original (preserva chaves que o formulário não conhece)."""
    erros: list[str] = []
    r = {k: v for k, v in original.items() if k not in GERENCIADAS}
    acao = c.get("acao", "clicar")
    r["acao"] = acao
    auto = c.get("auto_detect", "padrão")
    if auto == "sim":
        r["auto_detect"] = True
    elif auto == "não":
        r["auto_detect"] = False
    vezes = _int(c.get("vezes", "0"), "vezes", erros, 0)
    if (acao == "arrastar" and vezes != 1) or (acao != "arrastar" and vezes != 0):
        r["vezes"] = vezes
    if c.get("intervalo", "").strip():
        iv = _num(c["intervalo"], "intervalo", erros)
        if iv < 0:
            erros.append("“intervalo” não pode ser negativo.")
        r["intervalo"] = iv
    ox = _int(c.get("off_x", "0"), "deslocamento X", erros)
    oy = _int(c.get("off_y", "0"), "deslocamento Y", erros)
    if ox or oy:
        r["offset"] = [ox, oy]
    if c.get("reiniciar_loop") == "1":
        r["reiniciar_loop"] = True
    if c.get("escolha"):
        r["escolha"] = c["escolha"]
        if c.get("grupo", "").strip():
            r["grupo"] = c["grupo"].strip()
    for chave in ("requer", "ignorar_se"):
        nomes = _nomes(c.get(chave, ""))
        if nomes:
            r[chave] = nomes
    if c.get("etapa", "").strip():
        r["etapa"] = c["etapa"].strip()
    if acao == "arrastar":
        if c.get("confirmar_cinza") != "1":
            r["confirmar_cinza"] = False
        q = _num(c.get("queda", "0.5"), "queda de saturação", erros)
        if not (0 < q <= 1):
            erros.append("“queda de saturação” deve estar entre 0 e 1.")
        elif abs(q - 0.5) > 1e-9:
            r["queda_saturacao"] = q
        t = _int(c.get("tentativas", "3"), "tentativas", erros, 1)
        if t != 3:
            r["tentativas"] = t
        e = _num(c.get("espera_conf", "0.7"), "espera de confirmação", erros)
        if abs(e - 0.7) > 1e-9:
            r["espera_confirmacao"] = e
        tipo = c.get("dest_tipo", "nenhum")
        if tipo == "fixo":
            r["destino"] = [_int(c.get("dest_x", ""), "destino X", erros),
                            _int(c.get("dest_y", ""), "destino Y", erros)]
        elif tipo == "janela":
            fx, fy = _num(c.get("dest_fx", ""), "destino fração X", erros), \
                _num(c.get("dest_fy", ""), "destino fração Y", erros)
            if not (0 <= fx <= 1 and 0 <= fy <= 1):
                erros.append("A fração do destino deve estar entre 0 e 1 (0.5 = meio da janela).")
            r["destino"] = {"janela": [fx, fy]}
        elif tipo == "ancora":
            if not c.get("dest_ancora", "").strip():
                erros.append("Escolha a imagem âncora do destino.")
            r["destino"] = {"ancora": c.get("dest_ancora", "").strip(),
                            "offset": [_int(c.get("dest_dx", "0"), "deslocamento X da âncora", erros),
                                       _int(c.get("dest_dy", "0"), "deslocamento Y da âncora", erros)]}
        else:
            erros.append("“arrastar” precisa de um destino (fixo, fração da janela ou âncora).")
    elif acao == "clicar" and c.get("confirmar_cinza") == "1":
        r["confirmar_cinza"] = True
    if acao == "erro" and c.get("ao_ver", "avisar") != "avisar":
        r["ao_ver"] = c["ao_ver"]
    if acao == "erro" and c.get("ao_ver") == "reconectar" and c.get("reconectar_com", "").strip():
        r["reconectar_com"] = c["reconectar_com"].strip()
    return r, erros


def etapa_para_campos(e: dict[str, Any]) -> dict[str, str]:
    return {"etapa": str(e.get("etapa", "")), "quando": _lista(e.get("quando")),
            "timeout": "" if not e.get("timeout") else f"{float(e['timeout']):g}",
            "ao_estourar": str(e.get("ao_estourar", "avisar"))}


def campos_para_etapa(c: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    erros: list[str] = []
    nome = c.get("etapa", "").strip()
    quando = _nomes(c.get("quando", ""))
    if not nome:
        erros.append("Dê um nome à etapa.")
    if not quando:
        erros.append("Informe ao menos um botão em “aparece quando”.")
    e: dict[str, Any] = {"etapa": nome, "quando": quando}
    if c.get("timeout", "").strip():
        t = _num(c["timeout"], "tempo limite", erros)
        if t < 0:
            erros.append("O tempo limite não pode ser negativo.")
        elif t:
            e["timeout"] = t
    if c.get("ao_estourar", "avisar") != "avisar":
        e["ao_estourar"] = c["ao_estourar"]
    return e, erros
