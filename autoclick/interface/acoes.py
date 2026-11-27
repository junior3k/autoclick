# pyright: basic
"""Ações avulsas (antes na página Ferramentas): diagnóstico, mapa de regras, resumo de CSV e abrir pastas.
Cada uma é chamada por um botão na página onde faz sentido (Botões, Histórico e Configurações)."""
from __future__ import annotations

import os
import subprocess
import sys
from tkinter import filedialog
from typing import TYPE_CHECKING

from . import comandos

if TYPE_CHECKING:
    from .app import App


def diagnostico(app: "App") -> None:
    app.rodar("ferramenta", comandos.diagnostico(app.g))


def mapa_de_regras(app: "App") -> None:
    app.rodar("ferramenta", comandos.visualizar(app.g), minimizar=True,
              ao_fim=lambda _c: app.mostrar_imagem("mapa_regras.png", "Mapa de regras"))


def resumo_csv(app: "App") -> None:
    arq = filedialog.askopenfilename(parent=app.raiz, title="Escolher registro CSV",
                                     filetypes=[("CSV", "*.csv"), ("Todos", "*.*")])
    if arq:
        app.rodar("ferramenta", comandos.relatorio_csv(arq))


def abrir_pasta(app: "App", pasta: str) -> None:
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.abspath(pasta)
    try:
        if sys.platform == "win32":
            os.startfile(caminho)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", caminho])
        else:
            subprocess.Popen(["xdg-open", caminho])
    except OSError as e:
        app.log_texto(f"✖ Não consegui abrir {caminho}: {e}\n")
