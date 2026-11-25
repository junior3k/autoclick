"""Captura de tela (mss) e geometria de monitores/janelas."""
from __future__ import annotations

from typing import Any, Optional

import numpy as np

from .tipos import Img, Regiao
from . import windows as m_windows


class _MssTardio:
    """Carrega o mss só quando a captura é usada: o resto do programa (validar, relatório,
    janela...) funciona e mostra uma mensagem clara mesmo se ele não estiver instalado."""

    def __getattr__(self, nome: str) -> Any:
        try:
            import mss as _mss  # type: ignore
        except ImportError:
            raise SystemExit("A biblioteca 'mss' (captura de tela) não está instalada. "
                             "Rode: uv sync   (ou: uv add mss)")
        return getattr(_mss, nome)


# mss e pytesseract não têm stubs de tipo; tratamos como Any de forma explícita.
mss_lib: Any = _MssTardio()

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

def rect_seguro(titulo: Optional[str]) -> Optional[Regiao]:
    """rect_da_janela que nunca levanta erro (None se não achar ou fora do Windows)."""
    if not titulo:
        return None
    try:
        return m_windows.rect_da_janela(titulo)
    except Exception:
        return None
