# pyright: basic
"""Ícone na bandeja do Windows (área de notificação), só com ctypes (sem dependências).

- clique esquerdo: mostrar a janela; clique direito: menu (Mostrar, Pausar/Continuar, Parar, Sair);
- a cor do ícone acompanha o estado (parado, rodando, pausado, gravando);
- `balao()` mostra a notificação do Windows (usada nos alertas).

Em outros sistemas (ou se algo falhar) `disponivel` fica False e a janela segue normal.
A janela recebe os eventos pela fila `eventos`, lida no laço do Tk (thread-safe).
"""
from __future__ import annotations

import queue
import sys
import threading
from typing import Any, Optional

CORES = {  # BGR-ish tuplas (R, G, B)
    "parado": (140, 146, 160), "rodando": (46, 190, 110), "pausado": (240, 180, 40),
    "gravando": (230, 70, 70),
}
WM_USER = 0x0400
WM_TRAY = WM_USER + 1
WM_CLOSE, WM_DESTROY = 0x0010, 0x0002
WM_LBUTTONUP, WM_RBUTTONUP, WM_LBUTTONDBLCLK = 0x0202, 0x0205, 0x0203
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 1, 2, 4, 0x10
NIIF = {"info": 1, "aviso": 2, "erro": 3}
MF_STRING, MF_SEPARATOR = 0, 0x800
TPM_RETURNCMD, TPM_RIGHTBUTTON = 0x100, 0x2
CMD_MOSTRAR, CMD_PAUSA, CMD_PARAR, CMD_SAIR = 1, 2, 3, 4
CMD_SOM, CMD_REPRODUZIR, CMD_GRAVAR = 5, 6, 7
CMD_JOGO = 100  # 100 + posição do jogo na lista
NOMES_CMD = {CMD_MOSTRAR: "mostrar", CMD_PAUSA: "pausa", CMD_PARAR: "parar", CMD_SAIR: "sair",
             CMD_SOM: "som", CMD_REPRODUZIR: "reproduzir", CMD_GRAVAR: "gravar"}


def itens_do_menu(rodando: bool, pausado: bool, som: bool, jogos: list[tuple[str, str]],
                  atual: str) -> list[tuple[int, str, bool]]:
    """Itens do menu da bandeja: (id, texto, marcado). id 0 = separador. Função pura (testável)."""
    it: list[tuple[int, str, bool]] = [(CMD_MOSTRAR, "Mostrar janela", False), (0, "", False)]
    it.append((CMD_PAUSA, "Continuar o loop" if pausado else "Pausar o loop", False))
    it.append((CMD_REPRODUZIR, "Parar a reprodução" if rodando else "Reproduzir a gravação", False))
    it.append((CMD_GRAVAR, "Gravar / parar de gravar", False))
    it.append((CMD_PARAR, "Parar tudo", False))
    it.append((CMD_SOM, "Som ao concluir a volta", som))
    if jogos:
        it.append((0, "", False))
        for i, (slug, nome) in enumerate(jogos):
            it.append((CMD_JOGO + i, f"Jogo: {nome}", slug == atual))
    it += [(0, "", False), (CMD_SAIR, "Sair", False)]
    return it


