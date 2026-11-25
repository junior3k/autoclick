# pyright: basic
"""Aviso sonoro suave ao concluir cada volta do loop.

O som é um sino curto de duas notas (sino brando, com entrada e saída suaves e volume baixo),
gerado aqui mesmo em memória: não precisa de arquivo nem de biblioteca. Toca pelo `winsound`
(Windows). O estado liga/desliga pode mudar A QUALQUER MOMENTO: a janela manda "som:1" / "som:0"
ao processo que está rodando (ver operacao.Controle).
"""
from __future__ import annotations

import io
import math
import os
import struct
import sys
import tempfile
import wave
from typing import Callable, Optional

TAXA = 22050


def _nota(freq: float, seg: float, volume: float) -> list[float]:
    n = int(TAXA * seg)
    saida: list[float] = []
    for i in range(n):
        t = i / TAXA
        # ataque 15 ms e queda exponencial: som de sininho, sem "clique" no começo nem no fim
        env = min(1.0, t / 0.015) * math.exp(-t * 7.5)
        v = math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(2 * math.pi * freq * 2 * t)
        saida.append(volume * env * v / 1.25)
    return saida


TIPOS = ("sino", "gota", "marimba", "discreto")
NOMES_TIPOS = {"sino": "Sino (duas notas)", "gota": "Gota", "marimba": "Marimba",
               "discreto": "Discreto (um toque curto)", "arquivo": "Meu arquivo .wav"}


def _nota_suave(freq: float, seg: float, volume: float, queda: float, harm: float = 0.25) -> list[float]:
    n = int(TAXA * seg)
    out: list[float] = []
    for i in range(n):
        t = i / TAXA
        env = min(1.0, t / 0.012) * math.exp(-t * queda)
        v = math.sin(2 * math.pi * freq * t) + harm * math.sin(2 * math.pi * freq * 2 * t)
        out.append(volume * env * v / (1 + harm))
    return out


def _amostras(tipo: str, volume: float) -> list[float]:
    if tipo == "gota":   # uma gota: nota que cai rápido de altura
        n = int(TAXA * 0.28)
        out: list[float] = []
        fase = 0.0
        for i in range(n):
            t = i / TAXA
            f = 1300 * math.exp(-t * 9) + 420
            fase += 2 * math.pi * f / TAXA
            out.append(volume * min(1.0, t / 0.008) * math.exp(-t * 11) * math.sin(fase))
        return out
    if tipo == "marimba":  # três notas curtas, subindo
        out = []
        for f in (523.25, 659.25, 783.99):
            out += _nota_suave(f, 0.17, volume, 14.0, 0.5)
        return out
    if tipo == "discreto":  # um toque curto e baixinho
        return _nota_suave(740.0, 0.16, volume * 0.8, 20.0, 0.1)
    # sino (padrão): dó# 5 e depois lá 5
    return (_nota(554.37, 0.20, volume) + [0.0] * int(TAXA * 0.04) + _nota(880.0, 0.32, volume)
            + [0.0] * int(TAXA * 0.02))


# Sons de cada tipo de ação (mesmo estilo/timbre escolhido, mas notas diferentes para dar para
# distinguir de ouvido): gravação = duas notas graves; reprodução = três notas (arpejo); contagem = tique.
EVENTOS = ("volta", "gravar_inicio", "gravar_fim", "repro_inicio", "repro_fim", "tique")
GRUPOS = ("volta", "gravacao", "reproducao", "contagem")
GRUPO_DO_EVENTO = {"volta": "volta", "gravar_inicio": "gravacao", "gravar_fim": "gravacao",
                   "repro_inicio": "reproducao", "repro_fim": "reproducao", "tique": "contagem"}
_NOTAS_EVENTO = {
    "gravar_inicio": (392.00, 587.33),            # sobe
    "gravar_fim": (587.33, 392.00),               # desce
    "repro_inicio": (523.25, 659.25, 783.99),     # arpejo subindo
    "repro_fim": (783.99, 659.25, 523.25),        # arpejo descendo
}
_TIMBRES = {"sino": (9.0, 0.25), "gota": (16.0, 0.05), "marimba": (14.0, 0.5), "discreto": (20.0, 0.1)}


def _amostras_evento(evento: str, tipo: str, volume: float) -> list[float]:
    if evento == "tique":
        tq = _nota_suave(1000.0, 0.05, volume * 0.6, 45.0, 0.0)
        fade = int(TAXA * 0.012)  # termina em silêncio (sem estalo)
        for k in range(fade):
            tq[-1 - k] *= k / fade
        return tq
    queda, harm = _TIMBRES.get(tipo, _TIMBRES["sino"])
    notas = _NOTAS_EVENTO[evento]
    dur = 0.16 if len(notas) == 2 else 0.11
    out: list[float] = []
    for f in notas:
        out += _nota_suave(f, dur, volume, queda, harm) + [0.0] * int(TAXA * 0.02)
    return out


def _para_wav(amostras: list[float]) -> bytes:
    bruto = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, a)) * 32767)) for a in amostras)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(bruto)
    return buf.getvalue()


