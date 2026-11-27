# pyright: basic
"""Peças visuais reutilizáveis: cartões, botões, indicadores, área rolável."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Optional

from .tema import Tema


class Cartao(tk.Frame):
    """Caixa com borda fina, título e subtítulo. Coloque o conteúdo em `.corpo`."""

    def __init__(self, parent: tk.Misc, t: Tema, titulo: str = "", subtitulo: str = "",
                 numero: str = "") -> None:
        super().__init__(parent, bg=t.c["card"], highlightthickness=1,
                         highlightbackground=t.c["border"], highlightcolor=t.c["border"])
        self.t = t
        topo = tk.Frame(self, bg=t.c["card"])
        topo.pack(fill="x", padx=18, pady=(16, 0))
        if numero:
            tk.Label(topo, text=numero, bg=t.c["accent"], fg=t.c["accent_text"], font=t.f_negrito,
                     width=2).pack(side="left", padx=(0, 10))
        if titulo:
            tk.Label(topo, text=titulo, bg=t.c["card"], fg=t.c["text"], font=t.f_card,
                     anchor="w").pack(side="left")
        self._sub: Any = None
        if subtitulo:
            self._sub = tk.Label(self, text=subtitulo, bg=t.c["card"], fg=t.c["muted"],
                                 font=t.f_pequena, anchor="w", justify="left", wraplength=300)
            self._sub.pack(fill="x", padx=18, pady=(4, 0))
        self.corpo = tk.Frame(self, bg=t.c["card"])
        self.corpo.pack(fill="both", expand=True, padx=18, pady=(12, 16))
        self.corpo.columnconfigure(1, weight=1)
        self._linha = 0
        self._dicas: list[tk.Label] = []
        self.bind("<Configure>", self._ajustar)

    def _ajustar(self, e: Any) -> None:
        """Quebra os textos longos de acordo com a largura atual do cartão."""
        if self._sub is not None:
            self._sub.configure(wraplength=max(180, e.width - 40))
        try:
            caixa = self.corpo.grid_bbox(0, 0)
            col0 = caixa[2] if caixa else 160
        except tk.TclError:
            col0 = 160
        for d in self._dicas:
            d.configure(wraplength=max(160, e.width - 36 - col0 - 14))

    def campo(self, rotulo: str, widget: tk.Widget, dica: str = "", colspan: int = 1) -> None:
        """Adiciona uma linha 'rótulo | campo' (e uma dica pequena embaixo)."""
        t = self.t
        r = self._linha
        tk.Label(self.corpo, text=rotulo, bg=t.c["card"], fg=t.c["muted"], font=t.f_pequena,
                 anchor="w").grid(row=r, column=0, sticky="w", pady=4, padx=(0, 12))
        widget.grid(row=r, column=1, columnspan=colspan, sticky="ew", pady=4)
        self._linha += 1
        if dica:
            d = tk.Label(self.corpo, text=dica, bg=t.c["card"], fg=t.c["muted"], font=t.f_pequena,
                         anchor="w", justify="left", wraplength=300)
            d.grid(row=self._linha, column=1, sticky="w", pady=(0, 2))
            self._dicas.append(d)
            self._linha += 1

    def linha_cheia(self, widget: tk.Widget, pady: Any = 4) -> None:
        widget.grid(row=self._linha, column=0, columnspan=2, sticky="ew", pady=pady)
        self._linha += 1


class Indicador(tk.Label):
    """Etiqueta colorida de estado (Parado / Gravando / ...)."""

    def __init__(self, parent: tk.Misc, t: Tema) -> None:
        super().__init__(parent, font=t.f_negrito, padx=12, pady=4, anchor="center")
        self.t = t
        self.definir("Parado", "muted")

    def definir(self, texto: str, cor: str) -> None:
        c = self.t.c
        base = {"muted": c["hover"], "ok": c["ok"], "danger": c["danger"], "warn": c["warn"],
                "accent": c["accent"]}[cor]
        fg = c["muted"] if cor == "muted" else ("#06281d" if (cor in ("ok", "warn") and self.t.nome == "escuro")
                                               else "#ffffff")
        self.configure(text=texto, bg=base, fg=fg)


class Bloco(tk.Frame):
    """Número grande com legenda (Tempo, Ações...)."""

    def __init__(self, parent: tk.Misc, t: Tema, titulo: str, largura: int = 14) -> None:
        super().__init__(parent, bg=t.c["card"], highlightthickness=1,
                         highlightbackground=t.c["border"])
        tk.Label(self, text=titulo.upper(), bg=t.c["card"], fg=t.c["muted"],
                 font=(t.f_pequena[0], 8, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 0))
        self.valor = tk.Label(self, text="–", bg=t.c["card"], fg=t.c["text"], font=t.f_grande,
                              anchor="w", width=largura)
        self.valor.pack(fill="x", padx=14, pady=(0, 10))

    def definir(self, texto: str) -> None:
        self.valor.configure(text=texto)


def _mmss(seg: float) -> str:
    seg = max(0, int(seg))
    return f"{seg // 3600:d}:{seg % 3600 // 60:02d}:{seg % 60:02d}" if seg >= 3600 else f"{seg // 60:02d}:{seg % 60:02d}"


def texto_progresso(p: Optional[dict[str, Any]]) -> str:
    """"volta 3/5 · 04:12 / 10:00" (o total inclui a espera final); "" se não há progresso."""
    if not p:
        return ""
    total = float(p.get("total", 0) or 0)
    dec = min(float(p.get("decorrido", 0) or 0), total) if total else float(p.get("decorrido", 0) or 0)
    rot = str(p.get("rotulo", "") or "")
    if not rot:
        voltas = int(p.get("voltas", 0) or 0)
        rot = f"volta {int(p.get('volta', 1) or 1)}" + (f"/{voltas}" if voltas else "")
    return f"{rot} · {_mmss(dec)} / {_mmss(total)}" + ("  ⏸" if p.get("pausado") else "")


class BarraProgresso(tk.Frame):
    """Texto + barra da volta em andamento (escondida quando não há progresso)."""

    def __init__(self, parent: tk.Misc, t: Tema) -> None:
        super().__init__(parent, bg=t.c["bg"])
        self.lbl = tk.Label(self, text="", bg=t.c["bg"], fg=t.c["text"], font=t.f_negrito, anchor="w")
        self.lbl.pack(fill="x")
        self.barra = ttk.Progressbar(self, maximum=1000, mode="determinate")
        self.barra.pack(fill="x", pady=(2, 0))

    def atualizar(self, p: Optional[dict[str, Any]]) -> None:
        txt = texto_progresso(p)
        total = float((p or {}).get("total", 0) or 0)
        dec = float((p or {}).get("decorrido", 0) or 0)
        self.lbl.configure(text=txt or "—")
        self.barra.configure(value=min(1000.0, 1000.0 * dec / total) if total > 0 else 0)


class PainelStatus(tk.Frame):
    """Indicador de estado + blocos com tempo, ações, voltas e último evento."""

    def __init__(self, parent: tk.Misc, t: Tema, rotulo_voltas: str = "Voltas") -> None:
        super().__init__(parent, bg=t.c["bg"])
        self.t = t
        self.blocos = {
            "tempo": Bloco(self, t, "Tempo", 8), "acoes": Bloco(self, t, "Ações", 6),
            "voltas": Bloco(self, t, rotulo_voltas, 6), "ultimo": Bloco(self, t, "Último evento", 22),
        }
        for i, b in enumerate(self.blocos.values()):
            b.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            self.columnconfigure(i, weight=3 if i == 3 else 1, uniform="b" if i < 3 else "")
        self.progresso = BarraProgresso(self, t)
        self.progresso.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        self.zerar()

    def zerar(self) -> None:
        for k, b in self.blocos.items():
            b.definir("00:00" if k == "tempo" else "0" if k != "ultimo" else "–")
        self.progresso.atualizar(None)

    def atualizar(self, d: dict[str, Any]) -> None:
        r = d.get("resumo", {}) or {}
        seg = int(float(r.get("duracao_seg", 0)))
        self.blocos["tempo"].definir(f"{seg // 3600:d}:{seg % 3600 // 60:02d}:{seg % 60:02d}"
                                     if seg >= 3600 else f"{seg // 60:02d}:{seg % 60:02d}")
        self.blocos["acoes"].definir(str(r.get("total_acoes", 0)))
        self.blocos["voltas"].definir(str(r.get("partidas", 1)))
        self.blocos["ultimo"].definir(str(d.get("ultimo", "–")))
        self.progresso.atualizar(d.get("progresso"))


class Rolavel(tk.Frame):
    """Área com barra de rolagem vertical; coloque o conteúdo em `.corpo`."""

    def __init__(self, parent: tk.Misc, t: Tema) -> None:
        super().__init__(parent, bg=t.c["bg"])
        self.canvas = tk.Canvas(self, bg=t.c["bg"], highlightthickness=0, borderwidth=0)
        barra = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.corpo = tk.Frame(self.canvas, bg=t.c["bg"])
        self._id = self.canvas.create_window((0, 0), window=self.corpo, anchor="nw")
        self.corpo.bind("<Configure>", lambda _e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._id, width=e.width))
        for w in (self.canvas, self.corpo):
            w.bind("<Enter>", self._ligar_roda)
            w.bind("<Leave>", self._desligar_roda)

    def _ligar_roda(self, _e: Any) -> None:
        self.canvas.bind_all("<MouseWheel>", self._roda)
        self.canvas.bind_all("<Button-4>", lambda _e: self.canvas.yview_scroll(-3, "units"))
        self.canvas.bind_all("<Button-5>", lambda _e: self.canvas.yview_scroll(3, "units"))

    def _desligar_roda(self, e: Any) -> None:
        try:
            dentro = self.winfo_containing(e.x_root, e.y_root)
        except (KeyError, tk.TclError):
            dentro = None
        if dentro is not None and str(dentro).startswith(str(self)):
            return
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.unbind_all(ev)

    def _roda(self, e: Any) -> None:
        passo = -1 if e.delta > 0 else 1
        self.canvas.yview_scroll(passo * 3, "units")


def botao(parent: tk.Misc, texto: str, comando: Callable[[], Any], estilo: str = "Ghost",
          pequeno: bool = False) -> ttk.Button:
    nome = ("Small." if pequeno else "") + f"{estilo}.TButton"
    return ttk.Button(parent, text=texto, command=comando, style=nome, cursor="hand2")


def entrada(parent: tk.Misc, var: tk.Variable, largura: int = 0) -> ttk.Entry:
    return ttk.Entry(parent, textvariable=var, width=largura or 20)


def numero(parent: tk.Misc, var: tk.Variable, de: float, ate: float, passo: float = 1,
           largura: int = 8, formato: Optional[str] = None) -> ttk.Spinbox:
    kw: dict[str, Any] = {}
    if formato:
        kw["format"] = formato
    return ttk.Spinbox(parent, textvariable=var, from_=de, to=ate, increment=passo,
                       width=largura, **kw)


def escolha(parent: tk.Misc, var: tk.Variable, valores: list[str] | tuple[str, ...],
            largura: int = 18, editavel: bool = False) -> ttk.Combobox:
    return ttk.Combobox(parent, textvariable=var, values=list(valores), width=largura,
                        state="normal" if editavel else "readonly")


def marcar(parent: tk.Misc, texto: str, var: tk.Variable,
           comando: Optional[Callable[[], Any]] = None) -> ttk.Checkbutton:
    return ttk.Checkbutton(parent, text=texto, variable=var, style="Card.TCheckbutton",
                           command=comando or "", cursor="hand2")


def opcao(parent: tk.Misc, texto: str, var: tk.Variable, valor: str,
          comando: Optional[Callable[[], Any]] = None) -> ttk.Radiobutton:
    return ttk.Radiobutton(parent, text=texto, variable=var, value=valor,
                           style="Card.TRadiobutton", command=comando or "", cursor="hand2")


def linha_inline(parent: tk.Misc, t: Tema) -> tk.Frame:
    return tk.Frame(parent, bg=t.c["card"])


def rotulo(parent: tk.Misc, t: Tema, texto: str, muted: bool = False, **kw: Any) -> tk.Label:
    return tk.Label(parent, text=texto, bg=t.c["card"], fg=t.c["muted"] if muted else t.c["text"],
                    font=t.f_pequena if muted else t.f_normal, **kw)


def responsivo(cont: tk.Misc, itens: list[Any], limite: int = 700, linha0: int = 0,
               pady: tuple[int, int] = (0, 12)) -> None:
    """Dispõe `itens` em 2 colunas quando `cont` é largo e em 1 coluna quando estreito (sem cortes)."""
    estado: dict[str, int] = {"n": 0}

    def aplicar(_e: Any = None) -> None:
        n = 2 if cont.winfo_width() >= limite else 1
        if n == estado["n"]:
            return
        estado["n"] = n
        cont.columnconfigure(0, weight=1, uniform="resp" if n == 2 else "")
        cont.columnconfigure(1, weight=1 if n == 2 else 0, uniform="resp" if n == 2 else "")
        for i, w in enumerate(itens):
            if n == 2:
                w.grid(row=linha0 + i // 2, column=i % 2, sticky="nsew", pady=pady,
                       padx=(0, 8) if i % 2 == 0 else (8, 0))
            else:
                w.grid(row=linha0 + i, column=0, columnspan=1, sticky="nsew", pady=pady, padx=0)

    cont.bind("<Configure>", aplicar, add="+")
    aplicar()


class PreviaViva(tk.Frame):
    """Miniatura da tela com os botões reconhecidos (PNG escrito pelo processo em execução)."""

    def __init__(self, parent: tk.Misc, t: Tema, arquivo: str) -> None:
        super().__init__(parent, bg=t.c["log"], highlightthickness=1, highlightbackground=t.c["border"])
        self.t, self.arquivo = t, arquivo
        self._mtime = 0.0
        self._img: Any = None
        self.lbl = tk.Label(self, text="Aparece aqui quando uma função estiver rodando.", bg=t.c["log"],
                            fg=t.c["muted"], font=t.f_pequena, height=6)
        self.lbl.pack(fill="both", expand=True, padx=6, pady=6)

    def atualizar(self, rodando: bool) -> None:
        import os
        try:
            m = os.path.getmtime(self.arquivo)
        except OSError:
            m = 0.0
        if not rodando:
            if self._img is not None and m == 0.0:
                self.limpar()
            return
        if m and m != self._mtime:
            try:
                img = tk.PhotoImage(file=self.arquivo)
            except tk.TclError:
                return  # arquivo sendo trocado agora: tenta no próximo ciclo
            self._mtime, self._img = m, img
            self.lbl.configure(image=img, text="", height=img.height(), width=img.width())

    def limpar(self) -> None:
        self._img, self._mtime = None, 0.0
        self.lbl.configure(image="", text="Aparece aqui quando uma função estiver rodando.", height=6, width=0)


class GraficoBarras(tk.Canvas):
    """Barras simples (sem bibliotecas): [(rótulo, valor)]."""

    def __init__(self, parent: tk.Misc, t: Tema, altura: int = 150) -> None:
        super().__init__(parent, bg=t.c["card"], height=altura, highlightthickness=0)
        self.t, self.dados = t, []  # type: ignore[var-annotated]
        self.bind("<Configure>", lambda _e: self.desenhar())

    def definir(self, dados: list[tuple[str, float]]) -> None:
        self.dados = dados  # type: ignore[assignment]
        self.desenhar()

    def desenhar(self) -> None:
        c, t = self.t.c, self.t
        self.delete("all")
        w, h = max(self.winfo_width(), 50), max(self.winfo_height(), 50)
        if not self.dados:
            self.create_text(w / 2, h / 2, text="Sem dados ainda.", fill=c["muted"], font=t.f_pequena)
            return
        n = len(self.dados)
        maior = max(v for _, v in self.dados) or 1.0
        topo, base = 18, h - 20
        larg = w / n
        for i, (rot, v) in enumerate(self.dados):
            x0 = i * larg + larg * 0.18
            x1 = (i + 1) * larg - larg * 0.18
            y = base - (base - topo) * (v / maior)
            self.create_rectangle(x0, y, x1, base, fill=c["accent"], outline="")
            self.create_text((x0 + x1) / 2, y - 8, text=f"{v:g}", fill=c["text"], font=t.f_pequena)
            self.create_text((x0 + x1) / 2, base + 10, text=rot, fill=c["muted"], font=t.f_pequena)


def _misturar(a: str, b: str, t: float) -> str:
    """Mistura duas cores #rrggbb (t=0 → a, t=1 → b)."""
    try:
        ra = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
        rb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
        return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(ra, rb))
    except (ValueError, IndexError):
        return a


