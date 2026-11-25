"""Interface gráfica (Tk): usa só a biblioteca padrão; cada função roda em processo separado."""
from __future__ import annotations


def abrir_app() -> None:
    from .app import abrir_app as _abrir

    _abrir()


__all__ = ["abrir_app"]
