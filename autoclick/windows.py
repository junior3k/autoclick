"""Camada Windows (ctypes): janelas, mouse e teclado reais, sem dependências externas."""
from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
from typing import Any, Callable, Optional

from .tipos import Regiao


# --------------------------------------------------------------------------- #
# Camada Windows (ctypes, sem pyautogui): janelas, mouse e teclado "de verdade"
# --------------------------------------------------------------------------- #
class FailSafe(Exception):
    """Mouse no canto superior esquerdo da tela: abortar."""

_api_cache: Optional[tuple[Any, Any]] = None

def api() -> tuple[Any, Any]:
    """(user32, kernel32) com os tipos dos argumentos definidos (evita truncar handles)."""
    global _api_cache
    if _api_cache is not None:
        return _api_cache
    from ctypes import wintypes

    windll: Any = getattr(ctypes, "windll")
    u: Any = windll.user32
    k: Any = windll.kernel32
    try:
        u.SetProcessDPIAware()  # coordenadas em pixels reais (telas com zoom 125%/150%)
    except Exception:
        pass
    u.WindowFromPoint.argtypes = [wintypes.POINT]
    u.WindowFromPoint.restype = wintypes.HWND
    u.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    u.GetAncestor.restype = wintypes.HWND
    u.GetForegroundWindow.restype = wintypes.HWND
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u.GetWindowThreadProcessId.restype = wintypes.DWORD
    u.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    u.SetForegroundWindow.argtypes = [wintypes.HWND]
    u.IsIconic.argtypes = [wintypes.HWND]
    u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    u.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    u.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    u.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    u.MapVirtualKeyW.restype = wintypes.UINT
    k.GetConsoleWindow.restype = wintypes.HWND
    _api_cache = (u, k)
    return _api_cache

def posicao() -> tuple[int, int]:
    """Posição atual do cursor (pixels de tela)."""
    from ctypes import wintypes

    u, _ = api()
    pt = wintypes.POINT()
    u.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)

def limites_tela() -> tuple[int, int, int, int]:
    """(x, y, largura, altura) da área virtual (todos os monitores)."""
    u, _ = api()
    return (int(u.GetSystemMetrics(76)), int(u.GetSystemMetrics(77)),
            int(u.GetSystemMetrics(78)), int(u.GetSystemMetrics(79)))

def tamanho_tela() -> tuple[int, int]:
    """Largura e altura do monitor principal."""
    u, _ = api()
    return int(u.GetSystemMetrics(0)), int(u.GetSystemMetrics(1))

def checar_failsafe() -> None:
    x, y = posicao()
    if x <= 1 and y <= 1:
        raise FailSafe()

def _titulo_de(hwnd: Any) -> str:
    u, _ = api()
    buf = ctypes.create_unicode_buffer(512)
    u.GetWindowTextW(hwnd, buf, 512)
    return str(buf.value)

def _raiz(hwnd: Any) -> Any:
    u, _ = api()
    return u.GetAncestor(hwnd, 2) or hwnd  # GA_ROOT

def titulo_sob_ponto(x: int, y: int) -> Optional[str]:
    """Título da janela (de nível superior) sob o ponto (x, y); None se não achar."""
    if sys.platform != "win32":
        return None
    try:
        from ctypes import wintypes

        u, _ = api()
        hwnd = u.WindowFromPoint(wintypes.POINT(x, y))
        if not hwnd:
            return None
        t = _titulo_de(_raiz(hwnd))
        return t or None
    except Exception:
        return None

def titulo_ativo() -> Optional[str]:
    """Título da janela em primeiro plano."""
    if sys.platform != "win32":
        return None
    try:
        u, _ = api()
        h = u.GetForegroundWindow()
        return (_titulo_de(_raiz(h)) or None) if h else None
    except Exception:
        return None

