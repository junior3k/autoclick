# pyright: basic
"""Robustez do processo em execução: tela parada, alertas, captura no erro, avisos externos,
histórico de sessões e prévia ao vivo.

Tudo aqui é opcional e só usa a biblioteca padrão (numpy/cv2/mss entram de forma tardia,
somente dentro de quem já os usa). Configuração por variáveis de ambiente, que a janela
define ao iniciar cada função:

    AUTOCLICK_WEBHOOK       Discord/URL (POST JSON) ou  telegram:TOKEN@CHAT_ID
    AUTOCLICK_CAPTURA_ERRO  "1" (padrão) salva a tela em erros/ quando algo dá errado
    AUTOCLICK_PASTA_ERROS   pasta das capturas (padrão: erros)
    AUTOCLICK_PREVIA        arquivo PNG atualizado com a visão ao vivo (a janela exibe)
    AUTOCLICK_HISTORICO     arquivo .jsonl do histórico (padrão: historico/sessoes.jsonl)
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from . import captura as m_captura
from . import windows as m_windows
from .avisos import enviar_webhook_sync
from .operacao import pausa, tel
from .tipos import Hit, Regiao


# --------------------------------------------------------------------------- #
# Avisos externos (webhook)
# --------------------------------------------------------------------------- #
def enviar_webhook(titulo: str, texto: str) -> None:
    """Envia em segundo plano (não trava o programa)."""
    if not os.environ.get("AUTOCLICK_WEBHOOK", "").strip():
        return
    threading.Thread(target=enviar_webhook_sync, args=(titulo, texto), daemon=True).start()


# --------------------------------------------------------------------------- #
# Captura de tela no erro
# --------------------------------------------------------------------------- #
def capturar_erro(motivo: str, monitor: int = 1, regiao: Optional[Regiao] = None) -> Optional[str]:
    """Salva a tela em erros/AAAA-MM-DD_HH-MM-SS_motivo.png. Devolve o caminho (ou None)."""
    if os.environ.get("AUTOCLICK_CAPTURA_ERRO", "1") == "0":
        return None
    try:
        import cv2
        img = m_captura.capturar(monitor, regiao)[0]
        pasta = Path(os.environ.get("AUTOCLICK_PASTA_ERROS", "erros"))
        pasta.mkdir(parents=True, exist_ok=True)
        slug = "".join(c if c.isalnum() else "_" for c in motivo)[:40].strip("_") or "erro"
        caminho = pasta / f"{datetime.now():%Y-%m-%d_%H-%M-%S}_{slug}.png"
        cv2.imwrite(str(caminho), img)
        print(f"[captura] tela salva em {caminho}", flush=True)
        return str(caminho)
    except Exception as e:
        print(f"[captura] não consegui salvar a tela ({type(e).__name__}: {e})", flush=True)
        return None


def alerta(motivo: str, texto: str, capturar: bool = True, monitor: int = 1,
           regiao: Optional[Regiao] = None) -> None:
    """Algo merece atenção: registra, avisa a janela (linha [ALERTA]), captura e notifica."""
    print(f"[ALERTA] {motivo}: {texto}", flush=True)
    tel().aviso(f"{motivo}: {texto}")
    if capturar:
        capturar_erro(motivo, monitor, regiao)
    enviar_webhook(f"Autoclick: {motivo}", texto)


# --------------------------------------------------------------------------- #
# Tela parada (travamento do jogo)
# --------------------------------------------------------------------------- #
def diferenca_media(a: Any, b: Any) -> float:
    """Diferença média absoluta (0-255) entre dois quadros reduzidos."""
    import numpy as np
    return float(np.abs(a.astype("int16") - b.astype("int16")).mean())


def reduzir(img: Any) -> Any:
    """Quadro bem pequeno (amostragem) para comparar telas sem gastar CPU."""
    return img[::24, ::24, :3].copy()


class VigiaTela:
    """Thread que compara a tela de tempos em tempos. Se nada mudar por `segundos`,
    emite um alerta (e, com acao='parar', encerra). Fica quieta enquanto pausado."""

    def __init__(self, segundos: float, acao: str, monitor: int, titulo: Optional[str],
                 regiao: Optional[Regiao], limiar: float = 1.0, intervalo: float = 2.0) -> None:
        self.segundos, self.acao = segundos, acao
        self.monitor, self.titulo, self.regiao = monitor, titulo, regiao
        self.limiar, self.intervalo = limiar, intervalo
        self.disparos = 0
        self._parar = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _quadro(self) -> Any:
        regiao = self.regiao
        if self.titulo:
            rect = m_captura.rect_seguro(self.titulo)
            regiao = m_captura.regiao_da_janela(rect, self.monitor) if rect else None
            if regiao is None:
                return None
        return reduzir(m_captura.capturar(self.monitor, regiao)[0]), regiao

    def verificar(self, anterior: Any, atual: Any, agora: float,
                  parado_desde: Optional[float], avisou: bool) -> tuple[Optional[float], bool, bool]:
        """Regra pura (testável): devolve (parado_desde, avisou, disparar)."""
        if anterior is None or anterior.shape != atual.shape:
            return None, False, False
        if diferenca_media(anterior, atual) > self.limiar:
            return None, False, False
        if parado_desde is None:
            return agora, avisou, False
        if not avisou and agora - parado_desde >= self.segundos:
            return parado_desde, True, True
        return parado_desde, avisou, False

    def _laco(self) -> None:
        anterior: Any = None
        desde: Optional[float] = None
        avisou = False
        while not self._parar.wait(self.intervalo):
            if pausa.pausado:
                anterior, desde, avisou = None, None, False
                continue
            try:
                q = self._quadro()
            except Exception:
                continue
            if q is None:
                anterior, desde, avisou = None, None, False
                continue
            atual, regiao = q
            desde, avisou, disparar = self.verificar(anterior, atual, time.time(), desde, avisou)
            anterior = atual
            if disparar:
                self.disparos += 1
                alerta("tela parada",
                       f"a tela não muda há mais de {self.segundos:g}s (jogo travado?)",
                       monitor=self.monitor, regiao=regiao)
                if self.acao == "parar":
                    print("Encerrando (a tela ficou parada).", flush=True)
                    m_windows.PARADA.set()
                    return

    def iniciar(self) -> None:
        if self.segundos <= 0 or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._laco, daemon=True)
        self._thread.start()
        print(f"Vigia de tela parada ligada: avisa se a tela não mudar por {self.segundos:g}s"
              + (" e encerra." if self.acao == "parar" else "."), flush=True)

    def parar(self) -> None:
        self._parar.set()
        if self._thread is not None:
            self._thread.join(timeout=3)


def vigia_do_ambiente(segundos: float, acao: str, monitor: int, titulo: Optional[str],
                      regiao: Optional[Regiao]) -> Optional[VigiaTela]:
    v = VigiaTela(segundos, acao, monitor, titulo, regiao)
    if segundos <= 0:
        return None
    v.iniciar()
    return v


# --------------------------------------------------------------------------- #
# Reconexão: limite de tentativas
# --------------------------------------------------------------------------- #
class LimiteReconexao:
    """No máximo `maximo` reconexões em `janela` segundos; passou disso, desiste."""

    def __init__(self, maximo: int = 5, janela: float = 600.0) -> None:
        self.maximo, self.janela = maximo, janela
        self._marcas: list[float] = []

    def registrar(self, agora: Optional[float] = None) -> bool:
        """True = pode tentar de novo; False = já passou do limite (desistir)."""
        agora = time.time() if agora is None else agora
        self._marcas = [t for t in self._marcas if agora - t <= self.janela]
        self._marcas.append(agora)
        return len(self._marcas) <= self.maximo


# --------------------------------------------------------------------------- #
# Histórico de sessões
# --------------------------------------------------------------------------- #
def arquivo_historico() -> Path:
    return Path(os.environ.get("AUTOCLICK_HISTORICO", "historico/sessoes.jsonl"))


def registrar_sessao(modo: str, motivo: str) -> None:
    """Acrescenta o resumo da sessão ao histórico (uma linha JSON por sessão)."""
    try:
        r = dict(tel().resumo())
        from .jogos import slug_ativo
        r.update({"modo": modo, "motivo": motivo, "jogo": slug_ativo(),
                  "fim": datetime.now().isoformat(timespec="seconds")})
        p = arquivo_historico()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"(histórico não gravado: {e})", flush=True)


def ler_historico(caminho: Optional[str] = None) -> list[dict[str, Any]]:
    p = Path(caminho) if caminho else arquivo_historico()
    out: list[dict[str, Any]] = []
    if not p.is_file():
        return out
    for linha in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(linha)
        except ValueError:
            continue
        if isinstance(d, dict):
            out.append(d)
    return out


# --------------------------------------------------------------------------- #
# Prévia ao vivo
# --------------------------------------------------------------------------- #
class Previa:
    """Grava, no máximo a cada `cada` s, um PNG pequeno da tela com os botões desenhados."""

    def __init__(self) -> None:
        self._ultimo = 0.0

    @property
    def arquivo(self) -> str:
        return os.environ.get("AUTOCLICK_PREVIA", "")

    def atualizar(self, img: Any, hits: list[Hit], largura: int = 560, cada: float = 0.8) -> None:
        arq = self.arquivo
        agora = time.time()
        if not arq or agora - self._ultimo < cada:
            return
        self._ultimo = agora
        try:
            import cv2
            h0, w0 = img.shape[:2]
            esc = largura / float(w0) if w0 > largura else 1.0
            out = cv2.resize(img, (int(w0 * esc), int(h0 * esc))) if esc != 1.0 else img.copy()
            for h in hits:
                p1 = (int(h.x * esc), int(h.y * esc))
                p2 = (int((h.x + h.w) * esc), int((h.y + h.h) * esc))
                cv2.rectangle(out, p1, p2, (0, 220, 0), 2)
                cv2.putText(out, h.rotulo, (p1[0], max(12, p1[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX,
                            0.45, (0, 0, 255), 1, cv2.LINE_AA)
            ok, buf = cv2.imencode(".png", out)
            if ok:
                tmp = arq + ".tmp"
                with open(tmp, "wb") as f:
                    f.write(buf.tobytes())
                os.replace(tmp, arq)
        except Exception:
            pass  # a prévia nunca pode atrapalhar o trabalho


previa = Previa()


# --------------------------------------------------------------------------- #
# Resolução e DPI
# --------------------------------------------------------------------------- #
def descrever_tela() -> dict[str, Any]:
    """Tamanho da tela e DPI atuais (guardados na gravação)."""
    try:
        w, h = m_windows.tamanho_tela()
    except Exception:
        w, h = 0, 0
    return {"largura": w, "altura": h, "dpi": m_windows.dpi_sistema()}


def conferir_resolucao(dados: dict[str, Any], titulo: Optional[str]) -> list[str]:
    """Compara o ambiente da gravação com o atual. Devolve os avisos (lista vazia = ok)."""
    avisos: list[str] = []
    tela = dados.get("tela")
    if isinstance(tela, dict):
        atual = descrever_tela()
        if tela.get("largura") and atual["largura"] and (
                tela.get("largura") != atual["largura"] or tela.get("altura") != atual["altura"]):
            avisos.append(f"a tela era {tela.get('largura')}x{tela.get('altura')} na gravação e "
                          f"agora é {atual['largura']}x{atual['altura']}")
        if tela.get("dpi") and tela.get("dpi") != atual["dpi"]:
            avisos.append(f"a escala do Windows mudou (DPI {tela.get('dpi')} -> {atual['dpi']})")
    info = dados.get("janela")
    if titulo and isinstance(info, dict) and info.get("rect"):
        antigo = info["rect"]
        rect = m_captura.rect_seguro(titulo)
        if rect and len(antigo) == 4 and (antigo[2] != rect[2] or antigo[3] != rect[3]):
            avisos.append(f"a janela era {antigo[2]}x{antigo[3]} e agora é {rect[2]}x{rect[3]}")
    return avisos
