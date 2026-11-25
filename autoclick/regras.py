"""Regras por botão (botoes.json), estado da partida, escolhas e registro (CSV)."""
from __future__ import annotations

import csv
import json
import random
import sys
import threading
import time
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, cast

from .tipos import Hit, Regiao
from .windows import MonitorTeclado
from . import windows as m_windows


ACOES_VALIDAS = ("clicar", "arrastar", "inicio", "ancora", "marcador", "erro")
# Ações que só "olham" (nunca são clicadas):
NAO_CLICAVEIS = ("inicio", "ancora", "marcador", "erro")
AO_VER_VALIDOS = ("avisar", "parar", "reconectar")

@dataclass
class Regra:
    """Regra de um botão (chave = nome do PNG sem extensão)."""

    acao: str = "clicar"  # clicar | arrastar | inicio | ancora
    vezes: int = 0  # por partida; 0 = ilimitado
    intervalo: Optional[float] = None  # segundos mínimos entre ações deste botão
    # Para 'arrastar' (só um dos três é usado):
    destino: Optional[tuple[int, int]] = None  # (x, y) FIXO na tela
    destino_janela: Optional[tuple[float, float]] = None  # fração (0-1) da janela do jogo
    destino_ancora: Optional[tuple[str, int, int]] = None  # (imagem de referência, dx, dy)
    offset: tuple[int, int] = (0, 0)  # ajuste fino do ponto de clique
    confirmar_cinza: bool = False
    queda_saturacao: float = 0.5  # cinza = saturação caiu para <= 50% do original
    tentativas: int = 3
    espera_confirmacao: float = 0.7
    # True = clica assim que detectar (também durante a reprodução de uma gravação);
    # False = nunca é clicado sozinho; None = padrão (clica nos modos de varredura).
    auto_detect: Optional[bool] = None
    # Escolher UM entre vários botões parecidos (ex.: 3 cartas de "escolha uma"):
    escolha: Optional[str] = None  # "primeiro" (mais à esquerda) | "ultimo" | "aleatorio"
    grupo: Optional[str] = None  # botões com o mesmo grupo disputam a mesma escolha
    # Clicar neste botão reinicia o ciclo (zera a partida; na reprodução, volta ao início
    # da gravação sem clicar de novo neste botão).
    reiniciar_loop: bool = False
    # Condições (só clica se...): todos os botões de 'requer' estão à vista e nenhum de
    # 'ignorar_se' está; 'etapa' = só age durante essa etapa do "_fluxo".
    requer: tuple[str, ...] = ()
    ignorar_se: tuple[str, ...] = ()
    etapa: Optional[str] = None
    # Para acao "erro": o que fazer ao ver esta tela (avisar | parar)
    ao_ver: str = "avisar"
    # ao_ver "reconectar": nome do botão (regra "clicar") que reconecta; a partida recomeça
    reconectar_com: Optional[str] = None

ESCOLHAS_VALIDAS = ("primeiro", "ultimo", "aleatorio")

def carregar_regras(caminho: str) -> dict[str, Regra]:
    """Regras do botoes.json do jogo somadas às do "Roblox (geral)" (o jogo vence o geral)."""
    from . import jogos as m_jogos
    geral = m_jogos.camada_geral()[1]
    if not geral or Path(geral).resolve() == Path(caminho).resolve():
        return _regras_do_arquivo(caminho)
    regras = _regras_do_arquivo(geral)
    regras.update(_regras_do_arquivo(caminho))
    return regras

