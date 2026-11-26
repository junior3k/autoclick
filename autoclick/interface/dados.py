"""Dados da janela: configurações da GUI, botoes.json, gravação e lista de janelas.

Só biblioteca padrão (sem OpenCV/NumPy): a janela abre mesmo com dependências faltando.
"""
from __future__ import annotations

import contextlib
import json
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Generator, Optional, cast

from .. import windows as m_windows

ARQ_GUI = "autoclick_gui.json"


@dataclass
class Geral:
    # comuns
    janela: str = ""
    pasta: str = "botoes"
    config: str = "botoes.json"
    gravacao: str = "gravacao.json"
    monitor: int = 1
    confianca: float = 0.85
    tema: str = "escuro"
    minimizar: bool = True
    # gravar
    atraso: int = 3
    ancora: str = ""
    gerar_regras: bool = True
    sobrescrever: bool = False
    teclado: bool = True
    duracao: float = 0.0
    # reproduzir
    velocidade: float = 1.0
    repeticao: str = "uma"  # uma | n | loop
    voltas: int = 2
    pausa_loop: float = 1.0
    auto_detect: bool = True
    checar_janela: bool = True
    auto_max: float = 120.0
    # automático
    modo_auto: str = "imagem"
    intervalo: float = 1.5
    cooldown: float = 10.0
    variacao: float = 0.0
    escala: str = "auto"
    painel: float = 0.0
    inatividade: float = 0.0
    ao_travar: str = "avisar"
    janela_max: float = 120.0
    max_cliques: int = 0
    duracao_auto: float = 0.0
    log: str = ""
    relatorio: str = ""
    palavras: str = "ok aceitar continuar proximo"
    pagina: str = "gravar"
    # atalhos (valem para a janela e para os processos)
    tecla_pausa: str = "F8"
    tecla_parar: str = "F9"
    tecla_gravar: str = "F10"
    tecla_reproduzir: str = "F11"
    som_volta: bool = False  # sino suave ao concluir cada volta do loop
    som_gravacao: bool = True   # toque ao iniciar e outro ao parar a gravação
    som_reproducao: bool = True  # toque ao iniciar e outro ao parar a reprodução/rotina
    som_contagem: bool = False   # tique a cada segundo da contagem inicial
    som_tipo: str = "sino"   # sino | gota | marimba | discreto | arquivo
    som_volume: float = 37.0  # 0 a 100 %
    som_arquivo: str = ""    # .wav do usuário (som_tipo = arquivo)
    # jogos do Roblox
    jogo: str = ""           # "" ou "geral" = Roblox (geral); senão o nome da pasta em jogos/
    pasta_geral: str = "botoes"          # o "Roblox (geral)" guarda aqui o que ficou de lado
    config_geral: str = "botoes.json"    # quando um jogo está escolhido
    gravacao_geral: str = "gravacao.json"
    detectar_jogo: bool = True
    jogos_migrado: bool = False
    avisou_novidades: str = ""  # última versão cujas novidades já foram mostradas
    # segurança / robustez
    tela_parada: float = 0.0  # segundos sem a tela mudar (0 = desligado)
    captura_erro: bool = True
    previa_viva: bool = True
    # avisos
    notificar_windows: bool = True
    webhook: str = ""
    bandeja: bool = True
    ao_fechar_bandeja: bool = False
    # atualização
    url_atualizacao: str = ""
    f11_rotina: bool = False  # F11/bandeja iniciam a rotina do jogo em vez da gravação
    atualizar_ao_abrir: bool = True
    atualizar_ao_fechar: bool = True  # instala ao fechar a atualização que já foi baixada


def carregar_geral(caminho: str = ARQ_GUI) -> Geral:
    g = Geral()
    p = Path(caminho)
    if not p.is_file():
        return g
    try:
        bruto: Any = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return g
    if not isinstance(bruto, dict):
        return g
    dados = cast(dict[str, Any], bruto)
    for f in fields(Geral):
        if f.name in dados:
            atual = getattr(g, f.name)
            novo = dados[f.name]
            try:
                if isinstance(atual, bool):
                    setattr(g, f.name, bool(novo))
                elif isinstance(atual, int):
                    setattr(g, f.name, int(novo))
                elif isinstance(atual, float):
                    setattr(g, f.name, float(novo))
                else:
                    setattr(g, f.name, str(novo))
            except (TypeError, ValueError):
                pass
    return g


