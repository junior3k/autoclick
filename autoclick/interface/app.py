# pyright: basic
"""Janela principal: menu lateral, cabeçalho com controles, páginas e console de mensagens."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Optional

from . import comandos
from .. import registro_log
from .bandeja import Bandeja
from .dados import (ARQ_PREVIA, Geral, ambiente, carregar_geral, salvar_geral, tecla_global_pressionada,
                    teclas_validas)
from . import icone
from .executor import Executor
from .jogos_gui import ControleJogos
from .pag_servidor import ControleServidor
from .pagina import Pagina
from .tema import Tema
from .widgets import Indicador, botao, texto_progresso

from .. import __version__ as VERSAO

ESTADOS: dict[str, tuple[str, str]] = {
    "gravar": ("Gravando", "danger"), "reproduzir": ("Reproduzindo", "ok"),
    "imagem": ("Automático", "ok"), "texto": ("Automático (OCR)", "ok"),
    "auto": ("Automático (OCR)", "ok"), "instalar": ("Instalando", "accent"),
}


class App:
    def __init__(self, geral: Optional[Geral] = None, diretorio: Optional[str] = None) -> None:
        self.g = geral or carregar_geral()
        icone.agrupar_na_barra()
        self.raiz = tk.Tk()
        self.raiz.title(f"Autoclick Inteligente {VERSAO}")
        self._icone = icone.aplicar(self.raiz)
        self.raiz.geometry("1220x820")
        self.raiz.minsize(900, 640)
        self.t = Tema(self.raiz, self.g.tema if self.g.tema in ("escuro", "claro") else "escuro")
        self.exec = Executor(self._ao_texto, self._ao_status, self._ao_fim, diretorio)
        self.paginas: dict[str, Pagina] = {}
        self._nav: dict[str, tuple[tk.Frame, tk.Frame, tk.Label]] = {}
        self._cb_fim: Optional[Callable[[int], Any]] = None
        self._ultimo_status: dict[str, Any] = {}
        self._vars: list[tk.Variable] = []
        self._imagens: list[Any] = []
        self._previas: list[Any] = []
        self._tecla_antes = False
        self._tecla_t = 0.0
        self._tecla_antes_r = False
        self._vars_som: list[Any] = []
        self._tecla_t_r = 0.0
        self._fila_fundo: list[tuple[list[Any], Callable[[Any], None]]] = []
        self.bandeja = Bandeja()
        self._verificou = False
        self.jogos = ControleJogos(self)
        self.up = ControleServidor(self)
        self.montar()
        self.jogos.migrar_se_preciso()
        self.atualizar_menu_jogos()
        self.raiz.protocol("WM_DELETE_WINDOW", self.fechar)
        self.raiz.bind("<Control-z>", lambda _e: self._atalho_historico("desfazer"))
        self.raiz.bind("<Control-y>", lambda _e: self._atalho_historico("refazer"))
        self.raiz.bind("<Unmap>", self._ao_minimizar)
        if self.g.bandeja:
            self.bandeja.iniciar()
        self.raiz.after(100, self._tick)

    # ------------------------------------------------------------------ #
    # variáveis ligadas às configurações
    # ------------------------------------------------------------------ #
    def var(self, nome: str) -> tk.Variable:
        """Variável Tk ligada ao campo `nome` de Geral (grava de volta a cada edição)."""
        atual = getattr(self.g, nome)
        if isinstance(atual, bool):
            v: tk.Variable = tk.BooleanVar(self.raiz, value=atual)
            conv: Callable[[Any], Any] = bool
        else:
            txt = f"{atual:g}" if isinstance(atual, float) else str(atual)
            v = tk.StringVar(self.raiz, value=txt)
            tipo = type(atual)
            if tipo is int:
                conv = lambda x: int(float(str(x).replace(",", ".")))  # noqa: E731
            elif tipo is float:
                conv = lambda x: float(str(x).replace(",", "."))  # noqa: E731
            else:
                conv = str

        def gravar(*_a: Any) -> None:
            try:
                setattr(self.g, nome, conv(v.get()))
            except (ValueError, tk.TclError):
                pass

        v.trace_add("write", gravar)
        self._vars.append(v)
        return v

    # ------------------------------------------------------------------ #
    # montagem
    # ------------------------------------------------------------------ #
    def montar(self) -> None:
        from .pag_ajuda import PaginaAjuda
        from .pag_auto import PaginaAutomatico
        from .pag_config import PaginaConfig
        from .pag_ferramentas import PaginaFerramentas
        from .pag_gravacao import PaginaGravacao
        from .pag_historico import PaginaHistorico
        from .pag_jogos import PaginaJogos
        from .pag_regras import PaginaRegras
        from .pag_rotinas import PaginaRotinas

        c = self.t.c
        for w in self.raiz.winfo_children():
            w.destroy()
        self.paginas.clear()
        self._nav.clear()
        self._previas.clear()
        corpo = tk.Frame(self.raiz, bg=c["bg"])
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(1, weight=1)
        corpo.rowconfigure(0, weight=1)
        self._montar_lateral(corpo)

        direita = tk.Frame(corpo, bg=c["bg"])
        direita.grid(row=0, column=1, sticky="nsew")
        self._montar_cabecalho(direita)
        self.painel = painel = ttk.PanedWindow(direita, orient="vertical")
        painel.pack(fill="both", expand=True, padx=(0, 0))
        self.area = tk.Frame(painel, bg=c["bg"])
        painel.add(self.area, weight=5)
        painel.add(self._montar_console(painel), weight=1)

        for cls in (PaginaGravacao, PaginaRegras, PaginaAutomatico, PaginaJogos, PaginaRotinas, PaginaFerramentas,
                    PaginaHistorico, PaginaConfig, PaginaAjuda):
            p = cls(self, self.area)
            self.paginas[p.chave] = p
        inicial = self.g.pagina if self.g.pagina in self.paginas else "gravar"
        self.ir(inicial)
        self.atualizar_estado()
        if not self._verificou:
            self._verificou = True
            self.raiz.after(900, self.mostrar_novidades)
            self.raiz.after(2500, self.verificar_ao_abrir)

    def _montar_lateral(self, pai: tk.Misc) -> None:
        c, t = self.t.c, self.t
        lado = tk.Frame(pai, bg=c["side"], width=204)
        lado.grid(row=0, column=0, sticky="ns")
        lado.grid_propagate(False)
        lado.pack_propagate(False)
        logo = tk.Frame(lado, bg=c["side"])
        logo.pack(fill="x", padx=20, pady=(24, 22))
        mini = icone.miniatura(self.raiz, 36)
        if mini is not None:
            self._imagens.append(mini)
            tk.Label(logo, image=mini, bg=c["side"]).pack(side="left")
        else:
            tk.Label(logo, text="◎", bg=c["side"], fg=c["accent"], font=(t.f_grande[0], 22, "bold")).pack(side="left")
        tk.Label(logo, text="Autoclick", bg=c["side"], fg=c["text"],
                 font=(t.f_grande[0], 15, "bold")).pack(side="left", padx=(8, 0))
        itens = [("gravar", "⏺", "Gravar & Reproduzir"), ("regras", "▦", "Botões & regras"),
                 ("auto", "⚡", "Automático"), ("jogos", "🎮", "Jogos"), ("rotinas", "⛓", "Rotinas"), ("ferramentas", "⚙", "Ferramentas"),
                 ("historico", "◷", "Histórico"), ("config", "☰", "Configurações"),
                 ("ajuda", "?", "Ajuda")]
        for chave, simbolo, texto in itens:
            linha = tk.Frame(lado, bg=c["side"], cursor="hand2")
            linha.pack(fill="x", pady=1)
            barra = tk.Frame(linha, bg=c["side"], width=4)
            barra.pack(side="left", fill="y")
            lab = tk.Label(linha, text=texto, bg=c["side"], fg=c["muted"],
                           font=t.f_negrito, anchor="w", padx=16, pady=11)
            lab.pack(side="left", fill="x", expand=True)
            self._nav[chave] = (linha, barra, lab)
            for w in (linha, lab):
                w.bind("<Button-1>", lambda _e, k=chave: self.ir(k))
                w.bind("<Enter>", lambda _e, k=chave: self._hover(k, True))
                w.bind("<Leave>", lambda _e, k=chave: self._hover(k, False))
        rod = tk.Frame(lado, bg=c["side"])
        rod.pack(side="bottom", fill="x", padx=20, pady=18)
        self.lbl_teclas = tk.Label(rod, text="", bg=c["side"], fg=c["muted"],
                                   font=t.f_pequena, justify="left", anchor="w")
        self.lbl_teclas.pack(fill="x")
        self.atualizar_rodape_teclas()
        self.lbl_versao = tk.Label(rod, text=f"versão {VERSAO}", bg=c["side"], fg=c["muted"],
                                   font=t.f_pequena, anchor="w")
        self.lbl_versao.pack(fill="x", pady=(8, 0))

    def definir_nova_versao(self, versao: Optional[str], pronta: bool = False) -> None:
        """Mostra no rodapé lateral que há versão nova (None limpa)."""
        if versao:
            self.lbl_versao.configure(text=f"versão {VERSAO} → {versao} " + ("pronta" if pronta else "disponível"),
                                      fg=self.t.c["accent"])
        else:
            self.lbl_versao.configure(text=f"versão {VERSAO}", fg=self.t.c["muted"])

    def mostrar_novidades(self) -> None:
        """“O que mudou”: uma vez, na primeira abertura depois de atualizar."""
        from .. import novidades
        acao = novidades.decidir(self.g.avisou_novidades, VERSAO)
        self.g.avisou_novidades = VERSAO
        salvar_geral(self.g)
        if acao != "mostrar":
            return
        txt = novidades.ler(os.getcwd(), VERSAO)
        if txt:
            self.log_texto(f"✨ Novidades da versão {VERSAO}:\n{txt}\n", "ok")
            messagebox.showinfo(f"O que mudou na versão {VERSAO}", txt[:1800], parent=self.raiz)

    def verificar_ao_abrir(self) -> None:
        if not self.g.atualizar_ao_abrir:
            return
        if self.up.servidor() is not None:
            self.up.verificar(silencioso=True)

    def _hover(self, chave: str, dentro: bool) -> None:
        if chave == self.g.pagina:
            return
        c = self.t.c
        cor = c["hover"] if dentro else c["side"]
        linha, barra, lab = self._nav[chave]
        for w in (linha, lab):
            w.configure(bg=cor)

    def _montar_cabecalho(self, pai: tk.Misc) -> None:
        c = self.t.c
        topo = tk.Frame(pai, bg=c["bg"])
        topo.pack(fill="x", padx=28, pady=(22, 6))
        topo.columnconfigure(0, weight=1)
        esq = tk.Frame(topo, bg=c["bg"])
        self.lbl_titulo = ttk.Label(esq, text="", style="H1.TLabel")
        self.lbl_titulo.pack(anchor="w")
        self.lbl_sub = ttk.Label(esq, text="", style="PageMuted.TLabel", justify="left")
        self.lbl_sub.pack(anchor="w", pady=(2, 0), fill="x")
        # Estado + Pausar + Parar: três colunas de MESMA largura (uniform) e nunca cortadas.
        dir_ = tk.Frame(topo, bg=c["bg"])
        for i in (0, 2, 4):
            dir_.columnconfigure(i, weight=1, uniform="ctl", minsize=112)
        for i in (1, 3):
            dir_.columnconfigure(i, minsize=8)
        self.chip = Indicador(dir_, self.t)
        self.chip.grid(row=0, column=0, sticky="nsew")
        self.btn_pausa = botao(dir_, "Pausar", self.alternar_pausa, "Ghost")
        self.btn_pausa.grid(row=0, column=2, sticky="nsew")
        self.btn_parar = botao(dir_, "Parar", self.parar, "Danger")
        self.btn_parar.grid(row=0, column=4, sticky="nsew")
        self._topo, self._esq, self._dir = topo, esq, dir_
        self._topo_empilhado: Optional[bool] = None
        topo.bind("<Configure>", self._ajustar_topo)
        self._ajustar_topo()

    def _ajustar_topo(self, _e: Any = None) -> None:
        """Largura boa: título à esquerda, controles à direita. Estreita: controles abaixo do título."""
        largura = self._topo.winfo_width()
        empilhar = 1 < largura < 640
        if empilhar != self._topo_empilhado:
            self._topo_empilhado = empilhar
            if empilhar:
                self._esq.grid(row=0, column=0, sticky="ew")
                self._dir.grid(row=1, column=0, sticky="w", pady=(10, 0))
            else:
                self._esq.grid(row=0, column=0, sticky="ew", padx=(0, 16))
                self._dir.grid(row=0, column=1, sticky="e")
        livre = largura - (0 if empilhar else self._dir.winfo_reqwidth() + 16)
        if livre > 60:
            self.lbl_sub.configure(wraplength=livre)

    def _montar_console(self, pai: tk.Misc) -> tk.Frame:
        c, t = self.t.c, self.t
        quadro = tk.Frame(pai, bg=c["bg"])
        barra = tk.Frame(quadro, bg=c["bg"])
        barra.pack(fill="x", padx=28, pady=(8, 4))
        botao(barra, "Limpar", self.limpar_log, "Ghost", True).pack(side="right")
        botao(barra, "Copiar", self.copiar_log, "Ghost", True).pack(side="right", padx=6)
        self.btn_enter = botao(barra, "Enviar Enter", self.exec.enviar_enter, "Accent", True)
        self.btn_enter.pack(side="right", padx=6)
        self.btn_enter.state(["disabled"])
        self.btn_som = botao(barra, "", self.alternar_som, "Ghost", True)
        self.btn_som.pack(side="right", padx=6)
        self._pintar_som()
        self.mb_jogo = ttk.Menubutton(barra, text="", style="Small.Ghost.TButton", cursor="hand2")
        self.mb_jogo.pack(side="right", padx=6)
        self.menu_jogo = tk.Menu(self.mb_jogo, tearoff=0)
        self.mb_jogo.configure(menu=self.menu_jogo)
        self.atualizar_menu_jogos()
        ttk.Label(barra, text="Mensagens", style="TLabel", font=t.f_card).pack(side="left")
        caixa = tk.Frame(quadro, bg=c["log"], highlightthickness=1, highlightbackground=c["border"])
        caixa.pack(fill="both", expand=True, padx=28, pady=(0, 18))
        self.log = tk.Text(caixa, bg=c["log"], fg=c["text"], font=t.f_mono, wrap="word", height=8,
                           borderwidth=0, highlightthickness=0, padx=12, pady=8,
                           insertbackground=c["text"], state="disabled", spacing1=1)
        sb = ttk.Scrollbar(caixa, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        for tag, cor in (("erro", c["danger"]), ("aviso", c["warn"]), ("ok", c["ok"]),
                         ("cmd", c["accent"]), ("dim", c["muted"])):
            self.log.tag_configure(tag, foreground=cor)
        self.log_texto("Pronto. Escolha uma função no menu à esquerda.\n", "dim")
        return quadro

    # ------------------------------------------------------------------ #
    # navegação
    # ------------------------------------------------------------------ #
    def atualizar_rodape_teclas(self) -> None:
        g = self.g
        self.lbl_teclas.configure(text=f"{g.tecla_pausa}  pausar / continuar\n{g.tecla_parar}  parar\n"
                                       f"{g.tecla_gravar}  gravar / parar\n{g.tecla_reproduzir}  reproduzir / parar")

    def ir(self, chave: str) -> None:
        atual = self.paginas.get(self.g.pagina)
        if atual is not None and chave != self.g.pagina and not atual.pode_sair():
            return
        c = self.t.c
        self.g.pagina = chave
        for k, (linha, barra, lab) in self._nav.items():
            sel = k == chave
            for w in (linha, lab):
                w.configure(bg=c["sel"] if sel else c["side"])
            barra.configure(bg=c["accent"] if sel else c["side"])
            lab.configure(fg=c["text"] if sel else c["muted"])
        for p in self.paginas.values():
            p.frame.pack_forget()
        pg = self.paginas[chave]
        pg.frame.pack(fill="both", expand=True, padx=28, pady=(0, 6))
        self.lbl_titulo.configure(text=pg.titulo)
        self.lbl_sub.configure(text=pg.subtitulo)
        pg.ao_mostrar()

    # ------------------------------------------------------------------ #
    # execução
    # ------------------------------------------------------------------ #
    @property
    def rodando(self) -> bool:
        return self.exec.rodando

    def rodar(self, nome: str, argv: list[str], minimizar: bool = False,
              ao_fim: Optional[Callable[[int], Any]] = None,
              comando_completo: Optional[list[str]] = None) -> bool:
        """Roda `autoclick <argv>` num processo separado. Devolve False se já há algo rodando."""
        if self.exec.rodando:
            messagebox.showinfo("Já está rodando", "Pare a função atual antes de iniciar outra.",
                                parent=self.raiz)
            return False
        salvar_geral(self.g)
        self._cb_fim = ao_fim
        self.log_texto("\n> " + (" ".join(comando_completo) if comando_completo
                                 else comandos.para_texto(argv)) + "\n", "cmd")
        for p in self.paginas.values():
            p.ao_status({})
        self.exec.env_base = self._ambiente()
        try:
            os.remove(ARQ_PREVIA)
        except OSError:
            pass
        for w in self._previas:
            w.limpar()
        if not self.exec.rodar(nome, argv, comando_completo=comando_completo):
            return False
        self._ultimo_status = {}
        if minimizar and self.g.minimizar:
            self.raiz.iconify()
        self.atualizar_estado()
        return True

    def parar(self) -> None:
        if self.exec.rodando:
            self.log_texto("Parando...\n", "aviso")
            self.exec.pausar(False)
            self.exec.parar()

    def alternar_pausa(self) -> None:
        if self.exec.rodando:
            self.exec.pausar(not self.exec.pausado)

    def _ao_status(self, d: dict[str, Any]) -> None:
        self._ultimo_status = d
        self.atualizar_estado()
        for p in self.paginas.values():
            p.ao_status(d)

    def _ao_fim(self, nome: str, codigo: int) -> None:
        self.log_texto(("\n✔ Concluído.\n" if codigo == 0 else f"\n⚠ Terminou com código {codigo}.\n"),
                       "ok" if codigo == 0 else "aviso")
        if self.raiz.state() == "iconic":
            self.raiz.deiconify()
        elif self.raiz.state() == "withdrawn":
            self.notificar("Autoclick", "A função terminou." if codigo == 0
                           else f"A função terminou com código {codigo}.", "info" if codigo == 0 else "aviso")
        self.raiz.lift()
        self.atualizar_estado()
        cb, self._cb_fim = self._cb_fim, None
        if cb is not None:
            cb(codigo)

    def atualizar_estado(self) -> None:
        rodando = self.exec.rodando
        if not rodando:
            self.chip.definir("Parado", "muted")
        elif self.exec.pausado:
            self.chip.definir("Pausado", "warn")
        else:
            txt, cor = ESTADOS.get(self.exec.nome, ("Executando", "accent"))
            self.chip.definir(txt, cor)
        self.bandeja.rodando = rodando and self.exec.nome == "reproduzir"
        self.bandeja.som = self.g.som_volta
        if self.bandeja.disponivel:
            est = ("pausado" if self.exec.pausado else ("gravando" if self.exec.nome == "gravar" else "rodando")) \
                if rodando else "parado"
            dica = ESTADOS.get(self.exec.nome, ("", ""))[0] if rodando else "parado"
            prog = texto_progresso(self._ultimo_status.get("progresso")) if rodando else ""
            self.bandeja.definir_estado(est, f"{dica} · {prog}" if prog else dica, self.exec.pausado)
        ativo = rodando and self.exec.nome in ("reproduzir", "imagem", "texto", "auto")
        self.btn_pausa.state(["!disabled"] if ativo else ["disabled"])
        self.btn_pausa.configure(text="Continuar" if (ativo and self.exec.pausado) else "Pausar")
        self.btn_parar.state(["!disabled"] if rodando else ["disabled"])
        self.btn_enter.state(["!disabled"] if rodando else ["disabled"])
        for p in self.paginas.values():
            p.ao_estado(rodando)

    def _tick(self) -> None:
        try:
            self.exec.sondar()
            self._tick_fundo()
            self._tick_bandeja()
            self.jogos.tick()
            self.up.tick()
            self._tick_tecla_gravar()
            self._tick_tecla_reproduzir()
            if self.g.previa_viva:
                for w in self._previas:
                    w.atualizar(self.exec.rodando)
        except Exception as e:  # um erro de interface nunca pode parar o laço
            registro_log.escrever(f"erro no laço da janela: {type(e).__name__}: {e}")
        finally:
            self.raiz.after(100, self._tick)

    # ------------------------------------------------------------------ #
    # ambiente, tarefas em segundo plano, bandeja, atalho global, alertas
    # ------------------------------------------------------------------ #
    def _ambiente(self) -> dict[str, str]:
        g = self.g
        if teclas_validas(g.tecla_pausa, g.tecla_parar, g.tecla_gravar, g.tecla_reproduzir):
            g.tecla_pausa, g.tecla_parar, g.tecla_gravar, g.tecla_reproduzir = "F8", "F9", "F10", "F11"
        return ambiente(g)

    def registrar_previa(self, w: Any) -> None:
        self._previas.append(w)

    def em_segundo_plano(self, fn: Callable[[], Any], ao_fim: Callable[[Any], None]) -> None:
        """Roda `fn` numa thread (rede, instalação...) e entrega o resultado no laço do Tk."""
        caixa: list[Any] = []

        def trabalho() -> None:
            try:
                caixa.append(fn())
            except Exception as e:
                caixa.append(("erro", f"{type(e).__name__}: {e}"))

        threading.Thread(target=trabalho, daemon=True).start()
        self._fila_fundo.append((caixa, ao_fim))

    def _tick_fundo(self) -> None:
        for item in list(self._fila_fundo):
            caixa, cb = item
            if caixa:
                self._fila_fundo.remove(item)
                cb(caixa[0])

    def abrir_caminho(self, caminho: str) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(caminho)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", caminho])
        except OSError as e:
            messagebox.showerror("Abrir", str(e), parent=self.raiz)

    def notificar(self, titulo: str, texto: str, nivel: str = "aviso") -> None:
        """Balão do Windows (bandeja). Sem bandeja, toca o sinal sonoro e deixa no console."""
        if not self.g.notificar_windows:
            return
        if not self.bandeja.balao(titulo, texto, nivel):
            self.raiz.bell()

    def _ao_texto(self, txt: str) -> None:
        registro_log.escrever(txt)
        for linha in txt.splitlines():
            if linha.startswith("[ALERTA]"):
                corpo = linha[len("[ALERTA]"):].strip()
                self.notificar("Autoclick — alerta", corpo)
        self.log_texto(txt)

    def _tick_bandeja(self) -> None:
        while True:
            try:
                ev = self.bandeja.eventos.get_nowait()
            except Exception:
                return
            if ev == "mostrar":
                self.mostrar_janela()
            elif ev == "pausa":
                self.alternar_pausa()
            elif ev == "parar":
                self.parar()
            elif ev == "sair":
                self.fechar(forcar=True)
            elif ev == "som":
                self.alternar_som()
            elif ev == "reproduzir":
                if self.exec.rodando and self.exec.nome == "reproduzir":
                    self.parar()
                elif not self.exec.rodando:
                    pg = self.paginas.get("rotinas" if self.g.f11_rotina else "gravar")
                    if pg is not None and (self.g.f11_rotina or os.path.isfile(self.g.gravacao)):
                        (pg.iniciar if self.g.f11_rotina else pg.reproduzir)()  # type: ignore[attr-defined]
            elif ev == "gravar":
                if self.exec.rodando and self.exec.nome == "gravar":
                    self.parar()
                elif not self.exec.rodando:
                    pg = self.paginas.get("gravar")
                    if pg is not None:
                        pg.gravar()  # type: ignore[attr-defined]
            elif ev.startswith("jogo:"):
                self.jogos.escolher(ev[5:])

    def mostrar_janela(self) -> None:
        self.raiz.deiconify()
        self.raiz.lift()
        self.raiz.focus_force()

    def _ao_minimizar(self, e: Any) -> None:
        if e.widget is self.raiz and self.g.ao_fechar_bandeja and self.bandeja.disponivel:
            self.raiz.after_idle(lambda: self.raiz.withdraw() if self.raiz.state() == "iconic" else None)

    def _tick_tecla_gravar(self) -> None:
        agora = tecla_global_pressionada(self.g.tecla_gravar)
        borda = agora and not self._tecla_antes
        self._tecla_antes = agora
        if not borda or time.time() - self._tecla_t < 0.8:
            return
        self._tecla_t = time.time()
        if self.exec.rodando and self.exec.nome == "gravar":
            self.log_texto(f"{self.g.tecla_gravar}: parando a gravação.\n", "aviso")
            self.parar()
        elif not self.exec.rodando:
            pg = self.paginas.get("gravar")
            if pg is not None and hasattr(pg, "gravar"):
                self.log_texto(f"{self.g.tecla_gravar}: iniciando a gravação.\n", "aviso")
                pg.gravar()  # type: ignore[attr-defined]

    def _tick_tecla_reproduzir(self) -> None:
        """Atalho global (funciona com o jogo em primeiro plano): inicia ou para a reprodução."""
        agora = tecla_global_pressionada(self.g.tecla_reproduzir)
        borda = agora and not self._tecla_antes_r
        self._tecla_antes_r = agora
        if not borda or time.time() - self._tecla_t_r < 0.8:
            return
        self._tecla_t_r = time.time()
        if self.exec.rodando and self.exec.nome == "reproduzir":
            self.log_texto(f"{self.g.tecla_reproduzir}: parando a reprodução.\n", "aviso")
            self.parar()
        elif not self.exec.rodando:
            if self.g.f11_rotina and "rotinas" in self.paginas:
                self.log_texto(f"{self.g.tecla_reproduzir}: iniciando a rotina.\n", "aviso")
                self.paginas["rotinas"].iniciar()  # type: ignore[attr-defined]
                return
            if not os.path.isfile(self.g.gravacao):
                self.log_texto(f"⚠ {self.g.tecla_reproduzir}: não há gravação ({self.g.gravacao}). "
                               "Grave primeiro.\n", "aviso")
                return
            pg = self.paginas.get("gravar")
            if pg is not None and hasattr(pg, "reproduzir"):
                self.log_texto(f"{self.g.tecla_reproduzir}: iniciando a reprodução.\n", "aviso")
                pg.reproduzir()  # type: ignore[attr-defined]

    # ---- jogos ---- #
    def atualizar_menu_jogos(self) -> None:
        """Rótulo e menu rápido “🎮 Jogo: X ▾” (barra de mensagens) e dados do menu da bandeja."""
        ctl = self.jogos
        lista = ctl.lista()
        self.mb_jogo.configure(text=f"🎮 {ctl.nome_atual()} ▾")
        self.menu_jogo.delete(0, "end")
        for j in lista:
            self.menu_jogo.add_command(
                label=("✔ " if j.slug == ctl.atual() else "   ") + j.nome,
                command=lambda s=j.slug: self.jogos.escolher(s))
        self.menu_jogo.add_separator()
        self.menu_jogo.add_command(label="Gerenciar jogos…", command=lambda: self.ir("jogos"))
        self.bandeja.jogos = [(j.slug, j.nome) for j in lista]
        self.bandeja.jogo_atual = ctl.atual()

    def jogo_mudou(self) -> None:
        """Trocou de jogo: refaz as páginas (os campos passam a mostrar os arquivos do jogo)."""
        pagina = self.g.pagina
        self._vars.clear()
        self._vars_som.clear()
        self.montar()
        self.ir(pagina if pagina in self.paginas else "jogos")

    # ---- som por volta: vale a qualquer momento, mesmo com algo rodando ---- #
    def _pintar_som(self) -> None:
        ligado = self.g.som_volta
        self.btn_som.configure(text="🔔 Som por volta: ligado" if ligado else "🔕 Som por volta: desligado")

    def alternar_som(self) -> None:
        self.g.som_volta = not self.g.som_volta
        self.sincronizar_som()

    def sincronizar_som(self) -> None:
        """Aplica `g.som_volta` na janela e no processo em execução (se houver)."""
        self._pintar_som()
        self.bandeja.som = self.g.som_volta
        for v in self._vars_som:
            try:
                if bool(v.get()) != self.g.som_volta:
                    v.set(self.g.som_volta)
            except Exception:
                pass
        if self.exec.rodando:
            self.exec.enviar_comando("som:1" if self.g.som_volta else "som:0")
        salvar_geral(self.g)

    def sincronizar_grupo_som(self, grupo: str, ligado: bool) -> None:
        """Liga/desliga um tipo de som (gravacao, reproducao, contagem): vale na hora, mesmo rodando."""
        campo = {"gravacao": "som_gravacao", "reproducao": "som_reproducao", "contagem": "som_contagem"}[grupo]
        setattr(self.g, campo, ligado)
        if self.exec.rodando:
            self.exec.enviar_comando(f"somgrupo:{grupo}={'1' if ligado else '0'}")
        salvar_geral(self.g)

    def enviar_config_som(self) -> None:
        """Estilo/volume/arquivo do som: vale na hora, mesmo com algo rodando."""
        from urllib.parse import quote
        g = self.g
        if self.exec.rodando:
            self.exec.enviar_comando(f"somcfg:{quote(g.som_tipo)}|{g.som_volume:g}|{quote(g.som_arquivo)}")
        salvar_geral(g)

    def _atalho_historico(self, quem: str) -> None:
        foco = self.raiz.focus_get()
        if foco is not None and foco.winfo_class() in ("Entry", "TEntry", "Spinbox", "TSpinbox", "TCombobox"):
            return
        pg = self.paginas.get(self.g.pagina)
        fn = getattr(pg, quem, None)
        if callable(fn):
            fn()

    # ------------------------------------------------------------------ #
    # console
    # ------------------------------------------------------------------ #
    def log_texto_seguro(self, txt: str) -> None:
        self.log_texto(txt)

    def log_texto(self, txt: str, tag: str = "") -> None:
        self.log.configure(state="normal")
        for linha in txt.splitlines(True):
            t = tag
            if not t:
                if any(m in linha for m in ("✖", "Traceback", "Error", "Erro", "erro:")):
                    t = "erro"
                elif any(m in linha for m in ("⚠", "Aviso", "aviso")):
                    t = "aviso"
                elif "✔" in linha:
                    t = "ok"
                elif linha.startswith("  ") and "/" in linha[:12]:
                    t = "dim"
            self.log.insert("end", linha.replace("\r", ""), t)
        total = int(self.log.index("end-1c").split(".")[0])
        if total > 3000:
            self.log.delete("1.0", f"{total - 2500}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def limpar_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def copiar_log(self) -> None:
        self.raiz.clipboard_clear()
        self.raiz.clipboard_append(self.log.get("1.0", "end-1c"))

    # ------------------------------------------------------------------ #
    # utilidades para as páginas
    # ------------------------------------------------------------------ #
    def mostrar_imagem(self, caminho: str, titulo: str = "Imagem") -> None:
        if not os.path.isfile(caminho):
            messagebox.showwarning("Imagem não encontrada", f"{caminho} ainda não foi gerado.",
                                   parent=self.raiz)
            return
        j = tk.Toplevel(self.raiz)
        j.title(titulo)
        j.configure(bg=self.t.c["bg"])
        try:
            img = tk.PhotoImage(file=caminho)
        except tk.TclError as e:
            messagebox.showerror("Imagem", f"Não consegui abrir {caminho}: {e}", parent=self.raiz)
            j.destroy()
            return
        fx = max(1, -(-img.width() // 1180))
        fy = max(1, -(-img.height() // 720))
        f = max(fx, fy)
        if f > 1:
            img = img.subsample(f, f)
        self._imagens.append(img)
        tk.Label(j, image=img, bg=self.t.c["bg"]).pack(padx=10, pady=10)
        tk.Label(j, text=f"{caminho}  ·  exibida em escala 1/{f}" if f > 1 else caminho,
                 bg=self.t.c["bg"], fg=self.t.c["muted"], font=self.t.f_pequena).pack(pady=(0, 10))

    def trocar_tema(self, nome: str) -> None:
        if self.exec.rodando:
            messagebox.showinfo("Tema", "Pare a função em execução para trocar o tema.", parent=self.raiz)
            return
        atual = self.paginas.get(self.g.pagina)
        if atual is not None and not atual.pode_sair():
            return
        self.g.tema = nome
        salvar_geral(self.g)
        self.t = Tema(self.raiz, nome)
        self._vars.clear()
        self.montar()

    def fechar(self, forcar: bool = False) -> None:
        atual = self.paginas.get(self.g.pagina)
        if atual is not None and not atual.pode_sair():
            return
        if self.exec.rodando:
            if not forcar and not messagebox.askyesno("Fechar", "Há uma função em execução. Parar e fechar?",
                                       parent=self.raiz):
                return
            self.exec.parar()
            self.exec.matar()
        salvar_geral(self.g)
        self.up.ao_fechar()
        self.exec.limpar()
        self.bandeja.fechar()
        registro_log.fechar()
        self.raiz.destroy()

    def executar(self) -> None:
        self.raiz.mainloop()


def abrir_app() -> None:
    """Abre a janela (função chamada por `autoclick` sem argumentos)."""
    App().executar()