def _regras_do_arquivo(caminho: str) -> dict[str, Regra]:
    p = Path(caminho)
    if not p.is_file():
        return {}
    try:
        bruto: Any = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"{caminho}: JSON inválido ({e}).")
    if not isinstance(bruto, dict):
        sys.exit(f'{caminho}: o arquivo deve ser um objeto JSON: {{"botao": {{...}}}}.')

    regras: dict[str, Regra] = {}
    for nome, dados_raw in cast(dict[str, Any], bruto).items():
        if nome.startswith("_"):
            continue  # chaves iniciadas por _ são comentários
        if not isinstance(dados_raw, dict):
            sys.exit(f"{caminho}: a regra de '{nome}' deve ser um objeto.")
        d = cast(dict[str, Any], dados_raw)

        acao = str(d.get("acao", "clicar")).lower()
        if acao not in ACOES_VALIDAS:
            sys.exit(f"{caminho}: ação inválida em '{nome}': {acao!r} "
                     f"(use: {', '.join(ACOES_VALIDAS)}).")

        destino: Optional[tuple[int, int]] = None
        destino_janela: Optional[tuple[float, float]] = None
        destino_ancora: Optional[tuple[str, int, int]] = None
        formatos = ('deve ser [x, y], {"janela": [fx, fy]} ou '
                    '{"ancora": "nome_do_png", "offset": [dx, dy]}')
        if "destino" in d:
            dr: Any = d["destino"]
            if isinstance(dr, list) and len(cast(list[Any], dr)) == 2:
                lista = cast(list[Any], dr)
                destino = (int(lista[0]), int(lista[1]))
            elif isinstance(dr, dict):
                dd = cast(dict[str, Any], dr)
                if "janela" in dd:
                    jr: Any = dd["janela"]
                    if not (isinstance(jr, list) and len(cast(list[Any], jr)) == 2):
                        sys.exit(f'{caminho}: "janela" em destino de \'{nome}\' deve ser [fx, fy] '
                                 "(frações de 0 a 1 da janela).")
                    jl = cast(list[Any], jr)
                    fx, fy = float(jl[0]), float(jl[1])
                    if not (0.0 <= fx <= 1.0 and 0.0 <= fy <= 1.0):
                        sys.exit(f"{caminho}: destino.janela de '{nome}' deve ter valores entre "
                                 "0 e 1 (fração da largura e da altura da janela).")
                    destino_janela = (fx, fy)
                elif "ancora" in dd:
                    orr2: Any = dd.get("offset", [0, 0])
                    if not (isinstance(orr2, list) and len(cast(list[Any], orr2)) == 2):
                        sys.exit(f"{caminho}: destino.offset de '{nome}' deve ser [dx, dy].")
                    ol2 = cast(list[Any], orr2)
                    destino_ancora = (str(dd["ancora"]), int(ol2[0]), int(ol2[1]))
                else:
                    sys.exit(f"{caminho}: 'destino' de '{nome}' {formatos}.")
            else:
                sys.exit(f"{caminho}: 'destino' de '{nome}' {formatos}.")
        if acao == "arrastar" and destino is None and destino_janela is None \
                and destino_ancora is None:
            sys.exit(f"{caminho}: '{nome}' é 'arrastar' mas não tem 'destino'.")

        offset = (0, 0)
        if "offset" in d:
            orr: Any = d["offset"]
            if not (isinstance(orr, list) and len(cast(list[Any], orr)) == 2):
                sys.exit(f"{caminho}: 'offset' de '{nome}' deve ser [dx, dy].")
            ol = cast(list[Any], orr)
            offset = (int(ol[0]), int(ol[1]))

        intervalo: Optional[float] = (
            float(d["intervalo"]) if d.get("intervalo") is not None else None
        )
        auto_raw: Any = d.get("auto_detect")
        if auto_raw is not None and not isinstance(auto_raw, bool):
            sys.exit(f"{caminho}: 'auto_detect' de '{nome}' deve ser true ou false.")
        escolha_raw: Any = d.get("escolha")
        grupo_raw: Any = d.get("grupo")
        if escolha_raw is None and grupo_raw is not None:
            escolha_raw = "primeiro"
        if escolha_raw is not None and escolha_raw not in ESCOLHAS_VALIDAS:
            sys.exit(f"{caminho}: 'escolha' de '{nome}' deve ser uma de: "
                     f"{', '.join(ESCOLHAS_VALIDAS)}.")
        reiniciar_raw: Any = d.get("reiniciar_loop", False)
        if not isinstance(reiniciar_raw, bool):
            sys.exit(f"{caminho}: 'reiniciar_loop' de '{nome}' deve ser true ou false.")
        def lista_nomes(chave: str) -> tuple[str, ...]:
            bruto_l: Any = d.get(chave)
            if bruto_l is None:
                return ()
            if isinstance(bruto_l, str):
                return (bruto_l,)
            if isinstance(bruto_l, list):
                return tuple(str(x) for x in cast(list[Any], bruto_l))
            sys.exit(f"{caminho}: '{chave}' de '{nome}' deve ser um nome ou uma lista de nomes.")

        etapa_raw: Any = d.get("etapa")
        ao_ver = str(d.get("ao_ver", "avisar")).lower()
        if ao_ver not in AO_VER_VALIDOS:
            sys.exit(f"{caminho}: 'ao_ver' de '{nome}' deve ser: {', '.join(AO_VER_VALIDOS)}.")
        regras[nome] = Regra(
            requer=lista_nomes("requer"),
            ignorar_se=lista_nomes("ignorar_se"),
            etapa=str(etapa_raw) if etapa_raw is not None else None,
            ao_ver=ao_ver,
            reconectar_com=(str(d["reconectar_com"]) if d.get("reconectar_com") else None),
            escolha=cast(Optional[str], escolha_raw),
            grupo=str(grupo_raw) if grupo_raw is not None else None,
            reiniciar_loop=reiniciar_raw,
            auto_detect=auto_raw,
            acao=acao,
            vezes=int(d.get("vezes", 1 if acao == "arrastar" else 0)),
            intervalo=intervalo,
            destino=destino,
            destino_janela=destino_janela,
            destino_ancora=destino_ancora,
            offset=offset,
            confirmar_cinza=bool(d.get("confirmar_cinza", acao == "arrastar")),
            queda_saturacao=float(d.get("queda_saturacao", 0.5)),
            tentativas=int(d.get("tentativas", 3)),
            espera_confirmacao=float(d.get("espera_confirmacao", 0.7)),
        )
    return regras

