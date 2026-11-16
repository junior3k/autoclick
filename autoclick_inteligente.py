#!/usr/bin/env python3
"""
Autoclick inteligente: olha a tela, encontra botões e clica neles (Windows).

Instalação (uv):
    uv add mss opencv-python-headless numpy
    uv add pytesseract      # só se for usar os modos "texto" e "auto" (OCR)
    # + Tesseract OCR instalado no sistema (só para texto/auto):
    #   https://github.com/UB-Mannheim/tesseract/wiki  (marque o idioma Portuguese)

Modos:
    texto      lê a tela com OCR e clica em palavras como "Aceitar", "Continuar"...
    imagem     procura imagens de botões (PNGs recortados por você) na tela
    auto       detecta retângulos com formato de botão, lê o rótulo e clica
    gravar     grava SEUS cliques, arrastos e teclas (coordenadas e tempo)
    reproduzir refaz uma gravação (opcionalmente em loop)

Exemplos:
    python autoclick_inteligente.py imagem --pasta botoes --janela Roblox --preview
    python autoclick_inteligente.py imagem --pasta botoes --janela Roblox --log acoes.csv
    python autoclick_inteligente.py texto --palavras "aceitar" "continuar" --preview
    python autoclick_inteligente.py gravar --janela Roblox --ancora mapa_ref --gerar-regras
    python autoclick_inteligente.py reproduzir --arquivo gravacao.json --loop
    python autoclick_inteligente.py reproduzir --arquivo gravacao.json --loop --pasta botoes \
        --janela Roblox     # com "auto_detect": true no json, clica em maximo/novamente

Tamanho da janela (modo imagem):
    Tire os PNGs com a janela no MAIOR tamanho possível. Se depois você a deixar menor,
    o programa descobre sozinho a escala (todos os botões encolhem juntos) e a reaprende
    se a janela for redimensionada. Com --janela ele também acompanha a janela quando ela
    é movida. Pode ser forçada com --escala 0.6, ou desligada com --escala 1.
    Obs.: com recortes reduzidos o score cai um pouco; se faltar reconhecimento, use
    --confianca 0.8.

Regras por botão (botoes.json, ao lado do script; a chave é o nome do PNG sem extensão):
    {
      "_janela":        "Roblox",
      "maximo":         { "acao": "clicar" },
      "proxima":        { "acao": "clicar", "intervalo": 2 },
      "torre":          { "acao": "arrastar", "vezes": 1,
                          "destino": { "ancora": "mapa_ref", "offset": [320, -140] } },
      "mapa_ref":       { "acao": "ancora" },
      "inicio_partida": { "acao": "inicio" }
    }
    - clicar    clica sempre que vê o botão (padrão para PNGs sem regra).
    - arrastar  aperta no botão, leva até "destino", solta, e confirma que o botão ficou
                cinza. "vezes" = quantas vezes POR PARTIDA (padrão 1). Se não ficar cinza,
                tenta de novo ("tentativas", padrão 3).
    - inicio    PNG de algo que só aparece no começo da partida: ao aparecer, zera os
                contadores de "vezes" (libera os botões de "uma vez por partida").
    - ancora    PNG de uma referência do mapa (nunca é clicado); serve de base ao destino.
    Formas do "destino" (da mais frágil para a mais robusta):
        [980, 540]                                   coordenada FIXA de tela (quebra se a
                                                     janela mexer ou a câmera andar)
        {"janela": [0.62, 0.55]}                     fração da janela do jogo (acompanha
                                                     mover/redimensionar; exige --janela)
        {"ancora": "mapa_ref", "offset": [dx, dy]}   relativo a uma imagem do mapa (acompanha
                                                     também a câmera; dx/dy em pixels do PNG
                                                     de referência, a partir do centro dele)
    A âncora só funciona se a câmera apenas deslizar: girar ou dar zoom no mapa muda
    as distâncias e exige regravar o ponto.
    "auto_detect": true  = o botão é clicado assim que for detectado, em qualquer modo, inclusive
                durante a REPRODUÇÃO de uma gravação: se ele aparecer, a reprodução pausa,
                clica nele enquanto estiver à vista e só então continua (só para "clicar").
                false = nunca é clicado sozinho. Sem a chave: os modos de varredura clicam
                (como sempre) e a reprodução ignora o botão.
    "escolha": "primeiro" | "ultimo" | "aleatorio"  = vários botões parecidos aparecem juntos
                (ex.: 3 cartas de "escolha uma") e basta clicar em UM, uma vez por aparição.
                Com um único PNG que case em todos (uma parte igual entre eles, como a ponta
                do botão amarelo), ele clica em um só. "grupo": "nome" junta PNGs diferentes
                na mesma escolha. O grupo só destrava depois que as cartas somem da tela.
    "reiniciar_loop": true  = clicar neste botão (ex.: Jogar Novamente) reinicia o ciclo: zera
                a partida e, na reprodução com --loop, a gravação volta ao início SEM clicar de
                novo neste botão (o clique gravado nele é pulado uma vez).
    Opcionais: "offset": [dx, dy], "intervalo": segundos, "confirmar_cinza": true/false,
               "queda_saturacao": 0.5, "tentativas": 3, "espera_confirmacao": 0.7.

Gravação e reprodução:
    python autoclick_inteligente.py gravar --arquivo gravacao.json --janela Roblox --gerar-regras
        Grava seus cliques, arrastos e teclas até apertar F9. Cada ponto é salvo também como
        fração da janela. Com --gerar-regras, o ponto onde você soltou vira o "destino" no
        botoes.json (por âncora se usar --ancora NOME, senão por fração da janela).
        ATENÇÃO: tudo o que você digitar durante a gravação é salvo (não digite senhas);
        --sem-teclado desliga a gravação de teclas.
    python autoclick_inteligente.py reproduzir --arquivo gravacao.json --velocidade 1 --loop
        Refaz a gravação. --loop repete até F9 (--loop 5 = 5 vezes). Antes de cada ação
        confere se a janela do jogo está ativa: tenta trazê-la para frente e, se não der,
        pausa até ela voltar. F9 ou mouse no canto superior esquerdo para parar.
    Em qualquer modo de varredura, --log acoes.csv registra cada ação automática e também
    as teclas que você apertar.

Segurança:
    - Jogue o mouse para o canto superior esquerdo da tela para ABORTAR (failsafe).
    - Ctrl+C no terminal também para.
    - Use --preview primeiro: só salva preview.png com o que foi detectado, sem clicar.
    - Use apenas em apps/sites onde automação é permitida (veja os termos de uso).
"""
from __future__ import annotations

import argparse
import csv
import ctypes
import json
import math
import os
import random
import shutil
import sys
import threading
import unicodedata
from difflib import SequenceMatcher
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from functools import partial
from typing import Any, Callable, Optional, cast

import cv2
import mss as _mss  # type: ignore
import numpy as np
import numpy.typing as npt

# mss e pytesseract não têm stubs de tipo; tratamos como Any de forma explícita.
mss_lib: Any = _mss

Img = npt.NDArray[Any]
Regiao = tuple[int, int, int, int]
Palavra = tuple[str, int, int, int, int]  # texto, x, y, w, h

PALAVRAS_PADRAO: list[str] = [
    "ok", "aceitar", "continuar", "permitir", "confirmar", "próximo", "proximo",
    "sim", "accept", "allow", "continue", "next", "yes", "confirm",
]


