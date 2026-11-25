# pyright: basic
"""Ícone da janela e da barra de tarefas."""
from __future__ import annotations

import os
import sys
import tkinter as tk
from typing import Any

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recursos")
APP_ID = "Autoclick.Inteligente"


def agrupar_na_barra() -> None:
    """Faz a barra de tarefas do Windows usar o ícone do programa (e não o do Python)."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)  # type: ignore[attr-defined]
        except Exception:
            pass


def aplicar(raiz: tk.Tk) -> Any:
    """Põe o ícone na janela. Devolve a imagem (guarde a referência) ou None se não achou."""
    foto = None
    png, ico = os.path.join(PASTA, "icone.png"), os.path.join(PASTA, "icone.ico")
    try:
        if os.path.isfile(png):
            foto = tk.PhotoImage(master=raiz, file=png)
            raiz.iconphoto(True, foto)
        if sys.platform == "win32" and os.path.isfile(ico):
            raiz.iconbitmap(default=ico)
    except tk.TclError:
        pass
    return foto


def miniatura(raiz: tk.Tk, lado: int = 36) -> Any:
    """O ícone reduzido para `lado` px (para o menu lateral); None se não achar."""
    png = os.path.join(PASTA, "icone.png")
    try:
        foto = tk.PhotoImage(master=raiz, file=png)
        f = max(1, round(foto.width() / lado))
        return foto.subsample(f, f)
    except tk.TclError:
        return None
