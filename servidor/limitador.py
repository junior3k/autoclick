# pyright: basic
"""Limites simples em memória: bloqueio por falhas de autenticação e taxa de pedidos."""
from __future__ import annotations

import threading
import time
from typing import Optional


class Limitador:
    def __init__(self, max_falhas: int = 10, janela_falhas: float = 600.0,
                 max_pedidos: int = 120, janela_pedidos: float = 60.0) -> None:
        self.max_falhas, self.janela_falhas = max_falhas, janela_falhas
        self.max_pedidos, self.janela_pedidos = max_pedidos, janela_pedidos
        self._falhas: dict[str, list[float]] = {}
        self._pedidos: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _podar(lista: list[float], agora: float, janela: float) -> list[float]:
        return [t for t in lista if agora - t <= janela]

    def bloqueado(self, ip: str, agora: Optional[float] = None) -> bool:
        agora = time.time() if agora is None else agora
        with self._lock:
            f = self._podar(self._falhas.get(ip, []), agora, self.janela_falhas)
            self._falhas[ip] = f
            return len(f) >= self.max_falhas

    def falha(self, ip: str, agora: Optional[float] = None) -> None:
        agora = time.time() if agora is None else agora
        with self._lock:
            self._falhas.setdefault(ip, []).append(agora)

    def sucesso(self, ip: str) -> None:
        with self._lock:
            self._falhas.pop(ip, None)

    def permitir(self, chave: str, agora: Optional[float] = None) -> bool:
        """Taxa de pedidos por chave (amigo). False = passou do limite por minuto."""
        agora = time.time() if agora is None else agora
        with self._lock:
            p = self._podar(self._pedidos.get(chave, []), agora, self.janela_pedidos)
            if len(p) >= self.max_pedidos:
                self._pedidos[chave] = p
                return False
            p.append(agora)
            self._pedidos[chave] = p
            return True
