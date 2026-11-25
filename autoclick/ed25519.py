# pyright: basic
"""Ed25519 (RFC 8032) em Python puro: gerar chave, assinar e verificar.

Existe para o cliente conferir a assinatura das atualizações SEM depender de nenhuma
biblioteca externa. Só a verificação roda nos computadores dos usuários; a assinatura
(com a chave privada) roda apenas no seu PC, ao publicar uma versão.

Implementação de referência do RFC 8032 (seção 6). Não é de tempo constante, o que não
importa aqui: a chave privada nunca sai do seu computador. Testada contra os vetores do
RFC e, de forma cruzada, contra a biblioteca `cryptography`.
"""
from __future__ import annotations

import hashlib
import os
from typing import Optional

_P = 2**255 - 19
_Q = 2**252 + 27742317777372353535851937790883648493


def _sha512(dado: bytes) -> bytes:
    return hashlib.sha512(dado).digest()


def _inv(x: int) -> int:
    return pow(x, _P - 2, _P)


_D = -121665 * _inv(121666) % _P
_RAIZ_M1 = pow(2, (_P - 1) // 4, _P)

Ponto = tuple[int, int, int, int]


def _recuperar_x(y: int, sinal: int) -> Optional[int]:
    if y >= _P:
        return None
    x2 = (y * y - 1) * _inv(_D * y * y + 1)
    if x2 == 0:
        return None if sinal else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _RAIZ_M1 % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sinal:
        x = _P - x
    return x


_GY = 4 * _inv(5) % _P
_GX = _recuperar_x(_GY, 0) or 0
_G: Ponto = (_GX, _GY, 1, _GX * _GY % _P)
_ZERO: Ponto = (0, 1, 1, 0)


def _somar(a: Ponto, b: Ponto) -> Ponto:
    A = (a[1] - a[0]) * (b[1] - b[0]) % _P
    B = (a[1] + a[0]) * (b[1] + b[0]) % _P
    C = 2 * a[3] * b[3] * _D % _P
    D = 2 * a[2] * b[2] % _P
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _P, G * H % _P, F * G % _P, E * H % _P)


def _multiplicar(s: int, ponto: Ponto) -> Ponto:
    q = _ZERO
    while s > 0:
        if s & 1:
            q = _somar(q, ponto)
        ponto = _somar(ponto, ponto)
        s >>= 1
    return q


def _iguais(a: Ponto, b: Ponto) -> bool:
    if (a[0] * b[2] - b[0] * a[2]) % _P != 0:
        return False
    return (a[1] * b[2] - b[1] * a[2]) % _P == 0


def _comprimir(p: Ponto) -> bytes:
    zi = _inv(p[2])
    x, y = p[0] * zi % _P, p[1] * zi % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _descomprimir(s: bytes) -> Optional[Ponto]:
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sinal = y >> 255
    y &= (1 << 255) - 1
    x = _recuperar_x(y, sinal)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def _expandir(semente: bytes) -> tuple[int, bytes]:
    h = _sha512(semente)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def gerar_semente() -> bytes:
    """32 bytes aleatórios: esta É a chave privada. Guarde em segredo."""
    return os.urandom(32)


def chave_publica(semente: bytes) -> bytes:
    a, _ = _expandir(semente)
    return _comprimir(_multiplicar(a, _G))


def assinar(semente: bytes, mensagem: bytes) -> bytes:
    a, prefixo = _expandir(semente)
    publica = _comprimir(_multiplicar(a, _G))
    r = int.from_bytes(_sha512(prefixo + mensagem), "little") % _Q
    R = _comprimir(_multiplicar(r, _G))
    h = int.from_bytes(_sha512(R + publica + mensagem), "little") % _Q
    s = (r + h * a) % _Q
    return R + int.to_bytes(s, 32, "little")


def verificar(publica: bytes, mensagem: bytes, assinatura: bytes) -> bool:
    """True só se `assinatura` foi feita, com a chave privada correspondente, sobre `mensagem`."""
    if len(publica) != 32 or len(assinatura) != 64:
        return False
    A = _descomprimir(publica)
    R = _descomprimir(assinatura[:32])
    if A is None or R is None:
        return False
    s = int.from_bytes(assinatura[32:], "little")
    if s >= _Q:
        return False
    h = int.from_bytes(_sha512(assinatura[:32] + publica + mensagem), "little") % _Q
    return _iguais(_multiplicar(s, _G), _somar(R, _multiplicar(h, A)))


def verificar_hex(publica_hex: str, mensagem: bytes, assinatura_hex: str) -> bool:
    """Atalho: chave e assinatura em texto hexadecimal (como trafegam no manifesto)."""
    try:
        return verificar(bytes.fromhex(publica_hex.strip()), mensagem, bytes.fromhex(assinatura_hex.strip()))
    except ValueError:
        return False
