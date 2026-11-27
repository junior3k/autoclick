# pyright: basic
"""Modo automático: varre a tela e age conforme as regras (imagem; texto/auto são opcionais)."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

from ..opcionais import DICA_OCR, ocr_disponivel

from . import comandos
from .dados import ARQ_PREVIA
from .pagina import Pagina
from .widgets import Cartao, PainelStatus, Rolavel, botao, entrada, escolha, linha_inline, numero, opcao, responsivo, rotulo, PreviaViva

MODOS = (
    ("imagem", "Imagem", "Reconhece os PNGs da pasta de botões. Recomendado: rápido, preciso e "
     "não exige nada além do básico.", False),
    ("texto", "Texto (OCR)", "Lê palavras na tela (“Aceitar”, “Continuar”…). Opcional: precisa do "
     "Tesseract OCR.", True),
    ("auto", "Automático (OCR)", "Detecta retângulos com cara de botão e lê o rótulo. Opcional: "
     "precisa do Tesseract OCR.", True),
)


class PaginaAutomatico(Pagina):
    chave = "auto"
    titulo = "Automático"
    subtitulo = ""

    def construir(self) -> None:
        a, c = self.app, self.t.c
        rol = Rolavel(self.frame, self.t)
        rol.pack(fill="both", expand=True)
        f = rol.corpo
        self.ocr_ok, self.ocr_motivo = ocr_disponivel()
        if not self.ocr_ok and self.g.modo_auto in ("texto", "auto"):
            self.g.modo_auto = "imagem"

        # ---------------- modos ----------------
        m = Cartao(f, self.t, "Como detectar os botões", "")
        m.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        self.v_modo = a.var("modo_auto")
        linha = tk.Frame(m.corpo, bg=c["card"])
        m.linha_cheia(linha)
        caixas: list[tk.Frame] = []
        textos: list[tk.Label] = []
        for i, (chave, nome, desc, opcional) in enumerate(MODOS):
            cx = tk.Frame(linha, bg=c["card"], highlightthickness=1, highlightbackground=c["border"])
            caixas.append(cx)
            bloqueado = opcional and not self.ocr_ok
            rb = opcao(cx, nome + (" (recomendado)" if chave == "imagem" else ""), self.v_modo, chave,
                       self._mudou)
            rb.pack(anchor="w", padx=12, pady=(10, 0))
            if bloqueado:
                rb.state(["disabled"])
            lb = tk.Label(cx, text=desc, bg=c["card"], fg=c["muted"], font=self.t.f_pequena, wraplength=240,
                          justify="left", anchor="w")
            lb.pack(fill="x", padx=12, pady=(2, 4))
            textos.append(lb)
            if bloqueado:
                lw = tk.Label(cx, text=f"Indisponível: {self.ocr_motivo}.", bg=c["card"], fg=c["warn"],
                              font=self.t.f_pequena, wraplength=240, justify="left", anchor="w")
                lw.pack(fill="x", padx=12)
                textos.append(lw)
                botao(cx, "Como instalar", lambda: messagebox.showinfo(
                    "OCR (opcional)", DICA_OCR, parent=self.app.raiz), "Ghost", True).pack(
                    anchor="w", padx=12, pady=(4, 10))
            else:
                tk.Frame(cx, bg=c["card"], height=10).pack()

        estado_modos = {"n": 0, "w": 0}

        def dispor_modos(_e: Any = None) -> None:
            larg = linha.winfo_width()
            n = 3 if larg >= 660 else 1
            if n == estado_modos["n"] and abs(larg - estado_modos["w"]) < 8:
                return
            estado_modos["n"], estado_modos["w"] = n, larg
            for j in range(3):
                linha.columnconfigure(j, weight=1 if (n == 3 or j == 0) else 0, uniform="m" if n == 3 else "")
            for j, cx in enumerate(caixas):
                if n == 3:
                    cx.grid(row=0, column=j, sticky="nsew", padx=(0 if j == 0 else 8, 0), pady=0)
                else:
                    cx.grid(row=j, column=0, sticky="nsew", padx=0, pady=(0 if j == 0 else 8, 0))
            col = max(120, (larg - 16 * (n - 1)) // n - 30)
            for lb in textos:
                lb.configure(wraplength=col)

        linha.bind("<Configure>", dispor_modos)
        dispor_modos()

        # ---------------- varredura ----------------
        v = Cartao(f, self.t, "Varredura", "")
        v.campo("Intervalo entre varreduras", numero(v.corpo, a.var("intervalo"), 0.1, 60, 0.1, 8), "segundos")
        v.campo("Esperar antes de clicar de novo", numero(v.corpo, a.var("cooldown"), 0, 600, 1, 8),
                "segundos (no mesmo lugar)")
        var = linha_inline(v.corpo, self.t)
        var.columnconfigure(0, weight=1)
        self.esc_var = ttk.Scale(var, from_=0, to=0.5, orient="horizontal", style="Card.Horizontal.TScale",
                                 command=self._mudou_var)
        self.esc_var.grid(row=0, column=0, sticky="ew")
        self.lbl_var = rotulo(var, self.t, "0%", width=5)
        self.lbl_var.grid(row=0, column=1, padx=(8, 0))
        self.esc_var.set(self.g.variacao)
        v.campo("Variação aleatória dos tempos", var, "Evita um ritmo robótico (±%).")
        v.campo("Tamanho dos botões", escolha(v.corpo, a.var("escala"), ["auto", "1", "0.8", "0.6", "0.5"],
                                              10, editavel=True),
                "auto = descobre sozinho se a janela estiver menor que quando recortou os PNGs.")
        self.campo_palavras = entrada(v.corpo, a.var("palavras"), 28)
        v.campo("Palavras (modos OCR)", self.campo_palavras)
        v.campo("Parar após", numero(v.corpo, a.var("max_cliques"), 0, 999999, 10, 8), "ações (0 = sem limite)")
        v.campo("Parar após", numero(v.corpo, a.var("duracao_auto"), 0, 86400, 60, 8), "segundos (0 = sem limite)")

        # ---------------- segurança ----------------
        self.vars_arq = {"log": a.var("log"), "relatorio": a.var("relatorio")}
        s = Cartao(f, self.t, "Segurança e registro", "")
        s.campo("Janela sumida por mais de", numero(s.corpo, a.var("janela_max"), 0, 3600, 10, 8),
                "segundos: encerra (0 = nunca)")
        s.campo("Sem nenhuma ação por", numero(s.corpo, a.var("inatividade"), 0, 86400, 60, 8),
                "segundos = jogo travado? (0 = desligado)")
        s.campo("Tela sem mudar por", numero(s.corpo, a.var("tela_parada"), 0, 86400, 30, 8),
                "segundos = jogo travado? (0 = desligado)")
        s.campo("…então", escolha(s.corpo, a.var("ao_travar"), ["avisar", "parar"], 10))
        s.campo("Mostrar status a cada", numero(s.corpo, a.var("painel"), 0, 3600, 10, 8), "segundos (0 = não)")
        arq = linha_inline(s.corpo, self.t)
        arq.columnconfigure(0, weight=1)
        entrada(arq, self.vars_arq["log"]).grid(row=0, column=0, sticky="ew")
        botao(arq, "…", lambda: self._salvar_em("log", ".csv"), "Ghost", True).grid(row=0, column=1, padx=(6, 0))
        s.campo("Registro (CSV)", arq, "Cada clique, com horário e coordenadas.")
        arq2 = linha_inline(s.corpo, self.t)
        arq2.columnconfigure(0, weight=1)
        entrada(arq2, self.vars_arq["relatorio"]).grid(row=0, column=0, sticky="ew")
        botao(arq2, "…", lambda: self._salvar_em("relatorio", ".md"), "Ghost", True).grid(row=0, column=1, padx=(6, 0))
        s.campo("Relatório final", arq2, "Resumo da sessão (.md ou .json).")

        # ---------------- ações ----------------
        rod = tk.Frame(f, bg=c["bg"])
        rod.grid(row=99, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        responsivo(f, [v, s], linha0=1)
        pv = Cartao(f, self.t, "Visão ao vivo", "O que o programa enxerga agora, com os botões achados em verde "
                    "(atualiza a cada ~1 s enquanto roda).")
        self.previa = PreviaViva(pv.corpo, self.t, ARQ_PREVIA)
        self.previa.grid(row=0, column=0, columnspan=2, sticky="ew")
        pv.grid(row=50, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        a.registrar_previa(self.previa)
        rod.columnconfigure(0, weight=1)
        barra = tk.Frame(rod, bg=c["bg"])
        barra.grid(row=0, column=0, sticky="w", pady=(0, 10))
        self.btn_preview = botao(barra, "Pré-visualizar (não clica)", self.previsualizar, "Ghost")
        self.btn_preview.pack(side="left")
        self.btn_iniciar = botao(barra, "Iniciar automático", self.iniciar, "Ok")
        self.btn_iniciar.pack(side="left", padx=10)
        self.painel = PainelStatus(rod, self.t, "Partidas")
        self.painel.grid(row=1, column=0, sticky="ew")
        self.v_modo.trace_add("write", lambda *_a: self._mudou())
        self._mudou()

    # ------------------------------------------------------------------ #
    def _mudou(self) -> None:
        ocr = self.v_modo.get() in ("texto", "auto")
        self.campo_palavras.state(["!disabled"] if ocr else ["disabled"])

    def _mudou_var(self, val: str) -> None:
        x = round(float(val) * 20) / 20
        self.lbl_var.configure(text=f"{int(x * 100)}%")
        self.app.g.variacao = x

    def _salvar_em(self, campo: str, ext: str) -> None:
        arq = filedialog.asksaveasfilename(parent=self.app.raiz, defaultextension=ext,
                                           initialfile=f"{campo}{ext}")
        if arq:
            self.vars_arq[campo].set(arq)

    def iniciar(self) -> None:
        if not self._validar():
            return
        self.app.rodar(self.g.modo_auto, comandos.automatico(self.g), minimizar=True)

    def previsualizar(self) -> None:
        if not self._validar():
            return
        self.app.rodar(self.g.modo_auto, comandos.automatico(self.g, preview=True), minimizar=False,
                       ao_fim=lambda _c: self.app.mostrar_imagem("preview.png", "Pré-visualização"))

    def _validar(self) -> bool:
        if self.g.modo_auto in ("texto", "auto") and not self.ocr_ok:
            messagebox.showinfo("OCR indisponível", f"{self.ocr_motivo}.\n\n{DICA_OCR}", parent=self.app.raiz)
            return False
        return True

    def ao_estado(self, rodando: bool) -> None:
        for b in (self.btn_iniciar, self.btn_preview):
            b.state(["disabled"] if rodando else ["!disabled"])

    def ao_status(self, d: dict[str, Any]) -> None:
        if not d:
            self.painel.zerar()
        else:
            self.painel.atualizar(d)
