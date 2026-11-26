# pyright: basic
"""Cartão “Atualizações” (Configurações): verificar, atualizar, salvar relatório."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from tkinter import messagebox
from typing import Any, Optional

from .. import __version__, atualizacao, novidades, relatorio
from .widgets import Cartao, botao, marcar, rotulo


class ControleServidor:
    """Lógica do cartão (sem depender do layout): usada pela página e pela verificação ao abrir."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self.info: Optional[dict[str, Any]] = None
        self.pronto: Optional[dict[str, Any]] = None   # {"zip", "info"}: baixado, falta instalar
        self.baixando = False
        self.instalando = False
        self.aplicar_ao_fim = False
        self.oferecido = False
        self._ocioso_desde = 0.0
        self.lbl: Any = None
        self.lbl_srv: Any = None
        self.barra_txt = ""
        self._seguir: Any = None

    # ---- servidor ------------------------------------------------------ #
    def raiz(self) -> str:
        return os.getcwd()

    def servidor(self) -> Optional[atualizacao.Servidor]:
        return atualizacao.servidor_padrao()

    def texto_servidor(self) -> str:
        s = self.servidor()
        if s is None:
            return "Este programa não tem servidor de atualizações configurado."
        host = s.url.split("//", 1)[-1].split("/", 1)[0]
        return f"Atualizações de: {host}"

    def pintar(self) -> None:
        if self.lbl_srv is not None:
            self.lbl_srv.configure(text=self.texto_servidor())

    def _msg(self, txt: str) -> None:
        if self.lbl is not None:
            self.lbl.configure(text=txt)

    # ---- verificar / atualizar --------------------------------------- #
    def verificar(self, silencioso: bool = False) -> None:
        srv = self.servidor()
        if srv is None:
            if not silencioso:
                messagebox.showinfo("Atualização", "Este programa não tem servidor de atualizações configurado.",
                                    parent=self.app.raiz)
            return
        self._msg("Verificando…")
        self.app.em_segundo_plano(lambda: self._seguro(lambda: atualizacao.consultar(srv, __version__)),
                                  lambda r: self._fim_verificar(r, silencioso))

    def _fim_verificar(self, r: Any, silencioso: bool) -> None:
        estado, d = r
        if estado != "ok":
            self._msg("✖ " + str(d))
            if not silencioso:
                self.app.log_texto(f"✖ Atualização: {d}\n", "erro")
            return
        self.info = d
        if d.get("mensagem"):
            self.app.log_texto(f"ℹ Aviso do servidor: {d['mensagem']}\n")
        if not d["nova"]:
            self._msg(f"✔ Você está na versão mais recente ({__version__}).")
            self.app.definir_nova_versao(None)
            return
        self.app.definir_nova_versao(d["versao"])
        self._msg(f"Nova versão {d['versao']}."
                  + (" OBRIGATÓRIA." if d["obrigatoria"] else "") + f" {d.get('notas', '')}")
        if self.pronto and self.pronto["info"]["versao"] == d["versao"]:
            self.app.definir_nova_versao(d["versao"], pronta=True)
            return
        # baixa já, em segundo plano; instalar é só um clique (ou ao fechar)
        self.baixar_em_segundo_plano(aplicar_ao_fim=(not silencioso))

    # ---- download em segundo plano ----------------------------------- #
    def baixar_em_segundo_plano(self, aplicar_ao_fim: bool = False) -> None:
        d, srv = self.info, self.servidor()
        if not d or not d.get("nova") or srv is None:
            return
        if self.baixando:
            self.aplicar_ao_fim = self.aplicar_ao_fim or aplicar_ao_fim
            return
        self.baixando, self.aplicar_ao_fim = True, aplicar_ao_fim
        raiz = self.raiz()
        self.app.log_texto(f"⬇ Baixando a versão {d['versao']} em segundo plano (pode continuar usando o programa)…\n", "dim")

        def prog(feito: int, total: int) -> None:
            self.barra_txt = f"Baixando a versão {d['versao']}… {feito * 100 // max(total, 1)}%"

        def trabalho() -> Any:
            return atualizacao.baixar_pacote(srv, d, atualizacao.pasta_baixados(raiz), prog)

        self._msg("Baixando…")
        self.app.em_segundo_plano(lambda: self._seguro(trabalho), lambda r: self._fim_baixar(r, d))
        self._acompanhar()

    def _parar_acompanhar(self) -> None:
        if self._seguir is not None:
            try:
                self.app.raiz.after_cancel(self._seguir)
            except Exception:
                pass
            self._seguir = None

    def _fim_baixar(self, r: Any, d: dict[str, Any]) -> None:
        self.baixando = False
        self._parar_acompanhar()
        estado, z = r
        if estado != "ok":
            self._msg("✖ " + str(z))
            self.app.log_texto(f"✖ Não consegui baixar a atualização: {z}\n", "erro")
            self.aplicar_ao_fim = False
            return
        self.pronto = {"zip": z, "info": d}
        self.oferecido = False
        self.app.definir_nova_versao(d["versao"], pronta=True)
        self._msg(f"✔ Versão {d['versao']} baixada. Instala quando você clicar em “Atualizar agora”"
                  + (" ou ao fechar o programa." if self.app.g.atualizar_ao_fechar else "."))
        self.app.log_texto(f"✔ Versão {d['versao']} baixada e conferida; pronta para instalar.\n", "ok")
        if self.aplicar_ao_fim:
            self.aplicar_ao_fim = False
            self.aplicar_pronta()
        elif d.get("obrigatoria"):
            self.oferecer(forcar=True)

    # ---- instalar ------------------------------------------------------ #
    def atualizar(self) -> None:
        """Botão “Atualizar agora”."""
        if self.pronto:
            self.aplicar_pronta()
        elif self.baixando:
            self._msg("Ainda baixando; assim que terminar a instalação começa.")
            self.aplicar_ao_fim = True
        elif self.info and self.info.get("nova"):
            self.baixar_em_segundo_plano(aplicar_ao_fim=True)
        else:
            self.verificar()

    def oferecer(self, forcar: bool = False) -> None:
        """Pergunta (uma vez por execução) se pode instalar a versão baixada."""
        if not self.pronto or self.oferecido and not forcar or self.app.exec.rodando:
            return
        self.oferecido = True
        d = self.pronto["info"]
        if messagebox.askyesno(
                "Atualização pronta",
                f"A versão {d['versao']} já foi baixada.\n\n{d.get('notas', '')}\n\nInstalar agora? "
                + ("O programa fecha e abre de novo sozinho." if atualizacao.esta_congelado() else
                   "Depois feche e abra o programa.") + "\n\n(Se preferir, instala sozinho quando você fechar.)",
                parent=self.app.raiz):
            self.aplicar_pronta()

    def tick(self) -> None:
        """Chamado pelo laço da janela: só oferece a instalação com o programa visível e parado."""
        agora = time.time()
        if not self.pronto or self.oferecido or self.instalando:
            self._ocioso_desde = 0.0
            return
        if self.app.exec.rodando or self.app.raiz.state() != "normal":
            self._ocioso_desde = 0.0
            return
        if not self._ocioso_desde:
            self._ocioso_desde = agora
        elif agora - self._ocioso_desde >= 30.0:
            self.oferecer()

    def aplicar_pronta(self) -> None:
        if not self.pronto or self.instalando:
            return
        if self.app.exec.rodando:
            messagebox.showinfo("Atualização", "Pare a função em execução antes de atualizar.", parent=self.app.raiz)
            return
        z, d, raiz = self.pronto["zip"], self.pronto["info"], self.raiz()
        congelado = atualizacao.esta_congelado()
        self.instalando = True
        self._msg("Instalando…")

        def trabalho() -> Any:
            if congelado:
                novidades.guardar(raiz, str(d["versao"]), str(d.get("notas", "")))
                return {"cmd": atualizacao.preparar_troca_exe(z, raiz), "versao": d["versao"]}
            return atualizacao.instalar_zip_baixado(z, d, raiz)

        self.app.em_segundo_plano(lambda: self._seguro(trabalho), self._fim_atualizar)

    def _acompanhar(self) -> None:
        if self.barra_txt and self.lbl is not None and str(self.lbl.cget("text")).startswith(("Baixando", "…")):
            self._msg(self.barra_txt)
        if self.baixando:
            self._seguir = self.app.raiz.after(400, self._acompanhar)

    def _fim_atualizar(self, r: Any) -> None:
        self.instalando = False
        estado, d = r
        if estado != "ok":
            self._msg("✖ " + str(d))
            self.app.log_texto(f"✖ Atualização falhou: {d}\n", "erro")
            return
        atualizacao.limpar_baixados(self.raiz()) if "cmd" not in d else None
        self.pronto = None
        if "cmd" in d:
            self._msg("Pacote pronto. Reiniciando…")
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
            subprocess.Popen(["cmd", "/c", d["cmd"]], creationflags=flags, close_fds=True)
            self.app.fechar(forcar=True)
            return
        msg = (f"✔ Versão {d['versao']} instalada ({len(d['instalados'])} arquivo(s)); backup em "
               f"{d.get('backup', '—')}. Feche e abra o programa de novo.")
        self._msg(msg)
        self.app.log_texto(msg + "\n", "ok")
        self.app.definir_nova_versao(None)

    # ---- ao fechar: instala o que já foi baixado ----------------------- #
    def ao_fechar(self) -> None:
        """Chamado por App.fechar: com atualização baixada e a opção ligada, instala agora.

        No .exe um script espera o programa fechar e troca os arquivos (sem reabrir);
        no código-fonte instala direto (com backup, autoteste e reversão)."""
        if not self.pronto or not self.app.g.atualizar_ao_fechar or self.instalando:
            return
        z, d, raiz = self.pronto["zip"], self.pronto["info"], self.raiz()
        self.pronto = None
        try:
            if atualizacao.esta_congelado():
                novidades.guardar(raiz, str(d["versao"]), str(d.get("notas", "")))
                cmd = atualizacao.preparar_troca_exe(z, raiz, reabrir=False)
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
                subprocess.Popen(["cmd", "/c", cmd], creationflags=flags, close_fds=True)
            else:
                atualizacao.instalar_zip_baixado(z, d, raiz)
                atualizacao.limpar_baixados(raiz)
        except Exception as e:  # fechar nunca pode travar por causa da atualização
            from .. import registro_log
            registro_log.escrever(f"atualização ao fechar falhou: {atualizacao.descrever_erro(e)}")

    @staticmethod
    def _seguro(fn: Any) -> Any:
        try:
            return ("ok", fn())
        except Exception as e:
            return ("erro", atualizacao.descrever_erro(e))

    # ---- relatório ---------------------------------------------------- #
    def salvar_relatorio(self) -> None:
        """Monta o relatório de problema num .zip para a pessoa mandar a quem mantém o programa."""
        from tkinter import filedialog
        itens = relatorio.conteudo(self.raiz())
        if not messagebox.askyesno(
                "Salvar relatório de problema",
                "O arquivo terá:\n\n  • " + "\n  • ".join(itens)
                + "\n\nNão vão botões, perfis, gravações nem webhook. Nada é enviado: você escolhe a quem "
                "mandar o arquivo.\nSalvar?", parent=self.app.raiz):
            return
        destino = filedialog.asksaveasfilename(parent=self.app.raiz, title="Salvar relatório",
                                               defaultextension=".zip", initialfile="relatorio_autoclick.zip",
                                               filetypes=[("Arquivo zip", "*.zip")])
        if not destino:
            return
        try:
            relatorio.montar(destino, self.raiz(), f"v{__version__} {sys.platform}")
        except Exception as e:
            self._msg("✖ " + atualizacao.descrever_erro(e))
            return
        self._msg(f"✔ Relatório salvo em {destino}.")