def gerar_wav(volume: float = 0.22, tipo: str = "sino", evento: str = "volta") -> bytes:
    """WAV 16 bits mono. `volume` de 0 a 1 (o padrão do sino é baixo, 0,22)."""
    vol = max(0.0, min(1.0, volume))
    t = tipo if tipo in TIPOS else "sino"
    if evento != "volta" and evento in _NOTAS_EVENTO or evento == "tique":
        return _para_wav(_amostras_evento(evento, t, vol))
    amostras = _amostras(t, vol)
    bruto = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, a)) * 32767)) for a in amostras)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(bruto)
    return buf.getvalue()


def volume_do_controle(v: float) -> float:
    """Controle de 0 a 100 % -> volume da onda (100 % = 0,6; o padrão 37 % ≈ 0,22)."""
    return max(0.0, min(1.0, v / 100.0)) * 0.6


_arquivo: Optional[str] = None
_hash = 0


def _arquivo_do_sino(wav: bytes) -> str:
    """Grava o som numa pasta temporária (de novo só se mudou) e devolve o caminho."""
    global _arquivo, _hash
    h = hash(wav)
    if _arquivo is None or not os.path.isfile(_arquivo) or _hash != h:
        caminho = os.path.join(tempfile.gettempdir(), f"autoclick_sino_{os.getpid()}.wav")
        with open(caminho, "wb") as f:
            f.write(wav)
        _arquivo, _hash = caminho, h
    return _arquivo


def _saida_winsound(wav: bytes) -> None:
    """Toca sem travar a reprodução. ATENÇÃO: o winsound NÃO aceita SND_MEMORY junto com SND_ASYNC
    (levanta RuntimeError, e o som ficava mudo); por isso toca a partir de um arquivo."""
    import winsound  # só existe no Windows
    winsound.PlaySound(_arquivo_do_sino(wav), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)


class Som:
    def __init__(self, ativo: bool = False) -> None:
        self.grupos: dict[str, bool] = {g: False for g in GRUPOS}
        self.grupos["volta"] = ativo
        self.tocados = 0
        self.tocados_por_evento: dict[str, int] = {}
        self._wavs: dict[str, bytes] = {}
        self.tipo = "sino"
        self.volume = 37.0     # 0 a 100 %
        self.arquivo = ""      # .wav do usuário (tipo "arquivo")
        self.saida: Optional[Callable[[bytes], None]] = _saida_winsound if sys.platform == "win32" else None

    @property
    def ativo(self) -> bool:
        """Som de fim de volta ligado (o original)."""
        return self.grupos["volta"]

    @ativo.setter
    def ativo(self, v: bool) -> None:
        self.grupos["volta"] = v

    def definir(self, ativo: bool) -> None:
        self.grupos["volta"] = ativo

    def definir_grupo(self, grupo: str, ativo: bool) -> None:
        if grupo in self.grupos:
            self.grupos[grupo] = ativo

    def configurar(self, tipo: str = "sino", volume: float = 37.0, arquivo: str = "") -> None:
        self.tipo, self.volume, self.arquivo = tipo, volume, arquivo
        self._wavs = {}

    def _montar(self, evento: str = "volta") -> bytes:
        if self.tipo == "arquivo" and self.arquivo and evento != "tique":
            try:
                with open(self.arquivo, "rb") as f:
                    dados = f.read(5_000_000)
                if dados[:4] == b"RIFF":
                    return dados
            except OSError:
                pass  # arquivo sumiu: cai no sino
        return gerar_wav(volume_do_controle(self.volume), self.tipo, evento)

    def _tocar(self, evento: str, forcar: bool) -> bool:
        if not (self.grupos.get(GRUPO_DO_EVENTO.get(evento, "volta"), False) or forcar):
            return False
        try:
            wav = self._wavs.get(evento)
            if wav is None:
                wav = self._wavs[evento] = self._montar(evento)
            self.tocados += 1
            self.tocados_por_evento[evento] = self.tocados_por_evento.get(evento, 0) + 1
            if self.saida is not None:
                self.saida(wav)
            return True
        except Exception:
            return False

    def tocar(self, forcar: bool = False) -> bool:
        """Som de fim de volta: toca se estiver ligado (ou `forcar`). Nunca levanta erro."""
        return self._tocar("volta", forcar)

    def tocar_evento(self, evento: str, forcar: bool = False) -> bool:
        """Som de início/fim de gravação ou reprodução, ou tique da contagem (cada grupo liga/desliga
        sozinho). `forcar` toca mesmo desligado (botão "Ouvir")."""
        return self._tocar(evento, forcar)


som = Som(os.environ.get("AUTOCLICK_SOM", "0") == "1")
for _g, _v in (("gravacao", "AUTOCLICK_SOM_GRAVAR"), ("reproducao", "AUTOCLICK_SOM_REPRO"),
               ("contagem", "AUTOCLICK_SOM_TIQUE")):
    som.definir_grupo(_g, os.environ.get(_v, "0") == "1")
try:
    som.configurar(os.environ.get("AUTOCLICK_SOM_TIPO", "sino") or "sino",
                   float(os.environ.get("AUTOCLICK_SOM_VOLUME", "37") or 37),
                   os.environ.get("AUTOCLICK_SOM_ARQUIVO", ""))
except ValueError:
    pass
