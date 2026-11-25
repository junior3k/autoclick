"""Detecção de botões: imagens (multi-escala), texto (OCR) e formas."""
from __future__ import annotations

import os
import shutil
import time
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional, cast

import cv2
import numpy as np

from .tipos import Hit, Img, Palavra


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
    """Lê os PNG/JPG da pasta (o jogo), somando os do "Roblox (geral)" (AUTOCLICK_GERAL_PASTA):
    o jogo vence quando o nome é igual. Tem cache: só relê se o arquivo mudou."""
    from . import jogos as m_jogos
    geral = m_jogos.camada_geral()[0]
    if not geral or Path(geral).resolve() == Path(pasta).resolve():
        return _templates_da_pasta(pasta)
    mapa = dict(_templates_da_pasta(geral))
    mapa.update(dict(_templates_da_pasta(pasta)))
    return sorted(mapa.items())

def _templates_da_pasta(pasta: str) -> list[tuple[str, Img]]:
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