def carregar_janela_config(caminho: str) -> Optional[str]:
    """Lê "_janela": "Título" do botoes.json (a mesma opção do --janela)."""
    p = Path(caminho)
    if not p.is_file():
        return None
    try:
        bruto: Any = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(bruto, dict):
        v = cast(dict[str, Any], bruto).get("_janela")
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None

def dentro_da_tela(p: tuple[int, int]) -> bool:
    """True se o ponto cai dentro da área de tela (se não der para saber, True)."""
    try:
        vx, vy, vw, vh = m_windows.limites_tela()
    except Exception:
        return True
    return vx <= p[0] < vx + vw and vy <= p[1] < vy + vh

# nome -> (x_tela, y_tela, tela_px_por_px_do_png_x, idem_y, quando_visto)
Ancora = tuple[float, float, float, float, float]

def resolver_destino(
    r: Regra,
    janela: Optional[Regiao],
    ancoras: dict[str, Ancora],
    agora: float,
    validade: float = 5.0,
) -> tuple[Optional[tuple[int, int]], str]:
    """Converte o destino da regra em coordenadas de tela AGORA.

    - fixo:    o próprio (x, y);
    - janela:  esquerda/topo da janela + fração * largura/altura (acompanha mover/redimensionar);
    - âncora:  posição atual da imagem de referência + deslocamento (acompanha a câmera).
    Devolve (ponto, "") ou (None, motivo) se não der para calcular agora.
    """
    if r.destino is not None:
        return r.destino, ""
    if r.destino_janela is not None:
        if janela is None:
            return None, "janela do jogo não encontrada"
        fx, fy = r.destino_janela
        return (round(janela[0] + fx * janela[2]), round(janela[1] + fy * janela[3])), ""
    if r.destino_ancora is not None:
        nome, dx, dy = r.destino_ancora
        a = ancoras.get(nome)
        if a is None or agora - a[4] > validade:
            return None, f"a âncora '{nome}' não está visível"
        return (round(a[0] + dx * a[2]), round(a[1] + dy * a[3])), ""
    return None, "regra sem destino"