def montar_cartao(pagina: Any, g: Any, a: Any, c: Any) -> Cartao:
    ctl = pagina.app.up
    pagina.servidor_ctl = ctl
    cart = Cartao(g, pagina.t, "Atualizações",
                  "Atualizações assinadas, baixadas do site de downloads. Seus dados nunca são sobrescritos.")
    ctl.lbl_srv = rotulo(cart.corpo, pagina.t, ctl.texto_servidor(), muted=True, anchor="w", justify="left",
                         wraplength=320)
    cart.linha_cheia(ctl.lbl_srv)
    cart.linha_cheia(marcar(cart.corpo, "Verificar novidades ao abrir o programa", a.var("atualizar_ao_abrir")), (6, 0))
    cart.linha_cheia(marcar(cart.corpo, "Instalar a atualização já baixada ao fechar o programa",
                            a.var("atualizar_ao_fechar")), (2, 0))
    import tkinter as tk
    b2 = tk.Frame(cart.corpo, bg=c["card"]); cart.linha_cheia(b2, (8, 0))
    botao(b2, "Verificar atualização", lambda: ctl.verificar(), "Accent", True).pack(side="left")
    botao(b2, "Atualizar agora", ctl.atualizar, "Ghost", True).pack(side="left", padx=8)
    botao(b2, "Salvar relatório…", ctl.salvar_relatorio, "Ghost", True).pack(side="left")
    ctl.lbl = rotulo(cart.corpo, pagina.t, "", muted=True, anchor="w", justify="left", wraplength=320)
    cart.linha_cheia(ctl.lbl, (8, 0))
    return cart
