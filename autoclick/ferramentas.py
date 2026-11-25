"""Ferramentas de apoio: recortar botões, calibrar cinza, mapa de regras, destinos e diagnóstico."""
from __future__ import annotations

import base64
import json
import platform
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, cast

import cv2
import numpy as np

from .tipos import Hit, Img, Regiao
from .regras import NAO_CLICAVEIS, Ancora, Regra, resolver_destino
from . import windows as m_windows
from . import captura as m_captura
from . import deteccao as m_deteccao
from . import acao as m_acao
from .validar import relatorio, validar_config


# --------------------------------------------------------------------------- #
# Seleção na tela (Tk) — com o screenshot congelado
# --------------------------------------------------------------------------- #
def _tk_mostrar(img: Img, titulo: str, retangulo: bool) -> Optional[tuple[int, ...]]:
    """Mostra a imagem; devolve (x, y, w, h) arrastando ou (x, y) com um clique, em pixels da imagem."""
    try:
        import tkinter as tk
    except Exception:
        sys.exit("O Tk não está disponível neste Python. Use as opções --retangulo / --ponto.")
    alt, larg = img.shape[:2]
    k = min(1.0, 1400 / larg, 820 / alt)
    vis = cv2.resize(img, (int(larg * k), int(alt * k))) if k < 1.0 else img
    ok, buf = cv2.imencode(".png", vis)
    if not ok:
        sys.exit("Falha ao preparar a imagem.")
    raiz = tk.Tk()
    raiz.title(titulo + " (Esc cancela)")
    foto = tk.PhotoImage(data=base64.b64encode(buf.tobytes()))
    cv = tk.Canvas(raiz, width=vis.shape[1], height=vis.shape[0], cursor="crosshair")
    cv.pack()
    cv.create_image(0, 0, image=foto, anchor="nw")
    estado: dict[str, Any] = {"ini": None, "ret": None, "res": None}

    def baixo(e: Any) -> None:
        estado["ini"] = (e.x, e.y)

    def mexe(e: Any) -> None:
        if retangulo and estado["ini"] is not None:
            if estado["ret"] is not None:
                cv.delete(estado["ret"])
            x0, y0 = estado["ini"]
            estado["ret"] = cv.create_rectangle(x0, y0, e.x, e.y, outline="red", width=2)

    def cima(e: Any) -> None:
        x0, y0 = estado["ini"] or (e.x, e.y)
        if retangulo:
            x, y = min(x0, e.x), min(y0, e.y)
            w, h = abs(e.x - x0), abs(e.y - y0)
            estado["res"] = (round(x / k), round(y / k), round(w / k), round(h / k))
        else:
            estado["res"] = (round(e.x / k), round(e.y / k))
        raiz.destroy()

    cv.bind("<ButtonPress-1>", baixo)
    cv.bind("<B1-Motion>", mexe)
    cv.bind("<ButtonRelease-1>", cima)
    raiz.bind("<Escape>", lambda _e: raiz.destroy())
    raiz.protocol("WM_DELETE_WINDOW", raiz.destroy)
    raiz.geometry("+0+0")
    raiz.attributes("-topmost", True)  # sempre à frente do jogo
    raiz.after(300, lambda: (raiz.lift(), raiz.focus_force()))

    def vigiar() -> None:
        """Deixa Ctrl+C, F9, F8 e o canto do mouse fecharem a janela (o Tk sozinho ignora)."""
        if sys.platform == "win32" and (
                m_windows.pressionada("parar")
                or m_windows.pressionada("pausa")):
            estado["res"] = None
            raiz.destroy()
            return
        raiz.after(100, vigiar)

    vigiar()
    print("Janela de seleção aberta (canto superior esquerdo da tela). Arraste sobre o botão; "
          "Esc, F8 ou F9 cancelam.")
    try:
        raiz.mainloop()
    except KeyboardInterrupt:
        try:
            raiz.destroy()
        except Exception:
            pass
        return None
    return cast(Optional[tuple[int, ...]], estado["res"])


# --------------------------------------------------------------------------- #
# Recortar botão (item 4)
# --------------------------------------------------------------------------- #
@dataclass
class Analise:
    crop: Img
    avisos: list[str] = field(default_factory=lambda: [])
    ocorrencias: int = 0
    score_proprio: float = 0.0