class Escolhedor:
    """"Escolha UM": vários botões parecidos aparecem juntos (ex.: 3 cartas) e basta
    clicar em um, uma vez por aparição.

    Regras com "escolha" (e opcionalmente "grupo") competem entre si: a cada varredura
    só um dos botões do grupo é liberado para clique. Depois do clique o grupo fica
    travado até todos sumirem da tela por 'rearme' segundos (nova aparição). Se o grupo
    continuar à vista 'retentar_apos' segundos depois do clique, o clique é considerado
    perdido e uma nova escolha é liberada.
    """

    def __init__(self, rearme: float = 2.0, retentar_apos: float = 8.0) -> None:
        self.rearme, self.retentar_apos = rearme, retentar_apos
        self._travados: dict[str, float] = {}  # grupo -> quando foi clicado
        self._visto: dict[str, float] = {}  # grupo -> última vez à vista

    @staticmethod
    def grupo_de(h: Hit, regras: dict[str, Regra]) -> Optional[str]:
        r = regras.get(h.rotulo)
        if r is None or r.escolha is None:
            return None
        return r.grupo or h.rotulo

    def filtrar(self, hits: list[Hit], regras: dict[str, Regra], agora: float) -> list[Hit]:
        por_grupo: dict[str, list[Hit]] = {}
        livres: list[Hit] = []
        for h in hits:
            g = self.grupo_de(h, regras)
            if g is None:
                livres.append(h)
            else:
                por_grupo.setdefault(g, []).append(h)
        for g in list(self._travados):  # destrava quem sumiu (ou não respondeu ao clique)
            if g not in por_grupo and agora - self._visto.get(g, 0.0) >= self.rearme:
                del self._travados[g]
            elif g in por_grupo and agora - self._travados[g] >= self.retentar_apos:
                del self._travados[g]
        for g, lista in por_grupo.items():
            self._visto[g] = agora
            if g in self._travados:
                continue
            modo = regras[lista[0].rotulo].escolha
            ordenados = sorted(lista, key=lambda k: (k.x, k.y))
            if modo == "ultimo":
                livres.append(ordenados[-1])
            elif modo == "aleatorio":
                livres.append(random.choice(ordenados))
            else:
                livres.append(ordenados[0])
        return livres

    def travar(self, h: Hit, regras: dict[str, Regra], agora: float) -> None:
        g = self.grupo_de(h, regras)
        if g is not None:
            self._travados[g] = agora
            self._visto[g] = agora

@dataclass
class Estado:
    """Memória da partida atual: o que já foi feito e o que desistimos de fazer."""

    partida: int = 1
    feitos: dict[str, int] = field(default_factory=lambda: {})
    tentativas: dict[str, int] = field(default_factory=lambda: {})
    desistiu: set[str] = field(default_factory=lambda: set())
    inicio_visivel: bool = False

    def zerar(self) -> None:
        self.partida += 1
        self.feitos.clear()
        self.tentativas.clear()
        self.desistiu.clear()

class Registro:
    """Log CSV das ações automáticas: horário, tempo desde o início e coordenadas."""

    CABECALHO = ["horario", "t_seg", "tipo", "botao", "x", "y", "x2", "y2", "detalhe"]

    def __init__(self, caminho: Optional[str]) -> None:
        self.inicio = time.time()
        self._arq: Optional[Any] = None
        self._w: Optional[Any] = None
        self._trava = threading.Lock()
        if caminho:
            p = Path(caminho)
            p.parent.mkdir(parents=True, exist_ok=True)
            novo = (not p.exists()) or p.stat().st_size == 0
            self._arq = p.open("a", newline="", encoding="utf-8")
            self._w = csv.writer(self._arq)
            if novo:
                self._w.writerow(self.CABECALHO)
                self._arq.flush()

    def log(
        self,
        tipo: str,
        botao: str = "",
        x: Optional[int] = None,
        y: Optional[int] = None,
        x2: Optional[int] = None,
        y2: Optional[int] = None,
        detalhe: str = "",
    ) -> None:
        with self._trava:
            self._escrever(tipo, botao, x, y, x2, y2, detalhe)

    def _escrever(
        self, tipo: str, botao: str, x: Optional[int], y: Optional[int],
        x2: Optional[int], y2: Optional[int], detalhe: str,
    ) -> None:
        if self._w is None or self._arq is None:
            return
        agora = time.time()
        self._w.writerow([
            datetime.now().isoformat(timespec="milliseconds"),
            f"{agora - self.inicio:.3f}",
            tipo,
            botao,
            "" if x is None else x,
            "" if y is None else y,
            "" if x2 is None else x2,
            "" if y2 is None else y2,
            detalhe,
        ])
        self._arq.flush()

    @property
    def ativo(self) -> bool:
        return self._w is not None

    def fechar(self) -> None:
        with self._trava:
            if self._arq is not None:
                self._arq.close()
            self._arq = None
            self._w = None

def monitorar_teclado_no_log(parar: threading.Event, registro: Registro) -> None:
    """Em segundo plano, anota no --log as teclas que VOCÊ aperta enquanto o robô roda."""
    mon = MonitorTeclado()
    while not parar.is_set():
        try:
            for estado, vk in mon.varrer(time.time()):
                registro.log("tecla", m_windows.nome_tecla(vk), detalhe=estado)
        except Exception:
            pass
        parar.wait(0.01)
