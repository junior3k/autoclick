# pyright: basic
"""Editor visual do botoes.json: escolha um botão e configure o que o programa faz com ele."""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Optional

from . import comandos
from .dados import (caminho_png, escrever_config, lista_fluxo, ler_config, listar_pngs, regras_de)
from .dialogos import pedir_texto
from .pagina import Pagina
from .regras_form import (ACOES, AO_VER, AUTO_OPCOES, DESCRICAO_ACAO, DESTINOS, ESCOLHAS,
                          campos_para_etapa, campos_para_regra, etapa_para_campos,
                          regra_para_campos)
from .widgets import Cartao, Rolavel, botao, entrada, escolha, linha_inline, numero, rotulo


class PaginaRegras(Pagina):
    chave = "regras"
    titulo = "Botões & regras"
    subtitulo = "Diga ao programa o que fazer com cada botão: clicar, arrastar, esperar uma condição…"

    def construir(self) -> None:
        c = self.t.c
        f = self.frame
        f.columnconfigure(1, weight=1)
        f.rowconfigure(0, weight=1)
        self.dados: dict[str, Any] = {}
        self._desfazer: list[Optional[str]] = []  # texto do botoes.json antes de cada alteração
        self._refazer: list[Optional[str]] = []
        self._base: dict[str, str] = {}  # campos como estavam ao abrir o botão (para "alterações não salvas")
        self._voltando = False
        self.sel: Optional[str] = None
        self.v: dict[str, tk.StringVar] = {}
        self._thumb: Any = None

        # ---------------- lista ----------------
        # A lista fica numa área rolável: se a janela for baixa, rola em vez de esmagar a lista.
        self.rol_esq = Rolavel(f, self.t)
        self.rol_esq.canvas.configure(width=318)
        self.rol_esq.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        esq = Cartao(self.rol_esq.corpo, self.t, "Botões")
        esq.pack(fill="both", expand=True)
        self.arvore = ttk.Treeview(esq.corpo, columns=("acao", "info"), show="tree headings",
                                   height=10, selectmode="browse")
        self.arvore.heading("#0", text="Nome")
        self.arvore.heading("acao", text="Ação")
        self.arvore.heading("info", text="")
        self.arvore.column("#0", width=128, minwidth=100, stretch=True)
        self.arvore.column("acao", width=64, minwidth=56, stretch=False)
        self.arvore.column("info", width=70, minwidth=60, stretch=False)
        self.arvore.tag_configure("falta", foreground=c["warn"])
        self.arvore.tag_configure("sem_regra", foreground=c["muted"])
        sb = ttk.Scrollbar(esq.corpo, orient="vertical", command=self.arvore.yview)
        self.arvore.configure(yscrollcommand=sb.set)
        esq.corpo.rowconfigure(0, weight=1)
        self.arvore.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        esq.corpo.columnconfigure(0, weight=1)
        esq.corpo.columnconfigure(1, weight=0)
        self.arvore.bind("<<TreeviewSelect>>", self._escolhido)
        barra = tk.Frame(esq.corpo, bg=c["card"])
        barra.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        botao(barra, "+  Recortar novo botão", self.recortar_novo, "Accent", True).pack(fill="x")
        botao(barra, "Etapas do jogo (fluxo)…", self.editar_fluxo, "Ghost", True).pack(fill="x", pady=(6, 0))
        outra = tk.Frame(barra, bg=c["card"])
        outra.pack(fill="x", pady=(6, 0))
        botao(outra, "Atualizar", self.recarregar, "Ghost", True).pack(side="left", expand=True, fill="x")
        botao(outra, "Validar", self.validar, "Ghost", True).pack(side="left", expand=True, fill="x", padx=(6, 0))
        hist = tk.Frame(barra, bg=c["card"])
        hist.pack(fill="x", pady=(6, 0))
        self.btn_des = botao(hist, "Desfazer", self.desfazer, "Ghost", True)
        self.btn_des.pack(side="left", expand=True, fill="x")
        self.btn_ref = botao(hist, "Refazer", self.refazer, "Ghost", True)
        self.btn_ref.pack(side="left", expand=True, fill="x", padx=(6, 0))
        self.lbl_arq = rotulo(esq.corpo, self.t, "", muted=True, anchor="w", justify="left", wraplength=260)
        self.lbl_arq.grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

        # ---------------- editor ----------------
        self.rol = Rolavel(f, self.t)
        self.rol.grid(row=0, column=1, sticky="nsew")
        self._construir_editor(self.rol.corpo)
        self._esq, self._empilhado = esq, None
        f.bind("<Configure>", self._ajustar_layout)
        self._ajustar_layout()
        self.recarregar()

    def _ajustar_layout(self, _e: Any = None) -> None:
        """Largo: lista à esquerda e editor à direita. Estreito: lista em cima e editor embaixo.
        A lista sempre mostra algumas linhas (4 no mínimo) e o resto da coluna rola."""
        f = self.frame
        empilhar = 1 < f.winfo_width() < 640
        if empilhar != self._empilhado:
            self._empilhado = empilhar
            if empilhar:
                f.columnconfigure(0, weight=1)
                f.columnconfigure(1, weight=0)
                f.rowconfigure(0, weight=0)
                f.rowconfigure(1, weight=1)
                self.rol_esq.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 10))
                self.rol.grid(row=1, column=0, sticky="nsew")
            else:
                f.columnconfigure(0, weight=0)
                f.columnconfigure(1, weight=1)
                f.rowconfigure(0, weight=1)
                f.rowconfigure(1, weight=0)
                self.rol_esq.grid(row=0, column=0, sticky="ns", padx=(0, 14), pady=0)
                self.rol.grid(row=0, column=1, sticky="nsew")
        self._ajustar_linhas()

    def _ajustar_linhas(self) -> None:
        """Quantas linhas da lista cabem na altura disponível (4 a 16)."""
        altura = self.frame.winfo_height()
        if altura <= 1:
            return
        linha = 28  # altura de uma linha da lista (ver tema.py)
        fixo = self._esq.winfo_reqheight() - self.arvore.winfo_reqheight()
        if self._empilhado:
            linhas = 4
            self.rol_esq.canvas.configure(height=fixo + 4 * linha + 4)
        else:
            linhas = max(4, min(16, (altura - fixo - 8) // linha))
        if int(self.arvore.cget("height")) != linhas:
            self.arvore.configure(height=linhas)

    # ------------------------------------------------------------------ #
    # editor
    # ------------------------------------------------------------------ #
    def _sv(self, chave: str, valor: str = "") -> tk.StringVar:
        s = tk.StringVar(value=valor)
        self.v[chave] = s
        return s

    def _construir_editor(self, pai: tk.Misc) -> None:
        c, t = self.t.c, self.t
        # cabeçalho com miniatura
        self.cab = Cartao(pai, t, "", "")
        self.cab.pack(fill="x", pady=(0, 12))
        topo = tk.Frame(self.cab.corpo, bg=c["card"])
        topo.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.miniatura = tk.Label(topo, bg=c["field"], fg=c["muted"], text="sem\nprévia", width=14,
                                  height=4, font=t.f_pequena)
        self.miniatura.pack(side="left")
        info = tk.Frame(topo, bg=c["card"])
        info.pack(side="left", padx=16, fill="x", expand=True)
        self.lbl_nome = tk.Label(info, text="Selecione um botão", bg=c["card"], fg=c["text"],
                                 font=t.f_grande, anchor="w")
        self.lbl_nome.pack(fill="x")
        self.lbl_png = tk.Label(info, text="", bg=c["card"], fg=c["muted"], font=t.f_pequena, anchor="w",
                                justify="left")
        self.lbl_png.pack(fill="x", pady=(4, 0))

        # 1) ação
        s1 = Cartao(pai, t, "O que fazer", "")
        s1.pack(fill="x", pady=(0, 12))
        self.cb_acao = escolha(s1.corpo, self._sv("acao", "clicar"), ACOES, 22)
        self.cb_acao.bind("<<ComboboxSelected>>", lambda _e: self._visibilidade())
        s1.campo("Ação", self.cb_acao)
        self.lbl_desc = rotulo(s1.corpo, t, "", muted=True, anchor="w", justify="left", wraplength=620)
        s1.linha_cheia(self.lbl_desc)

        # 2) quando
        self.s2 = Cartao(pai, t, "Quando e quanto", "")
        self.s2.pack(fill="x", pady=(0, 12))
        s2 = self.s2
        s2.campo("Clicar sozinho (auto_detect)", escolha(s2.corpo, self._sv("auto_detect", "padrão"),
                                                          AUTO_OPCOES, 12),
                 "“sim” = clica assim que aparece, até durante a reprodução da gravação.")
        s2.campo("Vezes por partida", numero(s2.corpo, self._sv("vezes", "0"), 0, 9999, 1, 8),
                 "0 = quantas vezes aparecer.")
        s2.campo("Intervalo mínimo (s)", entrada(s2.corpo, self._sv("intervalo"), 10),
                 "Vazio = usa o padrão. Ex.: 2 para clicar no máximo a cada 2 s.")
        off = linha_inline(s2.corpo, t)
        numero(off, self._sv("off_x", "0"), -500, 500, 1, 6).pack(side="left")
        rotulo(off, t, "  ×  ", muted=True).pack(side="left")
        numero(off, self._sv("off_y", "0"), -500, 500, 1, 6).pack(side="left")
        s2.campo("Deslocar o clique (px)", off, "Mexe o ponto do clique em relação ao centro do botão.")
        rl = ttk.Checkbutton(s2.corpo, text="Este botão reinicia o ciclo (ex.: Jogar Novamente)",
                             variable=self._sv("reiniciar_loop", "0"), onvalue="1", offvalue="0",
                             style="Card.TCheckbutton")
        s2.linha_cheia(rl, (6, 0))
        s2.campo("Escolher UM entre vários", escolha(s2.corpo, self._sv("escolha"), ESCOLHAS, 14),
                 "Para 3 cartas parecidas: clica em uma só por aparição.")
        s2.campo("Grupo da escolha", entrada(s2.corpo, self._sv("grupo"), 18),
                 "Botões diferentes com o mesmo grupo disputam a mesma escolha.")

        # 3) condições
        self.s3 = Cartao(pai, t, "Condições", "")
        self.s3.pack(fill="x", pady=(0, 12))
        s3 = self.s3
        s3.campo("Só se estiver à vista", entrada(s3.corpo, self._sv("requer"), 30),
                 "Nomes de outros botões, separados por vírgula.")
        s3.campo("Ignorar se estiver à vista", entrada(s3.corpo, self._sv("ignorar_se"), 30))
        self.cb_etapa = escolha(s3.corpo, self._sv("etapa"), [""], 22, editavel=True)
        s3.campo("Só nesta etapa do jogo", self.cb_etapa, "Etapas definidas em “Etapas do jogo (fluxo)”.")

        # 4) arrastar
        self.s4 = Cartao(pai, t, "Arrastar e soltar", "Para onde levar o botão (ex.: colocar uma torre).")
        self.s4.pack(fill="x", pady=(0, 12))
        s4 = self.s4
        self.cb_dest = escolha(s4.corpo, self._sv("dest_tipo", "nenhum"), DESTINOS, 14)
        self.cb_dest.bind("<<ComboboxSelected>>", lambda _e: self._visibilidade())
        s4.campo("Tipo de destino", self.cb_dest,
                 "fração da janela = acompanha a janela; âncora = acompanha a câmera; fixo = ponto da tela.")
        self.f_fixo = linha_inline(s4.corpo, t)
        entrada(self.f_fixo, self._sv("dest_x"), 7).pack(side="left")
        rotulo(self.f_fixo, t, "  ,  ", muted=True).pack(side="left")
        entrada(self.f_fixo, self._sv("dest_y"), 7).pack(side="left")
        self.f_jan = linha_inline(s4.corpo, t)
        entrada(self.f_jan, self._sv("dest_fx"), 7).pack(side="left")
        rotulo(self.f_jan, t, "  ,  ", muted=True).pack(side="left")
        entrada(self.f_jan, self._sv("dest_fy"), 7).pack(side="left")
        rotulo(self.f_jan, t, "   (0 a 1: 0.5 = meio)", muted=True).pack(side="left")
        self.f_anc = linha_inline(s4.corpo, t)
        self.cb_anc = escolha(self.f_anc, self._sv("dest_ancora"), [""], 16, editavel=True)
        self.cb_anc.pack(side="left")
        rotulo(self.f_anc, t, "  desloca ", muted=True).pack(side="left")
        entrada(self.f_anc, self._sv("dest_dx", "0"), 6).pack(side="left")
        rotulo(self.f_anc, t, " , ", muted=True).pack(side="left")
        entrada(self.f_anc, self._sv("dest_dy", "0"), 6).pack(side="left")
        self._linha_destino = s4._linha
        s4._linha += 3
        cz = ttk.Checkbutton(s4.corpo, text="Confirmar que o botão ficou cinza depois de arrastar",
                             variable=self._sv("confirmar_cinza", "1"), onvalue="1", offvalue="0",
                             style="Card.TCheckbutton")
        s4.linha_cheia(cz, (8, 0))
        s4.campo("Queda de saturação", entrada(s4.corpo, self._sv("queda", "0.5"), 8),
                 "Cinza = cor caiu para esta fração (0.5 = metade). Use “Calibrar” para medir.")
        s4.campo("Tentativas", numero(s4.corpo, self._sv("tentativas", "3"), 1, 20, 1, 6))
        s4.campo("Esperar antes de conferir (s)", entrada(s4.corpo, self._sv("espera_conf", "0.7"), 8))
        ferr = tk.Frame(s4.corpo, bg=c["card"])
        s4.linha_cheia(ferr, (10, 0))
        botao(ferr, "Definir destino clicando na tela", self.definir_destino, "Accent", True).pack(side="left")
        botao(ferr, "Calibrar cinza", self.calibrar, "Ghost", True).pack(side="left", padx=8)

        # 5) erro
        self.s5 = Cartao(pai, t, "Tela de erro", "")
        self.s5.pack(fill="x", pady=(0, 12))
        self.s5.campo("Ao ver esta tela", escolha(self.s5.corpo, self._sv("ao_ver", "avisar"), AO_VER, 12),
                      "parar = encerra · reconectar = recomeça a partida (até 5 vezes em 10 min).")
        self.cb_reconectar = escolha(self.s5.corpo, self._sv("reconectar_com"), [""], 22, editavel=True)
        self.s5.campo("Reconectar com o botão", self.cb_reconectar,
                      "Opcional: o botão (regra “clicar”) que reconecta ou fecha o aviso.")

        # ações
        self.barra = tk.Frame(pai, bg=c["bg"])
        self.barra.pack(fill="x", pady=(0, 20))
        self.btn_salvar = botao(self.barra, "Salvar regra", self.salvar, "Accent")
        self.btn_salvar.pack(side="left")
        self.btn_remover = botao(self.barra, "Remover regra", self.remover, "Ghost")
        self.btn_remover.pack(side="left", padx=10)
        self._visibilidade()

    def _visibilidade(self) -> None:
        acao = self.v["acao"].get()
        self.lbl_desc.configure(text=DESCRICAO_ACAO.get(acao, ""))
        clicavel = acao in ("clicar", "arrastar")
        grupos = ((self.s2, clicavel), (self.s3, True), (self.s4, acao == "arrastar"),
                  (self.s5, acao == "erro"))
        for cartao, _m in grupos:
            cartao.pack_forget()
        for cartao, mostrar in grupos:  # reempacota em ordem, sempre antes da barra de botões
            if mostrar:
                cartao.pack(fill="x", pady=(0, 12), before=self.barra)
        tipo = self.v["dest_tipo"].get()
        for w in (self.f_fixo, self.f_jan, self.f_anc):
            w.grid_forget()
        alvo = {"fixo": (self.f_fixo, "Ponto da tela X , Y"), "janela": (self.f_jan, "Fração X , Y"),
                "ancora": (self.f_anc, "Âncora")}.get(tipo)
        if alvo is not None:
            w, _txt = alvo
            w.grid(row=self._linha_destino, column=1, sticky="w", pady=4)

    # ------------------------------------------------------------------ #
    # dados
    # ------------------------------------------------------------------ #
    def ao_mostrar(self) -> None:
        self.recarregar()
        self._botoes_historico()

    def recarregar(self) -> None:
        try:
            self.dados = ler_config(self.g.config)
            erro = ""
        except ValueError as e:
            self.dados, erro = {}, str(e)
        regras = regras_de(self.dados)
        pngs = listar_pngs(self.g.pasta)
        for i in self.arvore.get_children():
            self.arvore.delete(i)
        for nome in sorted(set(regras) | set(pngs)):
            r = regras.get(nome)
            if r is None:
                self.arvore.insert("", "end", iid=nome, text=nome, values=("-", "sem regra"),
                                   tags=("sem_regra",))
            else:
                tem = nome in pngs
                info = "" if tem else "sem img"
                if tem and r.get("auto_detect"):
                    info = "auto"
                self.arvore.insert("", "end", iid=nome, text=nome,
                                   values=(str(r.get("acao", "clicar")), info),
                                   tags=() if tem else ("falta",))
        self.lbl_arq.configure(text=(f"⚠ {erro}" if erro else f"{self.g.config}  ·  pasta “{self.g.pasta}”"
                                     f"  ·  {len(pngs)} imagem(ns), {len(regras)} regra(s)"))
        etapas = [str(e.get("etapa", "")) for e in lista_fluxo(self.dados)]
        self.cb_etapa.configure(values=[""] + etapas)
        self.cb_anc.configure(values=[""] + pngs)
        self.cb_reconectar.configure(values=[""] + sorted(regras))
        if self.sel and self.arvore.exists(self.sel):
            self.arvore.selection_set(self.sel)
        elif self.sel:
            self.sel = None
            self._mostrar(None)

    def _escolhido(self, _e: Any = None) -> None:
        if self._voltando:
            return
        s = self.arvore.selection()
        novo = s[0] if s else None
        if novo != self.sel and not self.pode_sair(f"Trocar para “{novo}”" if novo else "Continuar"):
            self._voltando = True  # o usuário cancelou: volta para o botão que estava aberto
            try:
                if self.sel and self.arvore.exists(self.sel):
                    self.arvore.selection_set(self.sel)
            finally:
                self._voltando = False
            return
        self._mostrar(novo)

    # ------------------------------------------------------------------ #
    # alterações não salvas, desfazer / refazer
    # ------------------------------------------------------------------ #
    def _sujo(self) -> bool:
        return bool(self.sel) and bool(self._base) and self._campos() != self._base

    def pode_sair(self, _acao: str = "Sair") -> bool:
        """Se há campos editados e não salvos, pergunta. False = o usuário cancelou."""
        if not self._sujo():
            return True
        r = messagebox.askyesnocancel("Alterações não salvas",
                                      f"O botão “{self.sel}” tem alterações não salvas.\n\nSalvar agora?",
                                      parent=self.app.raiz)
        if r is None:
            return False
        if r:
            return self.salvar(silencioso=True)
        self._base = {}  # descartar
        return True

    def _texto_config(self) -> Optional[str]:
        try:
            return Path(self.g.config).read_text(encoding="utf-8")
        except OSError:
            return None

    def _guardar_estado(self) -> None:
        """Chame ANTES de qualquer alteração do botoes.json (salvar, remover, ferramentas externas)."""
        atual = self._texto_config()
        if not self._desfazer or self._desfazer[-1] != atual:
            self._desfazer.append(atual)
            del self._desfazer[:-50]
        self._refazer.clear()
        self._botoes_historico()

    def _gravar(self, dados: dict[str, Any]) -> None:
        self._guardar_estado()
        escrever_config(self.g.config, dados)

    def _restaurar(self, texto: Optional[str]) -> None:
        p = Path(self.g.config)
        if texto is None:
            p.unlink(missing_ok=True)
        else:
            p.write_text(texto, encoding="utf-8")

    def desfazer(self) -> None:
        if not self._desfazer:
            return
        self._refazer.append(self._texto_config())
        self._restaurar(self._desfazer.pop())
        self.app.log_texto("↶ Desfeito (botoes.json voltou ao estado anterior).\n", "dim")
        self._depois_historico()

    def refazer(self) -> None:
        if not self._refazer:
            return
        self._desfazer.append(self._texto_config())
        self._restaurar(self._refazer.pop())
        self.app.log_texto("↷ Refeito.\n", "dim")
        self._depois_historico()

    def _depois_historico(self) -> None:
        self.recarregar()
        self._mostrar(self.sel if self.sel and self.arvore.exists(self.sel) else None)
        self._botoes_historico()

    def _botoes_historico(self) -> None:
        self.btn_des.state(["!disabled"] if self._desfazer else ["disabled"])
        self.btn_ref.state(["!disabled"] if self._refazer else ["disabled"])

    def _mostrar(self, nome: Optional[str]) -> None:
        self.sel = nome
        habil = nome is not None
        for b in (self.btn_salvar, self.btn_remover):
            b.state(["!disabled"] if habil else ["disabled"])
        self._thumb = None
        if nome is None:
            self.lbl_nome.configure(text="Selecione um botão")
            self.lbl_png.configure(text="Escolha um item na lista, ou recorte um botão novo.")
            self.miniatura.configure(image="", text="sem\nprévia", width=14, height=4)
            return
        r = regras_de(self.dados).get(nome)
        campos = regra_para_campos(r or {})
        for k, val in campos.items():
            if k in self.v:
                self.v[k].set(val)
        self.lbl_nome.configure(text=nome)
        png = caminho_png(self.g.pasta, nome)
        self.lbl_png.configure(text=(f"{png}" if png else "⚠ Não há imagem com esse nome na pasta de botões.")
                               + ("" if r else "\nEste botão ainda não tem regra: configure e salve."))
        self.miniatura.configure(image="", text="sem\nprévia", width=14, height=4)
        if png is not None and png.suffix.lower() == ".png":
            try:
                img = tk.PhotoImage(file=str(png))
                w, h = img.width(), img.height()
                if w < 60 and h < 60:
                    img = img.zoom(max(1, 90 // max(w, h, 1)))
                f = max(1, -(-img.width() // 150), -(-img.height() // 80))
                if f > 1:
                    img = img.subsample(f, f)
                self._thumb = img
                self.miniatura.configure(image=img, text="", width=img.width(), height=img.height())
                self.lbl_png.configure(text=f"{png.name}  ·  {w}×{h}px"
                                       + ("" if r else "\nEste botão ainda não tem regra: configure e salve."))
            except tk.TclError:
                pass
        self._visibilidade()
        self._base = self._campos() if nome else {}

    # ------------------------------------------------------------------ #
    # ações
    # ------------------------------------------------------------------ #
    def _campos(self) -> dict[str, str]:
        return {k: v.get() for k, v in self.v.items()}

    def salvar(self, silencioso: bool = False) -> bool:
        if not self.sel:
            return False
        original = regras_de(self.dados).get(self.sel, {})
        regra, erros = campos_para_regra(original, self._campos())
        if erros:
            messagebox.showwarning("Confira os campos", "\n".join("• " + e for e in erros),
                                   parent=self.app.raiz)
            return False
        try:
            dados = ler_config(self.g.config)
        except ValueError as e:
            messagebox.showerror("botoes.json", str(e), parent=self.app.raiz)
            return False
        dados[self.sel] = regra
        self._gravar(dados)
        self.app.log_texto(f"✔ Regra “{self.sel}” salva em {self.g.config}\n", "ok")
        self._base = self._campos()
        self.recarregar()
        return True

    def remover(self) -> None:
        if not self.sel or self.sel not in regras_de(self.dados):
            return
        if not messagebox.askyesno("Remover regra", f"Remover a regra de “{self.sel}”?\n"
                                   "(A imagem continua na pasta.)", parent=self.app.raiz):
            return
        dados = ler_config(self.g.config)
        dados.pop(self.sel, None)
        self._gravar(dados)
        self.recarregar()
        self._mostrar(self.sel)

    def recortar_novo(self) -> None:
        nome = pedir_texto(self.app.raiz, self.t, "Novo botão",
                           "Nome do botão (sem espaços, ex.: maximo).\n"
                           "Deixe o botão visível no jogo: em seguida a tela é capturada.")
        if not nome:
            return
        nome = "".join(ch if (ch.isalnum() or ch in "_-") else "_" for ch in nome)
        self._guardar_estado()
        self.app.rodar("ferramenta", comandos.recortar(self.g, nome), minimizar=True,
                       ao_fim=lambda _c: self._depois_recorte(nome))

    def _depois_recorte(self, nome: str) -> None:
        self.recarregar()
        if self.arvore.exists(nome):
            self.arvore.selection_set(nome)
            self.arvore.see(nome)

    def definir_destino(self) -> None:
        if not self.sel:
            return
        if not self.salvar(True):
            return
        anc = self.v["dest_ancora"].get().strip() if self.v["dest_tipo"].get() == "ancora" else None
        self._guardar_estado()
        self.app.rodar("ferramenta", comandos.definir_destino(self.g, self.sel, anc or None),
                       minimizar=True, ao_fim=lambda _c: (self.recarregar(), self._mostrar(self.sel)))

    def calibrar(self) -> None:
        if not self.sel:
            return
        self.app.log_texto("Calibrar: deixe o botão em cada estado e use o botão “Enviar Enter” "
                           "(abaixo) para avançar.\n", "aviso")
        self._guardar_estado()
        self.app.rodar("ferramenta", comandos.calibrar(self.g, self.sel), minimizar=False,
                       ao_fim=lambda _c: (self.recarregar(), self._mostrar(self.sel)))

    def validar(self) -> None:
        self.app.rodar("ferramenta", comandos.validar(self.g))

    # ------------------------------------------------------------------ #
    # fluxo
    # ------------------------------------------------------------------ #
    def editar_fluxo(self) -> None:
        DialogoFluxo(self)


class DialogoFluxo:
    """Editor das etapas do jogo ("_fluxo")."""

    def __init__(self, pag: PaginaRegras) -> None:
        self.pag, t = pag, pag.t
        c = t.c
        self.j = tk.Toplevel(pag.app.raiz)
        self.j.title("Etapas do jogo")
        self.j.configure(bg=c["card"])
        self.j.transient(pag.app.raiz)
        self.j.geometry("640x520")
        try:
            self.dados = ler_config(pag.g.config)
        except ValueError:
            self.dados = {}
        self.etapas = lista_fluxo(self.dados)
        tk.Label(self.j, text="Etapas do jogo", bg=c["card"], fg=c["text"], font=t.f_card).pack(
            anchor="w", padx=20, pady=(18, 2))
        tk.Label(self.j, text="A etapa atual é a última cujo botão apareceu. Use para só clicar certos "
                 "botões em certas fases e para avisar/parar se uma fase demorar demais.",
                 bg=c["card"], fg=c["muted"], font=t.f_pequena, wraplength=590, justify="left",
                 anchor="w").pack(fill="x", padx=20)
        self.lista = ttk.Treeview(self.j, columns=("quando", "timeout", "ao"), show="tree headings", height=6)
        for col, tx, w in (("#0", "Etapa", 120), ("quando", "Aparece quando", 200), ("timeout", "Limite (s)", 80),
                           ("ao", "Se estourar", 90)):
            self.lista.heading(col, text=tx)
            self.lista.column(col, width=w)
        self.lista.pack(fill="x", padx=20, pady=12)
        self.lista.bind("<<TreeviewSelect>>", self._sel)
        self.v = {k: tk.StringVar() for k in ("etapa", "quando", "timeout", "ao_estourar")}
        self.v["ao_estourar"].set("avisar")
        form = tk.Frame(self.j, bg=c["card"])
        form.pack(fill="x", padx=20)
        form.columnconfigure(1, weight=1)
        for i, (k, tx) in enumerate((("etapa", "Nome da etapa"), ("quando", "Aparece quando (botões)"),
                                     ("timeout", "Limite de tempo (s)"), ("ao_estourar", "Se estourar"))):
            rotulo(form, t, tx, muted=True).grid(row=i, column=0, sticky="w", pady=4, padx=(0, 12))
            if k == "ao_estourar":
                escolha(form, self.v[k], ("avisar", "parar", "reiniciar"), 14).grid(row=i, column=1, sticky="w")
            else:
                entrada(form, self.v[k]).grid(row=i, column=1, sticky="ew", pady=4)
        barra = tk.Frame(self.j, bg=c["card"])
        barra.pack(fill="x", padx=20, pady=14)
        botao(barra, "Adicionar / atualizar", self.adicionar, "Accent", True).pack(side="left")
        botao(barra, "Remover", self.remover, "Ghost", True).pack(side="left", padx=8)
        botao(barra, "Salvar e fechar", self.salvar, "Ok", True).pack(side="right")
        self._atualizar()

    def _atualizar(self) -> None:
        for i in self.lista.get_children():
            self.lista.delete(i)
        for i, e in enumerate(self.etapas):
            cp = etapa_para_campos(e)
            self.lista.insert("", "end", iid=str(i), text=cp["etapa"],
                              values=(cp["quando"], cp["timeout"] or "–", cp["ao_estourar"]))

    def _sel(self, _e: Any = None) -> None:
        s = self.lista.selection()
        if s:
            for k, val in etapa_para_campos(self.etapas[int(s[0])]).items():
                self.v[k].set(val)

    def adicionar(self) -> None:
        e, erros = campos_para_etapa({k: v.get() for k, v in self.v.items()})
        if erros:
            messagebox.showwarning("Etapa", "\n".join("• " + x for x in erros), parent=self.j)
            return
        for i, ex in enumerate(self.etapas):
            if ex.get("etapa") == e["etapa"]:
                self.etapas[i] = e
                break
        else:
            self.etapas.append(e)
        self._atualizar()

    def remover(self) -> None:
        s = self.lista.selection()
        if s:
            del self.etapas[int(s[0])]
            self._atualizar()

    def salvar(self) -> None:
        if self.etapas:
            self.dados["_fluxo"] = self.etapas
        else:
            self.dados.pop("_fluxo", None)
        self.pag._gravar(self.dados)
        self.pag.app.log_texto("✔ Etapas do jogo salvas.\n", "ok")
        self.pag.recarregar()
        self.j.destroy()
