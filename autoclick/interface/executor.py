"""Roda cada função do programa como um processo separado e conversa com ele.

Vantagens: a janela nunca trava, um erro no processo não derruba a janela, e as
dependências opcionais (OCR) só são tocadas dentro do processo que as usa.
"""
from __future__ import annotations

import codecs
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional, cast


def _python_com_console() -> str:
    """Com pythonw (sem console) o filho precisa do python.exe normal; a janela dele é ocultada."""
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        alt = exe[:-len("pythonw.exe")] + "python.exe"
        if os.path.exists(alt):
            return alt
    return exe


class Executor:
    """Um processo por vez. Chame `sondar()` periodicamente (a janela faz isso a cada 100 ms)."""

    def __init__(self, ao_texto: Callable[[str], None], ao_status: Callable[[dict[str, Any]], None],
                 ao_fim: Callable[[str, int], None], diretorio: Optional[str] = None) -> None:
        self.ao_texto, self.ao_status, self.ao_fim = ao_texto, ao_status, ao_fim
        self.diretorio = diretorio or os.getcwd()
        self._tmp = Path(tempfile.mkdtemp(prefix="autoclick_gui_"))
        self.arq_cmd = str(self._tmp / "comando.txt")
        self.arq_status = str(self._tmp / "status.json")
        self._proc: Optional[subprocess.Popen[bytes]] = None
        self._fila: "queue.Queue[Optional[str]]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self.nome = ""
        self.inicio = 0.0
        self._ultimo_status = 0.0
        self.pausado = False
        self._pedido_parar = 0.0
        self.comando_base: Optional[list[str]] = None  # para testes: substitui "python -m autoclick"
        self.env_base: dict[str, str] = {}  # variáveis extras para todo processo (webhook, teclas...)

    # ---------------- estado ---------------- #
    @property
    def rodando(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _comando_python(self, argv: list[str]) -> list[str]:
        base = self.comando_base
        if base is None:
            if getattr(sys, "frozen", False):  # .exe: o console-filho fica ao lado da janela
                cli = os.path.join(os.path.dirname(sys.executable), "autoclick-cli.exe")
                base = [cli if os.path.exists(cli) else sys.executable]
            else:
                base = [_python_com_console(), "-u", "-m", "autoclick"]
        return [*base, *argv]

    # ---------------- iniciar / parar ---------------- #
    def rodar(self, nome: str, argv: list[str], env_extra: Optional[dict[str, str]] = None,
              comando_completo: Optional[list[str]] = None) -> bool:
        """Inicia um processo. `argv` vai para o autoclick; `comando_completo` (ex.: instalar
        uma dependência) substitui o comando inteiro."""
        if self.rodando:
            return False
        for f in (self.arq_cmd, self.arq_status):
            try:
                os.remove(f)
            except OSError:
                pass
        env = dict(os.environ)
        env.update({"PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8",
                    "AUTOCLICK_CONTROLE": self.arq_cmd, "AUTOCLICK_STATUS": self.arq_status,
                    "AUTOCLICK_FILHO": "1"})
        env.update({**self.env_base, **(env_extra or {})})
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        try:
            self._proc = subprocess.Popen(
                comando_completo or self._comando_python(argv), cwd=self.diretorio, env=env, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=flags)
        except OSError as e:
            self.ao_texto(f"✖ Não consegui iniciar o processo: {e}\n")
            self._proc = None
            return False
        self.nome, self.inicio, self.pausado, self._pedido_parar = nome, time.time(), False, 0.0
        self._thread = threading.Thread(target=self._ler, args=(self._proc,), daemon=True)
        self._thread.start()
        return True

    def _ler(self, proc: "subprocess.Popen[bytes]") -> None:
        dec = codecs.getincrementaldecoder("utf-8")(errors="replace")
        out = proc.stdout
        assert out is not None
        reader = cast(Any, out)
        while True:
            try:
                pedaco: bytes = reader.read1(4096)
            except (OSError, ValueError):
                break
            if not pedaco:
                break
            txt = dec.decode(pedaco)
            if txt:
                self._fila.put(txt)
        self._fila.put(None)

    def _escrever_comando(self, cmd: str) -> None:
        try:
            with open(self.arq_cmd, "a", encoding="utf-8") as f:
                f.write(cmd + "\n")
        except OSError:
            pass

    def enviar_comando(self, cmd: str) -> None:
        """Comando livre para o processo em execução (ex.: "som:1")."""
        if self.rodando:
            self._escrever_comando(cmd)

    def pausar(self, pausar: bool) -> None:
        if self.rodando:
            self._escrever_comando("pausar" if pausar else "continuar")

    def parar(self) -> None:
        """Pede para parar com educação; se o processo não obedecer em 4 s, encerra à força."""
        if not self.rodando:
            return
        self._escrever_comando("parar")
        self._pedido_parar = time.time()

    def enviar_enter(self) -> None:
        p = self._proc
        if p is not None and p.poll() is None and p.stdin is not None:
            try:
                p.stdin.write(b"\n")
                p.stdin.flush()
            except OSError:
                pass

    def matar(self) -> None:
        p = self._proc
        if p is not None and p.poll() is None:
            p.terminate()

    # ---------------- sondagem (chamada pelo loop do Tk) ---------------- #
    def sondar(self) -> None:
        terminou = False
        while True:
            try:
                item = self._fila.get_nowait()
            except queue.Empty:
                break
            if item is None:
                terminou = True
            else:
                self.ao_texto(item)
        if self.rodando:
            self._ler_status()
            if self._pedido_parar and time.time() - self._pedido_parar > 4.0:
                self.ao_texto("\n⚠ O processo não parou sozinho; encerrando à força.\n")
                self._pedido_parar = 0.0
                self.matar()
        if terminou or (self._proc is not None and self._proc.poll() is not None
                        and self._fila.empty()):
            if self._proc is not None:
                if self._thread is not None:
                    self._thread.join(timeout=0.5)
                code = self._proc.poll()
                if code is None:
                    code = self._proc.wait(timeout=2)
                self._ler_status()
                nome = self.nome
                self._proc = None
                self.ao_fim(nome, code)

    def _ler_status(self) -> None:
        try:
            m = os.path.getmtime(self.arq_status)
        except OSError:
            return
        if m == self._ultimo_status:
            return
        self._ultimo_status = m
        try:
            with open(self.arq_status, encoding="utf-8") as f:
                dados = cast(dict[str, Any], json.load(f))
        except (OSError, ValueError):
            return
        self.pausado = bool(dados.get("pausado"))
        self.ao_status(dados)

    def limpar(self) -> None:
        self.matar()
        try:
            for f in self._tmp.iterdir():
                f.unlink()
            self._tmp.rmdir()
        except OSError:
            pass
