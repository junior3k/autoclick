"""Operação em andamento: pausa por tecla, telemetria, saúde da detecção, variação aleatória."""
from __future__ import annotations

import csv
import json
import os
import random
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from . import windows as m_windows


# --------------------------------------------------------------------------- #
# Variação aleatória de tempos (item 10)
# --------------------------------------------------------------------------- #
class Variacao:
    """Espalha tempos de espera: valor * (1 ± fração). 0 = tempos exatos."""

    def __init__(self, fracao: float = 0.0, semente: Optional[int] = None) -> None:
        self.fracao = max(0.0, min(fracao, 0.9))
        self._rnd = random.Random(semente)

    def __call__(self, valor: float) -> float:
        if self.fracao <= 0 or valor <= 0:
            return valor
        return valor * (1.0 + self._rnd.uniform(-self.fracao, self.fracao))


variacao = Variacao(0.0)


def configurar_variacao(fracao: float, semente: Optional[int] = None) -> None:
    global variacao
    variacao = Variacao(fracao, semente)


def v(valor: float) -> float:
    """Atalho: aplica a variação global a um tempo."""
    return variacao(valor)


# --------------------------------------------------------------------------- #
# Pausa / continuar (item 8) — SÓ pela tecla; mexer no mouse nunca pausa
# --------------------------------------------------------------------------- #
class Pausa:
    def __init__(self) -> None:
        self.pausado = False
        self.total = 0.0  # segundos acumulados em pausa
        self._desde = 0.0
        self._trava = threading.Lock()
        self._parar = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.ao_mudar: Optional[Callable[[bool], None]] = None

    def desde(self) -> float:
        """Instante em que a pausa atual começou (só vale se `pausado`)."""
        return self._desde

    def alternar(self) -> bool:
        with self._trava:
            self.pausado = not self.pausado
            if self.pausado:
                self._desde = time.time()
            else:
                self.total += time.time() - self._desde
            estado = self.pausado
        print(f"[{time.strftime('%H:%M:%S')}] "
              + (f"⏸ PAUSADO (aperte {m_windows.NOME_PAUSA} para continuar)" if estado else "▶ continuando"))
        if self.ao_mudar is not None:
            self.ao_mudar(estado)
        return estado

    def definir(self, pausado: bool) -> None:
        if pausado != self.pausado:
            self.alternar()

    def esperar(self, checar_parada: bool = True) -> Optional[float]:
        """Bloqueia enquanto pausado. Devolve os segundos esperados (0 se não estava
        pausado) ou None se o usuário abortou (F9 / canto) durante a pausa."""
        if not self.pausado:
            return 0.0
        ini = time.time()
        while self.pausado:
            if checar_parada and sys.platform == "win32" and m_windows.abortar():
                return None
            time.sleep(0.05)
        return time.time() - ini

    def iniciar(self, vk: Optional[int] = None, intervalo: float = 0.03) -> None:
        """Liga a vigia da tecla F8 (só Windows)."""
        if sys.platform != "win32" or self._thread is not None:
            return
        lido = (lambda: m_windows.tecla_pressionada(vk)) if vk is not None else (
            lambda: m_windows.pressionada("pausa"))

        def laco() -> None:
            antes = False
            while not self._parar.is_set():
                agora = lido()
                if agora and not antes:
                    self.alternar()
                antes = agora
                self._parar.wait(intervalo)

        self._thread = threading.Thread(target=laco, daemon=True)
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        self._thread = None
        self._parar = threading.Event()


pausa = Pausa()


