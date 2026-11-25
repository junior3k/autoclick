# pyright: basic
"""Ajuda dentro do programa: lista de assuntos à esquerda, texto à direita."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .ajuda_texto import TOPICOS
from .pagina import Pagina


class PaginaAjuda(Pagina):
    chave = "ajuda"
    titulo = "Ajuda"
    subtitulo = "Passo a passo e respostas rápidas."

    def construir(self) -> None:
        c, t = self.t.c, self.t
        f = self.frame
        f.columnconfigure(1, weight=1)
        f.rowconfigure(0, weight=1)
        self.lista = tk.Listbox(f, exportselection=False, width=30, bg=c["card"], fg=c["text"],
                                selectbackground=c["sel"], selectforeground=c["text"], font=t.f_normal,
                                borderwidth=0, highlightthickness=1, highlightbackground=c["border"],
                                activestyle="none")
        for titulo, _ in TOPICOS:
            self.lista.insert("end", "  " + titulo)
        self.lista.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        caixa = tk.Frame(f, bg=c["card"], highlightthickness=1, highlightbackground=c["border"])
        caixa.grid(row=0, column=1, sticky="nsew")
        self.texto = tk.Text(caixa, bg=c["card"], fg=c["text"], font=t.f_normal, wrap="word", borderwidth=0,
                             highlightthickness=0, padx=18, pady=14, state="disabled", spacing1=2, spacing3=3)
        sb = ttk.Scrollbar(caixa, orient="vertical", command=self.texto.yview)
        self.texto.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.texto.pack(side="left", fill="both", expand=True)
        self.texto.tag_configure("titulo", font=t.f_card, foreground=c["accent"], spacing3=8)
        self.lista.bind("<<ListboxSelect>>", self._escolhido)
        self.lista.selection_set(0)
        self.mostrar(0)

    def _escolhido(self, _e: object = None) -> None:
        s = self.lista.curselection()
        if s:
            self.mostrar(int(s[0]))

    def mostrar(self, i: int) -> None:
        titulo, corpo = TOPICOS[i]
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        self.texto.insert("end", titulo + "\n", "titulo")
        self.texto.insert("end", corpo)
        self.texto.configure(state="disabled")
        self.texto.yview_moveto(0)
