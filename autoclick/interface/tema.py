# pyright: basic
"""Tema visual (escuro/claro) para a janela: cores, fontes e estilos ttk."""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

ESCURO: dict[str, str] = {
    "bg": "#0f131a", "side": "#0a0d12", "card": "#171c26", "field": "#0f131a",
    "border": "#2a3242", "text": "#e8ecf4", "muted": "#8b95a9", "accent": "#5b8cff",
    "accent_hover": "#7aa2ff", "accent_text": "#ffffff", "ok": "#34d399", "warn": "#fbbf24",
    "danger": "#f87171", "danger_hover": "#fb9a9a", "sel": "#26344f", "hover": "#1d2431",
    "log": "#0b0e14",
}
CLARO: dict[str, str] = {
    "bg": "#f1f4f9", "side": "#ffffff", "card": "#ffffff", "field": "#f1f4f9",
    "border": "#d6dce8", "text": "#1b2130", "muted": "#667089", "accent": "#3b6cf6",
    "accent_hover": "#5a82f8", "accent_text": "#ffffff", "ok": "#12a36b", "warn": "#b97d00",
    "danger": "#e5484d", "danger_hover": "#ee6b6f", "sel": "#dbe6ff", "hover": "#e9eef8",
    "log": "#fafbfd",
}


def paleta(nome: str) -> dict[str, str]:
    return dict(CLARO if nome == "claro" else ESCURO)