def contar_ocorrencias(img: Img, crop: Img, limiar: float = 0.9) -> tuple[int, float]:
    """Quantos lugares distintos da imagem casam com o recorte (no tamanho original)."""
    if crop.shape[0] > img.shape[0] or crop.shape[1] > img.shape[1]:
        return 0, 0.0
    res = cast(Img, cv2.matchTemplate(img, crop, cv2.TM_CCOEFF_NORMED))
    melhor = float(res.max())
    pts = np.argwhere(res >= limiar)
    escolhidos: list[tuple[int, int]] = []
    for y, x in sorted(pts.tolist(), key=lambda p: -float(res[p[0], p[1]])):  # pyright: ignore
        if all(abs(x - ex) > crop.shape[1] // 2 or abs(y - ey) > crop.shape[0] // 2
               for ex, ey in escolhidos):
            escolhidos.append((int(x), int(y)))
    return len(escolhidos), melhor


def analisar_recorte(img: Img, rect: Regiao) -> Analise:
    x, y, w, h = rect
    x, y = max(0, x), max(0, y)
    crop = img[y:y + h, x:x + w].copy()
    a = Analise(crop)
    if crop.size == 0:
        a.avisos.append("a seleção está vazia.")
        return a
    ch, cw = crop.shape[:2]
    if cw < 12 or ch < 12:
        a.avisos.append(f"recorte muito pequeno ({cw}x{ch}px): pode casar com qualquer coisa.")
    if cw * ch > 0.25 * img.shape[0] * img.shape[1]:
        a.avisos.append("recorte muito grande (mais de 25% da tela): prefira só o botão.")
    cinza = cast(Img, cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))
    if float(cinza.std()) < 8.0:
        a.avisos.append("recorte quase de uma cor só (sem textura): o reconhecimento será "
                        "instável. Inclua o texto/ícone ou a borda do botão.")
    a.ocorrencias, a.score_proprio = contar_ocorrencias(img, crop)
    if a.ocorrencias == 0:
        a.avisos.append("o recorte não casou nem com a própria tela (confira a seleção).")
    elif a.ocorrencias > 1:
        a.avisos.append(f"o recorte aparece {a.ocorrencias}x na tela: é ambíguo. Se forem "
                        'cartas/botões parecidos, use "escolha" no json; senão recorte de novo '
                        "incluindo algo único.")
    return a


def recortar(nome: str, pasta: str, monitor: int, janela: Optional[str],
             retangulo: Optional[Regiao] = None, imagem: Optional[Img] = None,
             atraso: float = 3.0) -> Analise:
    """Captura a tela, deixa selecionar o botão e salva pasta/nome.png (com avisos)."""
    if imagem is None:
        for i in range(int(atraso), 0, -1):
            print(f"Capturando a tela em {i}... deixe o botão visível.")
            time.sleep(1)
        regiao = None
        if janela:
            rect = m_captura.rect_seguro(janela)
            regiao = m_captura.regiao_da_janela(rect, monitor) if rect else None
            if regiao is None:
                print(f"Aviso: janela '{janela}' não encontrada; usando o monitor inteiro.")
        imagem, _, _, _, _ = m_captura.capturar(monitor, regiao)
    if retangulo is None:
        sel = _tk_mostrar(imagem, f"Arraste um retângulo sobre o botão '{nome}'", True)
        if sel is None or len(sel) < 4:
            sys.exit("Nada selecionado.")
        retangulo = (sel[0], sel[1], sel[2], sel[3])
    a = analisar_recorte(imagem, retangulo)
    if a.crop.size == 0:
        sys.exit("A seleção está vazia.")
    Path(pasta).mkdir(parents=True, exist_ok=True)
    destino = Path(pasta) / f"{nome}.png"
    cv2.imwrite(str(destino), a.crop)
    print(f"Salvo: {destino} ({a.crop.shape[1]}x{a.crop.shape[0]}px). "
          f"Casou {a.ocorrencias}x na tela (certeza {a.score_proprio:.2f}).")
    for av in a.avisos:
        print(f"  ⚠ {av}")
    if not a.avisos:
        print("  ✔ recorte bom (único, com textura e tamanho razoável).")
    print(f'Dica: tire o PNG com a janela no MAIOR tamanho; adicione "{nome}" ao botoes.json.')
    return a


