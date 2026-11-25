"""Condições entre botões (requer / ignorar_se / etapa) e o fluxo do jogo em etapas."""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, cast

from .regras import Regra


class Visibilidade:
    """Lembra quais botões foram vistos há pouco (para 'requer' / 'ignorar_se')."""

    def __init__(self, validade: float = 1.5) -> None:
        self.validade = validade
        self._visto: dict[str, float] = {}

    def atualizar(self, rotulos: list[str], agora: Optional[float] = None) -> None:
        agora = time.time() if agora is None else agora
        for r in rotulos:
            self._visto[r] = agora

    def visivel(self, nome: str, agora: Optional[float] = None) -> bool:
        agora = time.time() if agora is None else agora
        return agora - self._visto.get(nome, -1e9) <= self.validade

    def agora_visiveis(self, agora: Optional[float] = None) -> set[str]:
        agora = time.time() if agora is None else agora
        return {n for n, t in self._visto.items() if agora - t <= self.validade}


@dataclass
class Etapa:
    nome: str
    quando: tuple[str, ...]  # basta UM destes estar à vista para a etapa começar
    timeout: float = 0.0  # 0 = sem limite
    ao_estourar: str = "avisar"  # avisar | parar | reiniciar


AO_ESTOURAR_VALIDOS = ("avisar", "parar", "reiniciar")


class Fluxo:
    """Máquina de estados simples: a etapa atual é a última cujo marcador apareceu."""

    def __init__(self, etapas: list[Etapa]) -> None:
        self.etapas = etapas
        self.atual: Optional[str] = None
        self.desde = time.time()
        self._avisou = False

    def nomes(self) -> list[str]:
        return [e.nome for e in self.etapas]

    def observar(self, visiveis: set[str], agora: Optional[float] = None) -> Optional[str]:
        """Atualiza a etapa. Devolve o nome se ela MUDOU agora."""
        agora = time.time() if agora is None else agora
        achada: Optional[str] = None
        for e in self.etapas:
            if any(q in visiveis for q in e.quando):
                achada = e.nome  # se vários, vale o último da lista (o mais avançado)
        if achada is not None and achada != self.atual:
            self.atual, self.desde, self._avisou = achada, agora, False
            return achada
        return None

    def estourou(self, agora: Optional[float] = None) -> Optional[tuple[Etapa, float]]:
        """(etapa, segundos) se a etapa atual passou do timeout (uma vez por etapa)."""
        agora = time.time() if agora is None else agora
        for e in self.etapas:
            if e.nome == self.atual and e.timeout and agora - self.desde > e.timeout:
                if self._avisou:
                    return None
                self._avisou = True
                return e, agora - self.desde
        return None

    def recomecar(self, agora: Optional[float] = None) -> None:
        self.atual = None
        self.desde = time.time() if agora is None else agora
        self._avisou = False


def parse_fluxo(bruto: Any, origem: str = "botoes.json") -> Optional[Fluxo]:
    """Converte o valor de "_fluxo" em um Fluxo (ou sai com mensagem clara)."""
    if bruto is None:
        return None
    if not isinstance(bruto, list) or not bruto:
        sys.exit(f'{origem}: "_fluxo" deve ser uma lista de etapas: '
                 '[{"etapa": "nome", "quando": ["botao"], "timeout": 300}, ...]')
    etapas: list[Etapa] = []
    for i, item in enumerate(cast(list[Any], bruto), 1):
        if not isinstance(item, dict):
            sys.exit(f'{origem}: a etapa #{i} de "_fluxo" deve ser um objeto.')
        d = cast(dict[str, Any], item)
        nome = d.get("etapa")
        quando: Any = d.get("quando")
        if not isinstance(nome, str) or not nome:
            sys.exit(f'{origem}: a etapa #{i} de "_fluxo" precisa de "etapa": "nome".')
        if isinstance(quando, str):
            quando = [quando]
        if not isinstance(quando, list) or not quando:
            sys.exit(f'{origem}: a etapa "{nome}" precisa de "quando": ["botao_visivel"].')
        ao = str(d.get("ao_estourar", "avisar")).lower()
        if ao not in AO_ESTOURAR_VALIDOS:
            sys.exit(f'{origem}: "ao_estourar" da etapa "{nome}" deve ser: '
                     f"{', '.join(AO_ESTOURAR_VALIDOS)}.")
        etapas.append(Etapa(nome, tuple(str(q) for q in cast(list[Any], quando)),
                            float(d.get("timeout", 0) or 0), ao))
    return Fluxo(etapas)


def carregar_fluxo(caminho: str) -> Optional[Fluxo]:
    p = Path(caminho)
    if not p.is_file():
        return None
    try:
        bruto: Any = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(bruto, dict):
        return None
    return parse_fluxo(cast(dict[str, Any], bruto).get("_fluxo"), caminho)


def permite(regra: Regra, vis: Visibilidade, fluxo: Optional[Fluxo],
            agora: Optional[float] = None) -> tuple[bool, str]:
    """A regra pode agir agora? Devolve (ok, motivo_se_não)."""
    for n in regra.requer:
        if not vis.visivel(n, agora):
            return False, f"requer '{n}' à vista"
    for n in regra.ignorar_se:
        if vis.visivel(n, agora):
            return False, f"'{n}' está à vista"
    if regra.etapa is not None:
        atual = fluxo.atual if fluxo is not None else None
        if atual != regra.etapa:
            return False, f"só na etapa '{regra.etapa}' (atual: {atual or 'nenhuma'})"
    return True, ""
