"""Modo gravar: grava cliques, arrastos e teclas; gera regras."""
from __future__ import annotations

import json
import math
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, cast

from .tipos import Caixa, Regiao
from .windows import MonitorTeclado, VK_DIREITO, VK_ESQUERDO
from .regras import Ancora
from . import windows as m_windows
from . import robustez as m_robustez
from . import operacao as m_operacao
from .som import som as m_som
from . import captura as m_captura
from . import deteccao as m_deteccao


def _varredura_continua(
    parar: threading.Event,
    trava: threading.Lock,
    conhecidos: dict[str, tuple[Caixa, float]],
    pasta: str,
    confianca: float,
    monitor: int,
    regiao: Optional[Regiao],
    centros: Optional[dict[str, Ancora]] = None,
) -> None:
    """Em segundo plano, lembra onde cada botão da pasta foi visto por último.

    Quando o mouse está em cima, o botão muda de aparência e deixa de ser
    reconhecido; por isso guardamos a última posição vista ANTES do hover.
    """
    while not parar.is_set():
        try:
            img, ex, ey, ox, oy = m_captura.capturar(monitor, regiao)
            for h in m_deteccao.detectar_imagens(img, pasta, confianca):
                caixa: Caixa = (
                    round(ox + h.x * ex),
                    round(oy + h.y * ey),
                    round(ox + (h.x + h.w) * ex),
                    round(oy + (h.y + h.h) * ey),
                )
                agora = time.time()
                with trava:
                    conhecidos[h.rotulo] = (caixa, agora)
                    if centros is not None:
                        centros[h.rotulo] = (
                            (caixa[0] + caixa[2]) / 2, (caixa[1] + caixa[3]) / 2,
                            h.escala * ex, h.escala * ey, agora,
                        )
        except Exception:
            pass  # uma falha de captura não pode derrubar a gravação
        parar.wait(0.4)

def _identificar(
    x: int,
    y: int,
    trava: threading.Lock,
    conhecidos: dict[str, tuple[Caixa, float]],
    janela: float = 20.0,
) -> Optional[str]:
    agora = time.time()
    melhor: Optional[tuple[float, str]] = None
    with trava:
        for rot, (caixa, ts) in conhecidos.items():
            if agora - ts > janela:
                continue
            x0, y0, x1, y1 = caixa
            if x0 - 6 <= x <= x1 + 6 and y0 - 6 <= y <= y1 + 6:
                if melhor is None or ts > melhor[0]:
                    melhor = (ts, rot)
    return melhor[1] if melhor is not None else None

def _frac(x: int, y: int, rect: Optional[Regiao]) -> Optional[tuple[float, float]]:
    """Posição (x, y) como fração da janela; None se a janela não é conhecida."""
    if rect is None:
        return None
    return round((x - rect[0]) / rect[2], 5), round((y - rect[1]) / rect[3], 5)

