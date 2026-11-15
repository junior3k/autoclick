#!/usr/bin/env python3
"""
Autoclick inteligente: olha a tela, encontra botões e clica neles.

Instalação:
    pip install mss opencv-python numpy pyautogui pytesseract
    # + Tesseract OCR instalado no sistema (necessário nos modos "texto" e "auto"):
    #   Windows: https://github.com/UB-Mannheim/tesseract/wiki
    #   macOS:   brew install tesseract tesseract-lang
    #   Linux:   sudo apt install tesseract-ocr tesseract-ocr-por

Modos:
    texto   lê a tela com OCR e clica em palavras como "Aceitar", "Continuar"...
    imagem  procura imagens de botões (PNGs recortados por você) na tela
    auto    detecta retângulos com formato de botão, lê o rótulo e clica
            se o texto bater com as palavras-chave

Exemplos:
    python autoclick_inteligente.py texto --palavras "aceitar" "continuar" "ok" --preview
    python autoclick_inteligente.py texto --palavras "permitir" --intervalo 2
    python autoclick_inteligente.py imagem --pasta botoes/ --confianca 0.85
    python autoclick_inteligente.py auto --palavras "próximo" "confirmar"

Regras por botão (botoes.json, ao lado do script; a chave é o nome do PNG sem extensão):
    {
      "maximo":         { "acao": "clicar" },
      "proxima":        { "acao": "clicar", "intervalo": 2 },
      "torre":          { "acao": "arrastar", "destino": [980, 540], "vezes": 1 },
      "inicio_partida": { "acao": "inicio" }
    }
    - clicar    clica sempre que vê o botão (padrão para PNGs sem regra).
    - arrastar  aperta no botão, leva até "destino" (x, y na tela), solta, e confirma que o
                botão ficou cinza. "vezes" = quantas vezes POR PARTIDA (padrão 1).
                Se não ficar cinza, tenta de novo ("tentativas", padrão 3).
    - inicio    PNG de algo que só aparece no começo da partida: ao aparecer, zera os
                contadores de "vezes" (libera os botões de "uma vez por partida").
    Opcionais: "offset": [dx, dy], "intervalo": segundos, "confirmar_cinza": true/false,
               "queda_saturacao": 0.5, "tentativas": 3, "espera_confirmacao": 0.7.

Gravação (Windows):
    python autoclick_inteligente.py gravar --arquivo gravacao.json --gerar-regras
        Grava os SEUS cliques e arrastos (coordenadas e tempo) até apertar F9. Com
        --gerar-regras, o ponto onde você soltou vira o "destino" no botoes.json.
    python autoclick_inteligente.py reproduzir --arquivo gravacao.json --velocidade 1
        Refaz a gravação (F9 ou mouse no canto superior esquerdo para parar).
    Em qualquer execução, --log acoes.csv registra cada ação automática.

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
import pyautogui

# mss e pytesseract não têm stubs de tipo; tratamos como Any de forma explícita.
mss_lib: Any = _mss

Img = npt.NDArray[Any]
Regiao = tuple[int, int, int, int]
Palavra = tuple[str, int, int, int, int]  # texto, x, y, w, h

pyautogui.FAILSAFE = True  # mouse no canto superior esquerdo = aborta
pyautogui.PAUSE = 0

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


def detectar_imagens(img: Img, pasta: str, confianca: float) -> list[Hit]:
    hits: list[Hit] = []
    arquivos = sorted(Path(pasta).glob("*.png")) + sorted(Path(pasta).glob("*.jpg"))
    for arq in arquivos:
        tpl = cast(Optional[Img], cv2.imread(str(arq)))
        if tpl is None:
            continue
        if tpl.shape[0] > img.shape[0] or tpl.shape[1] > img.shape[1]:
            continue
        res = cast(Img, cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED))
        ys, xs = np.where(res >= confianca)
        for y, x in zip(ys.tolist(), xs.tolist()):
            hits.append(
                Hit(int(x), int(y), int(tpl.shape[1]), int(tpl.shape[0]), arq.stem,
                    float(res[y, x]))
            )
    return dedupe(hits)


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
    """Ponto exato do clique (em pixels da imagem capturada): centro do botão + ajuste."""
    cx, cy = h.centro
    return cx + dx, cy + dy


def salvar_preview(
    img: Img, hits: list[Hit], caminho: str = "preview.png", dx: int = 0, dy: int = 0
) -> None:
    out = img.copy()
    for h in hits:
        cv2.rectangle(out, (h.x, h.y), (h.x + h.w, h.y + h.h), (0, 255, 0), 2)
        # Cruz vermelha = ponto exato onde o clique vai acontecer.
        cv2.drawMarker(out, ponto_de_clique(h, dx, dy), (0, 0, 255),
                       cv2.MARKER_CROSS, 24, 2)
        cv2.putText(out, h.rotulo, (h.x, max(12, h.y - 6)),
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


def trazer_janela_para_frente(x: int, y: int) -> bool:
    """Windows: traz para o primeiro plano a janela que está sob o ponto (x, y).

    Retorna True se a janela já estava (ou ficou) em foco.
    """
    if sys.platform != "win32":
        return False
    from ctypes import wintypes

    windll: Any = getattr(ctypes, "windll")
    user32: Any = windll.user32
    kernel32: Any = windll.kernel32

    # argtypes corretos evitam truncar handles de 64 bits.
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]

    hwnd = user32.WindowFromPoint(wintypes.POINT(x, y))
    if not hwnd:
        return False
    raiz = user32.GetAncestor(hwnd, 2) or hwnd  # GA_ROOT
    atual = user32.GetForegroundWindow()
    if atual == raiz:
        return True

    # O Windows só deixa trazer uma janela para frente se anexarmos a thread da atual.
    tid_atual = int(user32.GetWindowThreadProcessId(atual, None)) if atual else 0
    tid_nosso = int(kernel32.GetCurrentThreadId())
    anexado = False
    if tid_atual and tid_atual != tid_nosso:
        anexado = bool(user32.AttachThreadInput(tid_atual, tid_nosso, True))
    try:
        if user32.IsIconic(raiz):
            user32.ShowWindow(raiz, 9)  # SW_RESTORE (só se estiver minimizada)
        user32.SetForegroundWindow(raiz)
    finally:
        if anexado:
            user32.AttachThreadInput(tid_atual, tid_nosso, False)
    time.sleep(0.2)
    return bool(user32.GetForegroundWindow() == raiz)


# --------------------------------------------------------------------------- #
# Mouse "de verdade" no Windows (SendInput): gera eventos reais de movimento,
# que jogos usam para ativar o hover. O pyautogui usa SetCursorPos, que só
# teletransporta o ponteiro sem gerar esses eventos.
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


class _InputUnion(ctypes.Union):
    _fields_ = [("mi", _MouseInput)]


class _Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint32), ("u", _InputUnion)]


_MOVE = 0x0001
_LEFTDOWN = 0x0002
_LEFTUP = 0x0004
_VIRTUALDESK = 0x4000
_ABSOLUTE = 0x8000


def _enviar_mouse(dx: int, dy: int, flags: int) -> None:
    user32: Any = getattr(ctypes, "windll").user32
    entrada = _Input(type=0, u=_InputUnion(mi=_MouseInput(dx, dy, 0, flags, 0, 0)))
    user32.SendInput(1, ctypes.byref(entrada), ctypes.sizeof(entrada))


def mover_real(px: int, py: int) -> None:
    """Move o cursor para (px, py) enviando um evento de mouse real."""
    user32: Any = getattr(ctypes, "windll").user32
    vx = int(user32.GetSystemMetrics(76))  # SM_XVIRTUALSCREEN
    vy = int(user32.GetSystemMetrics(77))
    vw = int(user32.GetSystemMetrics(78))
    vh = int(user32.GetSystemMetrics(79))
    nx = round((px - vx) * 65535 / max(1, vw - 1))
    ny = round((py - vy) * 65535 / max(1, vh - 1))
    _enviar_mouse(nx, ny, _MOVE | _ABSOLUTE | _VIRTUALDESK)


def mover_suave(px: int, py: int, duracao: float = 0.3, passos: int = 18) -> None:
    """Trajetória curta com vários eventos reais de movimento até (px, py)."""
    pos = pyautogui.position()
    x0, y0 = int(pos.x), int(pos.y)
    for i in range(1, passos + 1):
        t = i / passos
        e = 1 - (1 - t) ** 2  # desacelera ao chegar
        mover_real(round(x0 + (px - x0) * e), round(y0 + (py - y0) * e))
        time.sleep(duracao / passos)


def estacionar_mouse(
    px: int, py: int, usar_input: bool, destino: Optional[tuple[int, int]] = None
) -> None:
    """Afasta o cursor do botão para o hover não atrapalhar a próxima detecção.

    Sem destino definido, vai 350 px para o lado (só passa o mouse, não clica).
    """
    largura, altura = pyautogui.size()
    if destino is None:
        alvo_x = px + 350 if px + 350 < largura - 20 else px - 350
        alvo_y = py
    else:
        alvo_x, alvo_y = destino
    # Evita os cantos da tela (o canto superior esquerdo aciona o failsafe).
    alvo_x = min(max(alvo_x, 20), largura - 20)
    alvo_y = min(max(alvo_y, 20), altura - 20)
    time.sleep(0.1)  # deixa o clique terminar de ser registrado
    if usar_input:
        mover_suave(alvo_x, alvo_y, duracao=0.25, passos=10)
    else:
        pyautogui.moveTo(alvo_x, alvo_y, duration=0.25)


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
    mouse: str = "input",
    confirmar: Optional[Callable[[], bool]] = None,
    estacionar: bool = True,
    destino: Optional[tuple[int, int]] = None,
    arrastar_para: Optional[tuple[int, int]] = None,
) -> bool:
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

    usar_input = mouse == "input" and sys.platform == "win32"

    # 2) Aproximação em duas etapas:
    #    a) para AO LADO do botão (fora dele, sem hover) e reconfirma que o botão
    #       ainda está ali. Com o cursor em cima, o hover mudaria a aparência e a
    #       checagem falharia;
    #    b) só então entra no botão com eventos de movimento REAIS (SendInput),
    #       para o jogo ativar o hover como se fosse o mouse físico, e clica.
    lado_x = max(20, round(off_x + h.x * esc_x) - 40)
    if usar_input:
        mover_suave(lado_x, py, duracao=random.uniform(0.2, 0.3))
    else:
        pyautogui.moveTo(lado_x, py, duration=random.uniform(0.15, 0.25))

    if confirmar is not None:
        time.sleep(0.05)
        if not confirmar():
            if debug:
                print("[debug] botão mudou de lugar; clique cancelado")
            if estacionar:
                estacionar_mouse(lado_x, py, usar_input, destino)
            return False

    if usar_input:
        mover_suave(px, py, duracao=0.2, passos=12)
        # Pequeno "tremor" sobre o botão, terminando exatamente no alvo.
        mover_real(px + 2, py)
        time.sleep(0.04)
        mover_real(px - 1, py)
        time.sleep(0.04)
        mover_real(px, py)
    else:
        pyautogui.moveTo(px, py, duration=0.2)
        pyautogui.moveRel(1, 0, duration=0.03)
        pyautogui.moveRel(-1, 0, duration=0.03)
    time.sleep(espera_hover)

    # 3) Confere onde o cursor realmente parou e corrige se desviou.
    real = pyautogui.position()
    if abs(real.x - px) > 3 or abs(real.y - py) > 3:
        if usar_input:
            mover_real(px, py)
        else:
            pyautogui.moveTo(px, py, duration=0.1)
        time.sleep(0.05)
        real = pyautogui.position()
    if debug:
        print(f"[debug] mouse={'SendInput' if usar_input else 'pyautogui'} "
              f"alvo=({px},{py}) cursor=({real.x},{real.y})")

    # 4) Pressiona, segura e solta. Com 'arrastar_para', mantém o botão pressionado
    #    e leva o cursor (com movimentos reais, devagar) até lá antes de soltar.
    if usar_input:
        _enviar_mouse(0, 0, _LEFTDOWN)
        time.sleep(hold)
        if arrastar_para is not None:
            mover_suave(arrastar_para[0], arrastar_para[1], duracao=0.7, passos=35)
            time.sleep(0.2)  # deixa o jogo registrar a posição de soltura
        _enviar_mouse(0, 0, _LEFTUP)
    else:
        pyautogui.mouseDown()
        time.sleep(hold)
        if arrastar_para is not None:
            pyautogui.moveTo(arrastar_para[0], arrastar_para[1], duration=0.7)
            time.sleep(0.2)
        pyautogui.mouseUp()
    if estacionar:
        estacionar_mouse(px, py, usar_input, destino)
    return True


# --------------------------------------------------------------------------- #
# Regras por botão (botoes.json), estado da partida e log de ações
# --------------------------------------------------------------------------- #
_RIGHTDOWN = 0x0008
_RIGHTUP = 0x0010
VK_ESQUERDO = 0x01
VK_DIREITO = 0x02
VK_F9 = 0x78

ACOES_VALIDAS = ("clicar", "arrastar", "inicio")


@dataclass
class Regra:
    """Regra de um botão (chave = nome do PNG sem extensão)."""

    acao: str = "clicar"  # clicar | arrastar | inicio
    vezes: int = 0  # por partida; 0 = ilimitado
    intervalo: Optional[float] = None  # segundos mínimos entre ações deste botão
    destino: Optional[tuple[int, int]] = None  # (x, y) na tela, para 'arrastar'
    offset: tuple[int, int] = (0, 0)  # ajuste fino do ponto de clique
    confirmar_cinza: bool = False
    queda_saturacao: float = 0.5  # cinza = saturação caiu para <= 50% do original
    tentativas: int = 3
    espera_confirmacao: float = 0.7


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
        if "destino" in d:
            dr: Any = d["destino"]
            if not (isinstance(dr, list) and len(cast(list[Any], dr)) == 2):
                sys.exit(f"{caminho}: 'destino' de '{nome}' deve ser [x, y].")
            lista = cast(list[Any], dr)
            destino = (int(lista[0]), int(lista[1]))
        if acao == "arrastar" and destino is None:
            sys.exit(f"{caminho}: '{nome}' é 'arrastar' mas não tem 'destino': [x, y].")

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
        regras[nome] = Regra(
            acao=acao,
            vezes=int(d.get("vezes", 1 if acao == "arrastar" else 0)),
            intervalo=intervalo,
            destino=destino,
            offset=offset,
            confirmar_cinza=bool(d.get("confirmar_cinza", acao == "arrastar")),
            queda_saturacao=float(d.get("queda_saturacao", 0.5)),
            tentativas=int(d.get("tentativas", 3)),
            espera_confirmacao=float(d.get("espera_confirmacao", 0.7)),
        )
    return regras


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

    def fechar(self) -> None:
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
    user32: Any = getattr(ctypes, "windll").user32
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def _abortar() -> bool:
    """F9 ou mouse no canto superior esquerdo."""
    pos = pyautogui.position()
    return _tecla_pressionada(VK_F9) or (pos.x <= 1 and pos.y <= 1)


# --------------------------------------------------------------------------- #
# Modo gravar: grava os SEUS cliques e arrastos (coordenadas + tempo)
# --------------------------------------------------------------------------- #
Caixa = tuple[int, int, int, int]


def _varredura_continua(
    parar: threading.Event,
    trava: threading.Lock,
    conhecidos: dict[str, tuple[Caixa, float]],
    pasta: str,
    confianca: float,
    monitor: int,
    regiao: Optional[Regiao],
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
                with trava:
                    conhecidos[h.rotulo] = (caixa, time.time())
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


def gravar(
    arquivo: str,
    pasta: str,
    confianca: float,
    monitor: int,
    regiao: Optional[Regiao],
    duracao: float,
    atraso: float,
    limiar_arrasto: int = 12,
) -> list[dict[str, Any]]:
    if sys.platform != "win32":
        sys.exit("O modo 'gravar' só funciona no Windows.")

    pngs: list[Path] = []
    if Path(pasta).is_dir():
        pngs = sorted(Path(pasta).glob("*.png")) + sorted(Path(pasta).glob("*.jpg"))

    parar = threading.Event()
    trava = threading.Lock()
    conhecidos: dict[str, tuple[Caixa, float]] = {}
    worker: Optional[threading.Thread] = None
    if pngs:
        worker = threading.Thread(
            target=_varredura_continua,
            args=(parar, trava, conhecidos, pasta, confianca, monitor, regiao),
            daemon=True,
        )
        worker.start()
        print(f"Identificando os botões da pasta '{pasta}' ({len(pngs)} imagem(ns)) "
              "para dar nome aos cliques.")
    else:
        print(f"Aviso: sem imagens em '{pasta}'; os cliques serão gravados sem nome de botão.")

    for i in range(int(atraso), 0, -1):
        print(f"Começando em {i}...")
        time.sleep(1)
    print("● GRAVANDO. Jogue normalmente. Aperte F9 para parar.")

    eventos: list[dict[str, Any]] = []
    abertos: dict[int, tuple[float, int, int, Optional[str]]] = {}
    t0 = time.time()
    try:
        while True:
            agora = time.time()
            if _tecla_pressionada(VK_F9) or (duracao and agora - t0 > duracao):
                break
            for vk, nome in ((VK_ESQUERDO, "esquerdo"), (VK_DIREITO, "direito")):
                premido = _tecla_pressionada(vk)
                if premido and vk not in abertos:
                    pos = pyautogui.position()
                    x, y = int(pos.x), int(pos.y)
                    abertos[vk] = (agora - t0, x, y, _identificar(x, y, trava, conhecidos))
                elif (not premido) and vk in abertos:
                    t_ini, x, y, rot = abertos.pop(vk)
                    pos = pyautogui.position()
                    x2, y2 = int(pos.x), int(pos.y)
                    dur = (agora - t0) - t_ini
                    tipo = "arrasto" if math.hypot(x2 - x, y2 - y) >= limiar_arrasto else "clique"
                    eventos.append({
                        "t": round(t_ini, 3),
                        "tipo": tipo,
                        "mouse": nome,
                        "x": x,
                        "y": y,
                        "x2": x2,
                        "y2": y2,
                        "duracao": round(dur, 3),
                        "botao": rot,
                    })
                    t_txt = f"{int(t_ini // 60):02d}:{t_ini % 60:06.3f}"
                    sufixo = f"  [{rot}]" if rot else ""
                    if tipo == "arrasto":
                        print(f"[{t_txt}] arrasto {nome} ({x},{y}) -> ({x2},{y2}) "
                              f"em {dur:.2f}s{sufixo}")
                    else:
                        print(f"[{t_txt}] clique {nome} em ({x},{y}){sufixo}")
            time.sleep(0.005)
    except KeyboardInterrupt:
        pass
    finally:
        parar.set()
        if worker is not None:
            worker.join(timeout=2)

    dados = {
        "versao": 1,
        "criado": datetime.now().isoformat(timespec="seconds"),
        "monitor": monitor,
        "eventos": eventos,
    }
    Path(arquivo).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    sem_nome = sum(1 for e in eventos if not e["botao"])
    print(f"\nGravação salva em '{arquivo}': {len(eventos)} evento(s) "
          f"({sem_nome} sem nome de botão).")
    return eventos


def gerar_regras(eventos: list[dict[str, Any]], config: str, sobrescrever: bool) -> None:
    """Transforma a gravação em regras no botoes.json (sem apagar as existentes)."""
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
    for ev in eventos:
        rot = ev.get("botao")
        if not rot:
            sem_nome += 1
            continue
        if ev["tipo"] == "arrasto":
            novas[str(rot)] = {"acao": "arrastar", "destino": [ev["x2"], ev["y2"]], "vezes": 1}
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

    p.write_text(json.dumps(atual, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Regras em '{config}': {len(escritas)} gravada(s)"
          + (f" ({', '.join(escritas)})" if escritas else "") + ".")
    if mantidas:
        print(f"  Já existiam e foram mantidas: {', '.join(mantidas)} "
              "(use --sobrescrever para trocar).")
    if sem_nome:
        print(f"  {sem_nome} evento(s) sem nome de botão não geraram regra "
              "(o clique não foi sobre nenhum PNG da pasta).")


# --------------------------------------------------------------------------- #
# Modo reproduzir: refaz uma gravação (coordenadas e tempos)
# --------------------------------------------------------------------------- #
def reproduzir(arquivo: str, velocidade: float, atraso: float) -> None:
    if sys.platform != "win32":
        sys.exit("O modo 'reproduzir' só funciona no Windows.")
    p = Path(arquivo)
    if not p.is_file():
        sys.exit(f"Gravação '{arquivo}' não encontrada.")
    dados: Any = json.loads(p.read_text(encoding="utf-8"))
    eventos = cast(list[dict[str, Any]], dados.get("eventos", []))
    if not eventos:
        sys.exit("A gravação não tem eventos.")
    vel = max(0.1, velocidade)

    for i in range(int(atraso), 0, -1):
        print(f"Reproduzindo em {i}... (F9 ou mouse no canto superior esquerdo para parar)")
        time.sleep(1)
    print(f"▶ Reproduzindo {len(eventos)} evento(s) a {vel:g}x.")

    t0 = time.time()
    for n, ev in enumerate(eventos, 1):
        alvo = float(ev["t"]) / vel
        while time.time() - t0 < alvo:
            if _abortar():
                print("Reprodução interrompida.")
                return
            time.sleep(0.005)
        if _abortar():
            print("Reprodução interrompida.")
            return

        x, y = int(ev["x"]), int(ev["y"])
        down, up = (_RIGHTDOWN, _RIGHTUP) if ev.get("mouse") == "direito" else (_LEFTDOWN, _LEFTUP)
        dur = float(ev.get("duracao", 0.08))

        mover_suave(x, y, duracao=0.2, passos=12)
        time.sleep(0.05)
        _enviar_mouse(0, 0, down)
        if ev["tipo"] == "arrasto":
            time.sleep(0.08)
            mover_suave(int(ev["x2"]), int(ev["y2"]),
                        duracao=max(0.2, dur / vel), passos=max(12, int(dur * 40)))
            time.sleep(0.1)
        else:
            time.sleep(min(max(dur, 0.04), 0.3))
        _enviar_mouse(0, 0, up)
        rot = f" [{ev['botao']}]" if ev.get("botao") else ""
        print(f"  {n}/{len(eventos)} {ev['tipo']} em ({x},{y}){rot}")
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
                    help="input = eventos reais via SendInput (Windows, melhor para jogos); "
                         "pyautogui = método antigo")
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
    mouse = str(args.mouse)
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
    if modo == "gravar":
        eventos = gravar(arquivo, pasta, confianca, monitor, regiao, duracao, float(args.atraso))
        if bool(args.gerar_regras):
            gerar_regras(eventos, config, bool(args.sobrescrever))
        return
    if modo == "reproduzir":
        reproduzir(arquivo, float(args.velocidade), float(args.atraso))
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

    print(f"Modo: {modo} | Ctrl+C ou mouse no canto superior esquerdo para parar.")
    registro = Registro(log_caminho)
    estado = Estado()
    recentes: dict[str, float] = {}
    acoes = 0
    inicio = time.time()

    try:
        while True:
            if duracao and time.time() - inicio > duracao:
                break
            img, ex, ey, ox, oy = capturar(monitor, regiao)

            if modo == "imagem":
                hits = detectar_imagens(img, pasta, confianca)
            elif modo == "texto":
                hits = detectar_texto(img, palavras, lang, debug)
            else:
                hits = detectar_auto(img, palavras, lang)

            if preview:
                salvar_preview(img, hits, "preview.png", off_dx, off_dy)
                print(f"{len(hits)} botão(ões) detectado(s). Veja preview.png (cruz vermelha = ponto do clique)")
                for h in hits:
                    r = regras.get(h.rotulo, padrao)
                    extra = f" [{r.acao}" + (f" -> {r.destino}" if r.destino else "") + "]"
                    print(f"  - {h.rotulo} em {h.centro} -> clique em "
                          f"{ponto_de_clique(h, off_dx, off_dy)} (score {h.score:.2f}){extra}")
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

            agora = time.time()
            for h in hits:
                regra = regras.get(h.rotulo, padrao)
                if regra.acao == "inicio" or h.rotulo in estado.desistiu:
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
                if agora - recentes.get(chave, 0.0) < espera:
                    continue

                dxr, dyr = off_dx + regra.offset[0], off_dy + regra.offset[1]
                sx, sy = para_tela(h, dxr, dyr, ex, ey, ox, oy)
                arrastando = regra.acao == "arrastar" and regra.destino is not None
                alvo_arrasto = regra.destino if arrastando else None
                checar_cinza = arrastando and regra.confirmar_cinza
                antes_sat = saturacao_media(img, h) if checar_cinza else 0.0

                confirmar: Optional[Callable[[], bool]] = None
                if modo == "imagem" and recheck:
                    confirmar = partial(
                        ainda_no_lugar, h, monitor, regiao, pasta, max(0.6, confianca - 0.05)
                    )
                executou = clicar(
                    h, ex, ey, ox, oy, espera_hover, max(hold, 0.15) if arrastando else hold,
                    dxr, dyr, jitter, foco, debug, mouse, confirmar, estacionar, destino,
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

                detalhe = ""
                if checar_cinza:
                    resultado, depois_sat = verificar_cinza(h, antes_sat, regra, monitor, regiao)
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
                if max_cliques and acoes >= max_cliques:
                    print("Limite de ações atingido.")
                    return
                time.sleep(random.uniform(0.3, 0.7))

            time.sleep(intervalo)
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário.")
    except pyautogui.FailSafeException:
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
        registro.fechar()
    print(f"Fim. Total de ações: {acoes}")


if __name__ == "__main__":
    main()