def pixels_do_icone(cor: tuple[int, int, int], tam: int = 16) -> bytes:
    """Bolinha colorida com borda escura, em BGRA (pura: dá para testar em qualquer sistema)."""
    r, g, b = cor
    centro = (tam - 1) / 2.0
    raio = tam / 2.0 - 1.0
    dados = bytearray()
    for y in range(tam - 1, -1, -1):  # bitmap do Windows é de baixo para cima
        for x in range(tam):
            d = ((x - centro) ** 2 + (y - centro) ** 2) ** 0.5
            if d <= raio - 1.2:
                dados += bytes((b, g, r, 255))
            elif d <= raio:
                dados += bytes((b // 3, g // 3, r // 3, 255))
            else:
                dados += bytes((0, 0, 0, 0))
    return bytes(dados)


class Bandeja:
    def __init__(self, titulo: str = "Autoclick Inteligente") -> None:
        self.titulo = titulo
        self.eventos: "queue.Queue[str]" = queue.Queue()
        self.disponivel = False
        self.estado = "parado"
        self.pausado = False
        self.rodando = False
        self.som = False
        self.jogos: list[tuple[str, str]] = []
        self.jogo_atual = ""
        self._hwnd: Any = None
        self._thread: Optional[threading.Thread] = None
        self._pronto = threading.Event()
        self._icones: dict[str, Any] = {}
        self._nid: Any = None
        self._u: Any = None
        self._s: Any = None
        self._g: Any = None

    # ------------------------------------------------------------------ #
    def iniciar(self) -> bool:
        if sys.platform != "win32" or self._thread is not None:
            return self.disponivel
        self._thread = threading.Thread(target=self._laco, daemon=True)
        self._thread.start()
        self._pronto.wait(3.0)
        return self.disponivel

    def _laco(self) -> None:
        try:
            self._montar()
        except Exception as e:  # nunca derrubar a janela por causa da bandeja
            self.disponivel = False
            self.erro = f"{type(e).__name__}: {e}"
            self._pronto.set()
            return
        self._pronto.set()
        from ctypes import byref, wintypes
        msg = wintypes.MSG()
        while self._u.GetMessageW(byref(msg), None, 0, 0) > 0:
            self._u.TranslateMessage(byref(msg))
            self._u.DispatchMessageW(byref(msg))

    erro = ""

    def _montar(self) -> None:
        import ctypes
        from ctypes import wintypes
        u, s, g = ctypes.windll.user32, ctypes.windll.shell32, ctypes.windll.gdi32  # type: ignore[attr-defined]
        self._u, self._s, self._g = u, s, g
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        u.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        u.DefWindowProcW.restype = LRESULT

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                        ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                        ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE),
                        ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR),
                        ("lpszClassName", wintypes.LPCWSTR)]

        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                        ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT),
                        ("hIcon", wintypes.HICON), ("szTip", ctypes.c_wchar * 128),
                        ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                        ("szInfo", ctypes.c_wchar * 256), ("uTimeout", wintypes.UINT),
                        ("szInfoTitle", ctypes.c_wchar * 64), ("dwInfoFlags", wintypes.DWORD)]

        class ICONINFO(ctypes.Structure):
            _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                        ("hbmMask", wintypes.HBITMAP), ("hbmColor", wintypes.HBITMAP)]

        self._NID = NOTIFYICONDATAW

        def criar_icone(cor: tuple[int, int, int]) -> Any:
            px = pixels_do_icone(cor)
            buf = ctypes.create_string_buffer(px, len(px))
            cor_bmp = g.CreateBitmap(16, 16, 1, 32, buf)
            mascara = g.CreateBitmap(16, 16, 1, 1, None)
            info = ICONINFO(True, 0, 0, mascara, cor_bmp)
            h = u.CreateIconIndirect(ctypes.byref(info))
            g.DeleteObject(cor_bmp)
            g.DeleteObject(mascara)
            return h

        for nome, cor in CORES.items():
            self._icones[nome] = criar_icone(cor)

        def proc(hwnd: Any, msg: int, wp: Any, lp: Any) -> int:
            if msg == WM_TRAY:
                ev = int(lp) & 0xFFFF
                if ev in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self.eventos.put("mostrar")
                elif ev == WM_RBUTTONUP:
                    self._menu(hwnd)
                return 0
            if msg == WM_DESTROY:
                u.PostQuitMessage(0)
                return 0
            return int(u.DefWindowProcW(hwnd, msg, wp, lp))

        self._proc = WNDPROC(proc)  # guardar referência (senão o coletor apaga)
        classe = WNDCLASSW()
        classe.lpfnWndProc = self._proc
        classe.lpszClassName = "AutoclickBandeja"
        classe.hInstance = ctypes.windll.kernel32.GetModuleHandleW(None)  # type: ignore[attr-defined]
        u.RegisterClassW(ctypes.byref(classe))
        self._hwnd = u.CreateWindowExW(0, "AutoclickBandeja", self.titulo, 0, 0, 0, 0, 0, None, None,
                                       classe.hInstance, None)
        if not self._hwnd:
            raise OSError("CreateWindowExW falhou")
        self._nid = NOTIFYICONDATAW()
        self._nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        self._nid.hWnd = self._hwnd
        self._nid.uID = 1
        self._nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        self._nid.uCallbackMessage = WM_TRAY
        self._nid.hIcon = self._icones["parado"]
        self._nid.szTip = self.titulo[:127]
        if not s.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._nid)):
            raise OSError("Shell_NotifyIconW(NIM_ADD) falhou")
        self.disponivel = True

    def _menu(self, hwnd: Any) -> None:
        import ctypes
        from ctypes import wintypes
        u = self._u
        m = u.CreatePopupMenu()
        jogos = list(self.jogos)
        for cid, txt, marcado in itens_do_menu(self.rodando, self.pausado, self.som, jogos, self.jogo_atual):
            if cid == 0:
                u.AppendMenuW(m, MF_SEPARATOR, 0, None)
            else:
                u.AppendMenuW(m, MF_STRING | (0x8 if marcado else 0), cid, txt)  # 0x8 = MF_CHECKED
        pt = wintypes.POINT()
        u.GetCursorPos(ctypes.byref(pt))
        u.SetForegroundWindow(hwnd)  # sem isto o menu não fecha ao clicar fora
        cmd = u.TrackPopupMenu(m, TPM_RETURNCMD | TPM_RIGHTBUTTON, pt.x, pt.y, 0, hwnd, None)
        u.DestroyMenu(m)
        if cmd in NOMES_CMD:
            self.eventos.put(NOMES_CMD[cmd])
        elif cmd >= CMD_JOGO and cmd - CMD_JOGO < len(jogos):
            self.eventos.put("jogo:" + jogos[cmd - CMD_JOGO][0])

    # ------------------------------------------------------------------ #
    def _modificar(self) -> None:
        if self.disponivel and self._nid is not None:
            import ctypes
            self._s.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))

    def definir_estado(self, estado: str, dica: str = "", pausado: bool = False) -> None:
        """estado: parado | rodando | pausado | gravando."""
        self.pausado = pausado
        if not self.disponivel or self._nid is None:
            self.estado = estado
            return
        self.estado = estado if estado in self._icones else "parado"
        self._nid.uFlags = NIF_ICON | NIF_TIP | NIF_MESSAGE
        self._nid.hIcon = self._icones[self.estado]
        self._nid.szTip = (f"{self.titulo} - {dica}" if dica else self.titulo)[:127]
        self._modificar()

    def balao(self, titulo: str, texto: str, nivel: str = "aviso") -> bool:
        """Notificação do Windows. False se a bandeja não está disponível."""
        if not self.disponivel or self._nid is None:
            return False
        self._nid.uFlags = NIF_INFO | NIF_MESSAGE
        self._nid.szInfoTitle = titulo[:63]
        self._nid.szInfo = texto[:255]
        self._nid.dwInfoFlags = NIIF.get(nivel, 1)
        self._modificar()
        return True

    def fechar(self) -> None:
        if self.disponivel and self._nid is not None:
            import ctypes
            try:
                self._s.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
                self._u.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
            except Exception:
                pass
        self.disponivel = False