# --------------------------------------------------------------------------- #
# Calibrar cinza / hover (item 11)
# --------------------------------------------------------------------------- #
def recomendar_queda(normal: float, cinza: float,
                     hover: Optional[float] = None) -> tuple[Optional[float], list[str]]:
    """Valor para 'queda_saturacao' (cinza = saturação <= normal * valor)."""
    avisos: list[str] = []
    if normal < 15.0:
        return None, ["o botão normal quase não tem cor (saturação "
                      f"{normal:.0f}): a confirmação por cinza não funciona nele; use "
                      '"confirmar_cinza": false.']
    r_cinza = cinza / normal
    if r_cinza > 0.85:
        return None, [f"o estado cinza ({cinza:.0f}) é quase igual ao normal ({normal:.0f}): "
                      "não dá para distinguir. O botão realmente ficou cinza?"]
    limite = r_cinza + 0.5 * (1.0 - r_cinza) if hover is None else (
        (r_cinza + max(hover / normal, r_cinza)) / 2)
    if hover is not None:
        r_h = hover / normal
        if r_h <= r_cinza + 0.08:
            avisos.append(f"o hover ({hover:.0f}) fica muito perto do cinza ({cinza:.0f}): "
                          "risco de confundir; confirme com --debug no jogo.")
    limite = round(min(max(limite, 0.05), 0.9), 2)
    if r_cinza >= limite:
        limite = round(min(r_cinza + 0.1, 0.95), 2)
    return limite, avisos


def escrever_queda(config: str, nome: str, valor: float) -> None:
    p = Path(config)
    dados: dict[str, Any] = {}
    if p.is_file():
        bruto: Any = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(bruto, dict):
            dados = cast(dict[str, Any], bruto)
    regra = dados.get(nome)
    if not isinstance(regra, dict):
        regra = {"acao": "clicar"}
        dados[nome] = regra
    cast(dict[str, Any], regra)["queda_saturacao"] = valor
    p.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def calibrar(nome: str, pasta: str, config: str, monitor: int, janela: Optional[str],
             confianca: float, atraso: float, escrever: bool = True) -> Optional[float]:
    """Mede a saturação do botão normal, cinza e (opcional) com o mouse em cima."""
    def foto() -> tuple[Img, float, float, int, int]:
        regiao = None
        if janela:
            r = m_captura.rect_seguro(janela)
            regiao = m_captura.regiao_da_janela(r, monitor) if r else None
        return m_captura.capturar(monitor, regiao)

    print(f"Calibrando '{nome}'. 1/3: deixe o botão NORMAL (colorido) visível.")
    input("  Pressione Enter quando estiver pronto... ")
    time.sleep(atraso)
    img, _, _, _, _ = foto()
    achados = [h for h in m_deteccao.detectar_imagens(img, pasta, confianca) if h.rotulo == nome]
    if not achados:
        sys.exit(f"Não achei '{nome}' na tela. Confira o PNG em '{pasta}' (modo recortar).")
    h = max(achados, key=lambda k: k.score)
    s_normal = m_acao.saturacao_media(img, h)
    print(f"  normal: saturação {s_normal:.0f}")
    print("2/3: deixe o botão CINZA (como fica quando não dá para usar).")
    input("  Pressione Enter... ")
    time.sleep(atraso)
    img2, _, _, _, _ = foto()
    s_cinza = m_acao.saturacao_media(img2, h)
    print(f"  cinza: saturação {s_cinza:.0f}")
    print("3/3 (opcional): ponha o mouse EM CIMA do botão normal (hover) ou só Enter para pular.")
    resp = input("  Pressione Enter... ")
    s_hover: Optional[float] = None
    if resp.strip().lower() not in ("pular", "p", "n"):
        time.sleep(atraso)
        img3, _, _, _, _ = foto()
        s_hover = m_acao.saturacao_media(img3, h)
        print(f"  hover: saturação {s_hover:.0f}")
    valor, avisos = recomendar_queda(s_normal, s_cinza, s_hover)
    for a in avisos:
        print(f"  ⚠ {a}")
    if valor is None:
        return None
    print(f"Recomendado: \"queda_saturacao\": {valor}")
    if escrever:
        escrever_queda(config, nome, valor)
        print(f"Gravado em {config}.")
    return valor


# --------------------------------------------------------------------------- #
# Mapa de regras (item 15)
# --------------------------------------------------------------------------- #
CORES = {"clicar": (0, 200, 0), "arrastar": (255, 140, 0), "inicio": (200, 0, 200),
         "ancora": (200, 200, 0), "marcador": (160, 160, 160), "erro": (0, 0, 255)}


