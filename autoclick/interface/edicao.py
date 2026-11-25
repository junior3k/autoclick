# pyright: basic
"""Edição de gravações (lógica pura, sem Tk): apagar, mexer em tempos, inserir marcadores.

Uma gravação é {"eventos": [{"t": segundos, "tipo": "clique"|"arrasto"|"tecla"|"aguardar", ...}]}.
Todas as funções devolvem uma lista NOVA (não alteram a recebida), o que torna desfazer/refazer
trivial: a `Historia` guarda cópias.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Optional

Evento = dict[str, Any]

AO_ESTOURAR = ("avisar", "parar", "pular")


def descrever(ev: Evento) -> tuple[str, str]:
    """(tipo legível, detalhes) de um evento, para a lista do editor."""
    tipo = str(ev.get("tipo", "?"))
    botao = f" [{ev['botao']}]" if ev.get("botao") else ""
    if tipo == "clique":
        lado = "direito" if ev.get("mouse") == "direito" else "esquerdo"
        return "Clique", f"{lado} em ({ev.get('x', '?')}, {ev.get('y', '?')}){botao}"
    if tipo == "arrasto":
        return "Arrasto", (f"({ev.get('x', '?')}, {ev.get('y', '?')}) até "
                           f"({ev.get('x2', '?')}, {ev.get('y2', '?')}){botao}")
    if tipo == "tecla":
        return "Tecla", f"{ev.get('tecla', ev.get('vk', '?'))} " + ("↓" if ev.get("estado") == "baixo" else "↑")
    if tipo == "aguardar":
        verbo = "sumir" if str(ev.get("ate", "aparecer")) == "sumir" else "aparecer"
        return "Marcador", (f"esperar [{ev.get('botao', '?')}] {verbo} (até {float(ev.get('timeout', 30)):g}s; "
                            f"se estourar: {ev.get('ao_estourar', 'avisar')})")
    return tipo.capitalize(), json.dumps({k: v for k, v in ev.items() if k not in ("t", "tipo")},
                                         ensure_ascii=False)


def duracao(eventos: list[Evento]) -> float:
    return max((float(e.get("t", 0)) for e in eventos), default=0.0)


def _ordenar(eventos: list[Evento]) -> list[Evento]:
    return sorted(eventos, key=lambda e: float(e.get("t", 0)))  # estável: empates mantêm a ordem


def apagar(eventos: list[Evento], indices: list[int]) -> list[Evento]:
    fora = set(indices)
    return [copy.deepcopy(e) for i, e in enumerate(eventos) if i not in fora]


def deslocar(eventos: list[Evento], indice: int, delta: float) -> tuple[list[Evento], float]:
    """Soma `delta` segundos ao tempo do evento `indice` e de todos os seguintes.

    delta > 0 insere uma espera antes do evento; delta < 0 encurta, sem passar do evento
    anterior. Devolve (nova lista, delta realmente aplicado).
    """
    novos = copy.deepcopy(eventos)
    if not (0 <= indice < len(novos)):
        return novos, 0.0
    anterior = float(novos[indice - 1]["t"]) if indice > 0 else 0.0
    minimo = anterior - float(novos[indice]["t"])
    aplicado = max(delta, minimo)
    for e in novos[indice:]:
        e["t"] = round(float(e["t"]) + aplicado, 4)
    return novos, aplicado


def definir_tempo(eventos: list[Evento], indice: int, novo_t: float) -> list[Evento]:
    """Muda o instante de UM evento (a lista é reordenada se ele ultrapassar vizinhos)."""
    novos = copy.deepcopy(eventos)
    if 0 <= indice < len(novos):
        novos[indice]["t"] = round(max(0.0, novo_t), 4)
    return _ordenar(novos)


def inserir_marcador(eventos: list[Evento], indice: int, botao: str, timeout: float = 30.0,
                     ate: str = "aparecer", ao_estourar: str = "avisar") -> list[Evento]:
    """Insere, ANTES do evento `indice`, um marcador "espere o botão aparecer/sumir"."""
    if ate not in ("aparecer", "sumir"):
        raise ValueError("'ate' deve ser aparecer ou sumir")
    if ao_estourar not in AO_ESTOURAR:
        raise ValueError("ao_estourar deve ser " + ", ".join(AO_ESTOURAR))
    novos = copy.deepcopy(eventos)
    if not novos:
        t = 0.0
    elif indice >= len(novos):
        t = float(novos[-1]["t"])
    else:
        t = float(novos[max(0, indice)]["t"])
    marcador: Evento = {"t": t, "tipo": "aguardar", "botao": botao, "timeout": float(timeout),
                        "ate": ate, "ao_estourar": ao_estourar}
    pos = min(max(indice, 0), len(novos))
    novos.insert(pos, marcador)
    return novos


def cortar_antes(eventos: list[Evento], indice: int) -> list[Evento]:
    """Descarta tudo antes do evento `indice`; o tempo recomeça em zero."""
    resto = copy.deepcopy(eventos[indice:])
    if not resto:
        return []
    base = float(resto[0]["t"])
    for e in resto:
        e["t"] = round(float(e["t"]) - base, 4)
    return resto


def cortar_depois(eventos: list[Evento], indice: int) -> list[Evento]:
    """Mantém só até o evento `indice` (inclusive)."""
    return copy.deepcopy(eventos[: indice + 1])


def duplicar(eventos: list[Evento], indices: list[int]) -> list[Evento]:
    """Repete os eventos escolhidos logo depois do último deles (com o mesmo ritmo)."""
    if not indices:
        return copy.deepcopy(eventos)
    ordem = sorted(indices)
    sel = [copy.deepcopy(eventos[i]) for i in ordem]
    base = float(sel[0]["t"])
    fim = float(eventos[ordem[-1]]["t"])
    folga = 0.3
    novos = copy.deepcopy(eventos)
    depois = [e for i, e in enumerate(novos) if i > ordem[-1]]
    gasto = (float(sel[-1]["t"]) - base) + folga
    for e in depois:
        e["t"] = round(float(e["t"]) + gasto, 4)
    copias = []
    for e in sel:
        e["t"] = round(fim + folga + (float(e["t"]) - base), 4)
        copias.append(e)
    return _ordenar(novos[: ordem[-1] + 1] + copias + depois)


def problemas(eventos: list[Evento]) -> list[str]:
    """Avisos sobre a gravação editada (tecla apertada sem soltar, marcador sem botão...)."""
    out: list[str] = []
    presas: dict[Any, int] = {}
    for i, e in enumerate(eventos, 1):
        if e.get("tipo") == "tecla":
            presas[e.get("vk")] = presas.get(e.get("vk"), 0) + (1 if e.get("estado") == "baixo" else -1)
        if e.get("tipo") == "aguardar" and not e.get("botao"):
            out.append(f"evento {i}: o marcador não tem botão")
    for vk, n in presas.items():
        if n > 0:
            out.append(f"a tecla {vk} é apertada e nunca solta")
        elif n < 0:
            out.append(f"a tecla {vk} é solta sem ter sido apertada")
    return out


class Historia:
    """Desfazer/refazer por cópias do estado."""

    def __init__(self, inicial: list[Evento], limite: int = 100) -> None:
        self.atual = copy.deepcopy(inicial)
        self._passado: list[list[Evento]] = []
        self._futuro: list[list[Evento]] = []
        self.limite = limite

    def mudar(self, novo: list[Evento]) -> None:
        self._passado.append(self.atual)
        del self._passado[: -self.limite]
        self.atual = copy.deepcopy(novo)
        self._futuro.clear()

    @property
    def pode_desfazer(self) -> bool:
        return bool(self._passado)

    @property
    def pode_refazer(self) -> bool:
        return bool(self._futuro)

    def desfazer(self) -> bool:
        if not self._passado:
            return False
        self._futuro.append(self.atual)
        self.atual = self._passado.pop()
        return True

    def refazer(self) -> bool:
        if not self._futuro:
            return False
        self._passado.append(self.atual)
        self.atual = self._futuro.pop()
        return True


def carregar(caminho: str) -> tuple[dict[str, Any], list[Evento]]:
    bruto = json.loads(Path(caminho).read_text(encoding="utf-8"))
    if not isinstance(bruto, dict) or not isinstance(bruto.get("eventos"), list):
        raise ValueError("arquivo sem lista de eventos (não é uma gravação)")
    return bruto, [e for e in bruto["eventos"] if isinstance(e, dict)]


def salvar(caminho: str, dados: dict[str, Any], eventos: list[Evento],
           copia_segurança: bool = True) -> Optional[str]:
    """Grava a gravação editada. Antes, guarda o original em <arquivo>.bak (uma vez por sessão
    de edição). Devolve o caminho do .bak, se criado."""
    p = Path(caminho)
    bak: Optional[str] = None
    if copia_segurança and p.is_file():
        bak = str(p) + ".bak"
        p.replace(bak) if not Path(bak).exists() else None
        if not Path(bak).exists():  # pragma: no cover
            bak = None
    novo = dict(dados)
    novo["eventos"] = _ordenar(eventos)
    novo["editado"] = True
    p.write_text(json.dumps(novo, ensure_ascii=False, indent=2), encoding="utf-8")
    return bak