def achar_janela(titulo: str) -> Optional[int]:
    """Procura uma janela visível cujo título contém 'titulo' (sem diferenciar
    maiúsculas). Prefere título igual > começa com > contém, e a maior janela. Ignora
    o próprio terminal (o comando com o nome da janela aparece no título dele)."""
    if sys.platform != "win32" or not titulo:
        return None
    u, k = api()
    alvo = titulo.casefold()
    console = int(k.GetConsoleWindow() or 0)
    achados: list[tuple[int, int, int]] = []

    def cb(hwnd: Any, _lp: Any) -> bool:
        if not u.IsWindowVisible(hwnd) or int(hwnd or 0) == console:
            return True
        t = _titulo_de(hwnd).casefold()
        if not t or alvo not in t:
            return True
        prio = 0 if t == alvo else (1 if t.startswith(alvo) else 2)
        r = retangulo_janela(int(hwnd))
        achados.append((prio, -(r[2] * r[3] if r else 0), int(hwnd)))
        return True

    proto: Any = getattr(ctypes, "WINFUNCTYPE")(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    u.EnumWindows(proto(cb), 0)
    return min(achados)[2] if achados else None

def retangulo_janela(hwnd: int) -> Optional[Regiao]:
    """Área CLIENTE (sem bordas/título) da janela em coordenadas de tela:
    (esquerda, topo, largura, altura). None se minimizada ou sem tamanho."""
    from ctypes import wintypes

    u, _ = api()
    if u.IsIconic(hwnd):
        return None
    r = wintypes.RECT()
    if not u.GetClientRect(hwnd, ctypes.byref(r)):
        return None
    w, h = int(r.right - r.left), int(r.bottom - r.top)
    if w <= 0 or h <= 0:
        return None
    pt = wintypes.POINT(0, 0)
    u.ClientToScreen(hwnd, ctypes.byref(pt))
    return int(pt.x), int(pt.y), w, h

def rect_da_janela(titulo: str) -> Optional[Regiao]:
    """Atalho: área cliente da janela com esse título (ou None)."""
    hwnd = achar_janela(titulo)
    return retangulo_janela(hwnd) if hwnd else None

def janela_ativa(titulo: str) -> bool:
    """True se a janela em primeiro plano tem esse título."""
    if sys.platform != "win32":
        return True
    u, _ = api()
    atual = u.GetForegroundWindow()
    if not atual:
        return False
    return titulo.casefold() in _titulo_de(_raiz(atual)).casefold()

def focar_hwnd(raiz: Any) -> bool:
    """Traz a janela 'raiz' para o primeiro plano. True se ela ficou em foco."""
    u, k = api()
    atual = u.GetForegroundWindow()
    if atual == raiz:
        return True
    # O Windows só deixa trazer uma janela para frente se anexarmos a thread da atual.
    tid_atual = int(u.GetWindowThreadProcessId(atual, None)) if atual else 0
    tid_nosso = int(k.GetCurrentThreadId())
    anexado = False
    if tid_atual and tid_atual != tid_nosso:
        anexado = bool(u.AttachThreadInput(tid_atual, tid_nosso, True))
    try:
        if u.IsIconic(raiz):
            u.ShowWindow(raiz, 9)  # SW_RESTORE (só se estiver minimizada)
        u.SetForegroundWindow(raiz)
    finally:
        if anexado:
            u.AttachThreadInput(tid_atual, tid_nosso, False)
    time.sleep(0.2)
    return bool(u.GetForegroundWindow() == raiz)

def trazer_janela_para_frente(x: int, y: int) -> bool:
    """Windows: traz para o primeiro plano a janela que está sob o ponto (x, y).

    Retorna True se a janela já estava (ou ficou) em foco.
    """
    if sys.platform != "win32":
        return False
    from ctypes import wintypes

    u, _ = api()
    hwnd = u.WindowFromPoint(wintypes.POINT(x, y))
    if not hwnd:
        return False
    return focar_hwnd(_raiz(hwnd))

# --------------------------------------------------------------------------- #
# Mouse "de verdade" (SendInput): gera eventos reais de movimento, que jogos usam
# para ativar o hover (SetCursorPos só teletransporta o ponteiro, sem esses eventos).
# --------------------------------------------------------------------------- #
class _MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_int32),
        ("dy", ctypes.c_int32),
        ("mouseData", ctypes.c_uint32),
        ("dwFlags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_size_t),
    ]

