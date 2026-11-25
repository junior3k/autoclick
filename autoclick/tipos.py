"""Tipos básicos compartilhados (imagem, região, detecção)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy.typing as npt


Img = npt.NDArray[Any]

Regiao = tuple[int, int, int, int]

Palavra = tuple[str, int, int, int, int]  # texto, x, y, w, h

PALAVRAS_PADRAO: list[str] = [
    "ok", "aceitar", "continuar", "permitir", "confirmar", "próximo", "proximo",
    "sim", "accept", "allow", "continue", "next", "yes", "confirm",
]

@dataclass
class Hit:
    x: int
    y: int
    w: int
    h: int
    rotulo: str
    score: float = 1.0
    escala: float = 1.0  # escala do recorte que casou (1.0 = tamanho original do PNG)

    @property
    def centro(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2

# --------------------------------------------------------------------------- #
# Modo gravar: grava os SEUS cliques e arrastos (coordenadas + tempo)
# --------------------------------------------------------------------------- #
Caixa = tuple[int, int, int, int]