def gravar(
    arquivo: str,
    pasta: str,
    confianca: float,
    monitor: int,
    regiao: Optional[Regiao],
    duracao: float,
    atraso: float,
    limiar_arrasto: int = 12,
    janela: Optional[str] = None,
    ancora: Optional[str] = None,
    teclado: bool = True,
) -> list[dict[str, Any]]:
    """Grava seus cliques, arrastos e (opcional) teclas, com coordenadas e tempo.

    Se houver uma janela (--janela, ou detectada no 1º clique), cada ponto também é
    salvo como fração da janela: assim a gravação e as regras geradas continuam valendo
    se a janela mudar de lugar ou de tamanho. Com --ancora, o ponto de soltura dos
    arrastos também é salvo relativo a essa imagem do mapa (acompanha a câmera).
    """
    if sys.platform != "win32":
        sys.exit("O modo 'gravar' só funciona no Windows.")

    pngs: list[Path] = []
    if Path(pasta).is_dir():
        pngs = sorted(Path(pasta).glob("*.png")) + sorted(Path(pasta).glob("*.jpg"))

    parar = threading.Event()
    trava = threading.Lock()
    conhecidos: dict[str, tuple[Caixa, float]] = {}
    centros: dict[str, Ancora] = {}
    worker: Optional[threading.Thread] = None
    if pngs:
        worker = threading.Thread(
            target=_varredura_continua,
            args=(parar, trava, conhecidos, pasta, confianca, monitor, regiao, centros),
            daemon=True,
        )
        worker.start()
        print(f"Identificando os botões da pasta '{pasta}' ({len(pngs)} imagem(ns)) "
              "para dar nome aos cliques.")
    else:
        print(f"Aviso: sem imagens em '{pasta}'; os cliques serão gravados sem nome de botão.")
    if ancora and not any(p.stem == ancora for p in pngs):
        print(f"Aviso: não há '{ancora}.png' em '{pasta}'; os arrastos não terão âncora.")

    for i in range(int(atraso), 0, -1):
        print(f"Começando em {i}...")
        m_som.tocar_evento("tique")
        time.sleep(1)
    print(f"● GRAVANDO. Jogue normalmente. Aperte {m_windows.NOME_PARAR} para parar."
          + (" (teclas também são gravadas)" if teclado else ""))

    titulo = janela
    rect_ultimo: Optional[Regiao] = m_captura.rect_seguro(titulo)
    mon_tec = MonitorTeclado() if teclado else None
    eventos: list[dict[str, Any]] = []
    abertos: dict[int, tuple[float, int, int, Optional[str], Optional[Regiao]]] = {}
    m_som.tocar_evento("gravar_inicio")  # toca (sem travar) logo antes de marcar o zero da gravação
    t0 = time.time()
    m_operacao.tel().gravacao_iniciar(t0)  # cronômetro na tela: conta a partir daqui

    def _marca(t: float, texto: str) -> None:
        print(f"[{_hora(t)}] {texto}")
        m_operacao.tel().gravacao_evento(f"{_hora(t)}  {texto}")

    def _hora(t: float) -> str:
        return f"{int(t // 60):02d}:{t % 60:06.3f}"

    try:
        while True:
            agora = time.time()
            if (m_windows.pressionada("parar") or m_windows.PARADA.is_set()
                    or (duracao and agora - t0 > duracao)):
                break
            for vk, nome in ((VK_ESQUERDO, "esquerdo"), (VK_DIREITO, "direito")):
                premido = m_windows.tecla_pressionada(vk)
                if premido and vk not in abertos:
                    x, y = m_windows.posicao()
                    if titulo is None:
                        titulo = m_windows.titulo_sob_ponto(x, y)
                        if titulo:
                            print(f"Janela detectada: '{titulo}' (para outra, use --janela).")
                    rect = m_captura.rect_seguro(titulo)
                    abertos[vk] = (agora - t0, x, y, _identificar(x, y, trava, conhecidos), rect)
                elif (not premido) and vk in abertos:
                    t_ini, x, y, rot, rect_ini = abertos.pop(vk)
                    x2, y2 = m_windows.posicao()
                    rect_fim = m_captura.rect_seguro(titulo)
                    rect_ultimo = rect_fim or rect_ini or rect_ultimo
                    dur = (agora - t0) - t_ini
                    tipo = "arrasto" if math.hypot(x2 - x, y2 - y) >= limiar_arrasto else "clique"
                    ev: dict[str, Any] = {
                        "t": round(t_ini, 3),
                        "tipo": tipo,
                        "mouse": nome,
                        "x": x,
                        "y": y,
                        "x2": x2,
                        "y2": y2,
                        "duracao": round(dur, 3),
                        "botao": rot,
                    }
                    f1 = _frac(x, y, rect_ini)
                    f2 = _frac(x2, y2, rect_fim)
                    if f1 is not None:
                        ev["fx"], ev["fy"] = f1
                    if f2 is not None:
                        ev["fx2"], ev["fy2"] = f2
                    if ancora and tipo == "arrasto":
                        with trava:
                            c = centros.get(ancora)
                        if c is not None and agora - c[4] <= 20.0 and c[2] > 0 and c[3] > 0:
                            ev["ancora"] = {
                                "nome": ancora,
                                "dx": round((x2 - c[0]) / c[2]),
                                "dy": round((y2 - c[1]) / c[3]),
                            }
                        else:
                            print(f"  Aviso: a âncora '{ancora}' não estava visível; "
                                  "este arrasto fica sem âncora.")
                    eventos.append(ev)
                    sufixo = f"  [{rot}]" if rot else ""
                    if tipo == "arrasto":
                        _marca(t_ini, f"arrasto {nome} ({x},{y}) -> ({x2},{y2}) "
                                      f"em {dur:.2f}s{sufixo}")
                    else:
                        _marca(t_ini, f"clique {nome} em ({x},{y}){sufixo}")
            if mon_tec is not None:
                for estado, vk in mon_tec.varrer(agora):
                    if titulo is None:
                        titulo = m_windows.titulo_ativo()
                    t_ev = agora - t0
                    eventos.append({"t": round(t_ev, 3), "tipo": "tecla",
                                    "tecla": m_windows.nome_tecla(vk), "vk": vk, "estado": estado})
                    _marca(t_ev, f"tecla {m_windows.nome_tecla(vk)} "
                                 f"{'↓' if estado == 'baixo' else '↑'}")
            time.sleep(0.005)
    except KeyboardInterrupt:
        pass
    finally:
        t_fim_total = time.time() - t0  # quando você parou: o tempo depois do último clique também conta
        m_som.tocar_evento("gravar_fim")
        parar.set()
        if worker is not None:
            worker.join(timeout=2)

    if mon_tec is not None:  # teclas ainda apertadas quando o F9 foi pressionado
        t_fim = round(time.time() - t0, 3)
        for vk in list(mon_tec.premidas):
            eventos.append({"t": t_fim, "tipo": "tecla", "tecla": m_windows.nome_tecla(vk),
                            "vk": vk, "estado": "cima"})
    # atalho de parar com Ctrl/Alt/Shift (ex.: Ctrl+F9): os modificadores apertados para parar não são ação do jogo
    mods_parar = set(m_windows.vks_dos_modificadores(
        tuple(dict.fromkeys(m_windows._atalhos["parar"][0] + m_windows._atalhos["gravar"][0]))))
    if mods_parar:
        eventos = [e for e in eventos if not (e["tipo"] == "tecla" and int(e["vk"]) in mods_parar
                                              and float(e["t"]) >= t_fim_total - 1.5)]
    eventos.sort(key=lambda e: float(e["t"]))
    ultimo_t = float(eventos[-1]["t"]) if eventos else 0.0
    # "cauda": segundos entre a última ação e o fim da gravação. A reprodução espera esse tempo
    # antes de recomeçar o loop (se você só parou aos 10 min, a volta dura 10 min, não 7).
    cauda = round(max(0.0, t_fim_total - ultimo_t), 3)

    dados = {
        "versao": 2,
        "criado": datetime.now().isoformat(timespec="seconds"),
        "monitor": monitor,
        "janela": {"titulo": titulo, "rect": list(rect_ultimo) if rect_ultimo else None},
        "tela": m_robustez.descrever_tela(),
        "duracao_total": round(max(t_fim_total, ultimo_t), 3),
        "cauda": cauda,
        "eventos": eventos,
    }
    Path(arquivo).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    mouse_ev = [e for e in eventos if e["tipo"] != "tecla"]
    teclas = len(eventos) - len(mouse_ev)
    sem_nome = sum(1 for e in mouse_ev if not e["botao"])
    print(f"\nGravação salva em '{arquivo}': {len(mouse_ev)} clique(s)/arrasto(s) "
          f"({sem_nome} sem nome de botão) e {teclas} evento(s) de tecla."
          + (f" Janela: '{titulo}'." if titulo else " Sem janela identificada."))
    for linha in resumo_teclas(eventos, t_fim_total):
        print(linha)
    return eventos


