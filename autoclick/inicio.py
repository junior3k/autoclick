"""Ponto de entrada: sem argumentos (ou `gui`) abre a janela; com argumentos usa a linha de comando.

Importa só o necessário para cada caminho: a janela abre mesmo que bibliotecas opcionais
(ou até as principais) estejam faltando, e então mostra o que fazer.
"""
from __future__ import annotations

import os
import sys


def _sem_console() -> None:
    """Sob pythonw não há stdout/stderr: manda erros para autoclick_erro.log em vez de sumirem."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        try:
            sys.stderr = open("autoclick_erro.log", "a", encoding="utf-8")
        except OSError:
            sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _console_utf8() -> None:
    """Acentos certos no terminal do Windows (que usa páginas de código antigas, tipo cp850).

    Troca a página de código do console para UTF-8 enquanto o programa roda e devolve a original
    ao sair; também deixa stdout/stderr em UTF-8 (sem nunca falhar por um caractere estranho)."""
    if sys.platform == "win32":
        try:
            import atexit
            import ctypes
            k = ctypes.windll.kernel32  # type: ignore[attr-defined]
            antigo_saida, antigo_entrada = k.GetConsoleOutputCP(), k.GetConsoleCP()
            if antigo_saida and antigo_saida != 65001:
                k.SetConsoleOutputCP(65001)
                k.SetConsoleCP(65001)
                atexit.register(lambda: (k.SetConsoleOutputCP(antigo_saida), k.SetConsoleCP(antigo_entrada)))
        except Exception:
            pass
    for fluxo in (sys.stdout, sys.stderr):
        try:
            if fluxo is not None:
                fluxo.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass


def principal() -> None:
    if getattr(sys, "frozen", False):  # .exe: os dados (botões, perfis, id da instalação) ficam ao lado dele
        try:
            os.chdir(os.path.dirname(sys.executable))
        except OSError:
            pass
    _console_utf8()
    from . import registro_log
    if not registro_log.sou_filho():
        registro_log.capturar_saida()  # logs/autoclick.log com rotação
    argv = sys.argv[1:]
    if not argv or argv[0] == "gui":
        _sem_console()
        from .interface import abrir_app
        abrir_app()
        return
    from .cli import main
    main()