class _KeybdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_uint16),
        ("wScan", ctypes.c_uint16),
        ("dwFlags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_size_t),
    ]

class _InputUnion(ctypes.Union):
    _fields_ = [("mi", _MouseInput), ("ki", _KeybdInput)]

class _Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint32), ("u", _InputUnion)]

_MOVE = 0x0001

LEFTDOWN = 0x0002

LEFTUP = 0x0004

_VIRTUALDESK = 0x4000

_ABSOLUTE = 0x8000

def enviar_mouse(dx: int, dy: int, flags: int) -> None:
    u, _ = api()
    entrada = _Input(type=0, u=_InputUnion(mi=_MouseInput(dx, dy, 0, flags, 0, 0)))
    u.SendInput(1, ctypes.byref(entrada), ctypes.sizeof(entrada))

def mover_real(px: int, py: int) -> None:
    """Move o cursor para (px, py) enviando um evento de mouse real."""
    vx, vy, vw, vh = limites_tela()
    nx = round((px - vx) * 65535 / max(1, vw - 1))
    ny = round((py - vy) * 65535 / max(1, vh - 1))
    enviar_mouse(nx, ny, _MOVE | _ABSOLUTE | _VIRTUALDESK)

def mover_suave(px: int, py: int, duracao: float = 0.3, passos: int = 18) -> None:
    """Trajetória curta com vários eventos reais de movimento até (px, py)."""
    checar_failsafe()
    x0, y0 = posicao()
    for i in range(1, passos + 1):
        t = i / passos
        e = 1 - (1 - t) ** 2  # desacelera ao chegar
        mover_real(round(x0 + (px - x0) * e), round(y0 + (py - y0) * e))
        time.sleep(duracao / passos)

def estacionar_mouse(px: int, py: int, destino: Optional[tuple[int, int]] = None) -> None:
    """Afasta o cursor do botão para o hover não atrapalhar a próxima detecção.

    Sem destino definido, vai 350 px para o lado (só passa o mouse, não clica).
    """
    largura, altura = tamanho_tela()
    if destino is None:
        alvo_x = px + 350 if px + 350 < largura - 20 else px - 350
        alvo_y = py
    else:
        alvo_x, alvo_y = destino
    # Evita os cantos da tela (o canto superior esquerdo aciona o failsafe).
    alvo_x = min(max(alvo_x, 20), largura - 20)
    alvo_y = min(max(alvo_y, 20), altura - 20)
    time.sleep(0.1)  # deixa o clique terminar de ser registrado
    mover_suave(alvo_x, alvo_y, duracao=0.25, passos=10)

# --------------------------------------------------------------------------- #
# Teclado: nomes, leitura (para gravar) e envio (para reproduzir)
# --------------------------------------------------------------------------- #
VK_F9 = 0x78  # tecla de parada (não é gravada)
VK_F8 = 0x77  # tecla de pausar/continuar (não é gravada)
NOME_PAUSA = "F8"
NOME_PARAR = "F9"
VK_REPRODUZIR = 0x7A  # F11: tecla de reproduzir (não é gravada)
VK_F10 = 0x79  # tecla global de iniciar/parar a gravação (usada pela janela; não é gravada)


