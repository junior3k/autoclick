# pyright: basic
"""Liga a Rotina (autoclick/rotina.py) ao mouse de verdade: modo `rotina` do terminal."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

from . import reproducao as m_reproducao
from . import robustez as m_robustez
from . import rotina as m_rotina
from . import windows as m_windows
from .operacao import tel
from .som import som as m_som


def _titulo_do_script(caminho: str) -> Optional[str]:
    try:
        d: Any = json.loads(Path(caminho).read_text(encoding="utf-8"))
        t = (d.get("janela") or {}).get("titulo")
        # gravações antigas podem ter guardado a janela do próprio Autoclick: isso nunca é o jogo
        return str(t) if t and not m_windows.janela_propria(str(t)) else None
    except (OSError, ValueError, AttributeError):
        return None


def executar_arquivo(arquivo: str, velocidade: float, atraso: float, janela: Optional[str],
                     checar_janela: bool, espera_janela: float, teclas: bool, config: str, pasta: str,
                     confianca: float, monitor: int, auto_detect: bool, auto_max: float,
                     registro: Any = None) -> str:
    if sys.platform != "win32":
        sys.exit("O modo 'rotina' só funciona no Windows.")
    rot = m_rotina.ler(arquivo)
    scripts = m_rotina.listar_scripts(arquivo)
    problemas = m_rotina.validar(rot, set(scripts))
    if problemas:
        sys.exit("A rotina não pode rodar:\n  - " + "\n  - ".join(problemas))
    usados = [str(i.get("script")) for i in rot["itens"] if i.get("tipo") == "script"]
    usados += [str(iv.get("script")) for iv in rot["intervalos"] if iv.get("script")]
    por_script = {n: _titulo_do_script(scripts[n]) for n in dict.fromkeys(usados) if n in scripts}
    do_rot = str(rot.get("janela") or "").strip() or None
    qualquer = next((t for t in por_script.values() if t), None)
    padrao_t = janela or do_rot or qualquer      # usado por quem não tem janela própria

    def titulo_de(nome: str) -> Optional[str]:
        return janela or por_script.get(nome) or padrao_t

    titulo = padrao_t
    if checar_janela and not titulo:
        sys.exit("Não sei qual é a janela do jogo: nenhum script da rotina guardou a janela e o campo "
                 "'Janela do jogo' das Configurações está vazio.\n"
                 "  Defina a janela em Configurações (ou regrave os scripts com ela definida); sem isso a "
                 "rotina clicaria em qualquer janela que estiver na frente.")
    print(f"▶ Rotina: {len(rot['itens'])} item(ns), {len(rot['intervalos'])} intervalo(s)"
          + (f", {rot['voltas']} volta(s)." if rot["voltas"] else " em loop (F9 para parar)."))
    for i in range(int(atraso), 0, -1):
        print(f"Começando em {i}... ({m_windows.NOME_PARAR} ou mouse no canto superior esquerdo para parar)")
        m_som.tocar_evento("tique")
        time.sleep(1)
    m_som.tocar_evento("repro_inicio")
    if titulo and checar_janela:   # traz o jogo para a frente antes do primeiro clique
        print(f"Trazendo a janela '{titulo}' para a frente...")
        if m_reproducao._garantir_janela(titulo, espera_janela) is None:
            print("Rotina interrompida: a janela do jogo não ficou ativa.")
            return "interrompida"

    volta_rot = [1]

    def _inicio_volta(n: int) -> None:
        volta_rot[0] = n
        if n > 1:
            tel().nova_partida()

    def rodar(nome: str) -> str:
        tel().progresso_rotulo = f"volta {volta_rot[0]} · {nome}"
        try:
            return m_reproducao.reproduzir(
                m_rotina.caminho_do_script(arquivo, nome), velocidade, 0, loop=None, pausa_loop=0.0,
                janela=titulo_de(nome), checar_janela=checar_janela, espera_janela=espera_janela, teclas=teclas,
                config=config, pasta=pasta, confianca=confianca, monitor=monitor, auto_detect=auto_detect,
                auto_max=auto_max, registro=registro, som=False)
        except SystemExit as e:  # gravação sumiu / sem eventos
            print(f"  {e}")
            return "falhou"

    def esperar_botao(botao: str, timeout: float, ate: str) -> Optional[bool]:
        r, _ = m_reproducao._aguardar_marcador({"botao": botao, "timeout": timeout, "ate": ate}, pasta,
                                               confianca, monitor, titulo, None)
        return r

    r = m_rotina.Rotina(
        rot, rodar, esperar_botao, abortou=m_windows.abortar,
        avisar=lambda m, t: m_robustez.alerta(m, t, monitor=monitor),
        fim_de_volta=lambda n: (m_som.tocar(), None)[1],
        inicio_de_volta=_inicio_volta)
    res = r.executar()
    m_som.tocar_evento("repro_fim")
    print({"ok": "Rotina concluída.", "interrompida": "Rotina interrompida.", "falhou": "Rotina parou por falha."}[res])
    return res
