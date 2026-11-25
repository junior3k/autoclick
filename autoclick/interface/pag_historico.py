# pyright: basic
"""Histórico de sessões: totais, gráfico dos últimos dias e a lista de execuções."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
from typing import Any

from .dados import agregar_historico, formatar_duracao, ler_historico
from .pagina import Pagina
from .widgets import Cartao, GraficoBarras, botao


class PaginaHistorico(Pagina):
    chave = "historico"
    titulo = "Histórico"
    subtitulo = "O que o programa fez em cada execução (fica salvo em historico/sessoes.jsonl)."

    def construir(self) -> None:
        c, t = self.t.c, self.t
        topo = tk.Frame(self.frame, bg=c["bg"])
        topo.pack(fill="x", pady=(0, 10))
        self.totais: dict[str, tk.Label] = {}
        for i, (chave, rot) in enumerate((("sessoes", "Sessões"), ("acoes", "Ações"), ("partidas", "Partidas"),
                                          ("tempo", "Tempo ativo"), ("falhas", "Falhas"))):
            topo.columnconfigure(i, weight=1, uniform="tot")
            cx = tk.Frame(topo, bg=c["card"], highlightthickness=1, highlightbackground=c["border"])
            cx.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))
            v = tk.Label(cx, text="0", bg=c["card"], fg=c["text"], font=t.f_grande)
            v.pack(padx=12, pady=(10, 0), anchor="w")
            tk.Label(cx, text=rot, bg=c["card"], fg=c["muted"], font=t.f_pequena).pack(
                padx=12, pady=(0, 10), anchor="w")
            self.totais[chave] = v

        g = Cartao(self.frame, t, "Ações por dia", "Últimos 7 dias (cliques e arrastos).")
        g.pack(fill="x", pady=(0, 10))
        self.grafico = GraficoBarras(g.corpo, t)
        self.grafico.grid(row=0, column=0, columnspan=2, sticky="ew")

        quadro = tk.Frame(self.frame, bg=c["bg"])
        quadro.pack(fill="both", expand=True)
        cols = ("fim", "modo", "dur", "acoes", "partidas", "motivo")
        self.arv = ttk.Treeview(quadro, columns=cols, show="headings", height=8)
        for col, txt, w in (("fim", "Terminou", 140), ("modo", "Função", 90), ("dur", "Duração", 80),
                            ("acoes", "Ações", 60), ("partidas", "Partidas", 70), ("motivo", "Como terminou", 160)):
            self.arv.heading(col, text=txt)
            self.arv.column(col, width=w, stretch=(col == "motivo"))
        sb = ttk.Scrollbar(quadro, orient="vertical", command=self.arv.yview)
        self.arv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.arv.pack(side="left", fill="both", expand=True)

        rod = tk.Frame(self.frame, bg=c["bg"])
        rod.pack(fill="x", pady=(8, 0))
        botao(rod, "Atualizar", self.recarregar, "Ghost", True).pack(side="left")
        botao(rod, "Abrir pasta de capturas de erro", self.abrir_erros, "Ghost", True).pack(side="left", padx=6)
        botao(rod, "Apagar histórico", self.apagar, "Danger", True).pack(side="right")

    def ao_mostrar(self) -> None:
        self.recarregar()

    def recarregar(self) -> None:
        sess = ler_historico()
        r = agregar_historico(sess)
        self.totais["sessoes"].configure(text=str(r["sessoes"]))
        self.totais["acoes"].configure(text=str(r["acoes"]))
        self.totais["partidas"].configure(text=str(r["partidas"]))
        self.totais["tempo"].configure(text=formatar_duracao(r["segundos"]))
        self.totais["falhas"].configure(text=str(r["falhas"]))
        self.grafico.definir([(d, float(v)) for d, v in r["por_dia"]])
        for i in self.arv.get_children():
            self.arv.delete(i)
        for i, s in enumerate(reversed(sess[-300:])):
            fim = str(s.get("fim", ""))[:16].replace("T", " ")
            self.arv.insert("", "end", iid=str(i), values=(
                fim, s.get("modo", ""), formatar_duracao(float(s.get("duracao_seg", 0) or 0)),
                s.get("total_acoes", 0), s.get("partidas", 0), s.get("motivo", "")))

    def abrir_erros(self) -> None:
        pasta = os.path.abspath("erros")
        if not os.path.isdir(pasta):
            messagebox.showinfo("Capturas de erro", "Ainda não há capturas (a pasta “erros” é criada "
                                "quando algo dá errado).", parent=self.app.raiz)
            return
        self.app.abrir_caminho(pasta)

    def apagar(self) -> None:
        if messagebox.askyesno("Apagar histórico", "Apagar todo o histórico de sessões?", parent=self.app.raiz):
            try:
                Path("historico/sessoes.jsonl").unlink(missing_ok=True)
            except OSError as e:
                messagebox.showerror("Histórico", str(e), parent=self.app.raiz)
            self.recarregar()

    def ao_status(self, dados: dict[str, Any]) -> None:
        pass
