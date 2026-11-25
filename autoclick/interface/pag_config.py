# pyright: basic
"""Configurações: janela do jogo, pastas, perfis, aparência e dependências."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
from typing import Any, Optional

from ..opcionais import DICA_OCR

from . import comandos
from .. import __version__
from .. import atualizacao
from ..avisos import enviar_webhook_sync
from .dados import (aviso_atalho, estado_global, URL_TESSERACT, aplicar_perfil, comando_instalar_pytesseract, comando_instalar_tesseract,
                    dependencias, ler_perfil, listar_janelas, listar_perfis, teclas_validas)
from .dialogos import pedir_texto
from .pag_servidor import montar_cartao
from .. import windows as m_windows
from .pagina import Pagina
from .widgets import (Cartao, Rolavel, botao, entrada, escolha, linha_inline, marcar, numero, opcao, responsivo,
                      rotulo)


NOMES_ATALHOS = {"pausa": "Pausar / continuar", "parar": "Parar", "gravar": "Iniciar / parar gravação",
                 "reproduzir": "Iniciar / parar reprodução"}
PADRAO_ATALHOS = {"pausa": "F8", "parar": "F9", "gravar": "F10", "reproduzir": "F11"}


class PaginaConfig(Pagina):
    chave = "config"
    titulo = "Configurações"
    subtitulo = "Janela do jogo, pastas, perfis e aparência."

    def construir(self) -> None:
        a, c = self.app, self.t.c
        rol = Rolavel(self.frame, self.t)
        rol.pack(fill="both", expand=True)
        g = rol.corpo

        # ---------------- jogo ----------------
        j = Cartao(g, self.t, "Jogo e arquivos", "")
        lin = linha_inline(j.corpo, self.t)
        lin.columnconfigure(0, weight=1)
        self.cb_janela = escolha(lin, a.var("janela"), [], 30, editavel=True)
        self.cb_janela.grid(row=0, column=0, sticky="ew")
        botao(lin, "Listar janelas", self.listar, "Ghost", True).grid(row=0, column=1, padx=(6, 0))
        j.campo("Janela do jogo", lin, "Parte do título basta (ex.: Roblox). Limita a busca à janela e "
                "acompanha quando ela mexe.")
        j.campo("Pasta dos botões (PNG)", self._com_pasta(j.corpo, "pasta"))
        j.campo("Arquivo de regras", self._com_arquivo(j.corpo, "config"))
        j.campo("Monitor", numero(j.corpo, a.var("monitor"), 1, 8, 1, 6), "1 = principal")
        j.campo("Rigor do reconhecimento", numero(j.corpo, a.var("confianca"), 0.5, 0.99, 0.01, 8, "%.2f"),
                "0.85 é um bom começo; menor reconhece mais (e erra mais).")
        j.linha_cheia(marcar(j.corpo, "Minimizar esta janela ao iniciar gravação/reprodução", a.var("minimizar")), (8, 0))

        # ---------------- perfis ----------------
        p = Cartao(g, self.t, "Perfis", "Guarde as opções de um jogo e use também no terminal "
                   "(uv run autoclick --perfil nome).")
        self.v_perfil = tk.StringVar()
        self.cb_perfil = escolha(p.corpo, self.v_perfil, listar_perfis(), 24)
        p.campo("Perfis salvos", self.cb_perfil)
        barra = tk.Frame(p.corpo, bg=c["card"])
        p.linha_cheia(barra, (4, 0))
        botao(barra, "Carregar", self.carregar_perfil, "Ghost", True).pack(side="left")
        botao(barra, "Salvar configuração atual como…", self.salvar_perfil, "Accent", True).pack(side="left", padx=8)

        # ---------------- aparência ----------------
        ap = Cartao(g, self.t, "Aparência", "")
        self.v_tema = tk.StringVar(value=self.g.tema)
        t = linha_inline(ap.corpo, self.t)
        opcao(t, "Escuro", self.v_tema, "escuro", self._tema).pack(side="left")
        opcao(t, "Claro", self.v_tema, "claro", self._tema).pack(side="left", padx=14)
        ap.campo("Tema", t)

        # ---------------- dependências ----------------
        d = Cartao(g, self.t, "Dependências", "O programa funciona sem as opcionais: só os modos "
                   "de texto/OCR dependem delas.")
        # ---------------- atalhos ----------------
        at = Cartao(g, self.t, "Atalhos de teclado", "Funcionam mesmo com o jogo em primeiro plano. Clique em "
                    "“Mudar” e aperte a tecla ou a combinação (Ctrl, Alt ou Shift + tecla). As teclas dos "
                    "atalhos não entram nas gravações.")
        self.v_teclas = {k: tk.StringVar(value=getattr(self.g, "tecla_" + k)) for k in NOMES_ATALHOS}
        self._captura: Optional[str] = None
        self._captura_id: Optional[str] = None
        self.botoes_mudar: dict[str, Any] = {}
        dicas = {"parar": "também: mouse no canto superior esquerdo",
                 "gravar": "vale para esta janela, de qualquer lugar",
                 "reproduzir": "reproduz a gravação de qualquer lugar; aperte de novo para parar"}
        for k, rotulo_atalho in NOMES_ATALHOS.items():
            lin = linha_inline(at.corpo, self.t)
            ttk.Entry(lin, textvariable=self.v_teclas[k], width=16, state="readonly").pack(side="left")
            b = botao(lin, "Mudar", lambda k=k: self.capturar(k), "Ghost", True)
            b.pack(side="left", padx=(6, 0))
            self.botoes_mudar[k] = b
            botao(lin, "Padrão", lambda k=k: self._atalho_padrao(k), "Ghost", True).pack(side="left", padx=(6, 0))
            at.campo(rotulo_atalho, lin, dicas.get(k, ""))
        at.linha_cheia(botao(at.corpo, "Aplicar atalhos", self.aplicar_teclas, "Accent", True), (8, 0))

        # ---------------- segurança e avisos ----------------
        se = Cartao(g, self.t, "Segurança e avisos", "O que fazer quando algo dá errado e como ser avisado.")
        se.campo("Tela sem mudar por", numero(se.corpo, a.var("tela_parada"), 0, 86400, 30, 8),
                 "segundos = jogo travado? (0 = desligado)")
        se.campo("…então", escolha(se.corpo, a.var("ao_travar"), ["avisar", "parar"], 10))
        se.linha_cheia(marcar(se.corpo, "Salvar uma captura da tela em erros/ quando der erro",
                              a.var("captura_erro")), (8, 0))
        se.linha_cheia(marcar(se.corpo, "Mostrar a visão ao vivo (o que o programa enxerga)", a.var("previa_viva")))
        se.linha_cheia(marcar(se.corpo, "Ícone na bandeja do sistema", a.var("bandeja")))
        se.linha_cheia(marcar(se.corpo, "Esconder na bandeja ao minimizar", a.var("ao_fechar_bandeja")))
        se.linha_cheia(marcar(se.corpo, "Notificação do Windows nos alertas", a.var("notificar_windows")))
        v_som = a.var("som_volta")
        a._vars_som.append(v_som)
        sl = linha_inline(se.corpo, self.t)
        marcar(sl, "Som suave ao concluir cada volta do loop", v_som, a.sincronizar_som).pack(side="left")
        botao(sl, "Ouvir", self.ouvir_som, "Ghost", True).pack(side="left", padx=(10, 0))
        se.linha_cheia(sl)
        for campo, grupo, texto, evs in (
                ("som_gravacao", "gravacao", "Som ao iniciar e ao parar a gravação", ("gravar_inicio", "gravar_fim")),
                ("som_reproducao", "reproducao", "Som ao iniciar e ao parar a reprodução e as rotinas",
                 ("repro_inicio", "repro_fim")),
                ("som_contagem", "contagem", "Tique a cada segundo da contagem inicial", ("tique",))):
            lin = linha_inline(se.corpo, self.t)
            vg = a.var(campo)
            marcar(lin, texto, vg, lambda g=grupo, v=vg: a.sincronizar_grupo_som(g, bool(v.get()))).pack(side="left")
            for ev, rot_ev in zip(evs, ("Ouvir início", "Ouvir fim") if len(evs) == 2 else ("Ouvir",)):
                botao(lin, rot_ev, lambda e=ev: self.ouvir_som(e), "Ghost", True).pack(side="left", padx=(10, 0))
            se.linha_cheia(lin)
        from ..som import NOMES_TIPOS
        self._nomes_som = dict(NOMES_TIPOS)
        self.v_estilo = tk.StringVar(value=self._nomes_som.get(self.g.som_tipo, self._nomes_som["sino"]))
        cb = escolha(se.corpo, self.v_estilo, list(self._nomes_som.values()), 24)
        cb.bind("<<ComboboxSelected>>", lambda _e: self._estilo_som())
        se.campo("Estilo do som", cb)
        v_vol = a.var("som_volume")
        v_vol.trace_add("write", lambda *_a: self._som_mudou())
        se.campo("Volume do som (%)", numero(se.corpo, v_vol, 0, 100, 5, 6),
                 "O som é sempre suave; 0 = mudo.")
        va = a.var("som_arquivo")
        va.trace_add("write", lambda *_a: self._som_mudou())
        arq = linha_inline(se.corpo, self.t)
        arq.columnconfigure(0, weight=1)
        entrada(arq, va).grid(row=0, column=0, sticky="ew")
        botao(arq, "…", self._escolher_wav, "Ghost", True).grid(row=0, column=1, padx=(6, 0))
        se.campo("Meu arquivo .wav", arq, "Opcional: escolha “Meu arquivo .wav” no estilo para usar.")
        wl = linha_inline(se.corpo, self.t)
        wl.columnconfigure(0, weight=1)
        entrada(wl, a.var("webhook")).grid(row=0, column=0, sticky="ew")
        botao(wl, "Testar", self.testar_webhook, "Ghost", True).grid(row=0, column=1, padx=(6, 0))
        se.campo("Webhook (opcional)", wl, "Discord/URL ou telegram:TOKEN@CHAT_ID. Recebe os alertas.")

        sv = montar_cartao(self, g, a, c)

        # ---------------- atualização (manifesto por URL, avançado) ----------------
        up = Cartao(g, self.t, "Atualização", f"Versão instalada: {__version__}. Seus botões, regras, "
                    "perfis e gravações nunca são sobrescritos.")
        up.campo("Endereço do manifesto", entrada(up.corpo, a.var("url_atualizacao")),
                 "Um JSON com {\"versao\": \"x.y.z\", \"url\": \"…zip\"}. Opcional.")
        bu = tk.Frame(up.corpo, bg=c["card"])
        up.linha_cheia(bu, (6, 0))
        botao(bu, "Verificar atualização", self.verificar_atualizacao, "Accent", True).pack(side="left")
        botao(bu, "Aplicar pacote .zip…", self.aplicar_zip, "Ghost", True).pack(side="left", padx=8)
        botao(bu, "Desfazer última", self.desfazer_atualizacao, "Ghost", True).pack(side="left")
        self.lbl_up = rotulo(up.corpo, self.t, "", muted=True, anchor="w", justify="left", wraplength=320)
        up.linha_cheia(self.lbl_up, (8, 0))

        self._cartoes = [j, p, at, se, d, sv, up, ap]
        responsivo(g, self._cartoes)
        self.quadro_deps = tk.Frame(d.corpo, bg=c["card"])
        d.linha_cheia(self.quadro_deps)
        botao(d.corpo, "Como instalar o OCR (opcional)", lambda: messagebox.showinfo(
            "OCR (opcional)", DICA_OCR, parent=self.app.raiz), "Ghost", True).grid(
            row=d._linha, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ins = tk.Frame(d.corpo, bg=c["card"])
        d.linha_cheia(ins, (8, 0))
        botao(ins, "Instalar pytesseract", self.instalar_pytesseract, "Ghost", True).pack(side="left")
        botao(ins, "Instalar Tesseract", self.instalar_tesseract, "Ghost", True).pack(side="left", padx=8)
        self._deps()

    # ------------------------------------------------------------------ #
    def _com_pasta(self, pai: tk.Misc, campo: str) -> tk.Frame:
        lin = linha_inline(pai, self.t)
        lin.columnconfigure(0, weight=1)
        v = self.app.var(campo)
        entrada(lin, v).grid(row=0, column=0, sticky="ew")
        botao(lin, "…", lambda: self._escolher_pasta(v), "Ghost", True).grid(row=0, column=1, padx=(6, 0))
        return lin

    def _com_arquivo(self, pai: tk.Misc, campo: str) -> tk.Frame:
        lin = linha_inline(pai, self.t)
        lin.columnconfigure(0, weight=1)
        v = self.app.var(campo)
        entrada(lin, v).grid(row=0, column=0, sticky="ew")
        botao(lin, "…", lambda: self._escolher_arquivo(v), "Ghost", True).grid(row=0, column=1, padx=(6, 0))
        return lin

    def _escolher_pasta(self, v: tk.Variable) -> None:
        p = filedialog.askdirectory(parent=self.app.raiz)
        if p:
            v.set(p)

    def _escolher_arquivo(self, v: tk.Variable) -> None:
        p = filedialog.askopenfilename(parent=self.app.raiz, filetypes=[("JSON", "*.json"), ("Todos", "*.*")])
        if p:
            v.set(p)

    def listar(self) -> None:
        janelas = listar_janelas()
        if not janelas:
            self.app.log_texto("Não consegui listar janelas (só funciona no Windows). Digite o título.\n", "aviso")
        self.cb_janela.configure(values=janelas)
        if janelas:
            self.cb_janela.event_generate("<Button-1>")

    def carregar_perfil(self) -> None:
        nome = self.v_perfil.get()
        if not nome:
            return
        try:
            usados = aplicar_perfil(self.g, ler_perfil(nome))
        except (OSError, ValueError) as e:
            messagebox.showerror("Perfil", f"Não consegui ler o perfil: {e}", parent=self.app.raiz)
            return
        self.app.log_texto(f"✔ Perfil “{nome}” carregado ({', '.join(usados) or 'nada'}).\n", "ok")
        self.app.montar()
        self.app.ir("config")

    def salvar_perfil(self) -> None:
        nome = pedir_texto(self.app.raiz, self.t, "Salvar perfil", "Nome do perfil (ex.: roblox):",
                           self.g.janela.split()[0].lower() if self.g.janela.strip() else "")
        if not nome:
            return
        nome = "".join(ch if (ch.isalnum() or ch in "_-") else "_" for ch in nome)
        caminho = comandos.salvar_perfil(self.g, nome, self.g.modo_auto)
        self.app.log_texto(f"✔ Perfil salvo em {caminho}. No terminal: uv run autoclick --perfil {nome}\n", "ok")
        self.cb_perfil.configure(values=listar_perfis())
        self.v_perfil.set(nome)

    def _tema(self) -> None:
        self.app.trocar_tema(self.v_tema.get())

    def _deps(self) -> None:
        for w in self.quadro_deps.winfo_children():
            w.destroy()
        c = self.t.c
        for nome, ok, obrig, uso in dependencias():
            lin = tk.Frame(self.quadro_deps, bg=c["card"])
            lin.pack(fill="x", pady=3)
            cor = c["ok"] if ok else (c["danger"] if obrig else c["warn"])
            tk.Label(lin, text="✔" if ok else ("✖" if obrig else "–"), bg=c["card"], fg=cor,
                     font=self.t.f_negrito, width=2).grid(row=0, column=0, rowspan=2, sticky="n")
            tk.Label(lin, text=nome, bg=c["card"], fg=c["text"], font=self.t.f_normal,
                     anchor="w").grid(row=0, column=1, sticky="w")
            sufixo = "" if ok else (" — obrigatória: rode uv sync" if obrig else " — opcional, não instalada")
            tk.Label(lin, text=uso + sufixo, bg=c["card"], fg=c["muted"], font=self.t.f_pequena,
                     anchor="w").grid(row=1, column=1, sticky="w")

    # ------------------------------------------------------------------ #
    # atalhos
    # ------------------------------------------------------------------ #
    def _atalho_padrao(self, k: str) -> None:
        self._cancelar_captura()
        self.v_teclas[k].set(PADRAO_ATALHOS[k])

    def ler_tecla(self, ignorar: set[int]) -> Optional[str]:
        """Tecla/combinação apertada agora (separado para os testes poderem simular)."""
        return m_windows.ler_atalho(estado_global, ignorar)

    def teclas_agora(self) -> set[int]:
        return m_windows.teclas_apertadas(estado_global)

    def capturar(self, k: str) -> None:
        """Escuta a próxima tecla (até 8 s). Esc cancela."""
        import time
        self._cancelar_captura()
        self._captura = k
        self._captura_fim = time.time() + 8.0
        self._captura_antes = self.teclas_agora()  # o que já estava apertado (ex.: o clique) não conta
        self._captura_valor = self.v_teclas[k].get()
        self.v_teclas[k].set("Aperte a tecla… (Esc cancela)")
        self._captura_tick()

    def _captura_tick(self) -> None:
        import time
        k = self._captura
        if k is None:
            return
        if m_windows.tecla_pressionada_global(0x1B):  # Esc
            self._cancelar_captura()
            return
        nome = self.ler_tecla(self._captura_antes)
        if nome is not None:
            self._captura_id = None
            self._captura = None
            self._receber_atalho(k, nome)
            return
        self._captura_antes &= self.teclas_agora()  # tecla solta volta a valer
        if time.time() > self._captura_fim:
            self._cancelar_captura()
            return
        self._captura_id = self.app.raiz.after(20, self._captura_tick)

    def _cancelar_captura(self) -> None:
        if self._captura_id is not None:
            try:
                self.app.raiz.after_cancel(self._captura_id)
            except Exception:
                pass
            self._captura_id = None
        if self._captura is not None:
            self.v_teclas[self._captura].set(self._captura_valor)
            self._captura = None

    def _receber_atalho(self, k: str, nome: str) -> None:
        antigo = self._captura_valor
        outro = next((o for o, v in self.v_teclas.items()
                      if o != k and m_windows.normalizar_atalho(v.get()) == nome), None)
        if outro is not None:
            if not messagebox.askyesno("Atalho em uso", f"{nome} já é o atalho de “{NOMES_ATALHOS[outro]}”. "
                                       f"Trocar os dois?", parent=self.app.raiz):
                self.v_teclas[k].set(antigo)
                return
            self.v_teclas[outro].set(antigo)
        aviso = aviso_atalho(nome)
        if aviso and not messagebox.askyesno("Atalho", aviso + "\n\nUsar mesmo assim?", parent=self.app.raiz):
            self.v_teclas[k].set(antigo)
            if outro is not None:
                self.v_teclas[outro].set(nome)
            return
        self.v_teclas[k].set(nome)

    def aplicar_teclas(self) -> None:
        self._cancelar_captura()
        v = {k: (m_windows.normalizar_atalho(x.get()) or x.get().strip()) for k, x in self.v_teclas.items()}
        erro = teclas_validas(v["pausa"], v["parar"], v["gravar"], v["reproduzir"])
        if erro:
            messagebox.showwarning("Atalhos", erro, parent=self.app.raiz)
            return
        for k, val in v.items():
            setattr(self.g, "tecla_" + k, val)
        self.app.log_texto(f"✔ Atalhos: pausar {v['pausa']}, parar {v['parar']}, gravação {v['gravar']}, reproduzir {v['reproduzir']}. "
                           "Valem a partir da próxima função iniciada.\n", "ok")
        self.app.atualizar_rodape_teclas()

    # ------------------------------------------------------------------ #
    # avisos
    # ------------------------------------------------------------------ #
    def ouvir_som(self, evento: str = "volta") -> None:
        from ..som import som
        import threading
        som.configurar(self.g.som_tipo, self.g.som_volume, self.g.som_arquivo)
        threading.Thread(target=lambda: som.tocar_evento(evento, forcar=True), daemon=True).start()

    def _estilo_som(self) -> None:
        inv = {v: k for k, v in self._nomes_som.items()}
        self.g.som_tipo = inv.get(self.v_estilo.get(), "sino")
        self._som_mudou()
        self.ouvir_som()

    def _som_mudou(self) -> None:
        self.app.enviar_config_som()

    def _escolher_wav(self) -> None:
        p = filedialog.askopenfilename(parent=self.app.raiz, filetypes=[("Som WAV", "*.wav"), ("Todos", "*.*")])
        if p:
            self.app.var("som_arquivo").set(p)
            self.g.som_arquivo = p
            self.g.som_tipo = "arquivo"
            self.v_estilo.set(self._nomes_som["arquivo"])
            self._som_mudou()

    def testar_webhook(self) -> None:
        url = self.g.webhook.strip()
        if not url:
            messagebox.showinfo("Webhook", "Preencha o endereço do webhook primeiro.", parent=self.app.raiz)
            return
        self.app.log_texto("Enviando aviso de teste...\n", "dim")
        self.app.em_segundo_plano(lambda: enviar_webhook_sync("Autoclick", "Aviso de teste: tudo certo!", url),
                                  self._fim_teste_webhook)

    def _fim_teste_webhook(self, r: Any) -> None:
        ok, msg = r
        self.app.log_texto(("✔ Webhook respondeu: " if ok else "✖ Webhook falhou: ") + str(msg) + "\n",
                           "ok" if ok else "erro")

    # ------------------------------------------------------------------ #
    # atualização
    # ------------------------------------------------------------------ #
    def _raiz_projeto(self) -> str:
        import os
        return os.getcwd()

    def verificar_atualizacao(self) -> None:
        url = self.g.url_atualizacao.strip()
        if not url:
            messagebox.showinfo("Atualização", "Informe o endereço do manifesto (ou use “Aplicar pacote .zip”).",
                                parent=self.app.raiz)
            return
        self.lbl_up.configure(text="Verificando...")
        self.app.em_segundo_plano(lambda: atualizacao.verificar(url, __version__), self._fim_verificar)

    def _fim_verificar(self, r: Any) -> None:
        ok, info = r
        self._manifesto = info
        if not ok:
            self.lbl_up.configure(text="✖ " + str(info.get("erro", "falhou")))
            return
        if not info.get("nova"):
            self.lbl_up.configure(text=f"✔ Você já está na versão mais recente ({__version__}).")
            return
        self.lbl_up.configure(text=f"Nova versão {info['versao']} disponível. {info.get('notas', '')}")
        if info.get("url") and messagebox.askyesno(
                "Atualização", f"Baixar e instalar a versão {info['versao']}?\n\n"
                "Seus dados são preservados e o que for trocado fica em backup/.", parent=self.app.raiz):
            self.lbl_up.configure(text="Baixando e instalando...")
            raiz = self._raiz_projeto()
            self.app.em_segundo_plano(lambda: self._seguro(lambda: atualizacao.atualizar_de_url(info["url"], raiz)),
                                      self._fim_aplicar)

    @staticmethod
    def _seguro(fn: Any) -> Any:
        try:
            return ("ok", fn())
        except Exception as e:
            return ("erro", f"{type(e).__name__}: {e}")

    def aplicar_zip(self) -> None:
        arq = filedialog.askopenfilename(parent=self.app.raiz, title="Pacote de atualização",
                                         filetypes=[("Pacote .zip", "*.zip")])
        if not arq:
            return
        try:
            itens = atualizacao.listar_pacote(arq)
        except Exception as e:
            messagebox.showerror("Atualização", f"Não consegui abrir o pacote: {e}", parent=self.app.raiz)
            return
        if not messagebox.askyesno("Atualização", f"O pacote vai instalar {len(itens)} arquivo(s). "
                                   "Seus botões, regras, perfis e gravações são preservados e o que for "
                                   "trocado fica em backup/.\n\nContinuar?", parent=self.app.raiz):
            return
        raiz = self._raiz_projeto()
        self.app.em_segundo_plano(lambda: self._seguro(lambda: atualizacao.aplicar_zip(arq, raiz)),
                                  self._fim_aplicar)

    def _fim_aplicar(self, r: Any) -> None:
        estado, dados = r
        if estado != "ok":
            self.lbl_up.configure(text="✖ " + str(dados))
            self.app.log_texto(f"✖ Atualização falhou: {dados}\n", "erro")
            return
        msg = f"✔ {len(dados['instalados'])} arquivo(s) atualizado(s)" + (
            f"; backup em {dados['backup']}" if dados.get("backup") else "") + ". Feche e abra o programa de novo."
        self.lbl_up.configure(text=msg)
        self.app.log_texto(msg + "\n", "ok")

    def desfazer_atualizacao(self) -> None:
        bks = atualizacao.listar_backups(self._raiz_projeto())
        if not bks:
            messagebox.showinfo("Atualização", "Não há backups de atualização.", parent=self.app.raiz)
            return
        if messagebox.askyesno("Desfazer", f"Voltar os arquivos de {bks[0]}?", parent=self.app.raiz):
            n = atualizacao.restaurar_backup(bks[0], self._raiz_projeto())
            self.app.log_texto(f"✔ {n} arquivo(s) restaurado(s). Feche e abra o programa de novo.\n", "ok")

    # ------------------------------------------------------------------ #
    # instalar dependências opcionais
    # ------------------------------------------------------------------ #
    def _instalar(self, nome: str, cmd: list[str]) -> None:
        self.app.rodar(nome, [], minimizar=False, ao_fim=lambda _c: self._deps(), comando_completo=cmd)

    def instalar_pytesseract(self) -> None:
        cmd = comando_instalar_pytesseract()
        if cmd is None:
            messagebox.showinfo("pytesseract", "Esta é a versão empacotada (.exe): ela não consegue instalar "
                                "pacotes Python. Use a versão com Python/uv.", parent=self.app.raiz)
            return
        if messagebox.askyesno("Instalar pytesseract", "Vai executar:\n\n  " + " ".join(cmd)
                               + "\n\nÉ preciso internet. Continuar?", parent=self.app.raiz):
            self._instalar("instalar", cmd)

    def instalar_tesseract(self) -> None:
        cmd = comando_instalar_tesseract()
        if cmd is None:
            import webbrowser
            if messagebox.askyesno("Tesseract", "Não achei o winget neste computador. Abrir a página de "
                                   "download do Tesseract no navegador?\n(Marque o idioma Portuguese.)",
                                   parent=self.app.raiz):
                webbrowser.open(URL_TESSERACT)
            return
        if messagebox.askyesno("Instalar Tesseract", "Vai executar:\n\n  " + " ".join(cmd)
                               + "\n\nO Windows pode pedir permissão de administrador. Continuar?",
                               parent=self.app.raiz):
            self._instalar("instalar", cmd)

    def ao_mostrar(self) -> None:
        self.cb_perfil.configure(values=listar_perfis())
        self._deps()

    def ao_status(self, dados: dict[str, Any]) -> None:
        pass