class ListaRica(tk.Frame):
    """Lista de linhas com 'etiquetas' coloridas, linhas de grupo e seleção destacada.

    Faz o papel do ttk.Treeview onde o visual importa: insert/delete/get_children/selection/
    selection_set/selection_remove/item(iid, "values"), e os eventos "<Double-1>" e
    "<<TreeviewSelect>>" via bind(). `colunas` = [(id, título, largura, estica, etiqueta?)].
    Tags de linha: "ok" / "warn" / "neutro" colorem a etiqueta; "off" esmaece; "grupo" = título de grupo.
    """

    def __init__(self, parent: tk.Misc, t: Tema, colunas: list[tuple[str, str, int, bool, bool]],
                 vazio: str = "") -> None:
        super().__init__(parent, bg=t.c["card"], highlightthickness=1, highlightbackground=t.c["border"])
        self.t = t
        self.cols = colunas
        self.vazio = vazio
        self._linhas: dict[str, dict[str, Any]] = {}
        self._ordem: list[str] = []
        self._sel: Optional[str] = None
        self._cb: dict[str, Any] = {}
        self.columnconfigure(0, weight=1)
        self._cab = tk.Frame(self, bg=t.c["bg"])
        self._cab.grid(row=0, column=0, sticky="ew")
        self._grade(self._cab)
        for i, (_id, titulo, _w, _e, _ch) in enumerate(colunas):
            tk.Label(self._cab, text=titulo, bg=t.c["bg"], fg=t.c["muted"], font=t.f_pequena, anchor="w").grid(
                row=0, column=i, sticky="ew", padx=(12 if i == 0 else 6, 6), pady=6)
        self._corpo = tk.Frame(self, bg=t.c["card"])
        self._corpo.grid(row=1, column=0, sticky="ew")
        self._corpo.columnconfigure(0, weight=1)
        self._lbl_vazio = tk.Label(self._corpo, text=vazio, bg=t.c["card"], fg=t.c["muted"], font=t.f_pequena)

    def _grade(self, f: tk.Frame) -> None:
        for i, (_id, _t, larg, estica, _ch) in enumerate(self.cols):
            f.columnconfigure(i, minsize=larg, weight=1 if estica else 0)

    # ---- API parecida com a do Treeview ---- #
    def bind(self, sequencia: Optional[str] = None, func: Any = None, add: Any = None) -> Any:  # type: ignore[override]
        if sequencia in ("<Double-1>", "<<TreeviewSelect>>"):
            self._cb[sequencia] = func
            return None
        return super().bind(sequencia, func, add)

    def tag_configure(self, *_a: Any, **_k: Any) -> None:
        return None

    def get_children(self) -> tuple[str, ...]:
        return tuple(self._ordem)

    def delete(self, *iids: str) -> None:
        for iid in iids:
            d = self._linhas.pop(iid, None)
            if d:
                d["w"].destroy()
                self._ordem.remove(iid)
                if self._sel == iid:
                    self._sel = None
        self._rotular()

    def insert(self, _pai: str, _pos: str, iid: str, values: tuple[Any, ...], tags: tuple[str, ...] = ()) -> str:
        c = self.t.c
        grupo = "grupo" in tags
        f = tk.Frame(self._corpo, bg=c["bg"] if grupo else c["card"])
        f.grid(row=len(self._ordem), column=0, sticky="ew")
        self._grade(f)
        dados: dict[str, Any] = {"w": f, "valores": tuple(values), "tags": tags, "labels": [], "grupo": grupo}
        if grupo:
            l = tk.Label(f, text=str(values[1]), bg=c["bg"], fg=c["muted"], font=self.t.f_pequena, anchor="w")
            l.grid(row=0, column=0, columnspan=len(self.cols), sticky="ew", padx=12, pady=5)
            dados["labels"].append(l)
        else:
            tk.Frame(f, width=3, bg=c["card"]).place(x=0, y=0, relheight=1)  # faixa de seleção (acende ao selecionar)
            esmaece = "off" in tags
            for i, (col, _t, _w, _e, chip) in enumerate(self.cols):
                txt = str(values[i])
                px = (12 if i == 0 else 6, 6)
                if chip and txt:
                    cor = c["ok"] if "ok" in tags else c["warn"] if "warn" in tags else c["muted"]
                    l = tk.Label(f, text=txt, bg=_misturar(c["card"], cor, 0.20), fg=cor, font=self.t.f_pequena,
                                 padx=8, pady=2)
                    l.grid(row=0, column=i, sticky="w", padx=px, pady=7)
                else:
                    l = tk.Label(f, text=txt, bg=c["card"], fg=c["muted"] if (esmaece or i == 0) else c["text"],
                                 font=self.t.f_normal, anchor="w")
                    l.grid(row=0, column=i, sticky="ew", padx=px, pady=7)
                dados["labels"].append(l)
            for w in (f, *dados["labels"]):
                w.bind("<Button-1>", lambda _e, k=iid: self._clicar(k))
                w.bind("<Double-1>", lambda _e, k=iid: self._duplo(k))
                w.bind("<Enter>", lambda _e, k=iid: self._pintar(k, hover=True))
                w.bind("<Leave>", lambda _e, k=iid: self._pintar(k))
        self._linhas[iid] = dados
        self._ordem.append(iid)
        self._rotular()
        return iid

    def selection(self) -> tuple[str, ...]:
        return (self._sel,) if self._sel else ()

    def selection_set(self, iid: str) -> None:
        d = self._linhas.get(iid)
        if d is None or d["grupo"]:
            return
        ant, self._sel = self._sel, iid
        if ant:
            self._pintar(ant)
        self._pintar(iid)
        self._avisar()

    def selection_remove(self, *iids: str) -> None:
        if self._sel in iids:
            ant, self._sel = self._sel, None
            if ant:
                self._pintar(ant)
            self._avisar()

    def item(self, iid: str, opcao: str = "values") -> tuple[Any, ...]:
        return self._linhas[iid]["valores"]

    # ---- interno ---- #
    def _avisar(self) -> None:
        f = self._cb.get("<<TreeviewSelect>>")
        if f:
            f(None)

    def _clicar(self, iid: str) -> None:
        self.selection_set(iid)

    def _duplo(self, iid: str) -> None:
        self.selection_set(iid)
        f = self._cb.get("<Double-1>")
        if f:
            f(None)

    def _pintar(self, iid: str, hover: bool = False) -> None:
        d = self._linhas.get(iid)
        if d is None or d["grupo"]:
            return
        c = self.t.c
        cor = c["sel"] if iid == self._sel else c["hover"] if hover else c["card"]
        d["w"].configure(bg=cor)
        faixa = d["w"].place_slaves()
        for fx in faixa:
            fx.configure(bg=c["accent"] if iid == self._sel else cor)
        chip_cols = {i for i, col in enumerate(self.cols) if col[4]}
        for i, l in enumerate(d["labels"]):
            if i not in chip_cols:
                l.configure(bg=cor)

    def _rotular(self) -> None:
        if not self._ordem and self.vazio:
            self._lbl_vazio.grid(row=0, column=0, sticky="ew", pady=14)
        else:
            self._lbl_vazio.grid_forget()