def resumo_teclas(eventos: list[dict[str, Any]], total: float) -> list[str]:
    """Conferência pós-gravação (só leitura): cada tecla com quantas vezes e em que tempos."""
    def h(t: float) -> str:
        return f"{int(t // 60):02d}:{t % 60:06.3f}"

    por: dict[str, list[float]] = {}
    for e in eventos:
        if e.get("tipo") == "tecla" and e.get("estado") == "baixo":
            por.setdefault(str(e.get("tecla")), []).append(float(e["t"]))
    n_mouse = sum(1 for e in eventos if e.get("tipo") != "tecla")
    linhas = [f"\nConferência: gravação de {h(total)} | {n_mouse} clique(s)/arrasto(s) | "
              f"{sum(len(v) for v in por.values())} tecla(s) apertada(s)"]
    for nome, ts in sorted(por.items(), key=lambda kv: kv[1][0]):
        mostra = ", ".join(h(t) for t in ts[:6]) + (f" … (+{len(ts) - 6})" if len(ts) > 6 else "")
        linhas.append(f"  {nome}: {len(ts)}× em {mostra}")
    return linhas


def gerar_regras(
    eventos: list[dict[str, Any]],
    config: str,
    sobrescrever: bool,
    janela: Optional[str] = None,
) -> None:
    """Transforma a gravação em regras no botoes.json (sem apagar as existentes).

    O destino de cada arrasto é gravado do jeito mais robusto disponível:
    âncora (se usou --ancora) > fração da janela > coordenada fixa de tela.
    """
    p = Path(config)
    atual: dict[str, Any] = {}
    if p.is_file():
        try:
            carregado: Any = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit(f"{config}: JSON inválido ({e}); corrija antes de gerar regras.")
        if isinstance(carregado, dict):
            atual = cast(dict[str, Any], carregado)

    novas: dict[str, dict[str, Any]] = {}
    sem_nome = 0
    tipos_destino: set[str] = set()
    for ev in eventos:
        if ev.get("tipo") == "tecla":
            continue
        rot = ev.get("botao")
        if not rot:
            sem_nome += 1
            continue
        if ev["tipo"] == "arrasto":
            destino: Any
            anc = ev.get("ancora")
            if isinstance(anc, dict):
                a = cast(dict[str, Any], anc)
                destino = {"ancora": a["nome"], "offset": [a["dx"], a["dy"]]}
                novas.setdefault(str(a["nome"]), {"acao": "ancora"})
                tipos_destino.add("ancora")
            elif "fx2" in ev and "fy2" in ev:
                destino = {"janela": [ev["fx2"], ev["fy2"]]}
                tipos_destino.add("janela")
            else:
                destino = [ev["x2"], ev["y2"]]
                tipos_destino.add("fixo")
            novas[str(rot)] = {"acao": "arrastar", "destino": destino, "vezes": 1}
        elif str(rot) not in novas:
            novas[str(rot)] = {"acao": "clicar"}

    escritas: list[str] = []
    mantidas: list[str] = []
    for rot, regra in novas.items():
        if rot in atual and not sobrescrever:
            mantidas.append(rot)
            continue
        atual[rot] = regra
        escritas.append(rot)
    if janela and "janela" in tipos_destino and "_janela" not in atual:
        atual["_janela"] = janela  # o programa usa isso como --janela automaticamente

    p.write_text(json.dumps(atual, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Regras em '{config}': {len(escritas)} gravada(s)"
          + (f" ({', '.join(escritas)})" if escritas else "") + ".")
    if mantidas:
        print(f"  Já existiam e foram mantidas: {', '.join(mantidas)} "
              "(use --sobrescrever para trocar).")
    if sem_nome:
        print(f"  {sem_nome} evento(s) sem nome de botão não geraram regra "
              "(o clique não foi sobre nenhum PNG da pasta).")
    if "fixo" in tipos_destino:
        print("  Aviso: há destino(s) em coordenada FIXA de tela (a janela não foi identificada); "
              "grave de novo com --janela para o destino acompanhar a janela.")
    if "janela" in tipos_destino:
        print("  Destino(s) relativos à janela: rode o programa com --janela "
              + (f"\"{janela}\"" if janela else "\"Título\"") + " (ou use \"_janela\" no json).")
