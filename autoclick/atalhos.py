# pyright: basic
"""Atalhos de teclado (Ctrl/Alt/Shift + tecla): análise de nomes e leitura do que está apertado.

Módulo PURO (sem numpy nem Windows), para a janela poder usá-lo sem carregar o resto do programa.
"""
from __future__ import annotations

from typing import Callable, Optional

_MODIFICADORES: dict[str, tuple[int, tuple[int, ...]]] = {
    "CTRL": (0x11, (0xA2, 0xA3)), "ALT": (0x12, (0xA4, 0xA5)), "SHIFT": (0x10, (0xA0, 0xA1)),
}
_BASES_NOMEADAS: dict[str, int] = {
    "INSERT": 0x2D, "DELETE": 0x2E, "HOME": 0x24, "END": 0x23, "PAGEUP": 0x21, "PAGEDOWN": 0x22,
    "CIMA": 0x26, "BAIXO": 0x28, "ESQUERDA": 0x25, "DIREITA": 0x27, "PAUSE": 0x13,
    "SCROLLLOCK": 0x91, "PRINTSCREEN": 0x2C,
    **{f"NUM{i}": 0x60 + i for i in range(10)},
}
_NOME_DA_BASE: dict[int, str] = {v: k for k, v in _BASES_NOMEADAS.items()}
Atalho = tuple[tuple[str, ...], int]  # (modificadores na ordem CTRL, ALT, SHIFT; tecla)


def analisar_atalho(nome: str) -> Optional[Atalho]:
    """'ctrl+F11' -> (('CTRL',), 0x7A). Aceita F1..F24, letra, número, Insert/Home/PageUp…, Num0..9,
    com Ctrl/Alt/Shift antes. None se não reconhece."""
    partes = [p.strip().upper() for p in nome.split("+")]
    if any(not p for p in partes):
        return None
    base, mods = partes[-1], partes[:-1]
    if len(set(mods)) != len(mods) or any(m not in _MODIFICADORES for m in mods):
        return None
    vk: Optional[int] = None
    if len(base) >= 2 and base[0] == "F" and base[1:].isdigit() and 1 <= int(base[1:]) <= 24:
        vk = 0x6F + int(base[1:])
    elif len(base) == 1 and base.isascii() and (base.isalpha() or base.isdigit()):
        vk = ord(base)
    else:
        vk = _BASES_NOMEADAS.get(base)
    if vk is None:
        return None
    return tuple(m for m in _MODIFICADORES if m in mods), vk


def _nome_da_base(vk: int) -> str:
    if vk in _NOME_DA_BASE:
        return _NOME_DA_BASE[vk]
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x6F}"
    return chr(vk)


def nome_do_atalho(a: Atalho) -> str:
    return "+".join(list(a[0]) + [_nome_da_base(a[1])])


def normalizar_atalho(nome: str) -> Optional[str]:
    """Nome canônico ('ctrl + f11' -> 'CTRL+F11'); None se não vale."""
    a = analisar_atalho(nome)
    return nome_do_atalho(a) if a else None


def vk_de_nome(nome: str) -> Optional[int]:
    """Tecla principal do atalho (sem os modificadores) ou None."""
    a = analisar_atalho(nome)
    return a[1] if a else None


def atalho_pressionado(atalho: Atalho, est: Callable[[int], bool]) -> bool:
    """Tecla principal apertada e, se o atalho tem modificadores, exatamente eles. Sem modificadores
    a tecla vale sozinha (como sempre foi com F8/F9). `est(vk)` diz se a tecla está apertada."""
    mods, vk = atalho
    if not est(vk):
        return False
    if not mods:
        return True
    return all(est(_MODIFICADORES[m][0]) == (m in mods) for m in _MODIFICADORES)


def vks_dos_modificadores(mods: tuple[str, ...]) -> set[int]:
    return {v for m in mods for v in _MODIFICADORES[m][1]}


def _vks_capturaveis() -> list[int]:
    return (list(range(0x70, 0x88)) + list(range(0x30, 0x3A)) + list(range(0x41, 0x5B))
            + sorted(set(_BASES_NOMEADAS.values())))


def teclas_apertadas(estado: Callable[[int], bool]) -> set[int]:
    return {vk for vk in _vks_capturaveis() if estado(vk)}


def ler_atalho(estado: Callable[[int], bool], ignorar: Optional[set[int]] = None) -> Optional[str]:
    """Primeira tecla válida apertada agora (fora `ignorar`), com os modificadores que estão apertados.
    Ctrl, Alt ou Shift sozinhos não valem: espera a tecla principal."""
    for vk in _vks_capturaveis():
        if ignorar and vk in ignorar:
            continue
        if estado(vk):
            mods = tuple(m for m, (g, _) in _MODIFICADORES.items() if estado(g))
            return nome_do_atalho((mods, vk))
    return None
