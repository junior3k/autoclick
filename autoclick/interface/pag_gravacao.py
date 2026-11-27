# pyright: basic
"""Página inicial: gravar o que você faz e reproduzir (em loop, com auto_detect)."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any

from . import comandos
from .dados import (ARQ_PREVIA, atualizar_referencia, comparar_ambiente, copia_de_seguranca, eventos_da_gravacao, listar_pngs, referencia_gravacao,
                    resumo_gravacao, tamanho_da_janela, tamanho_da_tela)
from .pagina import Pagina
from .widgets import (Cartao, PainelStatus, Rolavel, botao, entrada, escolha, linha_inline, marcar, numero, responsivo,
                      opcao, rotulo, PreviaViva)


class PaginaGravacao(Pagina):
    chave = "gravar"
    titulo = "Gravar & Reproduzir"
    subtitulo = ""

    def construir(self) -> None:
        a, c = self.app, self.t.c
        rol = Rolavel(self.frame, self.t)
        rol.pack(fill="both", expand=True)
        f = rol.corpo

        # ---------------- 1 · gravar ----------------
        g = Cartao(f, self.t, "Gravar", f"{self.g.tecla_parar} termina a gravação.", "1")
        self.v_arq = a.var("gravacao")
        linha = linha_inline(g.corpo, self.t)
        linha.columnconfigure(0, weight=1)
        entrada(linha, self.v_arq).grid(row=0, column=0, sticky="ew")
        botao(linha, "Procurar…", self.procurar, "Ghost", True).grid(row=0, column=1, padx=(6, 0))
        g.campo("Arquivo da gravação", linha)
        self.cb_ancora = escolha(g.corpo, a.var("ancora"), [""] + listar_pngs(self.g.pasta),
                                 editavel=True)
        g.campo("Âncora do mapa", self.cb_ancora)
        g.campo("Contagem inicial (s)", numero(g.corpo, a.var("atraso"), 0, 30))
        g.campo("Duração máxima (s)", numero(g.corpo, a.var("duracao"), 0, 7200, 10), "0 = até apertar F9")
        g.linha_cheia(marcar(g.corpo, "Gravar também as teclas", a.var("teclado")), (8, 0))
        g.linha_cheia(marcar(g.corpo, "Criar/atualizar regras no botoes.json ao terminar",
                             a.var("gerar_regras")))
        g.linha_cheia(marcar(g.corpo, "Substituir regras que já existem", a.var("sobrescrever")))
        bg = linha_inline(g.corpo, self.t)
        self.btn_gravar = botao(bg, "Iniciar gravação", self.gravar, "Danger")
        self.btn_gravar.pack(side="left")
        self.btn_editar = botao(bg, "Editar gravação…", self.editar, "Ghost", True)
        self.btn_editar.pack(side="left", padx=8)
        g.linha_cheia(bg, (16, 0))

        # ---------------- 2 · reproduzir ----------------
        r = Cartao(f, self.t, "Reproduzir", "", "2")
        self.v_vel = a.var("velocidade")
        vel = linha_inline(r.corpo, self.t)
        vel.columnconfigure(0, weight=1)
        from tkinter import ttk
        self.esc_vel = ttk.Scale(vel, from_=0.25, to=4.0, orient="horizontal",
                                 style="Card.Horizontal.TScale", command=self._mudou_vel)
        self.esc_vel.grid(row=0, column=0, sticky="ew")
        self.lbl_vel = rotulo(vel, self.t, "1.0×", width=6)
        self.lbl_vel.grid(row=0, column=1, padx=(8, 0))
        try:
            self.esc_vel.set(float(self.g.velocidade))
        except ValueError:
            self.esc_vel.set(1.0)
        r.campo("Velocidade", vel)
        rep = linha_inline(r.corpo, self.t)
        self.v_rep = a.var("repeticao")
        opcao(rep, "Uma vez", self.v_rep, "uma", self._mudou_rep).grid(row=0, column=0, sticky="w")
        sub = linha_inline(rep, self.t)
        sub.grid(row=1, column=0, sticky="w")
        opcao(sub, "Repetir", self.v_rep, "n", self._mudou_rep).pack(side="left")
        self.sp_voltas = numero(sub, a.var("voltas"), 1, 9999, 1, 6)
        self.sp_voltas.pack(side="left", padx=6)
        rotulo(sub, self.t, "vezes", muted=True).pack(side="left")
        opcao(rep, "Em loop até parar", self.v_rep, "loop", self._mudou_rep).grid(row=2, column=0, sticky="w")
        r.campo("Repetição", rep)
        r.campo("Pausa entre voltas", numero(r.corpo, a.var("pausa_loop"), 0, 600, 0.5), "segundos")
        r.linha_cheia(marcar(r.corpo, "Clicar sozinho nos botões “auto_detect”", a.var("auto_detect")), (8, 0))
        r.linha_cheia(marcar(r.corpo, "Só agir com a janela do jogo ativa", a.var("checar_janela")))
        self.btn_repro = botao(r.corpo, "Reproduzir", self.reproduzir, "Ok")
        r.linha_cheia(self.btn_repro, (16, 0))
        self.v_rep.trace_add("write", lambda *_a: self._mudou_rep())
        self._mudou_rep()

        # ---------------- rodapé ----------------
        rod = tk.Frame(f, bg=c["bg"])
        rod.grid(row=99, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        responsivo(f, [g, r])
        rod.columnconfigure(0, weight=1)
        self.info = tk.Label(rod, text="", bg=c["bg"], fg=c["muted"], font=self.t.f_normal, anchor="w")
        self.info.grid(row=0, column=0, sticky="w", pady=(0, 4))
        amb = tk.Frame(rod, bg=c["bg"])
        amb.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.lbl_amb = tk.Label(amb, text="", bg=c["bg"], fg=c["warn"], font=self.t.f_pequena, anchor="w",
                                justify="left", wraplength=560)
        self.lbl_amb.pack(side="left")
        self.btn_amb = botao(amb, "Usar tamanho atual", self.usar_tamanho_atual, "Ghost", True)
        pv = Cartao(rod, self.t, "Visão ao vivo", "")
        self.previa = PreviaViva(pv.corpo, self.t, ARQ_PREVIA)
        self.previa.grid(row=0, column=0, columnspan=2, sticky="ew")
        pv.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        a.registrar_previa(self.previa)
        cr = Cartao(rod, self.t, "Cronômetro da gravação", "")
        self.lbl_cron = tk.Label(cr.corpo, text="00:00.0", bg=c["bg"], fg=c["text"],
                                 font=("Consolas", 26, "bold"), anchor="w")
        self.lbl_cron.grid(row=0, column=0, sticky="w")
        self.lista_cron = tk.Text(cr.corpo, height=8, width=60, bg=c["bg"], fg=c["text"],
                                  font=("Consolas", 10), relief="flat", state="disabled")
        self.lista_cron.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        cr.corpo.columnconfigure(0, weight=1)
        cr.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self._t0_cron: float | None = None
        self._tick_cron: str | None = None
        self._linhas_cron: list[str] = []
        self.painel = PainelStatus(rod, self.t, "Voltas")
        self.painel.grid(row=4, column=0, sticky="ew")
        self.atualizar_info()

    # ------------------------------------------------------------------ #
    def _mudou_vel(self, v: str) -> None:
        x = round(float(v) * 4) / 4
        self.lbl_vel.configure(text=f"{x:g}×")
        self.app.g.velocidade = x

    def _mudou_rep(self) -> None:
        self.sp_voltas.state(["!disabled"] if self.v_rep.get() == "n" else ["disabled"])

    def procurar(self) -> None:
        arq = filedialog.askopenfilename(parent=self.app.raiz, title="Escolher gravação",
                                         filetypes=[("Gravação JSON", "*.json"), ("Todos", "*.*")])
        if arq:
            self.v_arq.set(arq)
            self.atualizar_info()

    def atualizar_info(self) -> None:
        self.info.configure(text="Gravação atual: " + resumo_gravacao(self.g.gravacao))
        self.verificar_ambiente()

    def verificar_ambiente(self) -> None:
        """Avisa se a tela/janela de hoje é diferente da da gravação."""
        ref = referencia_gravacao(self.g.gravacao)
        j = self.g.janela.strip()
        avisos = comparar_ambiente(ref, j, tamanho_da_tela(), tamanho_da_janela(j) if j else None)
        if avisos:
            self.lbl_amb.configure(text="⚠ Ambiente diferente da gravação: " + "; ".join(avisos)
                                   + ". Cliques por fração da janela se ajustam; regrave se algo ficar torto.")
            self.btn_amb.pack(side="left", padx=8)
        else:
            self.lbl_amb.configure(text="")
            self.btn_amb.pack_forget()

    def usar_tamanho_atual(self) -> None:
        j = self.g.janela.strip()
        if atualizar_referencia(self.g.gravacao, tamanho_da_tela(), tamanho_da_janela(j) if j else None):
            self.app.log_texto("✔ A gravação agora usa o tamanho atual da tela/janela como referência.\n", "ok")
        self.verificar_ambiente()

    def editar(self) -> None:
        from .editor_gravacao import EditorGravacao
        import os
        if not os.path.isfile(self.g.gravacao):
            self.app.log_texto("⚠ Ainda não há gravação para editar. Grave primeiro.\n", "aviso")
            return
        EditorGravacao(self.app, self.g.gravacao, ao_salvar=self.atualizar_info)

    def ao_mostrar(self) -> None:
        self.cb_ancora.configure(values=[""] + listar_pngs(self.g.pasta))
        self.atualizar_info()

    # ------------------------------------------------------------------ #
    def gravar(self, perguntar: bool = True) -> None:
        """`perguntar=False` (atalho de teclado, com o jogo na frente): não abre janela, só guarda a cópia."""
        n = eventos_da_gravacao(self.g.gravacao)
        if n and not perguntar:
            copia_de_seguranca(self.g.gravacao)
        elif n:  # já tem gravação neste arquivo: confirma e guarda uma cópia antes de regravar por cima
            nome = self.g.gravacao.replace("\\", "/").rsplit("/", 1)[-1]
            if not messagebox.askyesno("Substituir gravação?", f"“{nome}” já tem {n} eventos.\n\n"
                                       "Gravar de novo substitui o conteúdo. Uma cópia fica em "
                                       f"{nome[:-5] if nome.endswith('.json') else nome}.bak.json.",
                                       parent=self.app.raiz):
                return
            copia_de_seguranca(self.g.gravacao)
        if not self.g.janela.strip():
            self.app.log_texto("⚠ Dica: defina a janela do jogo em Configurações para a gravação "
                               "acompanhar a janela quando ela mexer.\n", "aviso")
        self.app.rodar("gravar", comandos.gravar(self.g), minimizar=True,
                       ao_fim=lambda _c: self.atualizar_info())

    def reproduzir(self) -> None:
        self.app.rodar("reproduzir", comandos.reproduzir(self.g), minimizar=True)

    def ao_estado(self, rodando: bool) -> None:
        for b in (self.btn_gravar, self.btn_repro, self.btn_editar):
            b.state(["disabled"] if rodando else ["!disabled"])

    def ao_status(self, d: dict[str, Any]) -> None:
        if not d:
            self.painel.zerar()
            self._parar_cron()
            return
        self.painel.atualizar(d)
        g = d.get("gravando")
        if isinstance(g, dict):
            self._t0_cron = float(g.get("t0", 0)) or None
            linhas = [str(x) for x in g.get("recentes", [])]
            if linhas != self._linhas_cron:
                self._linhas_cron = linhas
                self.lista_cron.configure(state="normal")
                self.lista_cron.delete("1.0", "end")
                self.lista_cron.insert("end", "\n".join(linhas))
                self.lista_cron.see("end")
                self.lista_cron.configure(state="disabled")
            if self._tick_cron is None:
                self._tick()

    def _tick(self) -> None:
        import time
        if self._t0_cron is not None:
            t = max(0.0, time.time() - self._t0_cron)
            self.lbl_cron.configure(text=f"{int(t // 60):02d}:{t % 60:04.1f}")
        self._tick_cron = self.app.raiz.after(100, self._tick)

    def _parar_cron(self) -> None:
        if self._tick_cron is not None:
            try:
                self.app.raiz.after_cancel(self._tick_cron)
            except Exception:
                pass
            self._tick_cron = None
        self._t0_cron = None  # o último valor e a lista ficam na tela para conferir
