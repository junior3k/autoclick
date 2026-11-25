# pyright: basic
"""Caixas de diálogo no mesmo visual da janela."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from .tema import Tema
from .widgets import botao


def pedir_texto(pai: tk.Misc, t: Tema, titulo: str, mensagem: str, inicial: str = "") -> Optional[str]:
    """Pergunta um texto. Devolve None se cancelar."""
    j = tk.Toplevel(pai)
    j.title(titulo)
    j.configure(bg=t.c["card"])
    j.transient(pai)  # type: ignore[arg-type]
    j.resizable(False, False)
    tk.Label(j, text=mensagem, bg=t.c["card"], fg=t.c["text"], font=t.f_normal, justify="left",
             wraplength=380, anchor="w").pack(fill="x", padx=22, pady=(20, 8))
    v = tk.StringVar(value=inicial)
    e = ttk.Entry(j, textvariable=v, width=44)
    e.pack(padx=22, fill="x")
    res: dict[str, Optional[str]] = {"v": None}

    def ok(_e: object = None) -> None:
        res["v"] = v.get().strip() or None
        j.destroy()

    barra = tk.Frame(j, bg=t.c["card"])
    barra.pack(fill="x", padx=22, pady=18)
    botao(barra, "OK", ok, "Accent").pack(side="right")
    botao(barra, "Cancelar", j.destroy, "Ghost").pack(side="right", padx=8)
    e.bind("<Return>", ok)
    j.bind("<Escape>", lambda _e: j.destroy())
    e.focus_set()
    e.select_range(0, "end")
    j.grab_set()
    j.update_idletasks()
    try:
        x = pai.winfo_rootx() + (pai.winfo_width() - j.winfo_width()) // 2
        y = pai.winfo_rooty() + (pai.winfo_height() - j.winfo_height()) // 3
        j.geometry(f"+{max(0, x)}+{max(0, y)}")
    except tk.TclError:
        pass
    pai.wait_window(j)
    return res["v"]


def escolher_item(pai: tk.Misc, t: Tema, titulo: str, mensagem: str,
                  itens: list[str]) -> Optional[str]:
    """Escolhe um item de uma lista (ou digita um novo nome)."""
    j = tk.Toplevel(pai)
    j.title(titulo)
    j.configure(bg=t.c["card"])
    j.transient(pai)  # type: ignore[arg-type]
    j.resizable(False, False)
    tk.Label(j, text=mensagem, bg=t.c["card"], fg=t.c["text"], font=t.f_normal, justify="left",
             wraplength=380, anchor="w").pack(fill="x", padx=22, pady=(20, 8))
    v = tk.StringVar(value=itens[0] if itens else "")
    cb = ttk.Combobox(j, textvariable=v, values=itens, width=42)
    cb.pack(padx=22, fill="x")
    res: dict[str, Optional[str]] = {"v": None}

    def ok(_e: object = None) -> None:
        res["v"] = v.get().strip() or None
        j.destroy()

    barra = tk.Frame(j, bg=t.c["card"])
    barra.pack(fill="x", padx=22, pady=18)
    botao(barra, "OK", ok, "Accent").pack(side="right")
    botao(barra, "Cancelar", j.destroy, "Ghost").pack(side="right", padx=8)
    cb.bind("<Return>", ok)
    j.bind("<Escape>", lambda _e: j.destroy())
    cb.focus_set()
    j.grab_set()
    j.update_idletasks()
    try:
        x = pai.winfo_rootx() + (pai.winfo_width() - j.winfo_width()) // 2
        y = pai.winfo_rooty() + (pai.winfo_height() - j.winfo_height()) // 3
        j.geometry(f"+{max(0, x)}+{max(0, y)}")
    except tk.TclError:
        pass
    pai.wait_window(j)
    return res["v"]