# --------------------------------------------------------------------------- #
# Telemetria e relatório (itens 12 e 13)
# --------------------------------------------------------------------------- #
class Telemetria:
    """Contadores da sessão (thread-safe) para o painel e o relatório final."""

    def __init__(self) -> None:
        self.inicio = time.time()
        self._trava = threading.Lock()
        self.cliques: dict[str, int] = {}
        self.arrastos: dict[str, int] = {}
        self.falhas: dict[str, int] = {}
        self.partidas = 1
        self.avisos: list[str] = []
        self.ultimo: str = "-"
        self.ultimo_evento = time.time()
        self.escala: Optional[float] = None
        self.score_medio: Optional[float] = None
        self.gravacao_t0: Optional[float] = None  # só conferência na tela; não vai para o arquivo
        self.gravacao_linhas: list[str] = []
        self.gravacao_total = 0
        self.progresso_fn: Optional[Callable[[], dict[str, object]]] = None
        self.progresso_rotulo = ""  # ex.: "volta 2 · coletar" (modo rotina)

    def definir_progresso(self, fn: Optional[Callable[[], dict[str, object]]]) -> None:
        with self._trava:
            self.progresso_fn = fn

    def progresso_info(self) -> Optional[dict[str, object]]:
        with self._trava:
            fn, rot = self.progresso_fn, self.progresso_rotulo
        if fn is None:
            return None
        try:
            d = dict(fn())
        except Exception:
            return None
        d["rotulo"] = rot
        return d

    def gravacao_iniciar(self, t0: float) -> None:
        """Marca o começo REAL da gravação (depois da contagem regressiva)."""
        with self._trava:
            self.gravacao_t0 = t0
            self.gravacao_linhas = []
            self.gravacao_total = 0

    def gravacao_evento(self, linha: str) -> None:
        with self._trava:
            self.gravacao_total += 1
            self.gravacao_linhas.append(linha)
            del self.gravacao_linhas[:-40]

    def gravacao_info(self) -> Optional[dict[str, object]]:
        with self._trava:
            if self.gravacao_t0 is None:
                return None
            return {"t0": self.gravacao_t0, "total": self.gravacao_total,
                    "recentes": list(self.gravacao_linhas)}

    def clique(self, botao: str, arrasto: bool = False) -> None:
        with self._trava:
            d = self.arrastos if arrasto else self.cliques
            d[botao] = d.get(botao, 0) + 1
            self.ultimo = f"{'arrasto' if arrasto else 'clique'} em {botao}"
            self.ultimo_evento = time.time()

    def falha(self, botao: str) -> None:
        with self._trava:
            self.falhas[botao] = self.falhas.get(botao, 0) + 1

    def aviso(self, msg: str) -> None:
        with self._trava:
            self.avisos.append(f"{time.strftime('%H:%M:%S')} {msg}")
            del self.avisos[:-50]

    def nova_partida(self) -> None:
        with self._trava:
            self.partidas += 1

    @property
    def total_cliques(self) -> int:
        return sum(self.cliques.values()) + sum(self.arrastos.values())

    def duracao(self) -> float:
        return time.time() - self.inicio - pausa.total

    def linha(self) -> str:
        d = int(self.duracao())
        h, r = divmod(d, 3600)
        m, s = divmod(r, 60)
        esc = f" | escala {self.escala:.2f}" if self.escala else ""
        est = " | ⏸ PAUSADO" if pausa.pausado else ""
        return (f"[painel] {h:02d}:{m:02d}:{s:02d} | partida #{self.partidas} | "
                f"{self.total_cliques} ações | último: {self.ultimo}{esc}{est}")

    def resumo(self) -> dict[str, object]:
        with self._trava:
            return {
                "inicio": datetime.fromtimestamp(self.inicio).isoformat(timespec="seconds"),
                "duracao_seg": round(self.duracao(), 1),
                "pausado_seg": round(pausa.total, 1),
                "partidas": self.partidas,
                "total_acoes": self.total_cliques,
                "cliques": dict(sorted(self.cliques.items())),
                "arrastos": dict(sorted(self.arrastos.items())),
                "falhas": dict(sorted(self.falhas.items())),
                "avisos": list(self.avisos),
            }

    def texto(self) -> str:
        r = self.resumo()
        linhas = [
            "Resumo da sessão",
            f"  duração: {r['duracao_seg']}s (pausado: {r['pausado_seg']}s)",
            f"  partidas: {r['partidas']} | ações: {r['total_acoes']}",
        ]
        for titulo, chave in (("cliques", "cliques"), ("arrastos", "arrastos"), ("falhas", "falhas")):
            d = {"cliques": self.cliques, "arrastos": self.arrastos, "falhas": self.falhas}[chave]
            if d:
                linhas.append(f"  {titulo}: " + ", ".join(f"{k}={n}" for k, n in sorted(d.items())))
        if self.avisos:
            linhas.append(f"  avisos ({len(self.avisos)}):")
            linhas += [f"    - {a}" for a in self.avisos[-10:]]
        return "\n".join(linhas)

    def salvar(self, caminho: str) -> None:
        p = Path(caminho)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix.lower() == ".json":
            p.write_text(json.dumps(self.resumo(), ensure_ascii=False, indent=2),
                         encoding="utf-8")
        else:
            p.write_text("# Relatório do autoclick\n\n```\n" + self.texto() + "\n```\n",
                         encoding="utf-8")
        print(f"Relatório salvo em {p}")


_tel_atual = Telemetria()


def tel() -> Telemetria:
    """Telemetria da sessão em andamento (compartilhada por varredura, reprodução e GUI)."""
    return _tel_atual


