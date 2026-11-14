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
import os
import random
import shutil
import sys
import unicodedata
from difflib import SequenceMatcher
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, cast

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
def salvar_preview(img: Img, hits: list[Hit], caminho: str = "preview.png") -> None:
    out = img.copy()
    for h in hits:
        cv2.rectangle(out, (h.x, h.y), (h.x + h.w, h.y + h.h), (0, 255, 0), 2)
        cv2.putText(out, h.rotulo, (h.x, max(12, h.y - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)
    cv2.imwrite(caminho, out)


def clicar(
    h: Hit,
    esc_x: float,
    esc_y: float,
    off_x: int,
    off_y: int,
    espera_hover: float = 0.15,
    hold: float = 0.08,
) -> None:
    # Clica num ponto aleatório perto do centro (30% central do botão).
    cx, cy = h.centro
    cx_f = cx + random.uniform(-0.15, 0.15) * h.w
    cy_f = cy + random.uniform(-0.15, 0.15) * h.h
    px = off_x + cx_f * esc_x
    py = off_y + cy_f * esc_y
    pyautogui.moveTo(px, py, duration=random.uniform(0.15, 0.35))
    # Jogos costumam ignorar clique instantâneo e cursor "teletransportado":
    # 1) pequeno vaivém para gerar eventos reais de movimento (ativa o hover),
    # 2) espera o botão reagir, 3) segura o clique por alguns milissegundos.
    pyautogui.moveRel(2, 0, duration=0.05)
    pyautogui.moveRel(-2, 0, duration=0.05)
    time.sleep(espera_hover)
    pyautogui.mouseDown()
    time.sleep(hold)
    pyautogui.mouseUp()


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
    ap.add_argument("--espera-hover", type=float, default=0.15,
                    help="segundos com o mouse parado sobre o botão antes de clicar")
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
                salvar_preview(img, hits)
                print(f"{len(hits)} botão(ões) detectado(s). Veja preview.png")
                for h in hits:
                    print(f"  - {h.rotulo} em {h.centro} (score {h.score:.2f})")
                break

            agora = time.time()
            for h in hits:
                chave = (h.centro[0] // 20, h.centro[1] // 20)
                if agora - recentes.get(chave, 0.0) < cooldown:
                    continue
                clicar(h, ex, ey, ox, oy, espera_hover, hold)
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
