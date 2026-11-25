# pyright: basic
"""Classe-base das páginas da janela."""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .app import App


class Pagina:
    chave = ""
    titulo = ""
    subtitulo = ""

    def __init__(self, app: "App", pai: tk.Misc) -> None:
        self.app = app
        self.t = app.t
        self.g = app.g
        self.frame = tk.Frame(pai, bg=self.t.c["bg"])
        self.construir()

    def construir(self) -> None:  # pragma: no cover - cada página implementa
        raise NotImplementedError

    def ao_mostrar(self) -> None:
        """A página ficou visível."""

    def pode_sair(self, _acao: str = "Sair") -> bool:
        """Antes de trocar de página/fechar: False cancela (ex.: alterações não salvas)."""
        return True

    def ao_estado(self, rodando: bool) -> None:
        """Começou/terminou um processo (habilite/desabilite botões)."""

    def ao_status(self, dados: dict[str, Any]) -> None:
        """Chegou status do processo em execução."""