_MODIFICADORES: dict[str, tuple[int, tuple[int, ...]]] = {
    "CTRL": (0x11, (0xA2, 0xA3)), "ALT": (0x12, (0xA4, 0xA5)), "SHIFT": (0x10, (0xA0, 0xA1)),
}
_BASES_NOMEADAS: dict[str, int] = {
    "INSERT": 0x2D, "DELETE": 0x2E, "HOME": 0x24, "END": 0x23, "PAGEUP": 0x21, "PAGEDOWN": 0x22,
    "CIMA": 0x26, "BAIXO": 0x28, "ESQUERDA": 0x25, "DIREITA": 0x27, "PAUSE": 0x13,
    "SCROLLLOCK": 0x91, "PRINTSCREEN": 0x2C,
    **{f"NUM{i}": 0x60 + i for i in range(10)},
}
_NOME_DA_BASE: dict[int, str] = {v: k for k, v in _BASES_NOMEADAS.items()}
Atalho = tuple[tuple[str, ...], int]  # (modificadores na ordem CTRL, ALT, SHIFT; tecla)


def analisar_atalho(nome: str) -> Optional[Atalho]:
    """'ctrl+F11' -> (('CTRL',), 0x7A). Aceita F1..F24, letra, número, Insert/Home/PageUp…, Num0..9,
    com Ctrl/Alt/Shift antes. None se não reconhece."""
    partes = [p.strip().upper() for p in nome.split("+")]
    if any(not p for p in partes):
        return None
    base, mods = partes[-1], partes[:-1]
    if len(set(mods)) != len(mods) or any(m not in _MODIFICADORES for m in mods):
        return None
    vk: Optional[int] = None
    if len(base) >= 2 and base[0] == "F" and base[1:].isdigit() and 1 <= int(base[1:]) <= 24:
        vk = 0x6F + int(base[1:])
    elif len(base) == 1 and base.isascii() and (base.isalpha() or base.isdigit()):
        vk = ord(base)
    else:
        vk = _BASES_NOMEADAS.get(base)
    if vk is None:
        return None
    return tuple(m for m in _MODIFICADORES if m in mods), vk


def _nome_da_base(vk: int) -> str:
    if vk in _NOME_DA_BASE:
        return _NOME_DA_BASE[vk]
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x6F}"
    return chr(vk)


def nome_do_atalho(a: Atalho) -> str:
    return "+".join(list(a[0]) + [_nome_da_base(a[1])])


def normalizar_atalho(nome: str) -> Optional[str]:
    """Nome canônico ('ctrl + f11' -> 'CTRL+F11'); None se não vale."""
    a = analisar_atalho(nome)
    return nome_do_atalho(a) if a else None


def vk_de_nome(nome: str) -> Optional[int]:
    """Tecla principal do atalho (sem os modificadores) ou None."""
    a = analisar_atalho(nome)
    return a[1] if a else None


def atalho_pressionado(atalho: Atalho, estado: Optional[Callable[[int], bool]] = None) -> bool:
    """Tecla principal apertada e, se o atalho tem modificadores, exatamente eles. Sem modificadores
    a tecla vale sozinha (como sempre foi com F8/F9)."""
    est = estado or tecla_pressionada
    mods, vk = atalho
    if not est(vk):
        return False
    if not mods:
        return True
    return all(est(_MODIFICADORES[m][0]) == (m in mods) for m in _MODIFICADORES)


def tecla_pressionada_global(vk: int) -> bool:
    """Tecla apertada agora (de qualquer janela); False fora do Windows."""
    if sys.platform != "win32":
        return False
    try:
        return tecla_pressionada(vk)
    except Exception:
        return False


def vks_dos_modificadores(mods: tuple[str, ...]) -> set[int]:
    return {v for m in mods for v in _MODIFICADORES[m][1]}


def _vks_capturaveis() -> list[int]:
    return (list(range(0x70, 0x88)) + list(range(0x30, 0x3A)) + list(range(0x41, 0x5B))
            + sorted(set(_BASES_NOMEADAS.values())))


def teclas_apertadas(estado: Callable[[int], bool]) -> set[int]:
    return {vk for vk in _vks_capturaveis() if estado(vk)}


def ler_atalho(estado: Callable[[int], bool], ignorar: Optional[set[int]] = None) -> Optional[str]:
    """Primeira tecla válida apertada agora (fora `ignorar`), com os modificadores que estão apertados.
    Ctrl, Alt ou Shift sozinhos não valem: espera a tecla principal."""
    for vk in _vks_capturaveis():
        if ignorar and vk in ignorar:
            continue
        if estado(vk):
            mods = tuple(m for m, (g, _) in _MODIFICADORES.items() if estado(g))
            return nome_do_atalho((mods, vk))
    return None