def desenhar_mapa(img: Img, hits: list[Hit], regras: dict[str, Regra],
                  esc: tuple[float, float, int, int], rect_jogo: Optional[Regiao],
                  ancoras: Optional[dict[str, Ancora]] = None) -> Img:
    """Desenha caixas dos botões, ações e destinos de arrasto sobre a captura."""
    ex, ey, ox, oy = esc
    out = img.copy()

    def para_img(sx: float, sy: float) -> tuple[int, int]:
        return round((sx - ox) / ex), round((sy - oy) / ey)

    agora = time.time()
    ancs = ancoras or {}
    for h in hits:
        r = regras.get(h.rotulo, Regra())
        cor = CORES.get(r.acao, (0, 200, 0))
        cv2.rectangle(out, (h.x, h.y), (h.x + h.w, h.y + h.h), cor, 2)
        txt = f"{h.rotulo} [{r.acao}]" + (" auto" if r.auto_detect else "")
        cv2.putText(out, txt, (h.x, max(12, h.y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cor, 1,
                    cv2.LINE_AA)
        if r.acao == "arrastar":
            alvo, motivo = resolver_destino(r, rect_jogo, ancs, agora, 1e9)
            if alvo is not None:
                p0 = h.centro
                p1 = para_img(*alvo)
                cv2.arrowedLine(out, p0, p1, cor, 2, tipLength=0.05)
                cv2.drawMarker(out, p1, (0, 0, 255), cv2.MARKER_CROSS, 26, 2)
                cv2.putText(out, "destino", (p1[0] + 8, p1[1] - 8), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (0, 0, 255), 1, cv2.LINE_AA)
            else:
                cv2.putText(out, f"destino ?: {motivo}", (h.x, h.y + h.h + 16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1, cv2.LINE_AA)
    # destinos fixos / de janela de regras cujo botão NÃO está à vista também aparecem
    vistos = {h.rotulo for h in hits}
    for nome, r in regras.items():
        if r.acao == "arrastar" and nome not in vistos:
            alvo, _ = resolver_destino(r, rect_jogo, ancs, agora, 1e9)
            if alvo is not None:
                p1 = para_img(*alvo)
                cv2.drawMarker(out, p1, (0, 140, 255), cv2.MARKER_TILTED_CROSS, 22, 2)
                cv2.putText(out, f"{nome} (fora da tela)", (p1[0] + 8, p1[1] - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 140, 255), 1, cv2.LINE_AA)
    return out


def calcular_destino(ponto_img: tuple[int, int], esc: tuple[float, float, int, int],
                     rect_jogo: Optional[Regiao],
                     ancora: Optional[Ancora] = None, nome_ancora: str = "") -> dict[str, Any]:
    """Converte um clique na captura em 'destino' do json (fração da janela ou âncora)."""
    ex, ey, ox, oy = esc
    sx, sy = ox + ponto_img[0] * ex, oy + ponto_img[1] * ey
    if ancora is not None:
        return {"ancora": nome_ancora,
                "offset": [round((sx - ancora[0]) / ancora[2]), round((sy - ancora[1]) / ancora[3])]}
    if rect_jogo is not None:
        fx = round((sx - rect_jogo[0]) / rect_jogo[2], 4)
        fy = round((sy - rect_jogo[1]) / rect_jogo[3], 4)
        return {"janela": [min(max(fx, 0.0), 1.0), min(max(fy, 0.0), 1.0)]}
    return {"destino_fixo": [round(sx), round(sy)]}


def escrever_destino(config: str, nome: str, destino: dict[str, Any]) -> None:
    p = Path(config)
    dados: dict[str, Any] = {}
    if p.is_file():
        bruto: Any = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(bruto, dict):
            dados = cast(dict[str, Any], bruto)
    regra = dados.get(nome)
    if not isinstance(regra, dict):
        regra = {"acao": "arrastar"}
        dados[nome] = regra
    rd = cast(dict[str, Any], regra)
    rd["acao"] = "arrastar"
    rd["destino"] = destino["destino_fixo"] if "destino_fixo" in destino else destino
    p.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def mapa_regras(pasta: str, config: str, monitor: int, janela: Optional[str], confianca: float,
                regras: dict[str, Regra], saida: str = "mapa_regras.png") -> list[Hit]:
    regiao = None
    rect = m_captura.rect_seguro(janela) if janela else None
    if rect is not None:
        regiao = m_captura.regiao_da_janela(rect, monitor)
    img, ex, ey, ox, oy = m_captura.capturar(monitor, regiao)
    hits = m_deteccao.detectar_imagens(img, pasta, confianca)
    ancs: dict[str, Ancora] = {}
    for h in hits:
        if regras.get(h.rotulo, Regra()).acao == "ancora":
            ax, ay = m_acao.para_tela(h, 0, 0, ex, ey, ox, oy)
            ancs[h.rotulo] = (float(ax), float(ay), h.escala * ex, h.escala * ey, time.time())
    out = desenhar_mapa(img, hits, regras, (ex, ey, ox, oy), rect, ancs)
    cv2.imwrite(saida, out)
    print(f"{len(hits)} botão(ões) à vista. Mapa salvo em {saida} "
          "(verde = clicar, laranja = arrastar, seta/cruz vermelha = destino).")
    return hits


def definir_destino(nome: str, pasta: str, config: str, monitor: int, janela: Optional[str],
                    confianca: float, ancora: Optional[str],
                    ponto: Optional[tuple[int, int]] = None) -> dict[str, Any]:
    regiao = None
    rect = m_captura.rect_seguro(janela) if janela else None
    if rect is not None:
        regiao = m_captura.regiao_da_janela(rect, monitor)
    img, ex, ey, ox, oy = m_captura.capturar(monitor, regiao)
    anc: Optional[Ancora] = None
    if ancora:
        hs = [h for h in m_deteccao.detectar_imagens(img, pasta, confianca) if h.rotulo == ancora]
        if not hs:
            sys.exit(f"Âncora '{ancora}' não está visível agora.")
        h = max(hs, key=lambda k: k.score)
        ax, ay = m_acao.para_tela(h, 0, 0, ex, ey, ox, oy)
        anc = (float(ax), float(ay), h.escala * ex, h.escala * ey, time.time())
    elif rect is None:
        print("Aviso: sem --janela nem --ancora, o destino será FIXO na tela.")
    if ponto is None:
        sel = _tk_mostrar(img, f"Clique no destino do arrasto de '{nome}'", False)
        if sel is None or len(sel) < 2:
            sys.exit("Nenhum ponto escolhido.")
        ponto = (sel[0], sel[1])
    d = calcular_destino(ponto, (ex, ey, ox, oy), rect, anc, ancora or "")
    escrever_destino(config, nome, d)
    print(f"Destino de '{nome}' gravado em {config}: "
          f"{json.dumps(d['destino_fixo'] if 'destino_fixo' in d else d)}")
    return d


# --------------------------------------------------------------------------- #
# Diagnóstico (item 1)
# --------------------------------------------------------------------------- #
def _versao(mod: str) -> str:
    try:
        m = __import__(mod)
        return str(getattr(m, "__version__", "ok"))
    except Exception as e:
        return f"AUSENTE ({type(e).__name__})"


def diagnostico(pasta: str, config: str, monitor: int, janela: Optional[str],
                confianca: float, saida: str = "diagnostico.txt") -> list[str]:
    L: list[str] = []

    def ok(msg: str) -> None:
        L.append(f"✔ {msg}")

    def aviso(msg: str) -> None:
        L.append(f"⚠ {msg}")

    def erro(msg: str) -> None:
        L.append(f"✖ {msg}")

    ok(f"Python {platform.python_version()} em {platform.system()} {platform.release()}")
    for lib in ("cv2", "numpy", "mss"):
        v = _versao(lib)
        (erro if v.startswith("AUSENTE") else ok)(f"{lib}: {v}")
    pt = _versao("pytesseract")
    (aviso if pt.startswith("AUSENTE") else ok)(
        f"pytesseract: {pt}" + (" (só necessário nos modos texto/auto)" if pt.startswith("AUSENTE") else ""))
    win = sys.platform == "win32"
    if not win:
        aviso("não é Windows: mouse/teclado/janelas não podem ser testados aqui.")
    else:
        try:
            m_windows.api()
            ok("API do Windows carregada (DPI aware ligado)")
            x0, y0 = m_windows.posicao()
            m_windows.mover_real(x0 + 1, y0 + 1)
            time.sleep(0.05)
            x1, y1 = m_windows.posicao()
            m_windows.mover_real(x0, y0)
            (ok if (x1, y1) == (x0 + 1, y0 + 1) else aviso)(
                f"SendInput: pediu ({x0 + 1},{y0 + 1}), cursor foi para ({x1},{y1})"
                + ("" if (x1, y1) == (x0 + 1, y0 + 1)
                   else " — diferença indica escala de tela/DPI; clique pode errar o alvo"))
            m_windows.pressionada("parar")
            ok("leitura de teclas (F8 pausa / F9 para) funcionando")
        except Exception as e:
            erro(f"API do Windows: {type(e).__name__}: {e}")
    rect: Optional[Regiao] = None
    regiao: Optional[Regiao] = None
    if janela:
        rect = m_captura.rect_seguro(janela)
        if rect is None:
            erro(f"janela '{janela}' não encontrada (aberta? minimizada? título certo?)")
        else:
            ok(f"janela '{janela}': {rect[2]}x{rect[3]} em ({rect[0]},{rect[1]})")
            regiao = m_captura.regiao_da_janela(rect, monitor)
            if win:
                (ok if m_windows.janela_ativa(janela) else aviso)(
                    "janela " + ("ativa" if m_windows.janela_ativa(janela)
                                 else "NÃO está ativa agora (clique nela antes de iniciar)"))
    else:
        aviso("sem --janela/\"_janela\": a busca usa a tela inteira.")
    try:
        t0 = time.time()
        img, ex, _, _, _ = m_captura.capturar(monitor, regiao)
        for _ in range(2):
            m_captura.capturar(monitor, regiao)
        dt = (time.time() - t0) / 3
        ok(f"captura: {img.shape[1]}x{img.shape[0]}px em {dt * 1000:.0f} ms (escala {ex:.2f})")
        if dt > 0.25:
            aviso("captura lenta (>250 ms): reduza a janela do jogo ou use --regiao")
        if Path(pasta).is_dir():
            t0 = time.time()
            hits = m_deteccao.detectar_imagens(img, pasta, confianca)
            tpl = len(m_deteccao.carregar_templates(pasta))
            ok(f"{tpl} PNG(s) em '{pasta}'; {len(hits)} reconhecido(s) agora "
               f"({(time.time() - t0) * 1000:.0f} ms)")
            for h in hits:
                ok(f"   {h.rotulo}: certeza {h.score:.2f}, escala {h.escala:.2f}")
            if tpl and not hits:
                aviso("nenhum botão reconhecido agora (jogo na tela? mesmo tamanho dos PNGs?)")
        else:
            erro(f"pasta '{pasta}' não existe")
    except Exception as e:
        erro(f"captura/detecção: {type(e).__name__}: {e}")
    for p in validar_config(config, pasta, janela):
        L.append(str(p))
    if not any(s.startswith("✖") for s in L):
        L.append("Resultado: pronto para um teste real (use --preview e depois rode sem ele).")
    else:
        L.append("Resultado: há problemas (✖) acima; corrija antes de usar.")
    Path(saida).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"\n(Relatório salvo em {saida}; mande esse arquivo se precisar de ajuda.)")
    return L


def detectar_jogo(monitor: int, janela: Optional[str], confianca: float,
                  saida: str = "jogo_detectado.txt") -> Optional[str]:
    """Olha a tela uma vez e diz qual jogo cadastrado aparece (pelos PNGs da "assinatura").

    Grava o nome da pasta do jogo em `saida` (vazio se nenhum) e imprime o resultado."""
    from . import jogos as m_jogos
    rect = m_captura.rect_seguro(janela) if janela else None
    regiao = m_captura.regiao_da_janela(rect, monitor) if rect else None
    img, _, _, _, _ = m_captura.capturar(monitor, regiao)
    melhor: Optional[tuple[int, float, str, str]] = None
    for j in m_jogos.listar():
        if j.geral or not j.assinatura:
            continue
        pasta_j = str(m_jogos.pasta_do(j.slug) / "botoes")
        hits = m_deteccao.detectar_imagens(img, pasta_j, confianca)
        vistos = {h.rotulo: h.score for h in hits if h.rotulo in j.assinatura}
        if vistos:
            cand = (len(vistos), sum(vistos.values()), j.slug, j.nome)
            if melhor is None or cand[:2] > melhor[:2]:
                melhor = cand
    slug = melhor[2] if melhor else ""
    Path(saida).write_text(slug, encoding="utf-8")
    if melhor:
        print(f"✔ Jogo reconhecido pela tela: {melhor[3]} ({melhor[0]} sinal(is))")
    else:
        print("Nenhum jogo cadastrado foi reconhecido pela tela (cadastre PNGs na 'assinatura' do jogo).")
    return slug or None


__all__ = ["detectar_jogo", "recortar", "calibrar", "mapa_regras", "definir_destino", "diagnostico",
           "analisar_recorte", "recomendar_queda", "desenhar_mapa", "calcular_destino",
           "NAO_CLICAVEIS", "relatorio"]
