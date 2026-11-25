"""Monta os comandos (argumentos) que a janela executa. Funções puras, fáceis de testar."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .dados import Geral


def _base(g: Geral, janela: bool = True) -> list[str]:
    a = ["--pasta", g.pasta, "--config", g.config, "--monitor", str(g.monitor)]
    if janela and g.janela.strip():
        a += ["--janela", g.janela.strip()]
    return a


def gravar(g: Geral) -> list[str]:
    a = ["gravar", "--arquivo", g.gravacao, "--atraso", str(g.atraso),
         "--confianca", f"{g.confianca:g}", *_base(g)]
    if g.ancora.strip():
        a += ["--ancora", g.ancora.strip()]
    if g.gerar_regras:
        a.append("--gerar-regras")
        if g.sobrescrever:
            a.append("--sobrescrever")
    if not g.teclado:
        a.append("--sem-teclado")
    if g.duracao > 0:
        a += ["--duracao", f"{g.duracao:g}"]
    return a


def reproduzir(g: Geral) -> list[str]:
    a = ["reproduzir", "--arquivo", g.gravacao, "--atraso", str(g.atraso),
         "--velocidade", f"{g.velocidade:g}", "--pausa-loop", f"{g.pausa_loop:g}",
         "--confianca", f"{g.confianca:g}", "--auto-max", f"{g.auto_max:g}", *_base(g)]
    if g.repeticao == "loop":
        a.append("--loop")
    elif g.repeticao == "n":
        a += ["--loop", str(max(1, g.voltas))]
    if g.tela_parada > 0:
        a += ["--tela-parada", f"{g.tela_parada:g}", "--ao-travar", g.ao_travar]
    if not g.auto_detect:
        a.append("--sem-auto-detect")
    if not g.checar_janela:
        a.append("--sem-checar-janela")
    if not g.teclado:
        a.append("--sem-teclado")
    return a


def automatico(g: Geral, preview: bool = False) -> list[str]:
    a = [g.modo_auto, "--confianca", f"{g.confianca:g}", "--intervalo", f"{g.intervalo:g}",
         "--cooldown", f"{g.cooldown:g}", "--escala", g.escala.strip() or "auto",
         "--janela-max", f"{g.janela_max:g}", *_base(g)]
    if g.variacao > 0:
        a += ["--variacao", f"{g.variacao:g}"]
    if g.painel > 0:
        a += ["--painel", f"{g.painel:g}"]
    if g.inatividade > 0:
        a += ["--inatividade", f"{g.inatividade:g}", "--ao-travar", g.ao_travar]
    if g.tela_parada > 0:
        a += ["--tela-parada", f"{g.tela_parada:g}"] + ([] if g.inatividade > 0 else ["--ao-travar", g.ao_travar])
    if g.max_cliques > 0:
        a += ["--max-cliques", str(g.max_cliques)]
    if g.duracao_auto > 0:
        a += ["--duracao", f"{g.duracao_auto:g}"]
    if g.log.strip():
        a += ["--log", g.log.strip()]
    if g.relatorio.strip() and not preview:
        a += ["--relatorio", g.relatorio.strip()]
    if g.modo_auto in ("texto", "auto") and g.palavras.split():
        a += ["--palavras", *g.palavras.split()]
    if preview:
        a.append("--preview")
    return a


def diagnostico(g: Geral) -> list[str]:
    return ["diagnostico", *_base(g)]


def rotina(g: Geral, arquivo: str) -> list[str]:
    """Roda a rotina (vários scripts): mesmas opções da reprodução, outro modo e arquivo."""
    a = reproduzir(g)
    a[0] = "rotina"
    a[a.index("--arquivo") + 1] = arquivo
    for flag in ("--loop",):          # voltas e repetição vêm da própria rotina
        while flag in a:
            i = a.index(flag)
            del a[i:i + (2 if i + 1 < len(a) and a[i + 1].isdigit() else 1)]
    return a


def detectar_jogo(g: Geral, saida: str = "jogo_detectado.txt") -> list[str]:
    return ["detectar-jogo", "--confianca", f"{g.confianca:g}", "--saida", saida,
            "--monitor", str(g.monitor), *(["--janela", g.janela.strip()] if g.janela.strip() else [])]


def validar(g: Geral) -> list[str]:
    return ["validar", *_base(g)]


def visualizar(g: Geral, saida: str = "mapa_regras.png") -> list[str]:
    return ["visualizar", "--confianca", f"{g.confianca:g}", "--saida", saida, *_base(g)]


def recortar(g: Geral, nome: str) -> list[str]:
    return ["recortar", nome, "--atraso", str(g.atraso), *_base(g)]


def calibrar(g: Geral, nome: str) -> list[str]:
    return ["calibrar", nome, "--confianca", f"{g.confianca:g}", "--atraso", "1", *_base(g)]


def definir_destino(g: Geral, nome: str, ancora: Optional[str] = None) -> list[str]:
    a = ["definir-destino", nome, "--confianca", f"{g.confianca:g}", *_base(g)]
    if ancora:
        a += ["--ancora", ancora]
    return a


def relatorio_csv(csv: str) -> list[str]:
    return ["relatorio", csv]


def perfil_de(g: Geral, modo: str) -> dict[str, object]:
    """Perfil compatível com `--perfil` (mesmas opções do terminal)."""
    p: dict[str, object] = {"modo": modo, "pasta": g.pasta, "config": g.config,
                            "monitor": g.monitor, "confianca": g.confianca}
    if g.janela.strip():
        p["janela"] = g.janela.strip()
    if modo in ("reproduzir", "gravar"):
        p["arquivo"] = g.gravacao
    if modo in ("imagem", "texto", "auto"):
        p.update({"intervalo": g.intervalo, "cooldown": g.cooldown, "variacao": g.variacao})
        if g.log.strip():
            p["log"] = g.log.strip()
        if g.relatorio.strip():
            p["relatorio"] = g.relatorio.strip()
    return p


def salvar_perfil(g: Geral, nome: str, modo: str, pasta: str = "perfis") -> Path:
    Path(pasta).mkdir(parents=True, exist_ok=True)
    destino = Path(pasta) / f"{nome}.json"
    destino.write_text(json.dumps(perfil_de(g, modo), ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return destino


def para_texto(argv: list[str]) -> str:
    """Como ficaria no terminal (para mostrar no log e para o usuário aprender)."""
    def q(x: str) -> str:
        return f'"{x}"' if (" " in x or not x) else x
    return "uv run autoclick " + " ".join(q(x) for x in argv)