_atalhos: dict[str, Atalho] = {"pausa": ((), 0x77), "parar": ((), 0x78), "gravar": ((), 0x79),
                               "reproduzir": ((), 0x7A)}


def pressionada(qual: str) -> bool:
    """Atalho 'pausa', 'parar', 'gravar' ou 'reproduzir' apertado agora."""
    return atalho_pressionado(_atalhos[qual])


def definir_teclas(pausa: str = "F8", parar: str = "F9", gravar: str = "F10",
                   reproduzir: str = "F11") -> None:
    """Troca os atalhos (pausar, parar, iniciar/parar gravação, reproduzir) deste processo.
    Aceita combinações como 'Ctrl+F11'; o que não vale volta ao padrão."""
    global VK_F8, VK_F9, VK_F10, VK_REPRODUZIR, NOME_PAUSA, NOME_PARAR
    for qual, bruto, padrao in (("pausa", pausa, "F8"), ("parar", parar, "F9"),
                                ("gravar", gravar, "F10"), ("reproduzir", reproduzir, "F11")):
        _atalhos[qual] = analisar_atalho(bruto) or analisar_atalho(padrao) or ((), 0)
    NOME_PAUSA = nome_do_atalho(_atalhos["pausa"])  # pyright: ignore[reportConstantRedefinition]
    NOME_PARAR = nome_do_atalho(_atalhos["parar"])  # pyright: ignore[reportConstantRedefinition]
    VK_F8 = _atalhos["pausa"][1]  # pyright: ignore[reportConstantRedefinition]
    VK_F9 = _atalhos["parar"][1]  # pyright: ignore[reportConstantRedefinition]
    VK_F10 = _atalhos["gravar"][1]  # pyright: ignore[reportConstantRedefinition]
    VK_REPRODUZIR = _atalhos["reproduzir"][1]  # pyright: ignore[reportConstantRedefinition]
    VKS_TECLADO[:] = _montar_vks()


def teclas_do_ambiente() -> None:
    """Lê AUTOCLICK_TECLAS='pausa=F8;parar=F9;gravar=F10' (definido pela janela)."""
    bruto = os.environ.get("AUTOCLICK_TECLAS", "")
    if not bruto:
        return
    d: dict[str, str] = {}
    for parte in bruto.split(";"):
        if "=" in parte:
            k, v = parte.split("=", 1)
            d[k.strip().lower()] = v.strip()
    definir_teclas(d.get("pausa", "F8"), d.get("parar", "F9"), d.get("gravar", "F10"), d.get("reproduzir", "F11"))


def dpi_sistema() -> int:
    """DPI do sistema (96 = 100%); 96 se não der para saber."""
    if sys.platform != "win32":
        return 96
    try:
        u, _ = api()
        return int(u.GetDpiForSystem())
    except Exception:
        return 96

# Teclas monitoradas: letras, números, setas, F1-F24 (menos F9), modificadores, etc.
def _montar_vks() -> list[int]:
    return [
    v for v in (
        [0x08, 0x09, 0x0D, 0x13, 0x14, 0x1B]
        + list(range(0x20, 0x29)) + [0x2C, 0x2D, 0x2E]
        + list(range(0x30, 0x3A)) + list(range(0x41, 0x5B))
        + [0x5B, 0x5C] + list(range(0x60, 0x88)) + [0x90, 0x91]
        + list(range(0xA0, 0xA6)) + list(range(0xBA, 0xC1))
        + list(range(0xDB, 0xE0)) + [0xE2]
    ) if v not in (VK_F9, VK_F8, VK_F10, VK_REPRODUZIR)
    ]


VKS_TECLADO: list[int] = _montar_vks()

