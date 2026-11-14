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

Segurança:
    - Jogue o mouse para o canto superior esquerdo da tela para ABORTAR (failsafe).
    - Ctrl+C no terminal também para.
    - Use --preview primeiro: só salva preview.png com o que foi detectado, sem clicar.
    - Use apenas em apps/sites onde automação é permitida (veja os termos de uso).
"""
from __future__ import annotations

import argparse
import ctypes
import os
import random
import shutil
import sys
import unicodedata
from difflib import SequenceMatcher
import time
from dataclasses import dataclass
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

    # 4) Pressiona, segura e solta.
    if usar_input:
        _enviar_mouse(0, 0, _LEFTDOWN)
        time.sleep(hold)
        _enviar_mouse(0, 0, _LEFTUP)
    else:
        pyautogui.mouseDown()
        time.sleep(hold)
        pyautogui.mouseUp()
    if estacionar:
        estacionar_mouse(px, py, usar_input, destino)
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Autoclick inteligente baseado em visão computacional.")
    ap.add_argument("modo", choices=["texto", "imagem", "auto"])
    ap.add_argument("--palavras", nargs="+", default=PALAVRAS_PADRAO,
                    help="textos dos botões (modos texto/auto)")
    ap.add_argument("--pasta", default="botoes", help="pasta com PNGs dos botões (modo imagem)")
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
                    help="mostra todas as palavras que o OCR conseguiu ler (modo texto)")
    ap.add_argument("--tesseract", default="",
                    help=r"caminho do tesseract.exe se não estiver no PATH")
    ap.add_argument("--preview", action="store_true",
                    help="não clica; salva preview.png e mostra o que foi detectado")
    args = ap.parse_args()

    modo = str(args.modo)
    palavras = [str(p) for p in cast(list[Any], args.palavras)]
    pasta = str(args.pasta)
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

    if modo == "imagem" and not Path(pasta).is_dir():
        sys.exit(f"Pasta '{pasta}' não existe. Crie-a e coloque recortes PNG dos botões nela.")

    print(f"Modo: {modo} | Ctrl+C ou mouse no canto superior esquerdo para parar.")
    recentes: dict[tuple[int, int], float] = {}
    cliques = 0
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
                    print(f"  - {h.rotulo} em {h.centro} -> clique em "
                          f"{ponto_de_clique(h, off_dx, off_dy)} (score {h.score:.2f})")
                break

            agora = time.time()
            for h in hits:
                chave = (h.centro[0] // 20, h.centro[1] // 20)
                if agora - recentes.get(chave, 0.0) < cooldown:
                    continue
                confirmar: Optional[Callable[[], bool]] = None
                if modo == "imagem" and recheck:
                    confirmar = partial(
                        ainda_no_lugar, h, monitor, regiao, pasta, max(0.6, confianca - 0.05)
                    )
                clicou = clicar(h, ex, ey, ox, oy, espera_hover, hold,
                                off_dx, off_dy, jitter, foco, debug, mouse, confirmar,
                                estacionar, destino)
                if not clicou:
                    print(f"[{time.strftime('%H:%M:%S')}] botão mudou de lugar; clique cancelado")
                    continue
                recentes[chave] = agora
                cliques += 1
                print(f"[{time.strftime('%H:%M:%S')}] clique #{cliques}: {h.rotulo} em {h.centro}")
                if max_cliques and cliques >= max_cliques:
                    print("Limite de cliques atingido.")
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
    print(f"Fim. Total de cliques: {cliques}")


if __name__ == "__main__":
    main()
