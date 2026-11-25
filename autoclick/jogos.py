# pyright: basic
"""Jogos do Roblox: a plataforma tem milhares, cada um com botões e regras próprios.

Duas camadas:
  * "Roblox (geral)": o que vale para qualquer jogo (pasta botoes/ e botoes.json da raiz:
    desconectado, reconectar, erro de conexão...).
  * Um jogo: jogos/<slug>/ com jogo.json, botoes/ (PNGs só desse jogo), botoes.json (regras
    só desse jogo) e gravacao.json. O jogo vence o geral quando o nome é o mesmo.

O processo filho recebe AUTOCLICK_JOGO=<slug> e, com um jogo escolhido, AUTOCLICK_GERAL_PASTA/
AUTOCLICK_GERAL_CONFIG (o geral); deteccao.py e regras.py somam as duas camadas.
Só biblioteca padrão (a janela usa este módulo sem OpenCV).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, cast

RAIZ = "jogos"
GERAL = "geral"
NOME_GERAL = "Roblox (geral)"
ARQ_JOGO = "jogo.json"

# opções que cada jogo pode guardar (campos da janela de configurações)
OPCOES_DO_JOGO = ("modo_auto", "intervalo", "cooldown", "variacao", "confianca", "escala",
                  "repeticao", "voltas", "pausa_loop", "velocidade", "som_volta", "som_tipo",
                  "som_volume", "inatividade", "ao_travar", "tela_parada")


@dataclass
class Jogo:
    slug: str
    nome: str
    ids: list[str] = field(default_factory=lambda: [])          # place/universe ids do Roblox
    assinatura: list[str] = field(default_factory=lambda: [])   # PNGs que só existem nesse jogo
    opcoes: dict[str, Any] = field(default_factory=lambda: {})

    @property
    def geral(self) -> bool:
        return self.slug == GERAL


def slugificar(nome: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", _sem_acento(nome.lower())).strip("-")
    return (s or "jogo")[:40]


def _sem_acento(t: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def pasta_do(slug: str, raiz: str = RAIZ) -> Path:
    return Path(raiz) / slug


def arquivos_do(slug: str, raiz: str = RAIZ) -> dict[str, str]:
    """Caminhos que a janela usa quando este jogo está escolhido."""
    if slug in ("", GERAL):
        return {"gravacao": "gravacao.json", "rotina": "rotina.json"}
    p = pasta_do(slug, raiz)
    return {"gravacao": str(p / "gravacao.json"), "pasta": str(p / "botoes"),
            "config": str(p / "botoes.json"), "rotina": str(p / "rotina.json")}


def _para_jogo(slug: str, d: dict[str, Any]) -> Jogo:
    def lista(k: str) -> list[str]:
        v = d.get(k, [])
        return [str(x).strip() for x in cast(list[Any], v) if str(x).strip()] if isinstance(v, list) else []
    op = d.get("opcoes", {})
    return Jogo(slug, str(d.get("nome") or (NOME_GERAL if slug == GERAL else slug)),
                lista("ids"), lista("assinatura"),
                dict(cast(dict[str, Any], op)) if isinstance(op, dict) else {})


def ler(slug: str, raiz: str = RAIZ) -> Optional[Jogo]:
    arq = pasta_do(slug, raiz) / ARQ_JOGO
    if not arq.is_file():
        return Jogo(GERAL, NOME_GERAL) if slug == GERAL else None
    try:
        d: Any = json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return _para_jogo(slug, cast(dict[str, Any], d)) if isinstance(d, dict) else None


def salvar(j: Jogo, raiz: str = RAIZ) -> Path:
    p = pasta_do(j.slug, raiz)
    p.mkdir(parents=True, exist_ok=True)
    if not j.geral:
        (p / "botoes").mkdir(exist_ok=True)
    arq = p / ARQ_JOGO
    arq.write_text(json.dumps({"nome": j.nome, "ids": j.ids, "assinatura": j.assinatura,
                               "opcoes": j.opcoes}, ensure_ascii=False, indent=2), encoding="utf-8")
    return arq


def listar(raiz: str = RAIZ) -> list[Jogo]:
    """O geral primeiro, depois os jogos em ordem alfabética."""
    r = Path(raiz)
    out: list[Jogo] = []
    if r.is_dir():
        for d in sorted(r.iterdir()):
            if d.is_dir() and d.name != GERAL:
                j = ler(d.name, raiz)
                if j:
                    out.append(j)
    out.sort(key=lambda j: j.nome.lower())
    return [ler(GERAL, raiz) or Jogo(GERAL, NOME_GERAL), *out]


def criar(nome: str, raiz: str = RAIZ, ids: Optional[list[str]] = None) -> Jogo:
    """Cria jogos/<slug>/ (sem apagar nada se já existir)."""
    nome = nome.strip() or "Novo jogo"
    base = slugificar(nome)
    slug, n = base, 2
    while (pasta_do(slug, raiz) / ARQ_JOGO).exists() or slug == GERAL:
        slug, n = f"{base}-{n}", n + 1
    j = Jogo(slug, nome, list(ids or []))
    salvar(j, raiz)
    return j


def apagar(slug: str, raiz: str = RAIZ) -> bool:
    if slug in ("", GERAL):
        return False
    p = pasta_do(slug, raiz)
    if p.is_dir():
        shutil.rmtree(p, ignore_errors=True)
        return True
    return False


def nome_de(slug: str, raiz: str = RAIZ) -> str:
    j = ler(slug or GERAL, raiz)
    return j.nome if j else (slug or NOME_GERAL)


# --------------------------------------------------------------------------- #
# Camada (usada pelo motor)
# --------------------------------------------------------------------------- #
def camada_geral() -> tuple[Optional[str], Optional[str]]:
    """(pasta, botoes.json) do "Roblox (geral)", quando um jogo está escolhido.

    A janela passa o jogo em --pasta/--config e o geral por estas variáveis; os dois são
    somados e o jogo vence o geral quando o nome é o mesmo."""
    return (os.environ.get("AUTOCLICK_GERAL_PASTA", "").strip() or None,
            os.environ.get("AUTOCLICK_GERAL_CONFIG", "").strip() or None)


def slug_ativo() -> str:
    return os.environ.get("AUTOCLICK_JOGO", "").strip() or GERAL


# --------------------------------------------------------------------------- #
# Migração dos perfis antigos (perfis/*.json -> jogos/<nome>/perfil.json)
# --------------------------------------------------------------------------- #
_CAMPOS_PERFIL = {"modo": "modo_auto", "intervalo": "intervalo", "cooldown": "cooldown",
                  "variacao": "variacao", "confianca": "confianca", "inatividade": "inatividade",
                  "ao_travar": "ao_travar"}


def migrar_perfis(perfis: str = "perfis", raiz: str = RAIZ) -> list[str]:
    """Move cada perfis/X.json para jogos/X/perfil.json (o "roblox" vira o Roblox (geral)).

    Nada se perde: as opções viram as opções do jogo e o arquivo original continua
    legível pelo terminal (--perfil X procura também em jogos/X/perfil.json).
    """
    movidos: list[str] = []
    pp = Path(perfis)
    if not pp.is_dir():
        return movidos
    for arq in sorted(pp.glob("*.json")):
        try:
            d: Any = json.loads(arq.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict):
            continue
        dd = cast(dict[str, Any], d)
        slug = GERAL if arq.stem.lower() == "roblox" else slugificar(arq.stem)
        j = ler(slug, raiz)
        if j is None:
            j = Jogo(slug, NOME_GERAL if slug == GERAL else arq.stem)
        for k, campo in _CAMPOS_PERFIL.items():
            if k in dd and campo not in j.opcoes:
                j.opcoes[campo] = dd[k]
        salvar(j, raiz)
        destino = pasta_do(slug, raiz) / "perfil.json"
        if not destino.exists():
            try:
                shutil.move(str(arq), str(destino))
                movidos.append(arq.stem)
            except OSError:
                pass
    return movidos


def perfil_em_jogos(nome: str, raiz: str = RAIZ) -> Optional[Path]:
    for slug in (GERAL if nome.lower() == "roblox" else slugificar(nome), nome):
        p = pasta_do(slug, raiz) / "perfil.json"
        if p.is_file():
            return p
    return None


# --------------------------------------------------------------------------- #
# Detecção do jogo pelos logs do Roblox (experimental, melhor esforço)
# --------------------------------------------------------------------------- #
PADROES_ID = (
    re.compile(r"place\s*_?id\s*[:=]\s*(\d{4,})", re.I),
    re.compile(r"universe\s*_?id\s*[:=]\s*(\d{4,})", re.I),
    re.compile(r"\bplace\s+(\d{4,})", re.I),
    re.compile(r"/games/(\d{4,})", re.I),
)
PALAVRAS_PISTA = re.compile(r"place\s*_?id|universe\s*_?id|\bplace\s+\d|/games/\d|joining game|"
                            r"game_join|teleport|disconnect", re.I)


def pasta_logs_roblox() -> Optional[Path]:
    v = os.environ.get("AUTOCLICK_ROBLOX_LOGS", "").strip()
    if v:
        p = Path(v)
    else:
        base = os.environ.get("LOCALAPPDATA", "")
        if not base:
            return None
        p = Path(base) / "Roblox" / "logs"
    return p if p.is_dir() else None


def _log_mais_novo(pasta: Path, ate_s: float = 6 * 3600) -> Optional[Path]:
    achados: list[tuple[float, Path]] = []
    for f in pasta.glob("*.log"):
        try:
            achados.append((f.stat().st_mtime, f))
        except OSError:
            pass
    if not achados:
        return None
    m, f = max(achados)
    return f if time.time() - m <= ate_s else None


def ler_cauda(arq: Path, limite: int = 400_000) -> str:
    try:
        with open(arq, "rb") as f:
            f.seek(0, os.SEEK_END)
            tam = f.tell()
            f.seek(max(0, tam - limite))
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def ids_no_texto(texto: str) -> list[str]:
    """Ids de lugar/universo na ordem em que aparecem (o último é o jogo atual)."""
    achados: list[tuple[int, str]] = []
    for rx in PADROES_ID:
        for m in rx.finditer(texto):
            achados.append((m.start(), m.group(1)))
    achados.sort()
    return [i for _, i in achados]


_RX_PLACE = (re.compile(r"place\s*_?id\s*[:=]\s*\"?(\d{4,})", re.I), re.compile(r"\bplace\s+(\d{4,})", re.I),
             re.compile(r"/games/(\d{4,})", re.I))
_RX_UNIVERSE = (re.compile(r"universe\s*_?id\s*[:=]\s*\"?(\d{4,})", re.I),)


def _ultimo(texto: str, padroes: tuple[re.Pattern[str], ...]) -> str:
    pos, achado = -1, ""
    for rx in padroes:
        for m in rx.finditer(texto):
            if m.start() > pos:
                pos, achado = m.start(), m.group(1)
    return achado


def ids_recentes(pasta_logs: Optional[Path] = None) -> list[str]:
    """Os ids do jogo atual nos logs: [place id, universe id] (os que existirem)."""
    pasta = pasta_logs or pasta_logs_roblox()
    arq = _log_mais_novo(pasta) if pasta else None
    if arq is None:
        return []
    t = ler_cauda(arq)
    return [i for i in dict.fromkeys((_ultimo(t, _RX_PLACE), _ultimo(t, _RX_UNIVERSE))) if i]


# API pública do Roblox (sem login), só para sugerir o nome do jogo
API_UNIVERSO = "https://apis.roblox.com/universes/v1/places/{}/universe"
API_JOGOS = "https://games.roblox.com/v1/games?universeIds={}"


def nome_do_jogo(ids: list[str], timeout: float = 6.0) -> Optional[str]:
    """Pergunta ao Roblox o nome do jogo a partir dos ids (place e/ou universe). None se falhar."""
    import urllib.request

    def pegar(url: str) -> Any:
        req = urllib.request.Request(url, headers={"User-Agent": "autoclick"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read(200_000).decode("utf-8", errors="replace"))

    try:
        candidatos: list[str] = []
        for i in ids:
            try:
                u = pegar(API_UNIVERSO.format(i)).get("universeId")
                if u:
                    candidatos.append(str(u))
            except Exception:
                candidatos.append(i)  # talvez já seja um universe id
        for u in dict.fromkeys(candidatos):
            try:
                dados = pegar(API_JOGOS.format(u)).get("data") or []
                if dados and str(dados[0].get("name", "")).strip():
                    return str(dados[0]["name"]).strip()
            except Exception:
                continue
    except Exception:
        pass
    return None


def detectar_por_logs(jogos: list[Jogo], pasta_logs: Optional[Path] = None) -> tuple[Optional[str], str]:
    """(slug do jogo reconhecido ou None, último id visto nos logs ou "")."""
    pasta = pasta_logs or pasta_logs_roblox()
    if pasta is None:
        return None, ""
    arq = _log_mais_novo(pasta)
    if arq is None:
        return None, ""
    ids = ids_no_texto(ler_cauda(arq))
    if not ids:
        return None, ""
    for i in reversed(ids):
        for j in jogos:
            if i in j.ids:
                return j.slug, i
    return None, ids[-1]


def coletar_pistas(pasta_logs: Optional[Path] = None, maxlinhas: int = 40) -> str:
    """Só as linhas úteis dos logs (nada de milhares de linhas): para você me mandar."""
    pasta = pasta_logs or pasta_logs_roblox()
    if pasta is None:
        return "Pasta de logs do Roblox não encontrada (procurei em %LOCALAPPDATA%\\Roblox\\logs)."
    arq = _log_mais_novo(pasta, 7 * 24 * 3600)
    if arq is None:
        return "Nenhum log recente do Roblox."
    vistas: list[str] = []
    for ln in ler_cauda(arq).splitlines():
        if PALAVRAS_PISTA.search(ln):
            ln = re.sub(r"^\S+\s+", "", ln.strip())[:200]  # tira o carimbo de hora
            ln = re.sub(r"(?i)(token|cookie|ticket|auth)\S*[:=]\s*\S+", r"\1=***", ln)
            if ln not in vistas:
                vistas.append(ln)
    ids = ids_no_texto("\n".join(vistas))
    cab = [f"Log: {arq.name}", f"Ids encontrados: {', '.join(dict.fromkeys(ids)) or 'nenhum'}",
           f"Linhas úteis (últimas {maxlinhas}):"]
    return "\n".join(cab + vistas[-maxlinhas:])


# --------------------------------------------------------------------------- #
# Estatísticas por jogo (a partir do histórico de sessões)
# --------------------------------------------------------------------------- #
def estatisticas(sessoes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Uma linha por jogo: sessões, tempo, voltas, voltas/hora, tempo médio de volta, botões."""
    por: dict[str, dict[str, Any]] = {}
    for s in sessoes:
        slug = str(s.get("jogo") or GERAL)
        r = por.setdefault(slug, {"jogo": slug, "sessoes": 0, "segundos": 0.0, "voltas": 0,
                                  "acoes": 0, "botoes": {}})
        r["sessoes"] += 1
        r["segundos"] += float(s.get("duracao_seg", 0) or 0) - float(s.get("pausado_seg", 0) or 0)
        r["voltas"] += int(s.get("partidas", 0) or 0)
        r["acoes"] += int(s.get("total_acoes", 0) or 0)
        c = s.get("cliques")
        if isinstance(c, dict):
            for k, v in cast(dict[str, Any], c).items():
                r["botoes"][k] = r["botoes"].get(k, 0) + int(v)
    out: list[dict[str, Any]] = []
    for r in por.values():
        seg = max(0.0, r["segundos"])
        r["segundos"] = seg
        r["voltas_hora"] = round(r["voltas"] / (seg / 3600.0), 1) if seg > 0 and r["voltas"] else 0.0
        r["seg_por_volta"] = round(seg / r["voltas"], 1) if r["voltas"] else 0.0
        out.append(r)
    out.sort(key=lambda r: -r["segundos"])
    return out


def csv_estatisticas(sessoes: list[dict[str, Any]], nomes: Optional[dict[str, str]] = None) -> str:
    nomes = nomes or {}
    linhas = ["jogo;sessoes;tempo_seg;voltas;voltas_por_hora;seg_por_volta;acoes"]
    for r in estatisticas(sessoes):
        linhas.append(";".join(str(x) for x in (
            nomes.get(r["jogo"], r["jogo"]), r["sessoes"], round(r["segundos"]), r["voltas"],
            str(r["voltas_hora"]).replace(".", ","), str(r["seg_por_volta"]).replace(".", ","),
            r["acoes"])))
    return "\n".join(linhas) + "\n"
