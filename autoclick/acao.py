"""Ações sobre a tela: clique real com hover, confirmação do botão cinza."""
from __future__ import annotations

import random
import time
from typing import Callable, Optional, cast

import cv2

from .tipos import Hit, Img, Regiao
from .windows import LEFTDOWN, LEFTUP
from .regras import Regra
from . import windows as m_windows
from . import captura as m_captura
from . import deteccao as m_deteccao


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
    img, _, _, _, _ = m_captura.capturar(monitor, regiao)
    cx, cy = h.centro
    for n in m_deteccao.detectar_imagens(img, pasta, confianca):
        if n.rotulo == h.rotulo and abs(n.centro[0] - cx) <= 8 and abs(n.centro[1] - cy) <= 8:
            return True
    return False

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
    m_windows.checar_failsafe()
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
        ok = m_windows.trazer_janela_para_frente(px, py)
        if debug:
            print(f"[debug] janela em foco: {ok}")

    # 2) Aproximação em duas etapas:
    #    a) para AO LADO do botão (fora dele, sem hover) e reconfirma que o botão
    #       ainda está ali. Com o cursor em cima, o hover mudaria a aparência e a
    #       checagem falharia;
    #    b) só então entra no botão com eventos de movimento REAIS (SendInput),
    #       para o jogo ativar o hover como se fosse o mouse físico, e clica.
    lado_x = max(20, round(off_x + h.x * esc_x) - 40)
    m_windows.mover_suave(lado_x, py, duracao=random.uniform(0.2, 0.3))

    if confirmar is not None:
        time.sleep(0.05)
        if not confirmar():
            if debug:
                print("[debug] botão mudou de lugar; clique cancelado")
            if estacionar:
                m_windows.estacionar_mouse(lado_x, py, destino)
            return False

    m_windows.mover_suave(px, py, duracao=0.2, passos=12)
    # Pequeno "tremor" sobre o botão, terminando exatamente no alvo.
    m_windows.mover_real(px + 2, py)
    time.sleep(0.04)
    m_windows.mover_real(px - 1, py)
    time.sleep(0.04)
    m_windows.mover_real(px, py)
    time.sleep(espera_hover)

    # 3) Confere onde o cursor realmente parou e corrige se desviou.
    rx, ry = m_windows.posicao()
    if abs(rx - px) > 3 or abs(ry - py) > 3:
        m_windows.mover_real(px, py)
        time.sleep(0.05)
        rx, ry = m_windows.posicao()
    if debug:
        print(f"[debug] alvo=({px},{py}) cursor=({rx},{ry}) escala do botão={h.escala:.2f}")

    # 4) Pressiona, segura e solta. Com 'arrastar_para', mantém o botão pressionado
    #    e leva o cursor (com movimentos reais, devagar) até lá antes de soltar.
    m_windows.enviar_mouse(0, 0, LEFTDOWN)
    try:
        time.sleep(hold)
        if arrastar_para is not None:
            m_windows.mover_suave(arrastar_para[0], arrastar_para[1], duracao=0.7, passos=35)
            time.sleep(0.2)  # deixa o jogo registrar a posição de soltura
    finally:
        m_windows.enviar_mouse(0, 0, LEFTUP)  # nunca deixa o botão preso, mesmo se abortar
    if estacionar:
        m_windows.estacionar_mouse(px, py, destino)
    return True

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
    img2, _, _, _, _ = m_captura.capturar(monitor, regiao)
    depois = saturacao_media(img2, h)
    return ficou_cinza(antes, depois, regra.queda_saturacao), depois