def salvar_geral(g: Geral, caminho: str = ARQ_GUI) -> None:
    try:
        Path(caminho).write_text(json.dumps(asdict(g), ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# botoes.json
# --------------------------------------------------------------------------- #
def ler_config(caminho: str) -> dict[str, Any]:
    p = Path(caminho)
    if not p.is_file():
        return {}
    try:
        bruto: Any = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError(f"{caminho} não é um JSON válido")
    if not isinstance(bruto, dict):
        raise ValueError(f"{caminho} deve ser um objeto JSON")
    return cast(dict[str, Any], bruto)


def escrever_config(caminho: str, dados: dict[str, Any]) -> None:
    Path(caminho).write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")


def listar_pngs(pasta: str) -> list[str]:
    p = Path(pasta)
    if not p.is_dir():
        return []
    return sorted({f.stem for f in p.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg")})


def caminho_png(pasta: str, nome: str) -> Optional[Path]:
    for ext in (".png", ".jpg", ".jpeg"):
        c = Path(pasta) / f"{nome}{ext}"
        if c.is_file():
            return c
    return None


def regras_de(dados: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {k: cast(dict[str, Any], v) for k, v in dados.items()
            if not k.startswith("_") and isinstance(v, dict)}


def lista_fluxo(dados: dict[str, Any]) -> list[dict[str, Any]]:
    f: Any = dados.get("_fluxo")
    if not isinstance(f, list):
        return []
    return [cast(dict[str, Any], e) for e in cast(list[Any], f) if isinstance(e, dict)]


def resumo_gravacao(arquivo: str) -> str:
    """Texto curto sobre a gravação: eventos, duração, janela."""
    p = Path(arquivo)
    if not p.is_file():
        return "Nenhuma gravação ainda. Clique em “Iniciar gravação”."
    try:
        d: Any = json.loads(p.read_text(encoding="utf-8"))
        ev = cast(list[dict[str, Any]], d.get("eventos", []))
    except (OSError, ValueError, AttributeError):
        return "Arquivo de gravação ilegível."
    if not ev:
        return "Gravação vazia."
    dur = max(float(e.get("t", 0)) for e in ev)
    try:
        dur += max(0.0, float(d.get("cauda", 0) or 0))  # espera depois da última ação
    except (TypeError, ValueError):
        pass
    cliques = sum(1 for e in ev if e.get("tipo") == "clique")
    arrastos = sum(1 for e in ev if e.get("tipo") == "arrasto")
    teclas = sum(1 for e in ev if e.get("tipo") == "tecla")
    j: Any = d.get("janela")
    jt = cast(dict[str, Any], j).get("titulo") if isinstance(j, dict) else None
    m, s = divmod(int(dur), 60)
    txt = f"{len(ev)} eventos · {m}:{s:02d} · {cliques} cliques, {arrastos} arrastos, {teclas} teclas"
    return txt + (f" · janela “{jt}”" if jt else "")


def listar_janelas() -> list[str]:
    """Títulos das janelas visíveis (só Windows; em outros sistemas devolve [])."""
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    titulos: list[str] = []
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd: Any, _l: Any) -> bool:
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n > 0:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if buf.value.strip():
                    titulos.append(buf.value)
        return True

    user32.EnumWindows(proto(cb), 0)
    return sorted(set(titulos), key=str.lower)


def dependencias() -> list[tuple[str, bool, bool, str]]:
    """(nome, instalada, obrigatoria, para_que_serve)."""
    import importlib.util

    from ..opcionais import achar_tesseract

    def tem(m: str) -> bool:
        return importlib.util.find_spec(m) is not None

    return [
        ("OpenCV (opencv-python-headless)", tem("cv2"), True, "reconhecer botões por imagem"),
        ("NumPy", tem("numpy"), True, "processar imagens"),
        ("mss", tem("mss"), True, "capturar a tela"),
        ("pytesseract", tem("pytesseract"), False, "OCR: modos texto e auto"),
        ("Tesseract OCR (programa)", achar_tesseract() is not None, False,
         "OCR: modos texto e auto"),
    ]


# --------------------------------------------------------------------------- #
# perfis (mesmo formato do --perfil da linha de comando)
# --------------------------------------------------------------------------- #
_MAPA_PERFIL = {"janela": "janela", "pasta": "pasta", "config": "config", "arquivo": "gravacao",
                "monitor": "monitor", "confianca": "confianca", "intervalo": "intervalo",
                "cooldown": "cooldown", "variacao": "variacao", "log": "log",
                "relatorio": "relatorio", "painel": "painel", "inatividade": "inatividade"}


def listar_perfis(pasta: str = "perfis") -> list[str]:
    p = Path(pasta)
    return sorted(f.stem for f in p.glob("*.json")) if p.is_dir() else []


def aplicar_perfil(g: Geral, perfil: dict[str, Any]) -> list[str]:
    """Copia as opções do perfil para as configurações. Devolve os nomes aplicados."""
    aplicados: list[str] = []
    for chave, campo in _MAPA_PERFIL.items():
        if chave in perfil:
            atual = getattr(g, campo)
            try:
                novo: Any = type(atual)(perfil[chave])
            except (TypeError, ValueError):
                continue
            setattr(g, campo, novo)
            aplicados.append(chave)
    modo = perfil.get("modo")
    if modo in ("imagem", "texto", "auto"):
        g.modo_auto = str(modo)
        aplicados.append("modo")
    return aplicados


def ler_perfil(nome: str, pasta: str = "perfis") -> dict[str, Any]:
    bruto: Any = json.loads((Path(pasta) / f"{nome}.json").read_text(encoding="utf-8"))
    if not isinstance(bruto, dict):
        raise ValueError("o perfil deve ser um objeto JSON")
    return cast(dict[str, Any], bruto)


# --------------------------------------------------------------------------- #
# ambiente dos processos, atalhos globais, tamanho de janela
# --------------------------------------------------------------------------- #
ARQ_PREVIA = "previa_viva.png"


def ambiente(g: Geral) -> dict[str, str]:
    """Variáveis que a janela repassa a cada processo (teclas, webhook, captura, prévia)."""
    env = {"AUTOCLICK_SOM": "1" if g.som_volta else "0",
           "AUTOCLICK_SOM_GRAVAR": "1" if g.som_gravacao else "0",
           "AUTOCLICK_SOM_REPRO": "1" if g.som_reproducao else "0",
           "AUTOCLICK_SOM_TIQUE": "1" if g.som_contagem else "0",
           "AUTOCLICK_SOM_TIPO": g.som_tipo, "AUTOCLICK_SOM_VOLUME": f"{g.som_volume:g}",
           "AUTOCLICK_SOM_ARQUIVO": g.som_arquivo,
           "AUTOCLICK_JOGO": "" if g.jogo.strip() in ("", "geral") else g.jogo.strip(),
           "AUTOCLICK_GERAL_PASTA": "" if g.jogo.strip() in ("", "geral") else g.pasta_geral,
           "AUTOCLICK_GERAL_CONFIG": "" if g.jogo.strip() in ("", "geral") else g.config_geral,
           "AUTOCLICK_TECLAS": f"pausa={g.tecla_pausa};parar={g.tecla_parar};gravar={g.tecla_gravar};reproduzir={g.tecla_reproduzir}",
           "AUTOCLICK_CAPTURA_ERRO": "1" if g.captura_erro else "0",
           "AUTOCLICK_WEBHOOK": g.webhook.strip()}
    if g.previa_viva:
        env["AUTOCLICK_PREVIA"] = str(Path(ARQ_PREVIA).resolve())
    return env


def vk_de_nome(nome: str) -> Optional[int]:
    """'F8' -> 0x77 ('Ctrl+F11' -> a tecla principal). None se não reconhece."""
    return m_windows.vk_de_nome(nome)


def tecla_global_pressionada(nome: str) -> bool:
    """Atalho (tecla ou combinação) apertado agora, mesmo com a janela em segundo plano (só Windows)."""
    if sys.platform != "win32":
        return False
    a = m_windows.analisar_atalho(nome)
    if a is None:
        return False
    try:
        return m_windows.atalho_pressionado(a, estado_global)
    except Exception:
        return False


def estado_global(vk: int) -> bool:
    """Tecla apertada agora, de qualquer janela (só Windows)."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)  # type: ignore[attr-defined]
    except Exception:
        return False


def aviso_atalho(nome: str) -> Optional[str]:
    """Motivo para pensar duas vezes antes de usar este atalho (ou None)."""
    a = m_windows.analisar_atalho(nome)
    if a is not None and not a[0] and (chr(a[1]).isalnum() if 0x30 <= a[1] <= 0x5A else False):
        return ("Letras e números sozinhos costumam ser teclas do jogo e o atalho disparia enquanto você "
                "joga. Prefira F1–F24 ou uma combinação com Ctrl/Alt/Shift.")
    return None


def teclas_validas(pausa: str, parar: str, gravar: str, reproduzir: str = "F11") -> Optional[str]:
    """None se as teclas servem; senão, o motivo."""
    nomes = {"pausa": pausa, "parar": parar, "gravar": gravar, "reproduzir": reproduzir}
    for k, v in nomes.items():
        if m_windows.normalizar_atalho(v) is None:
            return (f"O atalho de {k} (“{v}”) não é válido. Use F1 a F24, uma letra, um número, Insert/Home/"
                    "PageUp…, teclado numérico, com Ctrl, Alt ou Shift antes se quiser (ex.: Ctrl+F11).")
    if len({m_windows.normalizar_atalho(v) for v in nomes.values()}) < len(nomes):
        return "Os atalhos precisam ser todos diferentes."
    return None


@contextlib.contextmanager
def _pixels_reais() -> Generator[None, None, None]:
    """Nesta thread, as medidas do Windows voltam em pixels reais (como no processo que grava),
    mesmo que a janela do programa não seja marcada como "DPI aware"."""
    antigo: Any = None
    fn: Any = None
    if sys.platform == "win32":
        try:
            import ctypes
            fn = ctypes.windll.user32.SetThreadDpiAwarenessContext  # type: ignore[attr-defined]
            fn.argtypes = [ctypes.c_void_p]
            fn.restype = ctypes.c_void_p
            antigo = fn(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
        except Exception:
            fn = None
    try:
        yield
    finally:
        if fn is not None and antigo:
            try:
                fn(antigo)
            except Exception:
                pass


def tamanho_da_janela(titulo: str) -> Optional[tuple[int, int]]:
    """Largura x altura atual da janela cujo título contém `titulo` (Windows)."""
    if sys.platform != "win32" or not titulo.strip():
        return None
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32  # type: ignore[attr-defined]
        achada: list[tuple[int, int]] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def cb(h: Any, _l: Any) -> bool:
            if not u.IsWindowVisible(h):
                return True
            n = u.GetWindowTextLengthW(h)
            buf = ctypes.create_unicode_buffer(n + 1)
            u.GetWindowTextW(h, buf, n + 1)
            if titulo.lower() in buf.value.lower():
                r = wintypes.RECT()
                u.GetClientRect(h, ctypes.byref(r))
                if r.right > 0:
                    achada.append((r.right, r.bottom))
                    return False
            return True

        with _pixels_reais():
            u.EnumWindows(cb, 0)
        return achada[0] if achada else None
    except Exception:
        return None


def referencia_gravacao(caminho: str) -> Optional[dict[str, Any]]:
    """Metadados de ambiente guardados na gravação (tela, DPI, janela), se existirem."""
    try:
        d = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    dd = cast(dict[str, Any], d)
    return {"tela": dd.get("tela"), "janela": dd.get("janela"), "editado": bool(dd.get("editado"))}


def comparar_ambiente(ref: Optional[dict[str, Any]], janela: str,
                      tela_atual: Optional[tuple[int, int]] = None,
                      janela_atual: Optional[tuple[int, int]] = None) -> list[str]:
    """Avisos (texto) de diferença entre a gravação e o ambiente atual. Pura, testável."""
    if not ref:
        return []
    out: list[str] = []
    t = cast(Any, ref.get("tela"))
    if isinstance(t, dict) and tela_atual and t.get("largura") and (
            (t.get("largura"), t.get("altura")) != tela_atual):
        out.append(f"tela {t.get('largura')}x{t.get('altura')} na gravação, {tela_atual[0]}x{tela_atual[1]} agora")
    j = cast(Any, ref.get("janela"))
    rect = cast(Any, j.get("rect")) if isinstance(j, dict) else None
    if isinstance(rect, list) and janela_atual and len(cast(list[Any], rect)) == 4:
        r4 = cast(list[Any], rect)
        w, h = int(r4[2]), int(r4[3])
        if janela and (w, h) != janela_atual and abs(w - janela_atual[0]) + abs(h - janela_atual[1]) > 4:
            out.append(f"janela {w}x{h} na gravação, {janela_atual[0]}x{janela_atual[1]} agora")
    return out


def tamanho_da_tela() -> Optional[tuple[int, int]]:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        u = ctypes.windll.user32  # type: ignore[attr-defined]
        with _pixels_reais():
            return int(u.GetSystemMetrics(0)), int(u.GetSystemMetrics(1))
    except Exception:
        return None


def atualizar_referencia(caminho: str, tela: Optional[tuple[int, int]],
                         janela: Optional[tuple[int, int]]) -> bool:
    """Passa a usar o tamanho de tela/janela ATUAL como referência da gravação."""
    try:
        d = cast(dict[str, Any], json.loads(Path(caminho).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return False
    if tela:
        info = cast(dict[str, Any], d.get("tela") if isinstance(d.get("tela"), dict) else {})
        info.update({"largura": tela[0], "altura": tela[1]})
        d["tela"] = info
    j = d.get("janela")
    if janela and isinstance(j, dict):
        jd = cast(dict[str, Any], j)
        rect = cast(Any, jd.get("rect"))
        if isinstance(rect, list) and len(cast(list[Any], rect)) == 4:
            r4 = cast(list[Any], rect)
            jd["rect"] = [r4[0], r4[1], janela[0], janela[1]]
    try:
        Path(caminho).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True


# --------------------------------------------------------------------------- #
# histórico de sessões
# --------------------------------------------------------------------------- #
def agregar_historico(sessoes: list[dict[str, Any]], dias: int = 7,
                      hoje: Optional[str] = None) -> dict[str, Any]:
    """Totais e ações por dia (últimos `dias`, terminando em `hoje` = AAAA-MM-DD)."""
    from datetime import date, timedelta
    fim = date.fromisoformat(hoje) if hoje else date.today()
    ult = [(fim - timedelta(days=i)).isoformat() for i in range(dias - 1, -1, -1)]
    por_dia = {d: 0 for d in ult}
    acoes = partidas = falhas = 0
    seg = 0.0
    for s in sessoes:
        a = int(s.get("total_acoes", 0) or 0)
        acoes += a
        partidas += int(s.get("partidas", 0) or 0)
        seg += float(s.get("duracao_seg", 0) or 0)
        f = s.get("falhas")
        if isinstance(f, dict):
            falhas += sum(int(v) for v in cast(dict[str, Any], f).values())
        dia = str(s.get("fim", s.get("inicio", "")))[:10]
        if dia in por_dia:
            por_dia[dia] += a
    return {"sessoes": len(sessoes), "acoes": acoes, "partidas": partidas, "falhas": falhas,
            "segundos": seg, "por_dia": [(d[5:].replace("-", "/"), por_dia[d]) for d in ult]}


def formatar_duracao(seg: float) -> str:
    s = int(round(seg))
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h}h{m:02d}m" if h else (f"{m}m{s:02d}s" if m else f"{s}s")


def ler_historico(caminho: str = "historico/sessoes.jsonl") -> list[dict[str, Any]]:
    """Sessões gravadas pelo programa (uma por linha JSON). Linhas quebradas são ignoradas."""
    p = Path(caminho)
    out: list[dict[str, Any]] = []
    if not p.is_file():
        return out
    for linha in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(linha)
        except ValueError:
            continue
        if isinstance(d, dict):
            out.append(cast(dict[str, Any], d))
    return out


# --------------------------------------------------------------------------- #
# instalação de dependências opcionais
# --------------------------------------------------------------------------- #
def comando_instalar_pytesseract() -> Optional[list[str]]:
    """Comando que instala o pytesseract (ou None se não der, ex.: no .exe empacotado)."""
    import shutil
    if getattr(sys, "frozen", False):
        return None
    if shutil.which("uv") and Path("pyproject.toml").is_file():
        return ["uv", "sync", "--extra", "ocr"]
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe") and Path(exe[:-len("pythonw.exe")] + "python.exe").exists():
        exe = exe[:-len("pythonw.exe")] + "python.exe"
    return [exe, "-m", "pip", "install", "pytesseract"]


def comando_instalar_tesseract() -> Optional[list[str]]:
    """winget do Windows 10/11, se existir."""
    import shutil
    if sys.platform != "win32" or not shutil.which("winget"):
        return None
    return ["winget", "install", "--id", "UB-Mannheim.TesseractOCR", "-e",
            "--accept-package-agreements", "--accept-source-agreements"]


URL_TESSERACT = "https://github.com/UB-Mannheim/tesseract/wiki"