def nova_telemetria() -> Telemetria:
    global _tel_atual
    _tel_atual = Telemetria()
    return _tel_atual


# --------------------------------------------------------------------------- #
# Controle externo (a GUI conversa com o processo por dois arquivos)
# --------------------------------------------------------------------------- #
class Controle:
    """Lê comandos (pausar | continuar | alternar | parar) de um arquivo e publica o status.

    A GUI roda cada função num processo separado; este objeto, dentro do processo,
    obedece ao botão Pausar/Parar da janela e devolve contadores em tempo real.
    """

    def __init__(self, arq_cmd: Optional[str], arq_status: Optional[str], modo: str) -> None:
        self.arq_cmd, self.arq_status, self.modo = arq_cmd, arq_status, modo
        self._parar = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def executar(self, comando: str) -> None:
        original = comando.strip()
        c = original.lower()
        if c == "pausar":
            pausa.definir(True)
        elif c == "continuar":
            pausa.definir(False)
        elif c == "alternar":
            pausa.alternar()
        elif c == "parar":
            m_windows.PARADA.set()
        elif c.startswith("som:"):
            from .som import som
            v = c[4:]
            som.definir((not som.ativo) if v == "alternar" else v in ("1", "on", "ligar"))
        elif c.startswith("somgrupo:"):
            from .som import som
            g, _, v = c[9:].partition("=")  # ex.: somgrupo:gravacao=1
            som.definir_grupo(g, v in ("1", "on", "ligar"))
        elif c.startswith("somcfg:"):
            from urllib.parse import unquote
            from .som import som
            partes = original[7:].split("|")  # caminho do .wav: maiúsculas contam
            try:
                som.configurar(unquote(partes[0]) or "sino", float(partes[1]),
                               unquote(partes[2]) if len(partes) > 2 else "")
            except (ValueError, IndexError):
                pass

    def _ler_comandos(self) -> None:
        if not self.arq_cmd or not os.path.exists(self.arq_cmd):
            return
        try:
            with open(self.arq_cmd, encoding="utf-8") as f:
                linhas = f.read().split()
            os.remove(self.arq_cmd)
        except OSError:
            return
        for c in linhas:
            self.executar(c)

    def publicar(self) -> None:
        if not self.arq_status:
            return
        t = tel()
        dados = {"modo": self.modo, "pid": os.getpid(), "pausado": pausa.pausado,
                 "agora": time.time(), "linha": t.linha(), "ultimo": t.ultimo,
                 "resumo": t.resumo(), "gravando": t.gravacao_info(), "progresso": t.progresso_info()}
        tmp = self.arq_status + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False)
            os.replace(tmp, self.arq_status)
        except OSError:
            pass

    def iniciar(self) -> None:
        if self._thread is not None:
            return

        def laco() -> None:
            n = 0
            while not self._parar.is_set():
                self._ler_comandos()
                if n % 5 == 0:
                    self.publicar()
                n += 1
                self._parar.wait(0.2)

        self._thread = threading.Thread(target=laco, daemon=True)
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        self.publicar()


def controle_do_ambiente(modo: str) -> Optional[Controle]:
    """Liga o controle se a GUI (ou qualquer script) definiu AUTOCLICK_CONTROLE/STATUS."""
    cmd, st = os.environ.get("AUTOCLICK_CONTROLE"), os.environ.get("AUTOCLICK_STATUS")
    if not cmd and not st:
        return None
    c = Controle(cmd, st, modo)
    c.iniciar()
    return c


def resumir_csv(caminho: str) -> str:
    """Modo 'relatorio': resume um CSV gerado por --log."""
    p = Path(caminho)
    if not p.is_file():
        sys.exit(f"Arquivo '{caminho}' não encontrado.")
    contagem: dict[tuple[str, str], int] = {}
    primeiro = ultimo = ""
    partidas = 0
    total = 0
    with p.open(newline="", encoding="utf-8") as f:
        for linha in csv.DictReader(f):
            tipo = linha.get("tipo", "")
            botao = linha.get("botao", "")
            horario = linha.get("horario", "")
            primeiro = primeiro or horario
            ultimo = horario or ultimo
            total += 1
            if tipo == "inicio_partida":
                partidas += 1
            elif tipo not in ("tecla",):
                contagem[(tipo, botao)] = contagem.get((tipo, botao), 0) + 1
    out = [f"Relatório de {caminho}", f"  {total} registro(s) | de {primeiro} até {ultimo}",
           f"  partidas iniciadas: {partidas}"]
    for (tipo, botao), n in sorted(contagem.items(), key=lambda kv: -kv[1]):
        out.append(f"  {tipo:<14} {botao or '-':<24} {n}")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Saúde da detecção (item 5)
