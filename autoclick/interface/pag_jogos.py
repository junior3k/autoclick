# pyright: basic
"""Página Jogos: o Roblox tem milhares; cada um com seus botões, regras, gravação e opções."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Optional

from .. import jogos
from .dados import formatar_duracao, ler_historico
from .dialogos import pedir_texto
from .pagina import Pagina
from .widgets import Cartao, Rolavel, botao, entrada, marcar


class PaginaJogos(Pagina):
    chave = "jogos"
    titulo = "Jogos"
    subtitulo = ""

    def construir(self) -> None:
        a, c, t = self.app, self.t.c, self.t
        rol = Rolavel(self.frame, t)
        rol.pack(fill="both", expand=True)
        g = rol.corpo
        ctl = a.jogos

        # ---- lista ---- #
        k = Cartao(g, t, "Seus jogos", "Escolha o jogo; as páginas Gravar, Regras e Automático passam a "
                   "usar os arquivos dele (pasta jogos/NOME).")
        k.pack(fill="x", pady=(0, 12))
        self.lbl_atual = tk.Label(k.corpo, text="", bg=c["card"], fg=c["accent"], font=t.f_negrito, anchor="w")
        self.lbl_atual.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.arv = ttk.Treeview(k.corpo, columns=("nome", "ids", "botoes"), show="headings", height=6,
                                selectmode="browse")
        for col, txt, w in (("nome", "Jogo", 200), ("ids", "Ids do Roblox", 160), ("botoes", "Botões", 60)):
            self.arv.heading(col, text=txt)
            self.arv.column(col, width=w, stretch=(col == "nome"))
        self.arv.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.arv.bind("<<TreeviewSelect>>", lambda _e: self._ao_selecionar())
        barra = tk.Frame(k.corpo, bg=c["card"])
        barra.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        botao(barra, "Usar este jogo", self.usar, "Accent", True).pack(side="left")
        botao(barra, "Novo jogo…", self.novo, "Ghost", True).pack(side="left", padx=6)
        botao(barra, "Salvar minhas opções neste jogo", self.salvar_opcoes, "Ghost", True).pack(side="left")
        botao(barra, "Apagar", self.apagar, "Danger", True).pack(side="right")

        # ---- reconhecimento ---- #
        r = Cartao(g, t, "Reconhecer o jogo", "Ids: o número que aparece no link do jogo "
                   "(roblox.com/games/NÚMERO/nome). Assinatura: PNGs que só existem nesse jogo.")
        r.pack(fill="x", pady=(0, 12))
        r.linha_cheia(marcar(r.corpo, "Trocar de jogo sozinho pelos logs do Roblox (experimental)",
                             a.var("detectar_jogo")))
        self.v_ids = tk.StringVar()
        self.v_ass = tk.StringVar()
        r.campo("Ids (separados por vírgula)", entrada(r.corpo, self.v_ids, 30))
        r.campo("Assinatura visual (nomes de PNG)", entrada(r.corpo, self.v_ass, 30))
        b2 = tk.Frame(r.corpo, bg=c["card"])
        r.linha_cheia(b2, (4, 0))
        botao(b2, "Salvar ids e assinatura", self.salvar_ids, "Ghost", True).pack(side="left")
        botao(b2, "Detectar pelos logs", self.detectar_logs, "Ghost", True).pack(side="left", padx=6)
        botao(b2, "Detectar pela tela", self.detectar_tela, "Ghost", True).pack(side="left")
        b3 = tk.Frame(r.corpo, bg=c["card"])
        r.linha_cheia(b3, (6, 0))
        botao(b3, "Cadastrar o jogo detectado nos logs…", self.cadastrar_detectado, "Ghost", True).pack(side="left")
        botao(b3, "Coletar pistas dos logs (só as linhas úteis)", self.coletar, "Ghost", True).pack(side="left", padx=6)
        self.lbl_det = tk.Label(r.corpo, text="", bg=c["card"], fg=c["muted"], font=t.f_pequena,
                                anchor="w", justify="left", wraplength=520)
        r.linha_cheia(self.lbl_det, (6, 0))

        # ---- estatísticas ---- #
        e = Cartao(g, t, "Estatísticas por jogo", "Calculadas do Histórico (voltas por hora, tempo médio de volta).")
        e.pack(fill="x", pady=(0, 12))
        cols = ("jogo", "sessoes", "tempo", "voltas", "vh", "spv")
        self.est = ttk.Treeview(e.corpo, columns=cols, show="headings", height=5)
        for col, txt, w in (("jogo", "Jogo", 170), ("sessoes", "Sessões", 60), ("tempo", "Tempo ativo", 90),
                            ("voltas", "Voltas", 60), ("vh", "Voltas/h", 70), ("spv", "s por volta", 80)):
            self.est.heading(col, text=txt)
            self.est.column(col, width=w, stretch=(col == "jogo"))
        self.est.grid(row=0, column=0, columnspan=2, sticky="ew")
        b4 = tk.Frame(e.corpo, bg=c["card"])
        b4.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        botao(b4, "Atualizar", self.atualizar_estatisticas, "Ghost", True).pack(side="left")
        botao(b4, "Exportar CSV…", self.exportar_csv, "Ghost", True).pack(side="left", padx=6)
        self.lbl_botoes = tk.Label(e.corpo, text="", bg=c["card"], fg=c["muted"], font=t.f_pequena,
                                   anchor="w", justify="left", wraplength=520)
        self.lbl_botoes.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

    # ------------------------------------------------------------------ #
    def ao_mostrar(self) -> None:
        self.recarregar()
        self.atualizar_estatisticas()

    def _selecionado(self) -> str:
        sel = self.arv.selection()
        return sel[0] if sel else self.app.jogos.atual()

    def recarregar(self) -> None:
        ctl = self.app.jogos
        for i in self.arv.get_children():
            self.arv.delete(i)
        for j in ctl.lista():
            n = len(list((jogos.pasta_do(j.slug) / "botoes").glob("*.png"))) if not j.geral else 0
            self.arv.insert("", "end", iid=j.slug, values=(j.nome, ", ".join(j.ids), n if not j.geral else "—"))
        atual = ctl.atual()
        if self.arv.exists(atual):
            self.arv.selection_set(atual)
        self.lbl_atual.configure(text=f"Jogo em uso: {ctl.nome_atual()}")
        self._ao_selecionar()

    def _ao_selecionar(self) -> None:
        j = jogos.ler(self._selecionado())
        if j is None:
            return
        self.v_ids.set(", ".join(j.ids))
        self.v_ass.set(", ".join(j.assinatura))

    def usar(self) -> None:
        if self.app.jogos.escolher(self._selecionado()):
            self.app.ir("jogos")

    def novo(self) -> None:
        nome = pedir_texto(self.app.raiz, self.t, "Novo jogo", "Nome do jogo (ex.: Blox Fruits):")
        if nome and nome.strip():
            j = self.app.jogos.novo(nome)
            self.app.jogos.escolher(j.slug, "novo")
            self.app.ir("jogos")

    def apagar(self) -> None:
        s = self._selecionado()
        if s == jogos.GERAL:
            messagebox.showinfo("Jogos", "O Roblox (geral) não pode ser apagado.", parent=self.app.raiz)
            return
        if messagebox.askyesno("Apagar jogo", f"Apagar “{jogos.nome_de(s)}” com seus botões, regras e "
                               "gravação? Não dá para desfazer.", parent=self.app.raiz):
            self.app.jogos.apagar(s)
            self.app.jogo_mudou()

    def salvar_opcoes(self) -> None:
        if self.app.jogos.salvar_opcoes():
            self.app.log_texto(f"✔ Opções guardadas em “{self.app.jogos.nome_atual()}” "
                               "(intervalo, variação, rigor, loop, som…).\n", "ok")

    def salvar_ids(self) -> None:
        s = self._selecionado()
        if s == jogos.GERAL:
            return
        sep = lambda v: [x.strip() for x in v.replace(";", ",").split(",") if x.strip()]  # noqa: E731
        self.app.jogos.definir_ids(s, sep(self.v_ids.get()), sep(self.v_ass.get()))
        self.recarregar()

    def detectar_logs(self) -> None:
        slug, i = self.app.jogos.detectar_logs()
        if slug:
            self.lbl_det.configure(text=f"Reconhecido: {jogos.nome_de(slug)} (id {i}).")
            self.app.jogos.escolher(slug, "detectado pelos logs")
        elif i:
            self.lbl_det.configure(text=f"Os logs mostram o id {i}, que nenhum jogo cadastrado tem. "
                                        "Use “Cadastrar o jogo detectado”.")
        else:
            self.lbl_det.configure(text="Não achei o jogo nos logs (o Roblox está aberto? a detecção é "
                                        "experimental; use a assinatura visual ou escolha à mão).")

    def detectar_tela(self) -> None:
        self.app.jogos.detectar_tela()

    def cadastrar_detectado(self) -> None:
        self.app.jogos.detectar_logs()
        ids = list(self.app.jogos.ids_atuais)
        if not self.app.jogos.ultimo_id or not ids:
            self.lbl_det.configure(text="Nenhum id novo nos logs agora.")
            return
        self.lbl_det.configure(text="Perguntando o nome ao Roblox…")
        self.app.em_segundo_plano(lambda: jogos.nome_do_jogo(ids), lambda n: self._perguntar_nome(ids, n))

    def _perguntar_nome(self, ids: list[str], sugestao: Optional[str]) -> None:
        self.lbl_det.configure(text="" if sugestao else "Não consegui o nome pela internet; digite à mão.")
        nome = pedir_texto(self.app.raiz, self.t, "Cadastrar jogo",
                           f"Nome do jogo (ids {', '.join(ids)}):", sugestao or "")
        if nome and nome.strip():
            j = self.app.jogos.novo(nome, ids)
            self.app.jogos.escolher(j.slug, "cadastrado")

    def coletar(self) -> None:
        linhas = self.app.jogos.coletar_pistas().splitlines()
        resumo = linhas[1] if len(linhas) > 1 else (linhas[0] if linhas else "")
        self.lbl_det.configure(text="Salvei pistas_roblox.txt (só as linhas úteis; pode me mandar esse "
                                    "arquivo). " + resumo)

    # ---- estatísticas ---- #
    def atualizar_estatisticas(self) -> None:
        sess = ler_historico()
        nomes = {j.slug: j.nome for j in self.app.jogos.lista()}
        for i in self.est.get_children():
            self.est.delete(i)
        todas = jogos.estatisticas(sess)
        for r in todas:
            self.est.insert("", "end", values=(
                nomes.get(r["jogo"], r["jogo"]), r["sessoes"], formatar_duracao(r["segundos"]),
                r["voltas"], r["voltas_hora"] or "—", r["seg_por_volta"] or "—"))
        atual = next((r for r in todas if r["jogo"] == self.app.jogos.atual()), None)
        if atual and atual["botoes"]:
            top = sorted(atual["botoes"].items(), key=lambda kv: -kv[1])[:6]
            self.lbl_botoes.configure(text="Cliques por botão (jogo em uso): "
                                      + ", ".join(f"{k} {v}" for k, v in top))
        else:
            self.lbl_botoes.configure(text="")

    def exportar_csv(self) -> None:
        arq = filedialog.asksaveasfilename(parent=self.app.raiz, defaultextension=".csv",
                                           initialfile="estatisticas.csv", filetypes=[("CSV", "*.csv")])
        if not arq:
            return
        nomes = {j.slug: j.nome for j in self.app.jogos.lista()}
        try:
            with open(arq, "w", encoding="utf-8-sig", newline="") as f:
                f.write(jogos.csv_estatisticas(ler_historico(), nomes))
            self.app.log_texto(f"✔ Estatísticas salvas em {arq}\n", "ok")
        except OSError as ex:
            messagebox.showerror("Exportar", str(ex), parent=self.app.raiz)