class Tema:
    """Aplica a paleta ao ttk e guarda as fontes usadas pelos widgets."""

    def __init__(self, raiz: tk.Misc, nome: str = "escuro") -> None:
        self.nome = nome
        self.c = paleta(nome)
        familias = set(tkfont.families(raiz))
        base = next((f for f in ("Segoe UI", "Inter", "SF Pro Text", "Helvetica Neue", "DejaVu Sans")
                     if f in familias), "TkDefaultFont")
        mono = next((f for f in ("Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Menlo", "Courier New")
                     if f in familias), "TkFixedFont")
        self.f_normal = (base, 10)
        self.f_pequena = (base, 9)
        self.f_negrito = (base, 10, "bold")
        self.f_titulo = (base, 20, "bold")
        self.f_sub = (base, 11)
        self.f_card = (base, 11, "bold")
        self.f_grande = (base, 18, "bold")
        self.f_mono = (mono, 9)
        self.f_botao = (base, 10, "bold")
        self.aplicar(raiz)

    def aplicar(self, raiz: tk.Misc) -> None:
        c = self.c
        st = ttk.Style(raiz)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        raiz.configure(bg=c["bg"])  # type: ignore[attr-defined]
        st.configure(".", background=c["bg"], foreground=c["text"], font=self.f_normal,
                     bordercolor=c["border"], lightcolor=c["border"], darkcolor=c["border"],
                     troughcolor=c["field"], focuscolor=c["accent"], insertcolor=c["text"])
        st.configure("TFrame", background=c["bg"])
        st.configure("Card.TFrame", background=c["card"])
        st.configure("Side.TFrame", background=c["side"])
        st.configure("TLabel", background=c["bg"], foreground=c["text"])
        st.configure("Card.TLabel", background=c["card"], foreground=c["text"])
        st.configure("Muted.TLabel", background=c["card"], foreground=c["muted"], font=self.f_pequena)
        st.configure("PageMuted.TLabel", background=c["bg"], foreground=c["muted"], font=self.f_sub)
        st.configure("H1.TLabel", background=c["bg"], font=self.f_titulo)
        st.configure("CardTitle.TLabel", background=c["card"], font=self.f_card)
        st.configure("Ok.TLabel", background=c["card"], foreground=c["ok"])
        st.configure("Warn.TLabel", background=c["card"], foreground=c["warn"])
        st.configure("Bad.TLabel", background=c["card"], foreground=c["danger"])

        campo = dict(fieldbackground=c["field"], foreground=c["text"], bordercolor=c["border"],
                     lightcolor=c["border"], darkcolor=c["border"], insertcolor=c["text"],
                     padding=6, arrowcolor=c["muted"], selectbackground=c["sel"],
                     selectforeground=c["text"])
        for nome in ("TEntry", "TCombobox", "TSpinbox"):
            st.configure(nome, **campo)
            st.map(nome, bordercolor=[("focus", c["accent"])], lightcolor=[("focus", c["accent"])],
                   darkcolor=[("focus", c["accent"])], fieldbackground=[("disabled", c["card"])],
                   foreground=[("disabled", c["muted"])])
        st.map("TCombobox", fieldbackground=[("readonly", c["field"])],
               selectbackground=[("readonly", c["field"])], selectforeground=[("readonly", c["text"])])
        raiz.option_add("*TCombobox*Listbox.background", c["field"])
        raiz.option_add("*TCombobox*Listbox.foreground", c["text"])
        raiz.option_add("*TCombobox*Listbox.selectBackground", c["accent"])
        raiz.option_add("*TCombobox*Listbox.selectForeground", c["accent_text"])
        raiz.option_add("*TCombobox*Listbox.font", self.f_normal)

        for nome in ("TCheckbutton", "TRadiobutton"):
            st.configure("Card." + nome, background=c["card"], foreground=c["text"],
                         indicatorbackground=c["field"], indicatorforeground=c["accent"],
                         indicatorcolor=c["field"], upperbordercolor=c["border"],
                         lowerbordercolor=c["border"], padding=3)
            st.map("Card." + nome, background=[("active", c["card"])],
                   indicatorcolor=[("selected", c["accent"]), ("disabled", c["card"])],
                   foreground=[("disabled", c["muted"])])
        st.configure("Card.Horizontal.TScale", background=c["card"], troughcolor=c["field"],
                     bordercolor=c["border"], lightcolor=c["accent"], darkcolor=c["accent"])
        st.configure("Horizontal.TProgressbar", background=c["accent"], troughcolor=c["field"],
                     bordercolor=c["border"], lightcolor=c["accent"], darkcolor=c["accent"])
        for o in ("Vertical", "Horizontal"):
            st.configure(f"{o}.TScrollbar", background=c["border"], troughcolor=c["bg"],
                         bordercolor=c["bg"], arrowcolor=c["muted"], lightcolor=c["border"],
                         darkcolor=c["border"], gripcount=0, arrowsize=12)
            st.map(f"{o}.TScrollbar", background=[("active", c["muted"])])

        def botao(nome: str, bg: str, fg: str, hover: str) -> None:
            st.configure(nome, background=bg, foreground=fg, bordercolor=bg, lightcolor=bg,
                         darkcolor=bg, focuscolor=bg, padding=(14, 8), font=self.f_botao,
                         relief="flat", borderwidth=0)
            st.map(nome, background=[("disabled", c["border"]), ("active", hover)],
                   foreground=[("disabled", c["muted"])], bordercolor=[("active", hover)],
                   lightcolor=[("active", hover)], darkcolor=[("active", hover)])

        botao("Accent.TButton", c["accent"], c["accent_text"], c["accent_hover"])
        botao("Danger.TButton", c["danger"], "#ffffff", c["danger_hover"])
        botao("Ok.TButton", c["ok"], "#06281d" if self.nome == "escuro" else "#ffffff", c["ok"])
        botao("Ghost.TButton", c["hover"], c["text"], c["sel"])
        st.configure("Small.Ghost.TButton", padding=(10, 5), font=self.f_pequena)
        st.configure("Small.Accent.TButton", padding=(10, 5), font=self.f_pequena)

        st.configure("Treeview", background=c["field"], fieldbackground=c["field"],
                     foreground=c["text"], rowheight=28, bordercolor=c["border"],
                     lightcolor=c["border"], darkcolor=c["border"], borderwidth=0)
        st.map("Treeview", background=[("selected", c["sel"])],
               foreground=[("selected", c["text"])])
        st.configure("Treeview.Heading", background=c["card"], foreground=c["muted"],
                     relief="flat", font=self.f_pequena, padding=6)
        st.map("Treeview.Heading", background=[("active", c["card"])])
        st.configure("TPanedwindow", background=c["bg"])
        st.configure("Sash", sashthickness=6, background=c["bg"])
        st.configure("TSeparator", background=c["border"])

    @property
    def plataforma_windows(self) -> bool:
        return sys.platform == "win32"