_TECLAS_ESTENDIDAS = frozenset(
    {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2C, 0x2D, 0x2E, 0x5B, 0x5C,
     0x6F, 0x90, 0xA3, 0xA5}
)

_NOMES_TECLA: dict[int, str] = {
    0x08: "Backspace", 0x09: "Tab", 0x0D: "Enter", 0x13: "Pause", 0x14: "CapsLock",
    0x1B: "Esc", 0x20: "Espaço", 0x21: "PageUp", 0x22: "PageDown", 0x23: "End",
    0x24: "Home", 0x25: "Esquerda", 0x26: "Cima", 0x27: "Direita", 0x28: "Baixo",
    0x2C: "PrintScreen", 0x2D: "Insert", 0x2E: "Delete", 0x5B: "Win", 0x5C: "Win",
    0x6A: "Num*", 0x6B: "Num+", 0x6D: "Num-", 0x6E: "Num.", 0x6F: "Num/",
    0x90: "NumLock", 0x91: "ScrollLock", 0xA0: "Shift", 0xA1: "Shift", 0xA2: "Ctrl",
    0xA3: "Ctrl", 0xA4: "Alt", 0xA5: "Alt",
}

def nome_tecla(vk: int) -> str:
    if vk in _NOMES_TECLA:
        return _NOMES_TECLA[vk]
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x60 <= vk <= 0x69:
        return f"Num{vk - 0x60}"
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x6F}"
    return f"VK_{vk:02X}"

def enviar_tecla(vk: int, baixo: bool) -> None:
    """Aperta (baixo=True) ou solta uma tecla com eventos reais (código de varredura,
    que é o que jogos costumam ler)."""
    u, _ = api()
    scan = int(u.MapVirtualKeyW(vk, 0))
    flags = 0 if baixo else 0x0002  # KEYEVENTF_KEYUP
    if vk in _TECLAS_ESTENDIDAS:
        flags |= 0x0001  # KEYEVENTF_EXTENDEDKEY
    wvk = vk
    if scan:
        flags |= 0x0008  # KEYEVENTF_SCANCODE
        wvk = 0
    entrada = _Input(type=1, u=_InputUnion(ki=_KeybdInput(wvk, scan, flags, 0, 0)))
    u.SendInput(1, ctypes.byref(entrada), ctypes.sizeof(entrada))

class MonitorTeclado:
    """Detecta quando teclas são apertadas/soltas (consulta o estado a cada chamada)."""

    def __init__(self) -> None:
        self.premidas: dict[int, float] = {}

    def varrer(self, agora: float) -> list[tuple[str, int]]:
        """Lista de ('baixo' | 'cima', vk) ocorridos desde a última chamada."""
        mudancas: list[tuple[str, int]] = []
        for vk in VKS_TECLADO:
            p = tecla_pressionada(vk)
            if p and vk not in self.premidas:
                self.premidas[vk] = agora
                mudancas.append(("baixo", vk))
            elif (not p) and vk in self.premidas:
                del self.premidas[vk]
                mudancas.append(("cima", vk))
        return mudancas

# --------------------------------------------------------------------------- #
# Regras por botão (botoes.json), estado da partida e log de ações
# --------------------------------------------------------------------------- #
RIGHTDOWN = 0x0008

RIGHTUP = 0x0010

VK_ESQUERDO = 0x01

VK_DIREITO = 0x02

# --------------------------------------------------------------------------- #
# Teclado/mouse físicos (Windows) usados por gravar e reproduzir
# --------------------------------------------------------------------------- #
def tecla_pressionada(vk: int) -> bool:
    u, _ = api()
    return bool(u.GetAsyncKeyState(vk) & 0x8000)

PARADA = threading.Event()  # o botão "Parar" da janela (--gui) liga isto


def abortar() -> bool:
    """F9, botão Parar da janela, ou mouse no canto superior esquerdo."""
    if PARADA.is_set():
        return True
    x, y = posicao()
    return pressionada("parar") or (x <= 1 and y <= 1)