# --------------------------------------------------------------------------- #
class Saude:
    """Avisa quando a detecção parece estar piorando."""

    def __init__(self, sem_deteccao: float = 60.0, queda_score: float = 0.07,
                 salto_escala: float = 0.15, avisar: Optional[Callable[[str], None]] = None) -> None:
        self.sem_deteccao = sem_deteccao
        self.queda_score = queda_score
        self.salto_escala = salto_escala
        self._avisar: Callable[[str], None] = avisar if avisar is not None else self._imprimir
        self._scores: dict[str, deque[float]] = {}
        self._ref: dict[str, float] = {}
        self._ultima_deteccao = time.time()
        self._escala_ref: Optional[float] = None
        self._ult_aviso: dict[str, float] = {}

    @staticmethod
    def _imprimir(msg: str) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] ⚠ {msg}")

    def _emitir(self, chave: str, msg: str, cada: float = 120.0) -> None:
        agora = time.time()
        if agora - self._ult_aviso.get(chave, 0.0) >= cada:
            self._ult_aviso[chave] = agora
            self._avisar(msg)

    def observar(self, scores: dict[str, float], escala: Optional[float],
                 agora: Optional[float] = None) -> None:
        agora = time.time() if agora is None else agora
        if scores:
            self._ultima_deteccao = agora
        elif agora - self._ultima_deteccao > self.sem_deteccao:
            self._emitir("nada", f"nenhum botão reconhecido há {int(agora - self._ultima_deteccao)}s "
                         "(jogo em outra tela? janela errada? PNGs desatualizados?)")
        for nome, sc in scores.items():
            q = self._scores.setdefault(nome, deque(maxlen=20))
            q.append(sc)
            ref = self._ref.get(nome)
            if ref is None:
                if len(q) >= 5:
                    self._ref[nome] = sum(q) / len(q)
            elif len(q) >= 5 and ref - sum(q) / len(q) > self.queda_score:
                self._emitir(f"score:{nome}", f"a certeza de '{nome}' caiu de {ref:.2f} para "
                             f"{sum(q) / len(q):.2f}: o visual do botão pode ter mudado "
                             "(refaça o PNG com o modo 'recortar')")
        if escala is not None:
            if self._escala_ref is None:
                self._escala_ref = escala
            elif abs(escala - self._escala_ref) / self._escala_ref > self.salto_escala:
                self._emitir("escala", f"a escala mudou de {self._escala_ref:.2f} para {escala:.2f} "
                             "(janela redimensionada? zoom do jogo?)", 30.0)
                self._escala_ref = escala


# --------------------------------------------------------------------------- #
# Recuperação de falhas (item 9)
# --------------------------------------------------------------------------- #
class Vigilante:
    """Decide quando desistir: janela sumida por muito tempo, erros seguidos ou
    inatividade (nenhuma ação por N segundos)."""

    def __init__(self, janela_max: float = 120.0, erros_max: int = 5,
                 inatividade: float = 0.0) -> None:
        self.janela_max, self.erros_max, self.inatividade = janela_max, erros_max, inatividade
        self._janela_sumiu: Optional[float] = None
        self._erros = 0
        self._ultima_acao = time.time()

    def janela(self, presente: bool, agora: Optional[float] = None) -> Optional[str]:
        agora = time.time() if agora is None else agora
        if presente:
            self._janela_sumiu = None
            return None
        if self._janela_sumiu is None:
            self._janela_sumiu = agora
        if self.janela_max and agora - self._janela_sumiu > self.janela_max:
            return f"a janela do jogo sumiu há mais de {self.janela_max:g}s (jogo fechado?)"
        return None

    def erro(self, msg: str) -> Optional[str]:
        self._erros += 1
        if self._erros >= self.erros_max:
            return f"{self._erros} erros seguidos ao capturar/detectar (último: {msg})"
        return None

    def ok(self) -> None:
        self._erros = 0

    def acao(self, agora: Optional[float] = None) -> None:
        self._ultima_acao = time.time() if agora is None else agora

    def parado(self, agora: Optional[float] = None) -> Optional[str]:
        agora = time.time() if agora is None else agora
        if self.inatividade and agora - self._ultima_acao > self.inatividade:
            return f"nenhuma ação há mais de {self.inatividade:g}s (jogo travado?)"
        return None