def _tesseract() -> Any:
    import pytesseract  # type: ignore

    tess: Any = pytesseract
    if shutil.which("tesseract") is None:
        candidatos = [
            os.environ.get("TESSERACT_CMD", ""),
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            str(Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tesseract.exe"),
        ]
        for c in candidatos:
            if c and Path(c).is_file():
                tess.pytesseract.tesseract_cmd = c
                break
    return tess


@dataclass
class Hit:
    x: int
    y: int
    w: int
    h: int
    rotulo: str
    score: float = 1.0
    escala: float = 1.0  # escala do recorte que casou (1.0 = tamanho original do PNG)

    @property
    def centro(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2


# --------------------------------------------------------------------------- #
# Captura de tela
# --------------------------------------------------------------------------- #
def capturar(
    monitor_idx: int, regiao: Optional[Regiao] = None
) -> tuple[Img, float, float, int, int]:
    """Retorna (imagem BGR, escala x, escala y, offset x, offset y)."""
    # mss.mss foi renomeado para mss.MSS nas versões novas.
    mss_cls: Any = getattr(mss_lib, "MSS", None) or mss_lib.mss
    with mss_cls() as sct:
        mon: dict[str, int] = dict(sct.monitors[monitor_idx])
        if regiao is not None:
            x, y, w, h = regiao
            mon = {
                "left": mon["left"] + x,
                "top": mon["top"] + y,
                "width": w,
                "height": h,
            }
        shot: Img = np.array(sct.grab(mon))[:, :, :3]
    # Em telas HiDPI/Retina a imagem tem mais pixels do que "pontos" de tela.
    esc_x = mon["width"] / shot.shape[1]
    esc_y = mon["height"] / shot.shape[0]
    return shot, esc_x, esc_y, mon["left"], mon["top"]


# --------------------------------------------------------------------------- #
# Detectores
# --------------------------------------------------------------------------- #
def dedupe(hits: list[Hit], dist: int = 15) -> list[Hit]:
    saida: list[Hit] = []
    for h in sorted(hits, key=lambda k: -k.score):
        cx, cy = h.centro
        if all(
            abs(cx - o.centro[0]) > dist or abs(cy - o.centro[1]) > dist for o in saida
        ):
            saida.append(h)
    return saida


@dataclass
class ConfigEscala:
    """Escala dos recortes em relação à tela atual.

    Os PNGs são tirados no MAIOR tamanho possível da janela (escala 1.0). Se a janela
    for redimensionada, todos os botões encolhem juntos; por isso aprendemos UMA escala
    global e a reutilizamos nas varreduras seguintes (rápido). Só quando nada casa mais
    é feita uma busca completa por escalas.
    """

    ativa: bool = True
    fixa: Optional[float] = None  # força uma escala (ex.: --escala 0.6)
    minima: float = 0.3
    maxima: float = 1.0
    passo: float = 0.04  # variação usada para acompanhar pequenas mudanças
    atual: Optional[float] = None  # escala aprendida
    busca_a_cada: float = 8.0  # segundos mínimos entre buscas completas (sem acertos)
    ultima_busca: float = -1e9
    ultimo_refino: float = 0.0


_esc = ConfigEscala()
_TPL_CACHE: dict[str, tuple[float, Img]] = {}


def configurar_escala(
    ativa: bool = True,
    fixa: Optional[float] = None,
    minima: float = 0.3,
    maxima: float = 1.0,
    busca_a_cada: float = 8.0,
) -> None:
    global _esc
    _esc = ConfigEscala(
        ativa=ativa, fixa=fixa, minima=min(minima, maxima), maxima=max(minima, maxima),
        busca_a_cada=busca_a_cada,
    )


def escala_atual() -> Optional[float]:
    return _esc.fixa if _esc.fixa is not None else _esc.atual


def escala_mudou_janela(fator: float) -> None:
    """A janela mudou de tamanho: prevê a nova escala e libera uma busca imediata."""
    if _esc.atual is not None and fator > 0:
        _esc.atual = min(max(_esc.atual * fator, _esc.minima), _esc.maxima)
    _esc.ultima_busca = -1e9
    _esc.ultimo_refino = 0.0


def carregar_templates(pasta: str) -> list[tuple[str, Img]]:
    """Lê os PNG/JPG da pasta (com cache; só relê se o arquivo mudou)."""
    arquivos = sorted(Path(pasta).glob("*.png")) + sorted(Path(pasta).glob("*.jpg"))
    saida: list[tuple[str, Img]] = []
    for arq in arquivos:
        chave = str(arq)
        try:
            mtime = arq.stat().st_mtime
        except OSError:
            continue
        em_cache = _TPL_CACHE.get(chave)
        if em_cache is None or em_cache[0] != mtime:
            lido = cast(Optional[Img], cv2.imread(chave))
            if lido is None:
                _TPL_CACHE.pop(chave, None)
                continue
            _TPL_CACHE[chave] = (mtime, lido)
            em_cache = _TPL_CACHE[chave]
        saida.append((arq.stem, em_cache[1]))
    return saida


def _redimensionar(tpl: Img, escala: float) -> Optional[Img]:
    """Recorte na escala pedida; None se ficaria pequeno demais para casar com segurança."""
    if abs(escala - 1.0) < 0.005:
        return tpl
    w = round(tpl.shape[1] * escala)
    h = round(tpl.shape[0] * escala)
    if w < 8 or h < 8:
        return None
    interp = cv2.INTER_AREA if escala < 1.0 else cv2.INTER_LINEAR
    return cast(Img, cv2.resize(tpl, (w, h), interpolation=interp))


class _Cena:
    """A captura + versões em cinza (inteira e em meia resolução), calculadas uma vez só.

    matchTemplate em cor e resolução cheia é ~50x mais lento do que em cinza e meia
    resolução; por isso a busca é em duas etapas: grossa (cinza/meia) para achar
    candidatos e fina (cor/cheia) só em volta deles.
    """

    def __init__(self, img: Img) -> None:
        self.img = img
        self.cinza = cast(Img, cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
        self._meia: Optional[Img] = None

    def meia(self) -> Img:
        if self._meia is None:
            self._meia = cast(Img, cv2.resize(self.cinza, None, fx=0.5, fy=0.5,
                                              interpolation=cv2.INTER_AREA))
        return self._meia


def _limpar(res: Img) -> Img:
    return np.nan_to_num(res, copy=False, nan=0.0, posinf=0.0, neginf=0.0)


def _resp_grossa(cena: _Cena, t: Img) -> Optional[tuple[Img, float]]:
    """Mapa de correlação (cinza) do recorte 't' sobre a cena; (mapa, fator de redução)."""
    img = cena.img
    th, tw = t.shape[:2]
    if th > img.shape[0] or tw > img.shape[1]:
        return None
    tg = cast(Img, cv2.cvtColor(t, cv2.COLOR_BGR2GRAY))
    reduz = 0.5 if (min(th, tw) >= 20 and max(img.shape[0], img.shape[1]) >= 600) else 1.0
    base = cena.cinza
    if reduz < 1.0:
        base = cena.meia()
        tg = cast(Img, cv2.resize(tg, None, fx=reduz, fy=reduz, interpolation=cv2.INTER_AREA))
    if tg.shape[0] > base.shape[0] or tg.shape[1] > base.shape[1] or min(tg.shape) < 4:
        return None
    return _limpar(cast(Img, cv2.matchTemplate(base, tg, cv2.TM_CCOEFF_NORMED))), reduz


def _casar(cena: _Cena, tpl: Img, rotulo: str, escala: float, confianca: float) -> list[Hit]:
    t = _redimensionar(tpl, escala)
    if t is None:
        return []
    r = _resp_grossa(cena, t)
    if r is None:
        return []
    res, reduz = r
    th, tw = t.shape[:2]
    ys, xs = np.where(res >= max(0.5, confianca - 0.2))
    if ys.size == 0:
        return []
    # Candidatos: os melhores picos, sem repetir o mesmo lugar.
    sup = max(4, min(th, tw) // 2)
    picos: list[tuple[int, int]] = []
    for k in np.argsort(-res[ys, xs])[:400].tolist():
        x, y = int(xs[k] / reduz), int(ys[k] / reduz)
        if all(abs(x - px) > sup or abs(y - py) > sup for px, py in picos):
            picos.append((x, y))
            if len(picos) >= 25:
                break
    # Etapa fina: confere em cor e tamanho cheio numa janelinha em volta de cada candidato.
    img = cena.img
    pad = 4 if reduz == 1.0 else 7
    hits: list[Hit] = []
    for fx, fy in picos:
        x0, y0 = max(0, fx - pad), max(0, fy - pad)
        x1, y1 = min(img.shape[1], fx + tw + pad), min(img.shape[0], fy + th + pad)
        roi = img[y0:y1, x0:x1]
        if roi.shape[0] < th or roi.shape[1] < tw:
            continue
        fino = _limpar(cast(Img, cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED)))
        _, mx, _, loc = cv2.minMaxLoc(fino)
        if mx >= confianca:
            hits.append(Hit(x0 + int(loc[0]), y0 + int(loc[1]), tw, th, rotulo, float(mx), escala))
    return hits


def _hits_na_escala(
    cena: _Cena, tpls: list[tuple[str, Img]], escala: float, confianca: float
) -> list[Hit]:
    hits: list[Hit] = []
    for nome, tpl in tpls:
        hits.extend(_casar(cena, tpl, nome, escala, confianca))
    return dedupe(hits)


def _pontuacao(hits: list[Hit]) -> tuple[int, float]:
    """(quantos recortes diferentes casaram, soma dos melhores scores de cada um)."""
    melhor: dict[str, float] = {}
    for h in hits:
        melhor[h.rotulo] = max(melhor.get(h.rotulo, 0.0), h.score)
    return len(melhor), sum(melhor.values())


def _buscar_escala(cena: _Cena, tpls: list[tuple[str, Img]], confianca: float) -> Optional[float]:
    """Busca completa: varre as escalas de maxima até minima (só etapa grossa, rápida)
    e refina a melhor com a etapa fina. None se nada casou."""
    cfg = _esc
    limiar = max(0.5, confianca - 0.2)
    melhor: Optional[tuple[int, float, float]] = None  # (acertos, soma, escala)
    e = cfg.maxima
    while e >= cfg.minima - 1e-9:
        acertos, soma = 0, 0.0
        for _, tpl in tpls:
            t = _redimensionar(tpl, e)
            r = _resp_grossa(cena, t) if t is not None else None
            if r is not None and r[0].size:
                v = float(r[0].max())
                if v >= limiar:
                    acertos += 1
                    soma += v
        if acertos and (melhor is None or (acertos, soma) > (melhor[0], melhor[1])):
            melhor = (acertos, soma, e)
        e *= 0.94
    if melhor is None:
        return None

    base = melhor[2]
    fino: Optional[tuple[int, float, float]] = None
    for k in (0.97, 0.985, 1.0, 1.015, 1.03):
        e2 = min(max(base * k, cfg.minima), cfg.maxima)
        acertos, soma = _pontuacao(_hits_na_escala(cena, tpls, e2, confianca))
        if acertos and (fino is None or (acertos, soma) > (fino[0], fino[1])):
            fino = (acertos, soma, e2)
    return fino[2] if fino is not None else None


def detectar_imagens(img: Img, pasta: str, confianca: float) -> list[Hit]:
    tpls = carregar_templates(pasta)
    if not tpls:
        return []
    cena = _Cena(img)
    cfg = _esc
    if not cfg.ativa:
        return _hits_na_escala(cena, tpls, 1.0, confianca)
    if cfg.fixa is not None:
        return _hits_na_escala(cena, tpls, cfg.fixa, confianca)

    agora = time.time()
    # 1) Escala já aprendida (ou 1.0 na primeira varredura): caminho rápido.
    esc = cfg.atual if cfg.atual is not None else min(max(1.0, cfg.minima), cfg.maxima)
    hits = _hits_na_escala(cena, tpls, esc, confianca)
    if hits:
        cfg.atual = esc
        # De tempos em tempos confere escalas vizinhas, para acompanhar redimensionamentos
        # lentos (a escala só muda se a vizinha casar claramente melhor).
        if agora - cfg.ultimo_refino > 3.0:
            cfg.ultimo_refino = agora
            ref = _pontuacao(hits)
            for viz in (esc * (1 - cfg.passo), esc * (1 + cfg.passo)):
                viz = min(max(viz, cfg.minima), cfg.maxima)
                hv = _hits_na_escala(cena, tpls, viz, confianca)
                pv = _pontuacao(hv)
                if pv[0] >= ref[0] and pv[1] > ref[1] + 0.05 * max(1, ref[0]):
                    hits, ref, cfg.atual = hv, pv, viz
        return hits

    # 2) Nada casou: pode ser só que não há botões agora. Busca completa, no máximo
    #    a cada 'busca_a_cada' segundos, para não pesar quando a tela está vazia.
    if agora - cfg.ultima_busca < cfg.busca_a_cada:
        return []
    cfg.ultima_busca = agora
    nova = _buscar_escala(cena, tpls, confianca)
    if nova is None:
        return []
    cfg.atual = nova
    return _hits_na_escala(cena, tpls, nova, confianca)


def _norm(s: str) -> str:
    """Minúsculas, sem acentos e sem pontuação nas pontas."""
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip(".,:;!?\"'()[]{}|")


def _parecido(lido: str, alvo: str) -> bool:
    """Igual, ou quase igual (tolera 1-2 letras erradas do OCR em palavras longas)."""
    if lido == alvo:
        return True
    if len(alvo) < 4:
        return False
    return SequenceMatcher(None, lido, alvo).ratio() >= 0.8


def _ocr_linhas(
    gray: Img, lang: str, escala: float = 2.0, conf_min: float = 30.0
) -> list[list[Palavra]]:
    tess = _tesseract()
    if escala != 1.0:
        gray = cast(
            Img, cv2.resize(gray, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC)
        )
    d: dict[str, list[Any]] = tess.image_to_data(
        gray, lang=lang, output_type=tess.Output.DICT
    )
    linhas: dict[tuple[int, int, int], list[Palavra]] = {}
    for i, bruto in enumerate(d["text"]):
        t = _norm(str(bruto))
        try:
            conf = float(d["conf"][i])
        except (ValueError, TypeError):
            continue
        if not t or conf < conf_min:
            continue
        chave = (int(d["block_num"][i]), int(d["par_num"][i]), int(d["line_num"][i]))
        # Coordenadas voltam para a escala da imagem original.
        linhas.setdefault(chave, []).append(
            (
                t,
                int(d["left"][i] / escala),
                int(d["top"][i] / escala),
                int(d["width"][i] / escala),
                int(d["height"][i] / escala),
            )
        )
    return list(linhas.values())


def detectar_texto(
    img: Img, palavras: list[str], lang: str, debug: bool = False
) -> list[Hit]:
    gray = cast(Img, cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    hits: list[Hit] = []
    vistas: set[str] = set()
    # Duas passadas: texto escuro em fundo claro e o inverso (botões escuros).
    for variante in (gray, cast(Img, cv2.bitwise_not(gray))):
        for palavras_linha in _ocr_linhas(variante, lang):
            vistas.update(w[0] for w in palavras_linha)
            for alvo in palavras:
                tw = [_norm(p) for p in alvo.split()]
                n = len(tw)
                for s in range(len(palavras_linha) - n + 1):
                    seq = palavras_linha[s:s + n]
                    if all(_parecido(w[0], t) for w, t in zip(seq, tw)):
                        x = min(w[1] for w in seq)
                        y = min(w[2] for w in seq)
                        x2 = max(w[1] + w[3] for w in seq)
                        y2 = max(w[2] + w[4] for w in seq)
                        hits.append(Hit(x, y, x2 - x, y2 - y, alvo))
    if debug:
        print(f"[debug] OCR leu {len(vistas)} palavras distintas:")
        print("  " + ", ".join(sorted(vistas)) if vistas else "  (nenhuma)")
    return dedupe(hits)


def caixas_de_botao(img: Img) -> list[tuple[int, int, int, int]]:
    """Acha retângulos com proporção e tamanho típicos de botão."""
    gray = cast(Img, cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    borrado = cast(Img, cv2.GaussianBlur(gray, (3, 3), 0))
    bordas = cast(Img, cv2.Canny(borrado, 40, 120))
    bordas = cast(Img, cv2.dilate(bordas, np.ones((3, 3), np.uint8), iterations=1))
    contornos, _ = cv2.findContours(bordas, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    caixas: list[tuple[int, int, int, int]] = []
    for c in contornos:
        x, y, w, h = cv2.boundingRect(c)
        if not (50 <= w <= 450 and 22 <= h <= 90):
            continue
        if not (1.6 <= w / h <= 9):
            continue
        if cv2.contourArea(c) < 0.6 * w * h:
            continue
        caixas.append((int(x), int(y), int(w), int(h)))
    return caixas


def detectar_auto(img: Img, palavras: list[str], lang: str) -> list[Hit]:
    tess = _tesseract()
    hits: list[Hit] = []
    for x, y, w, h in caixas_de_botao(img):
        crop: Img = img[y:y + h, x:x + w]
        crop = cast(Img, cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC))
        gray = cast(Img, cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))
        for variante in (gray, cast(Img, cv2.bitwise_not(gray))):
            txt = str(tess.image_to_string(variante, lang=lang, config="--psm 7"))
            txt = txt.strip().lower()
            if not txt:
                continue
            achou: Optional[str] = next((p for p in palavras if p.lower() in txt), None)
            if achou is not None:
                hits.append(Hit(x, y, w, h, f"{achou} ('{txt}')"))
                break
    return dedupe(hits)


# --------------------------------------------------------------------------- #
# Ação
# --------------------------------------------------------------------------- #
def ponto_de_clique(h: Hit, dx: int = 0, dy: int = 0) -> tuple[int, int]:
    """Ponto exato do clique (em pixels da imagem capturada): centro do botão + ajuste.

    O ajuste (dx, dy) é dado no tamanho original do PNG e acompanha a escala do botão.
    """
    cx, cy = h.centro
    return cx + round(dx * h.escala), cy + round(dy * h.escala)


def salvar_preview(
    img: Img, hits: list[Hit], caminho: str = "preview.png", dx: int = 0, dy: int = 0
) -> None:
    out = img.copy()
    for h in hits:
        cv2.rectangle(out, (h.x, h.y), (h.x + h.w, h.y + h.h), (0, 255, 0), 2)
        # Cruz vermelha = ponto exato onde o clique vai acontecer.
        cv2.drawMarker(out, ponto_de_clique(h, dx, dy), (0, 0, 255),
                       cv2.MARKER_CROSS, 24, 2)
        rotulo = h.rotulo if h.escala == 1.0 else f"{h.rotulo} x{h.escala:.2f}"
        cv2.putText(out, rotulo, (h.x, max(12, h.y - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)
    cv2.imwrite(caminho, out)


def ainda_no_lugar(
    h: Hit, monitor: int, regiao: Optional[Regiao], pasta: str, confianca: float
) -> bool:
    """Recaptura a tela e confirma que o botão continua onde foi detectado.

    Evita clicar em outro elemento (ex.: o botão de fechar) se a lista andou
    enquanto o mouse se movia. É chamada com o cursor AO LADO do botão (sem hover),
    pois com o cursor em cima a aparência do botão muda e o recorte não bate.
    """
    img, _, _, _, _ = capturar(monitor, regiao)
    cx, cy = h.centro
    for n in detectar_imagens(img, pasta, confianca):
        if n.rotulo == h.rotulo and abs(n.centro[0] - cx) <= 8 and abs(n.centro[1] - cy) <= 8:
            return True
    return False


# --------------------------------------------------------------------------- #
# Camada Windows (ctypes, sem pyautogui): janelas, mouse e teclado "de verdade"
# --------------------------------------------------------------------------- #
class FailSafe(Exception):
    """Mouse no canto superior esquerdo da tela: abortar."""


_api_cache: Optional[tuple[Any, Any]] = None


def _api() -> tuple[Any, Any]:
    """(user32, kernel32) com os tipos dos argumentos definidos (evita truncar handles)."""
    global _api_cache
    if _api_cache is not None:
        return _api_cache
    from ctypes import wintypes

    windll: Any = getattr(ctypes, "windll")
    u: Any = windll.user32
    k: Any = windll.kernel32
    try:
        u.SetProcessDPIAware()  # coordenadas em pixels reais (telas com zoom 125%/150%)
    except Exception:
        pass
    u.WindowFromPoint.argtypes = [wintypes.POINT]
    u.WindowFromPoint.restype = wintypes.HWND
    u.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    u.GetAncestor.restype = wintypes.HWND
    u.GetForegroundWindow.restype = wintypes.HWND
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u.GetWindowThreadProcessId.restype = wintypes.DWORD
    u.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    u.SetForegroundWindow.argtypes = [wintypes.HWND]
    u.IsIconic.argtypes = [wintypes.HWND]
    u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    u.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    u.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    u.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    u.MapVirtualKeyW.restype = wintypes.UINT
    k.GetConsoleWindow.restype = wintypes.HWND
    _api_cache = (u, k)
    return _api_cache


def posicao() -> tuple[int, int]:
    """Posição atual do cursor (pixels de tela)."""
    from ctypes import wintypes

    u, _ = _api()
    pt = wintypes.POINT()
    u.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def limites_tela() -> tuple[int, int, int, int]:
    """(x, y, largura, altura) da área virtual (todos os monitores)."""
    u, _ = _api()
    return (int(u.GetSystemMetrics(76)), int(u.GetSystemMetrics(77)),
            int(u.GetSystemMetrics(78)), int(u.GetSystemMetrics(79)))


def tamanho_tela() -> tuple[int, int]:
    """Largura e altura do monitor principal."""
    u, _ = _api()
    return int(u.GetSystemMetrics(0)), int(u.GetSystemMetrics(1))


def checar_failsafe() -> None:
    x, y = posicao()
    if x <= 1 and y <= 1:
        raise FailSafe()


def _titulo_de(hwnd: Any) -> str:
    u, _ = _api()
    buf = ctypes.create_unicode_buffer(512)
    u.GetWindowTextW(hwnd, buf, 512)
    return str(buf.value)


def _raiz(hwnd: Any) -> Any:
    u, _ = _api()
    return u.GetAncestor(hwnd, 2) or hwnd  # GA_ROOT


def titulo_sob_ponto(x: int, y: int) -> Optional[str]:
    """Título da janela (de nível superior) sob o ponto (x, y); None se não achar."""
    if sys.platform != "win32":
        return None
    try:
        from ctypes import wintypes

        u, _ = _api()
        hwnd = u.WindowFromPoint(wintypes.POINT(x, y))
        if not hwnd:
            return None
        t = _titulo_de(_raiz(hwnd))
        return t or None
    except Exception:
        return None


def titulo_ativo() -> Optional[str]:
    """Título da janela em primeiro plano."""
    if sys.platform != "win32":
        return None
    try:
        u, _ = _api()
        h = u.GetForegroundWindow()
        return (_titulo_de(_raiz(h)) or None) if h else None
    except Exception:
        return None


def achar_janela(titulo: str) -> Optional[int]:
    """Procura uma janela visível cujo título contém 'titulo' (sem diferenciar
    maiúsculas). Prefere título igual > começa com > contém, e a maior janela. Ignora
    o próprio terminal (o comando com o nome da janela aparece no título dele)."""
    if sys.platform != "win32" or not titulo:
        return None
    u, k = _api()
    alvo = titulo.casefold()
    console = int(k.GetConsoleWindow() or 0)
    achados: list[tuple[int, int, int]] = []

    def cb(hwnd: Any, _lp: Any) -> bool:
        if not u.IsWindowVisible(hwnd) or int(hwnd or 0) == console:
            return True
        t = _titulo_de(hwnd).casefold()
        if not t or alvo not in t:
            return True
        prio = 0 if t == alvo else (1 if t.startswith(alvo) else 2)
        r = retangulo_janela(int(hwnd))
        achados.append((prio, -(r[2] * r[3] if r else 0), int(hwnd)))
        return True

    proto: Any = getattr(ctypes, "WINFUNCTYPE")(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    u.EnumWindows(proto(cb), 0)
    return min(achados)[2] if achados else None


def retangulo_janela(hwnd: int) -> Optional[Regiao]:
    """Área CLIENTE (sem bordas/título) da janela em coordenadas de tela:
    (esquerda, topo, largura, altura). None se minimizada ou sem tamanho."""
    from ctypes import wintypes

    u, _ = _api()
    if u.IsIconic(hwnd):
        return None
    r = wintypes.RECT()
    if not u.GetClientRect(hwnd, ctypes.byref(r)):
        return None
    w, h = int(r.right - r.left), int(r.bottom - r.top)
    if w <= 0 or h <= 0:
        return None
    pt = wintypes.POINT(0, 0)
    u.ClientToScreen(hwnd, ctypes.byref(pt))
    return int(pt.x), int(pt.y), w, h


def rect_da_janela(titulo: str) -> Optional[Regiao]:
    """Atalho: área cliente da janela com esse título (ou None)."""
    hwnd = achar_janela(titulo)
    return retangulo_janela(hwnd) if hwnd else None


def janela_ativa(titulo: str) -> bool:
    """True se a janela em primeiro plano tem esse título."""
    if sys.platform != "win32":
        return True
    u, _ = _api()
    atual = u.GetForegroundWindow()
    if not atual:
        return False
    return titulo.casefold() in _titulo_de(_raiz(atual)).casefold()


def focar_hwnd(raiz: Any) -> bool:
    """Traz a janela 'raiz' para o primeiro plano. True se ela ficou em foco."""
    u, k = _api()
    atual = u.GetForegroundWindow()
    if atual == raiz:
        return True
    # O Windows só deixa trazer uma janela para frente se anexarmos a thread da atual.
    tid_atual = int(u.GetWindowThreadProcessId(atual, None)) if atual else 0
    tid_nosso = int(k.GetCurrentThreadId())
    anexado = False
    if tid_atual and tid_atual != tid_nosso:
        anexado = bool(u.AttachThreadInput(tid_atual, tid_nosso, True))
    try:
        if u.IsIconic(raiz):
            u.ShowWindow(raiz, 9)  # SW_RESTORE (só se estiver minimizada)
        u.SetForegroundWindow(raiz)
    finally:
        if anexado:
            u.AttachThreadInput(tid_atual, tid_nosso, False)
    time.sleep(0.2)
    return bool(u.GetForegroundWindow() == raiz)


def trazer_janela_para_frente(x: int, y: int) -> bool:
    """Windows: traz para o primeiro plano a janela que está sob o ponto (x, y).

    Retorna True se a janela já estava (ou ficou) em foco.
    """
    if sys.platform != "win32":
        return False
    from ctypes import wintypes

    u, _ = _api()
    hwnd = u.WindowFromPoint(wintypes.POINT(x, y))
    if not hwnd:
        return False
    return focar_hwnd(_raiz(hwnd))


# --------------------------------------------------------------------------- #
# Mouse "de verdade" (SendInput): gera eventos reais de movimento, que jogos usam
# para ativar o hover (SetCursorPos só teletransporta o ponteiro, sem esses eventos).
# --------------------------------------------------------------------------- #
class _MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_int32),
        ("dy", ctypes.c_int32),
        ("mouseData", ctypes.c_uint32),
        ("dwFlags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _KeybdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_uint16),
        ("wScan", ctypes.c_uint16),
        ("dwFlags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _InputUnion(ctypes.Union):
    _fields_ = [("mi", _MouseInput), ("ki", _KeybdInput)]


class _Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint32), ("u", _InputUnion)]


_MOVE = 0x0001
_LEFTDOWN = 0x0002
_LEFTUP = 0x0004
_VIRTUALDESK = 0x4000
_ABSOLUTE = 0x8000


def _enviar_mouse(dx: int, dy: int, flags: int) -> None:
    u, _ = _api()
    entrada = _Input(type=0, u=_InputUnion(mi=_MouseInput(dx, dy, 0, flags, 0, 0)))
    u.SendInput(1, ctypes.byref(entrada), ctypes.sizeof(entrada))


def mover_real(px: int, py: int) -> None:
    """Move o cursor para (px, py) enviando um evento de mouse real."""
    vx, vy, vw, vh = limites_tela()
    nx = round((px - vx) * 65535 / max(1, vw - 1))
    ny = round((py - vy) * 65535 / max(1, vh - 1))
    _enviar_mouse(nx, ny, _MOVE | _ABSOLUTE | _VIRTUALDESK)


def mover_suave(px: int, py: int, duracao: float = 0.3, passos: int = 18) -> None:
    """Trajetória curta com vários eventos reais de movimento até (px, py)."""
    checar_failsafe()
    x0, y0 = posicao()
    for i in range(1, passos + 1):
        t = i / passos
        e = 1 - (1 - t) ** 2  # desacelera ao chegar
        mover_real(round(x0 + (px - x0) * e), round(y0 + (py - y0) * e))
        time.sleep(duracao / passos)


def estacionar_mouse(px: int, py: int, destino: Optional[tuple[int, int]] = None) -> None:
    """Afasta o cursor do botão para o hover não atrapalhar a próxima detecção.

    Sem destino definido, vai 350 px para o lado (só passa o mouse, não clica).
    """
    largura, altura = tamanho_tela()
    if destino is None:
        alvo_x = px + 350 if px + 350 < largura - 20 else px - 350
        alvo_y = py
    else:
        alvo_x, alvo_y = destino
    # Evita os cantos da tela (o canto superior esquerdo aciona o failsafe).
    alvo_x = min(max(alvo_x, 20), largura - 20)
    alvo_y = min(max(alvo_y, 20), altura - 20)
    time.sleep(0.1)  # deixa o clique terminar de ser registrado
    mover_suave(alvo_x, alvo_y, duracao=0.25, passos=10)


# --------------------------------------------------------------------------- #
# Teclado: nomes, leitura (para gravar) e envio (para reproduzir)
# --------------------------------------------------------------------------- #
VK_F9 = 0x78  # tecla de parada (não é gravada)

# Teclas monitoradas: letras, números, setas, F1-F24 (menos F9), modificadores, etc.
VKS_TECLADO: tuple[int, ...] = tuple(
    v for v in (
        [0x08, 0x09, 0x0D, 0x13, 0x14, 0x1B]
        + list(range(0x20, 0x29)) + [0x2C, 0x2D, 0x2E]
        + list(range(0x30, 0x3A)) + list(range(0x41, 0x5B))
        + [0x5B, 0x5C] + list(range(0x60, 0x88)) + [0x90, 0x91]
        + list(range(0xA0, 0xA6)) + list(range(0xBA, 0xC1))
        + list(range(0xDB, 0xE0)) + [0xE2]
    ) if v != VK_F9
)
_TECLAS_ESTENDIDAS = frozenset(
    {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2C, 0x2D, 0x2E, 0x5B, 0x5C,
     0x6F, 0x90, 0xA3, 0xA5}
)
_NOMES_TECLA: dict[int, str] = {
    0x08: "Backspace", 0x09: "Tab", 0x0D: "Enter", 0x13: "Pause", 0x14: "CapsLock",
    0x1B: "Esc", 0x20: "Espaço", 0x21: "PageUp", 0x22: "PageDown", 0x23: "End",
    0x24: "Home", 0x25: "Esquerda", 0x26: "Cima", 0x27: "Direita", 0x28: "Baixo",
    0x2C: "PrintScreen", 0x2D: "Insert", 0x2E: "Delete", 0x5B: "Win", 0x5C: "Win",
    0x6A: "Num*", 0x6B: "Num+", 0x6D: "Num-", 0x6E: "Num.", 0x6F: "Num/",
    0x90: "NumLock", 0x91: "ScrollLock", 0xA0: "Shift", 0xA1: "Shift", 0xA2: "Ctrl",
    0xA3: "Ctrl", 0xA4: "Alt", 0xA5: "Alt",
}


def nome_tecla(vk: int) -> str:
    if vk in _NOMES_TECLA:
        return _NOMES_TECLA[vk]
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x60 <= vk <= 0x69:
        return f"Num{vk - 0x60}"
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x6F}"
    return f"VK_{vk:02X}"


def _enviar_tecla(vk: int, baixo: bool) -> None:
    """Aperta (baixo=True) ou solta uma tecla com eventos reais (código de varredura,
    que é o que jogos costumam ler)."""
    u, _ = _api()
    scan = int(u.MapVirtualKeyW(vk, 0))
    flags = 0 if baixo else 0x0002  # KEYEVENTF_KEYUP
    if vk in _TECLAS_ESTENDIDAS:
        flags |= 0x0001  # KEYEVENTF_EXTENDEDKEY
    wvk = vk
    if scan:
        flags |= 0x0008  # KEYEVENTF_SCANCODE
        wvk = 0
    entrada = _Input(type=1, u=_InputUnion(ki=_KeybdInput(wvk, scan, flags, 0, 0)))
    u.SendInput(1, ctypes.byref(entrada), ctypes.sizeof(entrada))


class MonitorTeclado:
    """Detecta quando teclas são apertadas/soltas (consulta o estado a cada chamada)."""

    def __init__(self) -> None:
        self.premidas: dict[int, float] = {}

    def varrer(self, agora: float) -> list[tuple[str, int]]:
        """Lista de ('baixo' | 'cima', vk) ocorridos desde a última chamada."""
        mudancas: list[tuple[str, int]] = []
        for vk in VKS_TECLADO:
            p = _tecla_pressionada(vk)
            if p and vk not in self.premidas:
                self.premidas[vk] = agora
                mudancas.append(("baixo", vk))
            elif (not p) and vk in self.premidas:
                del self.premidas[vk]
                mudancas.append(("cima", vk))
        return mudancas


def clicar(
    h: Hit,
    esc_x: float,
    esc_y: float,
    off_x: int,
    off_y: int,
    espera_hover: float = 0.25,
    hold: float = 0.08,
    dx: int = 0,
    dy: int = 0,
    jitter: float = 0.0,
    foco: bool = True,
    debug: bool = False,
    confirmar: Optional[Callable[[], bool]] = None,
    estacionar: bool = True,
    destino: Optional[tuple[int, int]] = None,
    arrastar_para: Optional[tuple[int, int]] = None,
) -> bool:
    checar_failsafe()
    cx, cy = ponto_de_clique(h, dx, dy)
    cx_f, cy_f = float(cx), float(cy)
    if jitter > 0:
        # Variação opcional (fração do tamanho do botão). Padrão: 0 = clique exato.
        cx_f += random.uniform(-jitter, jitter) * h.w
        cy_f += random.uniform(-jitter, jitter) * h.h
    px = round(off_x + cx_f * esc_x)
    py = round(off_y + cy_f * esc_y)

    # 1) Garante que a janela do botão está em foco (senão o 1º clique só foca).
    if foco:
        ok = trazer_janela_para_frente(px, py)
        if debug:
            print(f"[debug] janela em foco: {ok}")

    # 2) Aproximação em duas etapas:
    #    a) para AO LADO do botão (fora dele, sem hover) e reconfirma que o botão
    #       ainda está ali. Com o cursor em cima, o hover mudaria a aparência e a
    #       checagem falharia;
    #    b) só então entra no botão com eventos de movimento REAIS (SendInput),
    #       para o jogo ativar o hover como se fosse o mouse físico, e clica.
    lado_x = max(20, round(off_x + h.x * esc_x) - 40)
    mover_suave(lado_x, py, duracao=random.uniform(0.2, 0.3))

    if confirmar is not None:
        time.sleep(0.05)
        if not confirmar():
            if debug:
                print("[debug] botão mudou de lugar; clique cancelado")
            if estacionar:
                estacionar_mouse(lado_x, py, destino)
            return False

    mover_suave(px, py, duracao=0.2, passos=12)
    # Pequeno "tremor" sobre o botão, terminando exatamente no alvo.
    mover_real(px + 2, py)
    time.sleep(0.04)
    mover_real(px - 1, py)
    time.sleep(0.04)
    mover_real(px, py)
    time.sleep(espera_hover)

    # 3) Confere onde o cursor realmente parou e corrige se desviou.
    rx, ry = posicao()
    if abs(rx - px) > 3 or abs(ry - py) > 3:
        mover_real(px, py)
        time.sleep(0.05)
        rx, ry = posicao()
    if debug:
        print(f"[debug] alvo=({px},{py}) cursor=({rx},{ry}) escala do botão={h.escala:.2f}")

    # 4) Pressiona, segura e solta. Com 'arrastar_para', mantém o botão pressionado
    #    e leva o cursor (com movimentos reais, devagar) até lá antes de soltar.
    _enviar_mouse(0, 0, _LEFTDOWN)
    try:
        time.sleep(hold)
        if arrastar_para is not None:
            mover_suave(arrastar_para[0], arrastar_para[1], duracao=0.7, passos=35)
            time.sleep(0.2)  # deixa o jogo registrar a posição de soltura
    finally:
        _enviar_mouse(0, 0, _LEFTUP)  # nunca deixa o botão preso, mesmo se abortar
    if estacionar:
        estacionar_mouse(px, py, destino)
    return True


# --------------------------------------------------------------------------- #
# Regras por botão (botoes.json), estado da partida e log de ações
# --------------------------------------------------------------------------- #
_RIGHTDOWN = 0x0008
_RIGHTUP = 0x0010
VK_ESQUERDO = 0x01
VK_DIREITO = 0x02

ACOES_VALIDAS = ("clicar", "arrastar", "inicio", "ancora")


@dataclass
class Regra:
    """Regra de um botão (chave = nome do PNG sem extensão)."""

    acao: str = "clicar"  # clicar | arrastar | inicio | ancora
    vezes: int = 0  # por partida; 0 = ilimitado
    intervalo: Optional[float] = None  # segundos mínimos entre ações deste botão
    # Para 'arrastar' (só um dos três é usado):
    destino: Optional[tuple[int, int]] = None  # (x, y) FIXO na tela
    destino_janela: Optional[tuple[float, float]] = None  # fração (0-1) da janela do jogo
    destino_ancora: Optional[tuple[str, int, int]] = None  # (imagem de referência, dx, dy)
    offset: tuple[int, int] = (0, 0)  # ajuste fino do ponto de clique
    confirmar_cinza: bool = False
    queda_saturacao: float = 0.5  # cinza = saturação caiu para <= 50% do original
    tentativas: int = 3
    espera_confirmacao: float = 0.7
    # True = clica assim que detectar (também durante a reprodução de uma gravação);
    # False = nunca é clicado sozinho; None = padrão (clica nos modos de varredura).
    auto_detect: Optional[bool] = None
    # Escolher UM entre vários botões parecidos (ex.: 3 cartas de "escolha uma"):
    escolha: Optional[str] = None  # "primeiro" (mais à esquerda) | "ultimo" | "aleatorio"
    grupo: Optional[str] = None  # botões com o mesmo grupo disputam a mesma escolha
    # Clicar neste botão reinicia o ciclo (zera a partida; na reprodução, volta ao início
    # da gravação sem clicar de novo neste botão).
    reiniciar_loop: bool = False


ESCOLHAS_VALIDAS = ("primeiro", "ultimo", "aleatorio")


def carregar_regras(caminho: str) -> dict[str, Regra]:
    p = Path(caminho)
    if not p.is_file():
        return {}
    try:
        bruto: Any = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"{caminho}: JSON inválido ({e}).")
    if not isinstance(bruto, dict):
        sys.exit(f'{caminho}: o arquivo deve ser um objeto JSON: {{"botao": {{...}}}}.')

    regras: dict[str, Regra] = {}
    for nome, dados_raw in cast(dict[str, Any], bruto).items():
        if nome.startswith("_"):
            continue  # chaves iniciadas por _ são comentários
        if not isinstance(dados_raw, dict):
            sys.exit(f"{caminho}: a regra de '{nome}' deve ser um objeto.")
        d = cast(dict[str, Any], dados_raw)

        acao = str(d.get("acao", "clicar")).lower()
        if acao not in ACOES_VALIDAS:
            sys.exit(f"{caminho}: ação inválida em '{nome}': {acao!r} "
                     f"(use: {', '.join(ACOES_VALIDAS)}).")

        destino: Optional[tuple[int, int]] = None
        destino_janela: Optional[tuple[float, float]] = None
        destino_ancora: Optional[tuple[str, int, int]] = None
        formatos = ('deve ser [x, y], {"janela": [fx, fy]} ou '
                    '{"ancora": "nome_do_png", "offset": [dx, dy]}')
        if "destino" in d:
            dr: Any = d["destino"]
            if isinstance(dr, list) and len(cast(list[Any], dr)) == 2:
                lista = cast(list[Any], dr)
                destino = (int(lista[0]), int(lista[1]))
            elif isinstance(dr, dict):
                dd = cast(dict[str, Any], dr)
                if "janela" in dd:
                    jr: Any = dd["janela"]
                    if not (isinstance(jr, list) and len(cast(list[Any], jr)) == 2):
                        sys.exit(f'{caminho}: "janela" em destino de \'{nome}\' deve ser [fx, fy] '
                                 "(frações de 0 a 1 da janela).")
                    jl = cast(list[Any], jr)
                    fx, fy = float(jl[0]), float(jl[1])
                    if not (0.0 <= fx <= 1.0 and 0.0 <= fy <= 1.0):
                        sys.exit(f"{caminho}: destino.janela de '{nome}' deve ter valores entre "
                                 "0 e 1 (fração da largura e da altura da janela).")
                    destino_janela = (fx, fy)
                elif "ancora" in dd:
                    orr2: Any = dd.get("offset", [0, 0])
                    if not (isinstance(orr2, list) and len(cast(list[Any], orr2)) == 2):
                        sys.exit(f"{caminho}: destino.offset de '{nome}' deve ser [dx, dy].")
                    ol2 = cast(list[Any], orr2)
                    destino_ancora = (str(dd["ancora"]), int(ol2[0]), int(ol2[1]))
                else:
                    sys.exit(f"{caminho}: 'destino' de '{nome}' {formatos}.")
            else:
                sys.exit(f"{caminho}: 'destino' de '{nome}' {formatos}.")
        if acao == "arrastar" and destino is None and destino_janela is None \
                and destino_ancora is None:
            sys.exit(f"{caminho}: '{nome}' é 'arrastar' mas não tem 'destino'.")

        offset = (0, 0)
        if "offset" in d:
            orr: Any = d["offset"]
            if not (isinstance(orr, list) and len(cast(list[Any], orr)) == 2):
                sys.exit(f"{caminho}: 'offset' de '{nome}' deve ser [dx, dy].")
            ol = cast(list[Any], orr)
            offset = (int(ol[0]), int(ol[1]))

        intervalo: Optional[float] = (
            float(d["intervalo"]) if d.get("intervalo") is not None else None
        )
        auto_raw: Any = d.get("auto_detect")
        if auto_raw is not None and not isinstance(auto_raw, bool):
            sys.exit(f"{caminho}: 'auto_detect' de '{nome}' deve ser true ou false.")
        escolha_raw: Any = d.get("escolha")
        grupo_raw: Any = d.get("grupo")
        if escolha_raw is None and grupo_raw is not None:
            escolha_raw = "primeiro"
        if escolha_raw is not None and escolha_raw not in ESCOLHAS_VALIDAS:
            sys.exit(f"{caminho}: 'escolha' de '{nome}' deve ser uma de: "
                     f"{', '.join(ESCOLHAS_VALIDAS)}.")
        reiniciar_raw: Any = d.get("reiniciar_loop", False)
        if not isinstance(reiniciar_raw, bool):
            sys.exit(f"{caminho}: 'reiniciar_loop' de '{nome}' deve ser true ou false.")
        regras[nome] = Regra(
            escolha=cast(Optional[str], escolha_raw),
            grupo=str(grupo_raw) if grupo_raw is not None else None,
            reiniciar_loop=reiniciar_raw,
            auto_detect=auto_raw,
            acao=acao,
            vezes=int(d.get("vezes", 1 if acao == "arrastar" else 0)),
            intervalo=intervalo,
            destino=destino,
            destino_janela=destino_janela,
            destino_ancora=destino_ancora,
            offset=offset,
            confirmar_cinza=bool(d.get("confirmar_cinza", acao == "arrastar")),
            queda_saturacao=float(d.get("queda_saturacao", 0.5)),
            tentativas=int(d.get("tentativas", 3)),
            espera_confirmacao=float(d.get("espera_confirmacao", 0.7)),
        )
    return regras


def carregar_janela_config(caminho: str) -> Optional[str]:
    """Lê "_janela": "Título" do botoes.json (a mesma opção do --janela)."""
    p = Path(caminho)
    if not p.is_file():
        return None
    try:
        bruto: Any = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(bruto, dict):
        v = cast(dict[str, Any], bruto).get("_janela")
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _dentro_da_tela(p: tuple[int, int]) -> bool:
    """True se o ponto cai dentro da área de tela (se não der para saber, True)."""
    try:
        vx, vy, vw, vh = limites_tela()
    except Exception:
        return True
    return vx <= p[0] < vx + vw and vy <= p[1] < vy + vh


# nome -> (x_tela, y_tela, tela_px_por_px_do_png_x, idem_y, quando_visto)
Ancora = tuple[float, float, float, float, float]


def resolver_destino(
    r: Regra,
    janela: Optional[Regiao],
    ancoras: dict[str, Ancora],
    agora: float,
    validade: float = 5.0,
) -> tuple[Optional[tuple[int, int]], str]:
    """Converte o destino da regra em coordenadas de tela AGORA.

    - fixo:    o próprio (x, y);
    - janela:  esquerda/topo da janela + fração * largura/altura (acompanha mover/redimensionar);
    - âncora:  posição atual da imagem de referência + deslocamento (acompanha a câmera).
    Devolve (ponto, "") ou (None, motivo) se não der para calcular agora.
    """
    if r.destino is not None:
        return r.destino, ""
    if r.destino_janela is not None:
        if janela is None:
            return None, "janela do jogo não encontrada"
        fx, fy = r.destino_janela
        return (round(janela[0] + fx * janela[2]), round(janela[1] + fy * janela[3])), ""
    if r.destino_ancora is not None:
        nome, dx, dy = r.destino_ancora
        a = ancoras.get(nome)
        if a is None or agora - a[4] > validade:
            return None, f"a âncora '{nome}' não está visível"
        return (round(a[0] + dx * a[2]), round(a[1] + dy * a[3])), ""
    return None, "regra sem destino"


class Escolhedor:
    """"Escolha UM": vários botões parecidos aparecem juntos (ex.: 3 cartas) e basta
    clicar em um, uma vez por aparição.

    Regras com "escolha" (e opcionalmente "grupo") competem entre si: a cada varredura
    só um dos botões do grupo é liberado para clique. Depois do clique o grupo fica
    travado até todos sumirem da tela por 'rearme' segundos (nova aparição). Se o grupo
    continuar à vista 'retentar_apos' segundos depois do clique, o clique é considerado
    perdido e uma nova escolha é liberada.
    """

    def __init__(self, rearme: float = 2.0, retentar_apos: float = 8.0) -> None:
        self.rearme, self.retentar_apos = rearme, retentar_apos
        self._travados: dict[str, float] = {}  # grupo -> quando foi clicado
        self._visto: dict[str, float] = {}  # grupo -> última vez à vista

    @staticmethod
    def grupo_de(h: Hit, regras: dict[str, Regra]) -> Optional[str]:
        r = regras.get(h.rotulo)
        if r is None or r.escolha is None:
            return None
        return r.grupo or h.rotulo

    def filtrar(self, hits: list[Hit], regras: dict[str, Regra], agora: float) -> list[Hit]:
        por_grupo: dict[str, list[Hit]] = {}
        livres: list[Hit] = []
        for h in hits:
            g = self.grupo_de(h, regras)
            if g is None:
                livres.append(h)
            else:
                por_grupo.setdefault(g, []).append(h)
        for g in list(self._travados):  # destrava quem sumiu (ou não respondeu ao clique)
            if g not in por_grupo and agora - self._visto.get(g, 0.0) >= self.rearme:
                del self._travados[g]
            elif g in por_grupo and agora - self._travados[g] >= self.retentar_apos:
                del self._travados[g]
        for g, lista in por_grupo.items():
            self._visto[g] = agora
            if g in self._travados:
                continue
            modo = regras[lista[0].rotulo].escolha
            ordenados = sorted(lista, key=lambda k: (k.x, k.y))
            if modo == "ultimo":
                livres.append(ordenados[-1])
            elif modo == "aleatorio":
                livres.append(random.choice(ordenados))
            else:
                livres.append(ordenados[0])
        return livres

    def travar(self, h: Hit, regras: dict[str, Regra], agora: float) -> None:
        g = self.grupo_de(h, regras)
        if g is not None:
            self._travados[g] = agora
            self._visto[g] = agora


@dataclass
class Estado:
    """Memória da partida atual: o que já foi feito e o que desistimos de fazer."""

    partida: int = 1
    feitos: dict[str, int] = field(default_factory=lambda: {})
    tentativas: dict[str, int] = field(default_factory=lambda: {})
    desistiu: set[str] = field(default_factory=lambda: set())
    inicio_visivel: bool = False

    def zerar(self) -> None:
        self.partida += 1
        self.feitos.clear()
        self.tentativas.clear()
        self.desistiu.clear()


class Registro:
    """Log CSV das ações automáticas: horário, tempo desde o início e coordenadas."""

    CABECALHO = ["horario", "t_seg", "tipo", "botao", "x", "y", "x2", "y2", "detalhe"]

    def __init__(self, caminho: Optional[str]) -> None:
        self.inicio = time.time()
        self._arq: Optional[Any] = None
        self._w: Optional[Any] = None
        self._trava = threading.Lock()
        if caminho:
            p = Path(caminho)
            p.parent.mkdir(parents=True, exist_ok=True)
            novo = (not p.exists()) or p.stat().st_size == 0
            self._arq = p.open("a", newline="", encoding="utf-8")
            self._w = csv.writer(self._arq)
            if novo:
                self._w.writerow(self.CABECALHO)
                self._arq.flush()

    def log(
        self,
        tipo: str,
        botao: str = "",
        x: Optional[int] = None,
        y: Optional[int] = None,
        x2: Optional[int] = None,
        y2: Optional[int] = None,
        detalhe: str = "",
    ) -> None:
        with self._trava:
            self._escrever(tipo, botao, x, y, x2, y2, detalhe)

    def _escrever(
        self, tipo: str, botao: str, x: Optional[int], y: Optional[int],
        x2: Optional[int], y2: Optional[int], detalhe: str,
    ) -> None:
        if self._w is None or self._arq is None:
            return
        agora = time.time()
        self._w.writerow([
            datetime.now().isoformat(timespec="milliseconds"),
            f"{agora - self.inicio:.3f}",
            tipo,
            botao,
            "" if x is None else x,
            "" if y is None else y,
            "" if x2 is None else x2,
            "" if y2 is None else y2,
            detalhe,
        ])
        self._arq.flush()

    @property
    def ativo(self) -> bool:
        return self._w is not None

    def fechar(self) -> None:
        with self._trava:
            if self._arq is not None:
                self._arq.close()
            self._arq = None
            self._w = None


def para_tela(
    h: Hit, dx: int, dy: int, esc_x: float, esc_y: float, off_x: int, off_y: int
) -> tuple[int, int]:
    """Converte o ponto de clique de um Hit (pixels da imagem) para coordenadas de tela."""
    cx, cy = ponto_de_clique(h, dx, dy)
    return round(off_x + cx * esc_x), round(off_y + cy * esc_y)


# --------------------------------------------------------------------------- #
# Confirmação "o botão ficou cinza"
# --------------------------------------------------------------------------- #
def saturacao_media(img: Img, h: Hit) -> float:
    """Saturação média (0-255) da região do botão. Botão cinza => perto de 0."""
    x0, y0 = max(0, h.x), max(0, h.y)
    crop = img[y0:max(y0, h.y + h.h), x0:max(x0, h.x + h.w)]
    if crop.size == 0:
        return 0.0
    hsv = cast(Img, cv2.cvtColor(crop, cv2.COLOR_BGR2HSV))
    return float(hsv[:, :, 1].mean())


def ficou_cinza(antes: float, depois: float, queda: float) -> Optional[bool]:
    """True/False se a saturação caiu o bastante; None se não dá para decidir.

    Se o botão já era pouco colorido antes (saturação < 15), a comparação não
    prova nada, então devolve None.
    """
    if antes < 15.0:
        return None
    return depois <= antes * queda


def verificar_cinza(
    h: Hit, antes: float, regra: Regra, monitor: int, regiao: Optional[Regiao]
) -> tuple[Optional[bool], float]:
    """Espera um pouco, recaptura a região do botão e compara a saturação."""
    time.sleep(regra.espera_confirmacao)
    img2, _, _, _, _ = capturar(monitor, regiao)
    depois = saturacao_media(img2, h)
    return ficou_cinza(antes, depois, regra.queda_saturacao), depois


# --------------------------------------------------------------------------- #
# Teclado/mouse físicos (Windows) usados por gravar e reproduzir
# --------------------------------------------------------------------------- #
def _tecla_pressionada(vk: int) -> bool:
    u, _ = _api()
    return bool(u.GetAsyncKeyState(vk) & 0x8000)


def _abortar() -> bool:
    """F9 ou mouse no canto superior esquerdo."""
    x, y = posicao()
    return _tecla_pressionada(VK_F9) or (x <= 1 and y <= 1)


def _monitorar_teclado_no_log(parar: threading.Event, registro: Registro) -> None:
    """Em segundo plano, anota no --log as teclas que VOCÊ aperta enquanto o robô roda."""
    mon = MonitorTeclado()
    while not parar.is_set():
        try:
            for estado, vk in mon.varrer(time.time()):
                registro.log("tecla", nome_tecla(vk), detalhe=estado)
        except Exception:
            pass
        parar.wait(0.01)


# --------------------------------------------------------------------------- #
# Modo gravar: grava os SEUS cliques e arrastos (coordenadas + tempo)
# --------------------------------------------------------------------------- #
Caixa = tuple[int, int, int, int]


def geometria_monitor(idx: int) -> tuple[int, int, int, int]:
    """(esquerda, topo, largura, altura) do monitor, em coordenadas de tela."""
    mss_cls: Any = getattr(mss_lib, "MSS", None) or mss_lib.mss
    with mss_cls() as sct:
        m: dict[str, int] = dict(sct.monitors[idx])
    return m["left"], m["top"], m["width"], m["height"]


def regiao_da_janela(rect: Regiao, monitor: int) -> Optional[Regiao]:
    """Converte a área da janela (coordenadas de tela) numa região relativa ao monitor,
    recortada para caber nele. None se quase nada da janela está visível."""
    ml, mt, mw, mh = geometria_monitor(monitor)
    x0, y0 = max(rect[0], ml), max(rect[1], mt)
    x1, y1 = min(rect[0] + rect[2], ml + mw), min(rect[1] + rect[3], mt + mh)
    if x1 - x0 < 20 or y1 - y0 < 20:
        return None
    return x0 - ml, y0 - mt, x1 - x0, y1 - y0


def _rect_seguro(titulo: Optional[str]) -> Optional[Regiao]:
    """rect_da_janela que nunca levanta erro (None se não achar ou fora do Windows)."""
    if not titulo:
        return None
    try:
        return rect_da_janela(titulo)
    except Exception:
        return None


def _varredura_continua(
    parar: threading.Event,
    trava: threading.Lock,
    conhecidos: dict[str, tuple[Caixa, float]],
    pasta: str,
    confianca: float,
    monitor: int,
    regiao: Optional[Regiao],
    centros: Optional[dict[str, Ancora]] = None,
) -> None:
    """Em segundo plano, lembra onde cada botão da pasta foi visto por último.

    Quando o mouse está em cima, o botão muda de aparência e deixa de ser
    reconhecido; por isso guardamos a última posição vista ANTES do hover.
    """
    while not parar.is_set():
        try:
            img, ex, ey, ox, oy = capturar(monitor, regiao)
            for h in detectar_imagens(img, pasta, confianca):
                caixa: Caixa = (
                    round(ox + h.x * ex),
                    round(oy + h.y * ey),
                    round(ox + (h.x + h.w) * ex),
                    round(oy + (h.y + h.h) * ey),
                )
                agora = time.time()
                with trava:
                    conhecidos[h.rotulo] = (caixa, agora)
                    if centros is not None:
                        centros[h.rotulo] = (
                            (caixa[0] + caixa[2]) / 2, (caixa[1] + caixa[3]) / 2,
                            h.escala * ex, h.escala * ey, agora,
                        )
        except Exception:
            pass  # uma falha de captura não pode derrubar a gravação
        parar.wait(0.4)


def _identificar(
    x: int,
    y: int,
    trava: threading.Lock,
    conhecidos: dict[str, tuple[Caixa, float]],
    janela: float = 20.0,
) -> Optional[str]:
    agora = time.time()
    melhor: Optional[tuple[float, str]] = None
    with trava:
        for rot, (caixa, ts) in conhecidos.items():
            if agora - ts > janela:
                continue
            x0, y0, x1, y1 = caixa
            if x0 - 6 <= x <= x1 + 6 and y0 - 6 <= y <= y1 + 6:
                if melhor is None or ts > melhor[0]:
                    melhor = (ts, rot)
    return melhor[1] if melhor is not None else None


def _frac(x: int, y: int, rect: Optional[Regiao]) -> Optional[tuple[float, float]]:
    """Posição (x, y) como fração da janela; None se a janela não é conhecida."""
    if rect is None:
        return None
    return round((x - rect[0]) / rect[2], 5), round((y - rect[1]) / rect[3], 5)


def gravar(
    arquivo: str,
    pasta: str,
    confianca: float,
    monitor: int,
    regiao: Optional[Regiao],
    duracao: float,
    atraso: float,
    limiar_arrasto: int = 12,
    janela: Optional[str] = None,
    ancora: Optional[str] = None,
    teclado: bool = True,
) -> list[dict[str, Any]]:
    """Grava seus cliques, arrastos e (opcional) teclas, com coordenadas e tempo.

    Se houver uma janela (--janela, ou detectada no 1º clique), cada ponto também é
    salvo como fração da janela: assim a gravação e as regras geradas continuam valendo
    se a janela mudar de lugar ou de tamanho. Com --ancora, o ponto de soltura dos
    arrastos também é salvo relativo a essa imagem do mapa (acompanha a câmera).
    """
    if sys.platform != "win32":
        sys.exit("O modo 'gravar' só funciona no Windows.")

    pngs: list[Path] = []
    if Path(pasta).is_dir():
        pngs = sorted(Path(pasta).glob("*.png")) + sorted(Path(pasta).glob("*.jpg"))

    parar = threading.Event()
    trava = threading.Lock()
    conhecidos: dict[str, tuple[Caixa, float]] = {}
    centros: dict[str, Ancora] = {}
    worker: Optional[threading.Thread] = None
    if pngs:
        worker = threading.Thread(
            target=_varredura_continua,
            args=(parar, trava, conhecidos, pasta, confianca, monitor, regiao, centros),
            daemon=True,
        )
        worker.start()
        print(f"Identificando os botões da pasta '{pasta}' ({len(pngs)} imagem(ns)) "
              "para dar nome aos cliques.")
    else:
        print(f"Aviso: sem imagens em '{pasta}'; os cliques serão gravados sem nome de botão.")
    if ancora and not any(p.stem == ancora for p in pngs):
        print(f"Aviso: não há '{ancora}.png' em '{pasta}'; os arrastos não terão âncora.")

    for i in range(int(atraso), 0, -1):
        print(f"Começando em {i}...")
        time.sleep(1)
    print("● GRAVANDO. Jogue normalmente. Aperte F9 para parar."
          + (" (teclas também são gravadas)" if teclado else ""))

    titulo = janela
    rect_ultimo: Optional[Regiao] = _rect_seguro(titulo)
    mon_tec = MonitorTeclado() if teclado else None
    eventos: list[dict[str, Any]] = []
    abertos: dict[int, tuple[float, int, int, Optional[str], Optional[Regiao]]] = {}
    t0 = time.time()

    def _hora(t: float) -> str:
        return f"{int(t // 60):02d}:{t % 60:06.3f}"

    try:
        while True:
            agora = time.time()
            if _tecla_pressionada(VK_F9) or (duracao and agora - t0 > duracao):
                break
            for vk, nome in ((VK_ESQUERDO, "esquerdo"), (VK_DIREITO, "direito")):
                premido = _tecla_pressionada(vk)
                if premido and vk not in abertos:
                    x, y = posicao()
                    if titulo is None:
                        titulo = titulo_sob_ponto(x, y)
                        if titulo:
                            print(f"Janela detectada: '{titulo}' (para outra, use --janela).")
                    rect = _rect_seguro(titulo)
                    abertos[vk] = (agora - t0, x, y, _identificar(x, y, trava, conhecidos), rect)
                elif (not premido) and vk in abertos:
                    t_ini, x, y, rot, rect_ini = abertos.pop(vk)
                    x2, y2 = posicao()
                    rect_fim = _rect_seguro(titulo)
                    rect_ultimo = rect_fim or rect_ini or rect_ultimo
                    dur = (agora - t0) - t_ini
                    tipo = "arrasto" if math.hypot(x2 - x, y2 - y) >= limiar_arrasto else "clique"
                    ev: dict[str, Any] = {
                        "t": round(t_ini, 3),
                        "tipo": tipo,
                        "mouse": nome,
                        "x": x,
                        "y": y,
                        "x2": x2,
                        "y2": y2,
                        "duracao": round(dur, 3),
                        "botao": rot,
                    }
                    f1 = _frac(x, y, rect_ini)
                    f2 = _frac(x2, y2, rect_fim)
                    if f1 is not None:
                        ev["fx"], ev["fy"] = f1
                    if f2 is not None:
                        ev["fx2"], ev["fy2"] = f2
                    if ancora and tipo == "arrasto":
                        with trava:
                            c = centros.get(ancora)
                        if c is not None and agora - c[4] <= 20.0 and c[2] > 0 and c[3] > 0:
                            ev["ancora"] = {
                                "nome": ancora,
                                "dx": round((x2 - c[0]) / c[2]),
                                "dy": round((y2 - c[1]) / c[3]),
                            }
                        else:
                            print(f"  Aviso: a âncora '{ancora}' não estava visível; "
                                  "este arrasto fica sem âncora.")
                    eventos.append(ev)
                    sufixo = f"  [{rot}]" if rot else ""
                    if tipo == "arrasto":
                        print(f"[{_hora(t_ini)}] arrasto {nome} ({x},{y}) -> ({x2},{y2}) "
                              f"em {dur:.2f}s{sufixo}")
                    else:
                        print(f"[{_hora(t_ini)}] clique {nome} em ({x},{y}){sufixo}")
            if mon_tec is not None:
                for estado, vk in mon_tec.varrer(agora):
                    if titulo is None:
                        titulo = titulo_ativo()
                    t_ev = agora - t0
                    eventos.append({"t": round(t_ev, 3), "tipo": "tecla",
                                    "tecla": nome_tecla(vk), "vk": vk, "estado": estado})
                    print(f"[{_hora(t_ev)}] tecla {nome_tecla(vk)} "
                          f"{'↓' if estado == 'baixo' else '↑'}")
            time.sleep(0.005)
    except KeyboardInterrupt:
        pass
    finally:
        parar.set()
        if worker is not None:
            worker.join(timeout=2)

    if mon_tec is not None:  # teclas ainda apertadas quando o F9 foi pressionado
        t_fim = round(time.time() - t0, 3)
        for vk in list(mon_tec.premidas):
            eventos.append({"t": t_fim, "tipo": "tecla", "tecla": nome_tecla(vk),
                            "vk": vk, "estado": "cima"})
    eventos.sort(key=lambda e: float(e["t"]))

    dados = {
        "versao": 2,
        "criado": datetime.now().isoformat(timespec="seconds"),
        "monitor": monitor,
        "janela": {"titulo": titulo, "rect": list(rect_ultimo) if rect_ultimo else None},
        "eventos": eventos,
    }
    Path(arquivo).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    mouse_ev = [e for e in eventos if e["tipo"] != "tecla"]
    teclas = len(eventos) - len(mouse_ev)
    sem_nome = sum(1 for e in mouse_ev if not e["botao"])
    print(f"\nGravação salva em '{arquivo}': {len(mouse_ev)} clique(s)/arrasto(s) "
          f"({sem_nome} sem nome de botão) e {teclas} evento(s) de tecla."
          + (f" Janela: '{titulo}'." if titulo else " Sem janela identificada."))
    return eventos


def gerar_regras(
    eventos: list[dict[str, Any]],
    config: str,
    sobrescrever: bool,
    janela: Optional[str] = None,
) -> None:
    """Transforma a gravação em regras no botoes.json (sem apagar as existentes).

    O destino de cada arrasto é gravado do jeito mais robusto disponível:
    âncora (se usou --ancora) > fração da janela > coordenada fixa de tela.
    """
    p = Path(config)
    atual: dict[str, Any] = {}
    if p.is_file():
        try:
            carregado: Any = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit(f"{config}: JSON inválido ({e}); corrija antes de gerar regras.")
        if isinstance(carregado, dict):
            atual = cast(dict[str, Any], carregado)

    novas: dict[str, dict[str, Any]] = {}
    sem_nome = 0
    tipos_destino: set[str] = set()
    for ev in eventos:
        if ev.get("tipo") == "tecla":
            continue
        rot = ev.get("botao")
        if not rot:
            sem_nome += 1
            continue
        if ev["tipo"] == "arrasto":
            destino: Any
            anc = ev.get("ancora")
            if isinstance(anc, dict):
                a = cast(dict[str, Any], anc)
                destino = {"ancora": a["nome"], "offset": [a["dx"], a["dy"]]}
                novas.setdefault(str(a["nome"]), {"acao": "ancora"})
                tipos_destino.add("ancora")
            elif "fx2" in ev and "fy2" in ev:
                destino = {"janela": [ev["fx2"], ev["fy2"]]}
                tipos_destino.add("janela")
            else:
                destino = [ev["x2"], ev["y2"]]
                tipos_destino.add("fixo")
            novas[str(rot)] = {"acao": "arrastar", "destino": destino, "vezes": 1}
        elif str(rot) not in novas:
            novas[str(rot)] = {"acao": "clicar"}

    escritas: list[str] = []
    mantidas: list[str] = []
    for rot, regra in novas.items():
        if rot in atual and not sobrescrever:
            mantidas.append(rot)
            continue
        atual[rot] = regra
        escritas.append(rot)
    if janela and "janela" in tipos_destino and "_janela" not in atual:
        atual["_janela"] = janela  # o programa usa isso como --janela automaticamente

    p.write_text(json.dumps(atual, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Regras em '{config}': {len(escritas)} gravada(s)"
          + (f" ({', '.join(escritas)})" if escritas else "") + ".")
    if mantidas:
        print(f"  Já existiam e foram mantidas: {', '.join(mantidas)} "
              "(use --sobrescrever para trocar).")
    if sem_nome:
        print(f"  {sem_nome} evento(s) sem nome de botão não geraram regra "
              "(o clique não foi sobre nenhum PNG da pasta).")
    if "fixo" in tipos_destino:
        print("  Aviso: há destino(s) em coordenada FIXA de tela (a janela não foi identificada); "
              "grave de novo com --janela para o destino acompanhar a janela.")
    if "janela" in tipos_destino:
        print("  Destino(s) relativos à janela: rode o programa com --janela "
              + (f"\"{janela}\"" if janela else "\"Título\"") + " (ou use \"_janela\" no json).")


# --------------------------------------------------------------------------- #
# Modo reproduzir: refaz uma gravação (coordenadas, teclas e tempos)
# --------------------------------------------------------------------------- #
def _ponto_do_evento(ev: dict[str, Any], suf: str, rect: Optional[Regiao]) -> tuple[int, int]:
    """Ponto do evento: pela fração da janela atual (se conhecida), senão absoluto."""
    fx, fy = ev.get("fx" + suf), ev.get("fy" + suf)
    if rect is not None and fx is not None and fy is not None:
        return round(rect[0] + float(fx) * rect[2]), round(rect[1] + float(fy) * rect[3])
    return int(ev["x" + suf]), int(ev["y" + suf])


def _garantir_janela(titulo: str, espera_max: float) -> Optional[float]:
    """Espera a janela ficar ativa (tentando trazê-la para frente).

    Devolve os segundos esperados, ou None se foi abortado / estourou o tempo.
    """
    if janela_ativa(titulo):
        return 0.0
    inicio = time.time()
    avisou = False
    while True:
        hwnd = achar_janela(titulo)
        if hwnd is not None:
            try:
                focar_hwnd(hwnd)
            except Exception:
                pass
            if janela_ativa(titulo):
                if avisou:
                    print("  Janela ativa de novo; continuando.")
                return time.time() - inicio
        if not avisou:
            print(f"  A janela '{titulo}' não está ativa; aguardando "
                  "(F9 ou mouse no canto para parar)...")
            avisou = True
        if _abortar():
            return None
        if espera_max and time.time() - inicio > espera_max:
            print(f"  A janela '{titulo}' não ficou ativa em {espera_max:g}s; parando.")
            return None
        time.sleep(0.3)


class VigiaBotoes:
    """Durante a reprodução: clica sozinho nos botões com "auto_detect": true.

    Roda em segundo plano, olhando a tela. Enquanto algum desses botões está visível, ele
    clica (respeitando "intervalo", "vezes" e "offset" da regra) e a reprodução fica em
    pausa, para continuar só quando o botão sumir. Mouse e teclado da reprodução e os
    cliques daqui nunca se misturam: ambos usam a mesma trava.
    """

    def __init__(
        self,
        regras: dict[str, Regra],
        pasta: str,
        confianca: float,
        monitor: int,
        regiao: Optional[Regiao],
        titulo: Optional[str],
        checar_janela: bool,
        travar: threading.Lock,
        registro: Optional[Registro] = None,
        cooldown: float = 0.8,
        intervalo: float = 0.4,
        graca: float = 1.0,
        max_continuo: float = 120.0,
        espera_hover: float = 0.25,
    ) -> None:
        self.regras = {n: r for n, r in regras.items() if r.auto_detect is True and r.acao == "clicar"}
        self.pasta, self.confianca, self.monitor = pasta, confianca, monitor
        self.regiao, self.titulo, self.checar_janela = regiao, titulo, checar_janela
        self.travar = travar
        self.registro = registro
        self.cooldown, self.intervalo, self.graca = cooldown, intervalo, graca
        self.max_continuo, self.espera_hover = max_continuo, espera_hover
        self.cliques = 0
        self._feitos: dict[str, int] = {}
        self._recentes: dict[str, float] = {}
        self._ocupado_ate = 0.0
        self._ocupado_desde: Optional[float] = None
        self._suspenso_ate = 0.0
        self._reinicio: Optional[str] = None
        self.escolhedor = Escolhedor()
        self._parar = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def nomes(self) -> list[str]:
        return sorted(self.regras)

    def ocupado(self) -> bool:
        """True enquanto há botão automático à vista (a reprodução deve esperar)."""
        return time.time() < self._ocupado_ate

    def aguardar_livre(self) -> Optional[float]:
        """Espera o botão sumir. Devolve os segundos esperados, ou None se abortou."""
        ini = time.time()
        while self.ocupado():
            if _abortar():
                return None
            time.sleep(0.05)
        return time.time() - ini

    def pegar_reinicio(self) -> Optional[str]:
        """Nome do botão 'reiniciar_loop' clicado automaticamente (uma vez; limpa o pedido)."""
        r, self._reinicio = self._reinicio, None
        return r

    def _livre(self) -> None:
        self._ocupado_desde = None
        self._ocupado_ate = 0.0

    def varrer_uma_vez(self) -> None:
        agora = time.time()
        if agora < self._suspenso_ate:
            return
        if self.titulo and self.checar_janela and not janela_ativa(self.titulo):
            self._livre()  # o jogo não está à frente: não briga com o que você está fazendo
            return
        regiao = self.regiao
        if self.titulo:
            rect = _rect_seguro(self.titulo)
            regiao = regiao_da_janela(rect, self.monitor) if rect else None
            if regiao is None:
                self._livre()
                return
        img, ex, ey, ox, oy = capturar(self.monitor, regiao)
        alvos = [h for h in detectar_imagens(img, self.pasta, self.confianca)
                 if h.rotulo in self.regras]
        alvos = self.escolhedor.filtrar(alvos, self.regras, agora)
        if not alvos:
            self._livre()
            return
        if self._ocupado_desde is None:
            self._ocupado_desde = agora
        elif agora - self._ocupado_desde > self.max_continuo:
            print(f"[{time.strftime('%H:%M:%S')}] auto_detect: botão à vista há mais de "
                  f"{self.max_continuo:g}s; pausando a vigia por 30s para a reprodução seguir")
            self._suspenso_ate = agora + 30.0
            self._livre()
            return
        self._ocupado_ate = agora + self.graca
        for h in alvos:
            r = self.regras[h.rotulo]
            if r.vezes and self._feitos.get(h.rotulo, 0) >= r.vezes:
                continue
            espera = r.intervalo if r.intervalo is not None else self.cooldown
            if r.reiniciar_loop:
                espera = max(espera, 5.0)
            if agora - self._recentes.get(h.rotulo, 0.0) < espera:
                continue
            sx, sy = para_tela(h, r.offset[0], r.offset[1], ex, ey, ox, oy)
            confirmar = partial(ainda_no_lugar, h, self.monitor, regiao, self.pasta,
                                max(0.6, self.confianca - 0.05))
            with self.travar:
                feito = clicar(h, ex, ey, ox, oy, self.espera_hover, 0.08, r.offset[0],
                               r.offset[1], 0.0, True, False, confirmar, True, None)
            if not feito:
                continue
            self._recentes[h.rotulo] = time.time()
            if r.escolha is not None:
                self.escolhedor.travar(h, self.regras, time.time())
            if r.reiniciar_loop:
                self._reinicio = h.rotulo
            self._feitos[h.rotulo] = self._feitos.get(h.rotulo, 0) + 1
            self.cliques += 1
            self._ocupado_ate = time.time() + self.graca
            print(f"[{time.strftime('%H:%M:%S')}] auto_detect: clique em {h.rotulo} ({sx}, {sy})")
            if self.registro is not None:
                self.registro.log("clique_auto", h.rotulo, sx, sy, detalhe="auto_detect (reprodução)")

    def _loop(self) -> None:
        while not self._parar.is_set():
            try:
                self.varrer_uma_vez()
            except FailSafe:
                return
            except Exception as e:  # uma falha de captura não derruba a reprodução
                print(f"auto_detect: erro ao varrer a tela ({type(e).__name__}: {e})")
                self._parar.wait(2.0)
            self._parar.wait(self.intervalo)

    def iniciar(self) -> None:
        self.varrer_uma_vez()  # já olha uma vez antes da reprodução começar
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        if self._thread is not None:
            self._thread.join(timeout=3)


def reproduzir(
    arquivo: str,
    velocidade: float,
    atraso: float,
    loop: Optional[int] = None,
    pausa_loop: float = 1.0,
    janela: Optional[str] = None,
    checar_janela: bool = True,
    espera_janela: float = 60.0,
    teclas: bool = True,
    config: str = "botoes.json",
    pasta: str = "botoes",
    confianca: float = 0.85,
    monitor: int = 1,
    auto_detect: bool = True,
    auto_max: float = 120.0,
    registro: Optional[Registro] = None,
    intervalo_vigia: float = 0.4,
    graca: float = 1.0,
) -> None:
    """Refaz a gravação.

    loop: None = uma vez; 0 = repete até F9; N = N vezes.
    auto_detect: botões do botoes.json com "auto_detect": true são clicados assim que
    aparecem; a reprodução espera enquanto algum estiver à vista.
    Antes de cada evento confere se a janela do jogo está ativa; se não estiver, tenta
    trazê-la para frente e, se não conseguir, PAUSA até ela voltar (sem perder o ritmo).
    """
    if sys.platform != "win32":
        sys.exit("O modo 'reproduzir' só funciona no Windows.")
    p = Path(arquivo)
    if not p.is_file():
        sys.exit(f"Gravação '{arquivo}' não encontrada.")
    dados: Any = json.loads(p.read_text(encoding="utf-8"))
    eventos = cast(list[dict[str, Any]], dados.get("eventos", []))
    if not teclas:
        eventos = [e for e in eventos if e.get("tipo") != "tecla"]
    if not eventos:
        sys.exit("A gravação não tem eventos.")
    vel = max(0.1, velocidade)
    titulo = janela
    if titulo is None:
        info: Any = dados.get("janela")
        if isinstance(info, dict):
            t_gravado = cast(dict[str, Any], info).get("titulo")
            titulo = str(t_gravado) if t_gravado else None
    if titulo is None:
        if checar_janela:
            print("Aviso: a gravação não tem janela; não dá para conferir se o jogo está ativo "
                  "(use --janela \"Título\").")
    elif checar_janela:
        print(f"Só age com a janela '{titulo}' ativa (--sem-checar-janela desliga).")

    repeticoes = 1 if loop is None else max(0, loop)
    for i in range(int(atraso), 0, -1):
        print(f"Reproduzindo em {i}... (F9 ou mouse no canto superior esquerdo para parar)")
        time.sleep(1)
    print(f"▶ Reproduzindo {len(eventos)} evento(s) a {vel:g}x"
          + (" em loop (F9 para parar)." if repeticoes == 0
             else f", {repeticoes} vez(es)." if repeticoes > 1 else "."))

    presas: set[int] = set()  # teclas que nós apertamos e ainda não soltamos
    travar = threading.Lock()  # mouse/teclado: ou a reprodução, ou a vigia, nunca os dois
    vigia: Optional[VigiaBotoes] = None
    if auto_detect:
        regras_auto = carregar_regras(config)
        candidatos = VigiaBotoes(regras_auto, pasta, confianca, monitor, None, titulo,
                                 checar_janela, travar, registro, intervalo=intervalo_vigia,
                                 graca=graca, max_continuo=auto_max)
        if candidatos.nomes:
            if not Path(pasta).is_dir():
                print(f"Aviso: pasta '{pasta}' não existe; auto_detect desligado.")
            else:
                vigia = candidatos
                print("auto_detect ligado para: " + ", ".join(vigia.nomes)
                      + " (a reprodução espera enquanto eles estiverem à vista).")
    volta = 0
    # Botões "reiniciar_loop" já clicados pela vigia: o clique GRAVADO neles é pulado uma vez.
    pular: set[str] = set()
    reiniciou = False

    def checar_reinicio() -> bool:
        """A vigia clicou num botão 'reiniciar_loop'? Então esta volta termina aqui."""
        nonlocal reiniciou
        if vigia is not None:
            rot = vigia.pegar_reinicio()
            if rot is not None:
                pular.add(rot)
                reiniciou = True
        return reiniciou

    try:
        if vigia is not None:
            vigia.iniciar()
        while repeticoes == 0 or volta < repeticoes:
            volta += 1
            if repeticoes != 1:
                print(f"— Volta {volta}" + (f"/{repeticoes}" if repeticoes else "") + " —")
            reiniciou = False
            if vigia is not None:  # pedido que chegou entre uma volta e outra: já estamos no início
                pendente = vigia.pegar_reinicio()
                if pendente is not None:
                    pular.add(pendente)
            t0 = time.time()
            for n, ev in enumerate(eventos, 1):
                alvo = float(ev["t"]) / vel
                while time.time() - t0 < alvo:
                    if _abortar():
                        print("Reprodução interrompida.")
                        return
                    if checar_reinicio():
                        break
                    time.sleep(0.005)
                if reiniciou:
                    break
                if _abortar():
                    print("Reprodução interrompida.")
                    return
                if titulo and checar_janela:
                    esperou = _garantir_janela(titulo, espera_janela)
                    if esperou is None:
                        print("Reprodução interrompida.")
                        return
                    t0 += esperou  # o tempo parado não conta no ritmo da gravação

                if vigia is not None:
                    livre = vigia.aguardar_livre()  # botão automático à vista: espera ele sumir
                    if livre is None:
                        print("Reprodução interrompida.")
                        return
                    t0 += livre
                    if checar_reinicio():
                        break
                if ev["tipo"] != "tecla" and ev.get("botao") in pular:
                    pular.discard(cast(str, ev["botao"]))
                    print(f"  {n}/{len(eventos)} {ev['tipo']} em [{ev['botao']}] pulado: "
                          "já foi clicado automaticamente")
                    continue
                with travar:
                    if ev["tipo"] == "tecla":
                        vk = int(ev["vk"])
                        baixo = ev.get("estado") == "baixo"
                        _enviar_tecla(vk, baixo)
                        if baixo:
                            presas.add(vk)
                        else:
                            presas.discard(vk)
                        print(f"  {n}/{len(eventos)} tecla {ev.get('tecla', vk)} "
                              f"{'↓' if baixo else '↑'}")
                        continue

                    rect = _rect_seguro(titulo)
                    x, y = _ponto_do_evento(ev, "", rect)
                    down, up = ((_RIGHTDOWN, _RIGHTUP) if ev.get("mouse") == "direito"
                                else (_LEFTDOWN, _LEFTUP))
                    dur = float(ev.get("duracao", 0.08))

                    mover_suave(x, y, duracao=0.2, passos=12)
                    time.sleep(0.05)
                    _enviar_mouse(0, 0, down)
                    try:
                        if ev["tipo"] == "arrasto":
                            x2, y2 = _ponto_do_evento(ev, "2", rect)
                            time.sleep(0.08)
                            mover_suave(x2, y2, duracao=max(0.2, dur / vel),
                                        passos=max(12, int(dur * 40)))
                            time.sleep(0.1)
                        else:
                            time.sleep(min(max(dur, 0.04), 0.3))
                    finally:
                        _enviar_mouse(0, 0, up)  # nunca deixa o botão do mouse preso
                    rot = f" [{ev['botao']}]" if ev.get("botao") else ""
                    print(f"  {n}/{len(eventos)} {ev['tipo']} em ({x},{y}){rot}")
            if reiniciou:
                with travar:
                    for vk in list(presas):  # recomeço limpo: solta o que estava apertado
                        _enviar_tecla(vk, False)
                    presas.clear()
                print("  Botão de reinício clicado: recomeçando a gravação do início"
                      + ("" if (repeticoes == 0 or volta < repeticoes) else " (fim das voltas)")
                      + ".")
                continue
            pular.clear()  # nada a pular na próxima volta
            if repeticoes == 0 or volta < repeticoes:
                fim = time.time() + max(0.0, pausa_loop)
                while time.time() < fim:
                    if _abortar():
                        print("Reprodução interrompida.")
                        return
                    time.sleep(0.02)
    finally:
        if vigia is not None:
            vigia.parar()
        for vk in list(presas):  # não deixa tecla "presa" se parar no meio
            try:
                _enviar_tecla(vk, False)
            except Exception:
                pass
    if vigia is not None:
        print(f"auto_detect: {vigia.cliques} clique(s) automático(s) durante a reprodução.")
    print("Reprodução concluída.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Autoclick inteligente baseado em visão computacional.")
    ap.add_argument("modo", choices=["texto", "imagem", "auto", "gravar", "reproduzir"])
    ap.add_argument("--palavras", nargs="+", default=PALAVRAS_PADRAO,
                    help="textos dos botões (modos texto/auto)")
    ap.add_argument("--pasta", default="botoes", help="pasta com PNGs dos botões (modo imagem)")
    ap.add_argument("--config", default="botoes.json",
                    help="regras por botão: clicar, arrastar, inicio (padrão: botoes.json)")
    ap.add_argument("--log", default=None, metavar="ARQUIVO.csv",
                    help="grava um CSV com cada ação automática (horário, coordenadas)")
    ap.add_argument("--arquivo", default="gravacao.json",
                    help="arquivo da gravação (modos gravar/reproduzir)")
    ap.add_argument("--gerar-regras", action="store_true",
                    help="modo gravar: cria/atualiza regras no --config a partir da gravação")
    ap.add_argument("--sobrescrever", action="store_true",
                    help="com --gerar-regras, troca regras que já existem")
    ap.add_argument("--velocidade", type=float, default=1.0,
                    help="modo reproduzir: 1 = tempo original, 2 = dobro da velocidade")
    ap.add_argument("--atraso", type=float, default=3.0,
                    help="modos gravar/reproduzir: segundos de contagem antes de começar")
    ap.add_argument("--confianca", type=float, default=0.85, help="0-1, modo imagem")
    ap.add_argument("--lang", default="por+eng", help="idiomas do Tesseract")
    ap.add_argument("--monitor", type=int, default=1, help="índice do monitor (1 = principal)")
    ap.add_argument("--regiao", nargs=4, type=int, metavar=("X", "Y", "L", "A"),
                    help="limita a busca a uma região da tela")
    ap.add_argument("--intervalo", type=float, default=1.5, help="segundos entre varreduras")
    ap.add_argument("--cooldown", type=float, default=10.0,
                    help="segundos antes de clicar de novo na mesma posição")
    ap.add_argument("--max-cliques", type=int, default=0, help="0 = sem limite")
    ap.add_argument("--duracao", type=float, default=0, help="para após N segundos (0 = sem limite)")
    ap.add_argument("--espera-hover", type=float, default=0.25,
                    help="segundos com o mouse parado sobre o botão antes de clicar")
    ap.add_argument("--offset", nargs=2, type=int, default=[0, 0], metavar=("DX", "DY"),
                    help="desloca o ponto de clique em pixels (ex.: --offset -5 3)")
    ap.add_argument("--jitter", type=float, default=0.0,
                    help="variação aleatória do clique como fração do botão (0 = exato)")
    ap.add_argument("--mouse", choices=["input", "pyautogui"], default="input",
                    help=argparse.SUPPRESS)  # obsoleto: agora é sempre SendInput
    ap.add_argument("--janela", default=None, metavar="TÍTULO",
                    help="título (ou parte) da janela do jogo, ex.: --janela Roblox. Limita a "
                         "busca à janela (acompanha mover/redimensionar), habilita destinos "
                         "relativos à janela e, na reprodução, confere se ela está ativa")
    ap.add_argument("--escala", default="auto", metavar="auto|N",
                    help="tamanho dos PNGs em relação à tela. auto (padrão) = descobre sozinho "
                         "(PNGs tirados no maior tamanho da janela); 1 = só tamanho original; "
                         "0.6 = força 60%%")
    ap.add_argument("--escala-min", type=float, default=0.3,
                    help="menor escala testada na busca automática (padrão 0.3)")
    ap.add_argument("--escala-max", type=float, default=1.0,
                    help="maior escala testada (padrão 1.0 = tamanho do PNG)")
    ap.add_argument("--busca-escala", type=float, default=8.0, metavar="SEG",
                    help="intervalo mínimo entre buscas completas de escala quando nada é "
                         "reconhecido (padrão 8)")
    ap.add_argument("--loop", nargs="?", type=int, const=0, default=None, metavar="N",
                    help="modo reproduzir: repete a gravação. Sem número = até apertar F9; "
                         "--loop 5 = 5 vezes")
    ap.add_argument("--pausa-loop", type=float, default=1.0, metavar="SEG",
                    help="modo reproduzir: pausa entre uma volta e outra (padrão 1)")
    ap.add_argument("--sem-checar-janela", action="store_true",
                    help="modo reproduzir: não confere se a janela do jogo está ativa")
    ap.add_argument("--espera-janela", type=float, default=60.0, metavar="SEG",
                    help="modo reproduzir: quanto esperar a janela ficar ativa antes de "
                         "desistir (0 = esperar para sempre; padrão 60)")
    ap.add_argument("--ancora", default=None, metavar="NOME",
                    help="modo gravar: nome de um PNG do mapa (sem .png) usado como referência "
                         "para o ponto de soltura dos arrastos (acompanha a câmera)")
    ap.add_argument("--sem-auto-detect", action="store_true",
                    help="modo reproduzir: ignora os botões com \"auto_detect\": true do json")
    ap.add_argument("--auto-max", type=float, default=120.0, metavar="SEG",
                    help="modo reproduzir: se um botão auto_detect ficar à vista por mais de SEG "
                         "segundos seguidos, a vigia pausa 30s para a reprodução seguir (padrão 120)")
    ap.add_argument("--sem-teclado", action="store_true",
                    help="não grava/reproduz/registra teclas (gravar, reproduzir e --log)")
    ap.add_argument("--estacionar", nargs=2, type=int, default=None, metavar=("X", "Y"),
                    help="onde deixar o mouse após cada clique (padrão: 350 px ao lado do botão)")
    ap.add_argument("--sem-estacionar", action="store_true",
                    help="deixa o mouse parado sobre o botão após o clique")
    ap.add_argument("--sem-recheck", action="store_true",
                    help="não reconfirma a posição do botão logo antes de clicar (modo imagem)")
    ap.add_argument("--sem-foco", action="store_true",
                    help="não tenta trazer a janela do botão para o primeiro plano")
    ap.add_argument("--hold", type=float, default=0.08,
                    help="segundos com o botão do mouse pressionado")
    ap.add_argument("--debug", action="store_true",
                    help="mostra detalhes (palavras lidas pelo OCR, saturação, foco)")
    ap.add_argument("--tesseract", default="",
                    help=r"caminho do tesseract.exe se não estiver no PATH")
    ap.add_argument("--preview", action="store_true",
                    help="não clica; salva preview.png e mostra o que foi detectado")
    args = ap.parse_args()

    modo = str(args.modo)
    palavras = [str(p) for p in cast(list[Any], args.palavras)]
    pasta = str(args.pasta)
    config = str(args.config)
    log_caminho = cast(Optional[str], args.log)
    arquivo = str(args.arquivo)
    confianca = float(args.confianca)
    lang = str(args.lang)
    monitor = int(args.monitor)
    regiao_raw = cast(Optional[list[int]], args.regiao)
    regiao: Optional[Regiao] = (
        (regiao_raw[0], regiao_raw[1], regiao_raw[2], regiao_raw[3])
        if regiao_raw is not None
        else None
    )
    intervalo = float(args.intervalo)
    cooldown = float(args.cooldown)
    max_cliques = int(args.max_cliques)
    duracao = float(args.duracao)
    preview = bool(args.preview)
    debug = bool(args.debug)
    espera_hover = float(args.espera_hover)
    hold = float(args.hold)
    offset_raw = cast(list[int], args.offset)
    off_dx, off_dy = int(offset_raw[0]), int(offset_raw[1])
    jitter = float(args.jitter)
    foco = not bool(args.sem_foco)
    recheck = not bool(args.sem_recheck)
    estacionar = not bool(args.sem_estacionar)
    park_raw = cast(Optional[list[int]], args.estacionar)
    destino: Optional[tuple[int, int]] = (
        (int(park_raw[0]), int(park_raw[1])) if park_raw is not None else None
    )
    tesseract_cmd = str(args.tesseract)
    if tesseract_cmd:
        os.environ["TESSERACT_CMD"] = tesseract_cmd

    # ---- Modos que não varrem a tela em loop -------------------------------- #
    titulo_janela = cast(Optional[str], args.janela) or carregar_janela_config(config)
    sem_teclado = bool(args.sem_teclado)
    if sys.platform == "win32":
        _api()  # liga o modo "DPI aware" antes de capturar/clicar

    esc_txt = str(args.escala).strip().lower()
    if esc_txt == "auto":
        configurar_escala(True, None, float(args.escala_min), float(args.escala_max),
                          float(args.busca_escala))
    else:
        try:
            esc_val = float(esc_txt.replace(",", "."))
        except ValueError:
            sys.exit("--escala deve ser 'auto' ou um número (ex.: 1, 0.6).")
        if esc_val <= 0:
            sys.exit("--escala deve ser maior que zero.")
        configurar_escala(True, esc_val)

    if modo == "gravar":
        eventos = gravar(arquivo, pasta, confianca, monitor, regiao, duracao, float(args.atraso),
                         janela=titulo_janela, ancora=cast(Optional[str], args.ancora),
                         teclado=not sem_teclado)
        if bool(args.gerar_regras):
            info_j = titulo_janela
            if info_j is None:
                try:
                    info_j = cast(Optional[str], json.loads(
                        Path(arquivo).read_text(encoding="utf-8")).get("janela", {}).get("titulo"))
                except (OSError, ValueError, AttributeError):
                    info_j = None
            gerar_regras(eventos, config, bool(args.sobrescrever), info_j)
        return
    if modo == "reproduzir":
        reproduzir(arquivo, float(args.velocidade), float(args.atraso),
                   loop=cast(Optional[int], args.loop), pausa_loop=float(args.pausa_loop),
                   janela=titulo_janela, checar_janela=not bool(args.sem_checar_janela),
                   espera_janela=float(args.espera_janela), teclas=not sem_teclado,
                   config=config, pasta=pasta, confianca=confianca, monitor=monitor,
                   auto_detect=not bool(args.sem_auto_detect), auto_max=float(args.auto_max),
                   registro=Registro(log_caminho))
        return

    if modo == "imagem" and not Path(pasta).is_dir():
        sys.exit(f"Pasta '{pasta}' não existe. Crie-a e coloque recortes PNG dos botões nela.")

    regras = carregar_regras(config)
    padrao = Regra()
    if regras:
        resumo = ", ".join(
            f"{nome}={r.acao}" + (f"({r.vezes}x)" if r.vezes else "") for nome, r in regras.items()
        )
        print(f"Regras de '{config}': {resumo}")
        if modo == "imagem":
            for nome in regras:
                if not any((Path(pasta) / f"{nome}{ext}").exists() for ext in (".png", ".jpg")):
                    print(f"  Aviso: a regra '{nome}' não tem imagem '{nome}.png' em '{pasta}'.")
    elif modo == "imagem":
        print(f"Sem '{config}': todos os botões da pasta serão clicados repetidamente.")

    # Âncoras citadas em destinos nunca devem ser clicadas: viram regra "ancora".
    for r in list(regras.values()):
        if r.destino_ancora is not None and r.destino_ancora[0] not in regras:
            regras[r.destino_ancora[0]] = Regra(acao="ancora")
    if any(r.destino_janela is not None for r in regras.values()) and not titulo_janela:
        sys.exit("Há destinos relativos à janela em '" + config + "'. Informe a janela: "
                 '--janela "Título" (ou "_janela": "Título" no json).')
    if titulo_janela and regiao is not None:
        print("Aviso: --janela tem prioridade sobre --regiao.")
    if modo == "imagem":
        print("Escala dos botões: "
              + ("automática (os PNGs devem estar no tamanho máximo da janela)"
                 if esc_txt == "auto" else f"fixa em {esc_txt}") + ".")

    print(f"Modo: {modo} | Ctrl+C ou mouse no canto superior esquerdo para parar.")
    registro = Registro(log_caminho)
    estado = Estado()
    recentes: dict[str, float] = {}
    avisos: dict[str, float] = {}
    escolhedor = Escolhedor()
    ancoras: dict[str, Ancora] = {}
    acoes = 0
    inicio = time.time()
    rect_anterior: Optional[Regiao] = None
    escala_anunciada: Optional[float] = None
    janela_sumida = False

    def avisar(chave: str, msg: str, cada: float = 10.0) -> None:
        if time.time() - avisos.get(chave, 0.0) >= cada:
            avisos[chave] = time.time()
            print(f"[{time.strftime('%H:%M:%S')}] {msg}")

    parar_teclas = threading.Event()
    thread_teclas: Optional[threading.Thread] = None
    if registro.ativo and sys.platform == "win32" and not sem_teclado and not preview:
        thread_teclas = threading.Thread(
            target=_monitorar_teclado_no_log, args=(parar_teclas, registro), daemon=True)
        thread_teclas.start()
        print("O --log também registra as teclas que você apertar (--sem-teclado desliga).")

    try:
        while True:
            if duracao and time.time() - inicio > duracao:
                break
            regiao_cap = regiao
            rect_jogo: Optional[Regiao] = None
            if titulo_janela:
                rect_jogo = _rect_seguro(titulo_janela)
                regiao_cap = regiao_da_janela(rect_jogo, monitor) if rect_jogo else None
                if rect_jogo is None or regiao_cap is None:
                    if not janela_sumida:
                        print(f"[{time.strftime('%H:%M:%S')}] janela '{titulo_janela}' não "
                              "encontrada (ou minimizada); aguardando...")
                    janela_sumida = True
                    if preview:
                        sys.exit(f"Janela '{titulo_janela}' não encontrada.")
                    time.sleep(1.0)
                    continue
                if janela_sumida:
                    print(f"[{time.strftime('%H:%M:%S')}] janela encontrada de novo.")
                    janela_sumida = False
                if rect_anterior is not None and rect_anterior[2] != rect_jogo[2]:
                    escala_mudou_janela(rect_jogo[2] / rect_anterior[2])
                    print(f"[{time.strftime('%H:%M:%S')}] janela redimensionada "
                          f"({rect_anterior[2]}x{rect_anterior[3]} -> "
                          f"{rect_jogo[2]}x{rect_jogo[3]}); reajustando a escala")
                rect_anterior = rect_jogo
            img, ex, ey, ox, oy = capturar(monitor, regiao_cap)

            if modo == "imagem":
                hits = detectar_imagens(img, pasta, confianca)
                esc_now = escala_atual()
                if esc_now is not None and (
                    escala_anunciada is None or abs(esc_now - escala_anunciada) > 0.01
                ):
                    escala_anunciada = esc_now
                    print(f"[{time.strftime('%H:%M:%S')}] escala dos botões: {esc_now:.2f}")
            elif modo == "texto":
                hits = detectar_texto(img, palavras, lang, debug)
            else:
                hits = detectar_auto(img, palavras, lang)

            agora = time.time()
            # Âncoras (imagens de referência do mapa): guarda onde estão AGORA.
            for h in hits:
                if regras.get(h.rotulo, padrao).acao == "ancora":
                    ax, ay = para_tela(h, 0, 0, ex, ey, ox, oy)
                    ancoras[h.rotulo] = (float(ax), float(ay), h.escala * ex, h.escala * ey, agora)

            if preview:
                salvar_preview(img, hits, "preview.png", off_dx, off_dy)
                print(f"{len(hits)} botão(ões) detectado(s). Veja preview.png (cruz vermelha = ponto do clique)")
                for h in hits:
                    r = regras.get(h.rotulo, padrao)
                    extra = f" [{r.acao}"
                    if r.acao == "arrastar":
                        alvo_p, motivo_p = resolver_destino(r, rect_jogo, ancoras, agora)
                        extra += f" -> {alvo_p}" if alvo_p else f" -> ? ({motivo_p})"
                    extra += "]"
                    esc_txt_h = f", escala {h.escala:.2f}" if modo == "imagem" else ""
                    print(f"  - {h.rotulo} em {h.centro} -> clique em "
                          f"{ponto_de_clique(h, off_dx, off_dy)} (score {h.score:.2f}"
                          f"{esc_txt_h}){extra}")
                break

            # Marcador de início de partida: zera os contadores quando APARECE
            # (não quando continua visível), para não zerar a cada varredura.
            visivel = any(regras.get(h.rotulo, padrao).acao == "inicio" for h in hits)
            if visivel and not estado.inicio_visivel:
                estado.zerar()
                print(f"[{time.strftime('%H:%M:%S')}] nova partida detectada "
                      f"(#{estado.partida}); contadores zerados")
                registro.log("inicio_partida", detalhe=f"partida {estado.partida}")
            estado.inicio_visivel = visivel

            hits = escolhedor.filtrar(hits, regras, agora)  # "escolha UM" entre os parecidos
            for h in hits:
                regra = regras.get(h.rotulo, padrao)
                if (regra.acao in ("inicio", "ancora") or regra.auto_detect is False
                        or h.rotulo in estado.desistiu):
                    continue
                feitos = estado.feitos.get(h.rotulo, 0)
                if regra.vezes and feitos >= regra.vezes:
                    continue

                cx, cy = h.centro
                if regra.intervalo is not None or regra.vezes:
                    chave = h.rotulo  # limite por botão (independe de onde ele está)
                else:
                    chave = f"{h.rotulo}@{cx // 20},{cy // 20}"
                espera = regra.intervalo if regra.intervalo is not None else cooldown
                if regra.reiniciar_loop:
                    espera = max(espera, 5.0)  # um clique por aparição
                if agora - recentes.get(chave, 0.0) < espera:
                    continue

                dxr, dyr = off_dx + regra.offset[0], off_dy + regra.offset[1]
                sx, sy = para_tela(h, dxr, dyr, ex, ey, ox, oy)
                arrastando = regra.acao == "arrastar"
                alvo_arrasto: Optional[tuple[int, int]] = None
                if arrastando:
                    alvo_arrasto, motivo = resolver_destino(regra, rect_jogo, ancoras, agora)
                    if alvo_arrasto is None:
                        avisar(f"dest:{h.rotulo}", f"{h.rotulo}: destino indisponível "
                               f"({motivo}); aguardando")
                        continue
                    if not _dentro_da_tela(alvo_arrasto):
                        avisar(f"dest:{h.rotulo}", f"{h.rotulo}: destino {alvo_arrasto} fora "
                               "da tela; ação adiada")
                        continue
                checar_cinza = arrastando and regra.confirmar_cinza
                antes_sat = saturacao_media(img, h) if checar_cinza else 0.0

                confirmar: Optional[Callable[[], bool]] = None
                if modo == "imagem" and recheck:
                    confirmar = partial(
                        ainda_no_lugar, h, monitor, regiao_cap, pasta, max(0.6, confianca - 0.05)
                    )
                executou = clicar(
                    h, ex, ey, ox, oy, espera_hover, max(hold, 0.15) if arrastando else hold,
                    dxr, dyr, jitter, foco, debug, confirmar, estacionar, destino,
                    arrastar_para=alvo_arrasto,
                )
                hora = time.strftime("%H:%M:%S")
                x2 = alvo_arrasto[0] if alvo_arrasto else None
                y2 = alvo_arrasto[1] if alvo_arrasto else None
                if not executou:
                    print(f"[{hora}] {h.rotulo}: botão mudou de lugar; ação cancelada")
                    registro.log("cancelado", h.rotulo, sx, sy, detalhe="botão mudou de lugar")
                    continue
                recentes[chave] = agora
                if regra.escolha is not None:
                    escolhedor.travar(h, regras, agora)

                detalhe = ""
                if checar_cinza:
                    resultado, depois_sat = verificar_cinza(h, antes_sat, regra, monitor, regiao_cap)
                    detalhe = f"saturação {antes_sat:.0f}->{depois_sat:.0f}"
                    if debug:
                        print(f"[debug] {h.rotulo}: {detalhe} (queda exigida: <= "
                              f"{regra.queda_saturacao:.0%})")
                    if resultado is False:
                        tent = estado.tentativas.get(h.rotulo, 0) + 1
                        estado.tentativas[h.rotulo] = tent
                        if tent >= regra.tentativas:
                            estado.desistiu.add(h.rotulo)
                            msg = f"não ficou cinza; desisti após {tent} tentativa(s)"
                        else:
                            msg = f"não ficou cinza; nova tentativa ({tent}/{regra.tentativas})"
                        print(f"[{hora}] {h.rotulo}: {msg} ({detalhe})")
                        registro.log("arrasto_nao_confirmado", h.rotulo, sx, sy, x2, y2,
                                     f"{detalhe}; {msg}")
                        continue
                    if resultado is None:
                        detalhe += "; sem como confirmar por cor"
                        print(f"[{hora}] {h.rotulo}: o botão já era pouco colorido, não dá para "
                              "confirmar por cor; considerando feito")
                    else:
                        detalhe += "; confirmado (ficou cinza)"

                estado.feitos[h.rotulo] = feitos + 1
                acoes += 1
                tipo = "arrasto" if arrastando else "clique"
                trajeto = f" -> ({x2}, {y2})" if arrastando else ""
                print(f"[{hora}] {tipo} #{acoes}: {h.rotulo} em ({sx}, {sy}){trajeto}"
                      + (f"  [{detalhe}]" if detalhe else ""))
                registro.log(tipo, h.rotulo, sx, sy, x2, y2, detalhe)
                if regra.reiniciar_loop:
                    estado.zerar()
                    print(f"[{hora}] '{h.rotulo}' clicado: ciclo reiniciado "
                          f"(partida #{estado.partida}); contadores zerados")
                    registro.log("inicio_partida", h.rotulo, detalhe="reiniciar_loop")
                if max_cliques and acoes >= max_cliques:
                    print("Limite de ações atingido.")
                    return
                time.sleep(random.uniform(0.3, 0.7))

            time.sleep(intervalo)
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário.")
    except FailSafe:
        print("\nFailsafe acionado (mouse no canto). Encerrado.")
    except Exception as e:
        if type(e).__name__ == "TesseractNotFoundError":
            sys.exit(
                "Tesseract OCR não encontrado.\n"
                "1) Instale: https://github.com/UB-Mannheim/tesseract/wiki "
                "(marque o idioma Portuguese)\n"
                "2) Reabra o terminal, ou passe o caminho: "
                '--tesseract "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"\n'
                "Alternativa sem OCR: use o modo 'imagem'."
            )
        raise
    finally:
        parar_teclas.set()
        if thread_teclas is not None:
            thread_teclas.join(timeout=1)
        registro.fechar()
    print(f"Fim. Total de ações: {acoes}")


if __name__ == "__main__":
    main()
