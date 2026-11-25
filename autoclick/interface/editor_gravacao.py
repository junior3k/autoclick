# pyright: basic
"""Editor de gravação: ver os eventos, apagar, ajustar tempos, inserir esperas e marcadores."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Any, Optional

from . import edicao
from .dados import listar_pngs
from .dialogos import pedir_texto
from .widgets import botao

if TYPE_CHECKING:
    from .app import App


class DialogoMarcador:
    """Pergunta os dados de um marcador de verificação. `.resultado` é None se cancelar."""

    def __init__(self, app: "App", pai: tk.Misc, botoes: list[str]) -> None:
        t = app.t
        self.resultado: Optional[dict[str, Any]] = None
        j = self.j = tk.Toplevel(pai)
        j.title("Marcador de verificação")
        j.configure(bg=t.c["card"])
        j.transient(pai)  # type: ignore[arg-type]
        j.resizable(False, False)
        tk.Label(j, text="A reprodução espera aqui até a condição acontecer (o tempo gasto não "
                 "atrapalha o ritmo do resto).", bg=t.c["card"], fg=t.c["muted"], font=t.f_pequena,
                 wraplength=380, justify="left").pack(padx=22, pady=(18, 8), anchor="w")
        g = tk.Frame(j, bg=t.c["card"])
        g.pack(padx=22, fill="x")
        g.columnconfigure(1, weight=1)
        self.v_botao = tk.StringVar(value=botoes[0] if botoes else "")
        self.v_ate = tk.StringVar(value="aparecer")
        self.v_tempo = tk.StringVar(value="30")
        self.v_estourar = tk.StringVar(value="avisar")
        for i, (rot, w) in enumerate((
                ("Botão", ttk.Combobox(g, textvariable=self.v_botao, values=botoes, width=28)),
                ("Esperar até", ttk.Combobox(g, textvariable=self.v_ate, values=["aparecer", "sumir"],
                                             state="readonly", width=12)),
                ("Tempo máximo (s)", ttk.Spinbox(g, textvariable=self.v_tempo, from_=1, to=3600, width=8)),
                ("Se estourar", ttk.Combobox(g, textvariable=self.v_estourar, values=list(edicao.AO_ESTOURAR),
                                             state="readonly", width=12)))):
            tk.Label(g, text=rot, bg=t.c["card"], fg=t.c["text"], font=t.f_normal).grid(
                row=i, column=0, sticky="w", pady=4, padx=(0, 12))
            w.grid(row=i, column=1, sticky="w", pady=4)
        tk.Label(j, text="avisar = alerta e segue · parar = encerra · pular = só segue",
                 bg=t.c["card"], fg=t.c["muted"], font=t.f_pequena).pack(padx=22, anchor="w", pady=(4, 0))
        b = tk.Frame(j, bg=t.c["card"])
        b.pack(fill="x", padx=22, pady=16)
        botao(b, "Inserir", self._ok, "Accent").pack(side="right")
        botao(b, "Cancelar", j.destroy, "Ghost").pack(side="right", padx=8)
        j.grab_set()
        j.wait_window()

    def _ok(self) -> None:
        nome = self.v_botao.get().strip()
        try:
            tempo = float(self.v_tempo.get().replace(",", "."))
        except ValueError:
            messagebox.showwarning("Marcador", "O tempo máximo precisa ser um número.", parent=self.j)
            return
        if not nome:
            messagebox.showwarning("Marcador", "Escolha o botão a verificar.", parent=self.j)
            return
        self.resultado = {"botao": nome, "timeout": max(1.0, tempo), "ate": self.v_ate.get(),
                          "ao_estourar": self.v_estourar.get()}
        self.j.destroy()


class EditorGravacao:
    def __init__(self, app: "App", caminho: str, ao_salvar: Any = None) -> None:
        self.app, self.caminho, self.ao_salvar = app, caminho, ao_salvar
        t = app.t
        try:
            self.dados, eventos = edicao.carregar(caminho)
        except (OSError, ValueError) as e:
            messagebox.showerror("Editar gravação", f"Não consegui abrir {caminho}:\n{e}", parent=app.raiz)
            return
        self.hist = edicao.Historia(eventos)
        self.salvo = eventos
        self._cauda_salva = float(self.dados.get("cauda", 0) or 0)
        j = self.j = tk.Toplevel(app.raiz)
        j.title(f"Editar gravação — {caminho}")
        j.configure(bg=t.c["bg"])
        j.geometry("860x560")
        j.minsize(640, 420)
        j.transient(app.raiz)  # type: ignore[arg-type]
        j.protocol("WM_DELETE_WINDOW", self.fechar)

        barra = tk.Frame(j, bg=t.c["bg"])
        barra.pack(fill="x", padx=14, pady=(12, 6))
        self.btn_des = botao(barra, "Desfazer", self.desfazer, "Ghost", True)
        self.btn_ref = botao(barra, "Refazer", self.refazer, "Ghost", True)
        itens = [self.btn_des, self.btn_ref,
                 botao(barra, "Apagar", self.apagar, "Danger", True),
                 botao(barra, "Duplicar", self.duplicar, "Ghost", True),
                 botao(barra, "Inserir espera…", self.espera, "Ghost", True),
                 botao(barra, "Ajustar tempo…", self.ajustar, "Ghost", True),
                 botao(barra, "Inserir marcador…", self.marcador, "Ghost", True),
                 botao(barra, "Cortar antes", self.cortar_antes, "Ghost", True),
                 botao(barra, "Cortar depois", self.cortar_depois, "Ghost", True),
                 botao(barra, "Espera final…", self.espera_final, "Ghost", True)]
        # botões em linhas que quebram conforme a largura
        self._itens = itens
        self._barra = barra
        barra.bind("<Configure>", self._dispor_barra)

        quadro = tk.Frame(j, bg=t.c["bg"])
        quadro.pack(fill="both", expand=True, padx=14)
        self.arv = ttk.Treeview(quadro, columns=("t", "tipo", "det"), selectmode="extended", show="headings")
        for col, txt, w, anc in (("t", "Tempo (s)", 90, "e"), ("tipo", "Tipo", 90, "w"),
                                 ("det", "Detalhes", 520, "w")):
            self.arv.heading(col, text=txt)
            self.arv.column(col, width=w, anchor=anc, stretch=(col == "det"))  # type: ignore[arg-type]
        sb = ttk.Scrollbar(quadro, orient="vertical", command=self.arv.yview)
        self.arv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.arv.pack(side="left", fill="both", expand=True)
        self.arv.tag_configure("marcador", foreground=t.c["accent"])
        self.arv.tag_configure("tecla", foreground=t.c["muted"])
        self.arv.bind("<Delete>", lambda _e: self.apagar())
        j.bind("<Control-z>", lambda _e: self.desfazer())
        j.bind("<Control-y>", lambda _e: self.refazer())
        j.bind("<Control-s>", lambda _e: self.salvar())

        rod = tk.Frame(j, bg=t.c["bg"])
        rod.pack(fill="x", padx=14, pady=10)
        self.lbl = tk.Label(rod, text="", bg=t.c["bg"], fg=t.c["muted"], font=t.f_pequena, anchor="w",
                            justify="left")
        self.lbl.pack(side="left", fill="x", expand=True)
        botao(rod, "Fechar", self.fechar, "Ghost").pack(side="right")
        self.btn_salvar = botao(rod, "Salvar", self.salvar, "Accent")
        self.btn_salvar.pack(side="right", padx=8)
        self.atualizar()

    # ------------------------------------------------------------------ #
    def _dispor_barra(self, _e: Any = None) -> None:
        largura = max(self._barra.winfo_width(), 1)
        coluna = 0
        x = linha = 0
        for b in self._itens:
            w = b.winfo_reqwidth() + 6
            if x + w > largura and x > 0:
                linha, x, coluna = linha + 1, 0, 0
            b.grid(row=linha, column=coluna, padx=(0, 6), pady=2, sticky="w")
            coluna += 1
            x += w

    @property
    def eventos(self) -> list[edicao.Evento]:
        return self.hist.atual

    def _indices(self) -> list[int]:
        return sorted(int(i) for i in self.arv.selection())

    def _primeiro(self) -> Optional[int]:
        s = self._indices()
        return s[0] if s else None

    def atualizar(self, selecionar: Optional[list[int]] = None) -> None:
        for i in self.arv.get_children():
            self.arv.delete(i)
        for i, e in enumerate(self.eventos):
            tipo, det = edicao.descrever(e)
            tag = "marcador" if e.get("tipo") == "aguardar" else ("tecla" if e.get("tipo") == "tecla" else "")
            self.arv.insert("", "end", iid=str(i), values=(f"{float(e.get('t', 0)):.2f}", tipo, det),
                            tags=(tag,) if tag else ())
        if selecionar:
            ok = [str(i) for i in selecionar if 0 <= i < len(self.eventos)]
            if ok:
                self.arv.selection_set(ok)
                self.arv.see(ok[0])
        self.btn_des.state(["!disabled"] if self.hist.pode_desfazer else ["disabled"])
        self.btn_ref.state(["!disabled"] if self.hist.pode_refazer else ["disabled"])
        avisos = edicao.problemas(self.eventos)
        cauda = float(self.dados.get("cauda", 0) or 0)
        sujo = self.eventos != self.salvo or cauda != self._cauda_salva
        self.lbl.configure(
            text=f"{len(self.eventos)} evento(s) · duração {edicao.duracao(self.eventos):.1f}s"
                 + (f" + espera final {cauda:g}s" if cauda else " (sem espera final)")
                 + ("  ·  ● alterações não salvas" if sujo else "")
                 + ("".join(f"\n⚠ {a}" for a in avisos)),
            fg=self.app.t.c["warn"] if avisos else self.app.t.c["muted"])
        self.btn_salvar.state(["!disabled"] if sujo else ["disabled"])

    def _aplicar(self, novos: list[edicao.Evento], sel: Optional[list[int]] = None) -> None:
        self.hist.mudar(novos)
        self.atualizar(sel)

    # ------------------------------------------------------------------ #
    def desfazer(self) -> None:
        if self.hist.desfazer():
            self.atualizar()

    def refazer(self) -> None:
        if self.hist.refazer():
            self.atualizar()

    def apagar(self) -> None:
        s = self._indices()
        if s:
            self._aplicar(edicao.apagar(self.eventos, s), [min(s)])

    def duplicar(self) -> None:
        s = self._indices()
        if s:
            self._aplicar(edicao.duplicar(self.eventos, s))

    def _numero(self, titulo: str, msg: str, inicial: str) -> Optional[float]:
        txt = pedir_texto(self.j, self.app.t, titulo, msg, inicial)
        if txt is None:
            return None
        try:
            return float(txt.replace(",", "."))
        except ValueError:
            messagebox.showwarning(titulo, "Digite um número (ex.: 2,5).", parent=self.j)
            return None

    def espera(self) -> None:
        i = self._primeiro()
        if i is None:
            messagebox.showinfo("Inserir espera", "Selecione o evento ANTES do qual a espera entra.",
                                parent=self.j)
            return
        v = self._numero("Inserir espera", "Segundos de espera a inserir antes do evento selecionado "
                         "(negativo encurta a pausa):", "2")
        if v is not None:
            novos, ap = edicao.deslocar(self.eventos, i, v)
            if abs(ap - v) > 1e-6:
                self.app.log_texto(f"⚠ Encurtei só {abs(ap):g}s (não dá para passar do evento anterior).\n", "aviso")
            self._aplicar(novos, [i])

    def ajustar(self) -> None:
        i = self._primeiro()
        if i is None:
            return
        v = self._numero("Ajustar tempo", f"Novo instante do evento {i + 1} (segundos desde o início):",
                         f"{float(self.eventos[i].get('t', 0)):g}")
        if v is not None:
            self._aplicar(edicao.definir_tempo(self.eventos, i, v), [i])

    def marcador(self) -> None:
        i = self._primeiro()
        d = DialogoMarcador(self.app, self.j, listar_pngs(self.app.g.pasta))
        if d.resultado:
            r = d.resultado
            pos = i if i is not None else len(self.eventos)
            self._aplicar(edicao.inserir_marcador(self.eventos, pos, r["botao"], r["timeout"],
                                                  r["ate"], r["ao_estourar"]), [pos])

    def espera_final(self) -> None:
        """Segundos entre a última ação e o recomeço do loop (gravações antigas não têm isso)."""
        atual = float(self.dados.get("cauda", 0) or 0)
        v = self._numero("Espera final", "Segundos que a reprodução espera DEPOIS da última ação antes de "
                         "recomeçar o loop (ex.: se o jogo só termina 3 min depois do último clique):",
                         f"{atual:g}")
        if v is not None:
            self.dados["cauda"] = round(max(0.0, v), 3)
            self.atualizar()

    def cortar_antes(self) -> None:
        i = self._primeiro()
        if i is not None and i > 0 and messagebox.askyesno(
                "Cortar", f"Apagar os {i} evento(s) antes do selecionado?", parent=self.j):
            self._aplicar(edicao.cortar_antes(self.eventos, i), [0])

    def cortar_depois(self) -> None:
        s = self._indices()
        if s and s[-1] < len(self.eventos) - 1 and messagebox.askyesno(
                "Cortar", f"Apagar os {len(self.eventos) - 1 - s[-1]} evento(s) depois do selecionado?",
                parent=self.j):
            self._aplicar(edicao.cortar_depois(self.eventos, s[-1]))

    def salvar(self) -> bool:
        if self.eventos == self.salvo and float(self.dados.get("cauda", 0) or 0) == self._cauda_salva:
            return True
        try:
            bak = edicao.salvar(self.caminho, self.dados, self.eventos)
        except OSError as e:
            messagebox.showerror("Salvar", f"Não consegui salvar: {e}", parent=self.j)
            return False
        self.salvo = [dict(e) for e in self.eventos]
        self._cauda_salva = float(self.dados.get("cauda", 0) or 0)
        self.app.log_texto(f"✔ Gravação salva em {self.caminho}"
                           + (f" (original guardado em {bak})" if bak else "") + "\n", "ok")
        if self.ao_salvar:
            self.ao_salvar()
        self.atualizar()
        return True

    def fechar(self) -> None:
        if self.eventos != self.salvo or float(self.dados.get("cauda", 0) or 0) != self._cauda_salva:
            r = messagebox.askyesnocancel("Editar gravação", "Salvar as alterações antes de fechar?",
                                          parent=self.j)
            if r is None or (r and not self.salvar()):
                return
        self.j.destroy()
