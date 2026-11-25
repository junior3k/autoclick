# pyright: basic
"""Página Rotinas: vários scripts gravados do jogo, juntos (sequência + intervalos)."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Optional

from .. import jogos, rotina
from .dados import listar_pngs, resumo_gravacao
from .dialogos import escolher_item, pedir_texto
from .pagina import Pagina
from .widgets import BarraProgresso, Cartao, Rolavel, botao, entrada, marcar, numero


class PaginaRotinas(Pagina):
    chave = "rotinas"
    titulo = "Rotinas"
    subtitulo = ("Junte vários scripts gravados do jogo (coletar, ir à loja…). Eles se revezam: o mouse é um só, "
                 "então um script só começa quando o anterior termina.")

    # ------------------------------------------------------------------ #
    def caminho(self) -> str:
        return jogos.arquivos_do(self.app.jogos.atual()).get("rotina", "rotina.json")

    def construir(self) -> None:
        a, c, t = self.app, self.t.c, self.t
        rol = Rolavel(self.frame, t)
        rol.pack(fill="both", expand=True)
        g = rol.corpo
        self.rot: dict[str, Any] = rotina.ler(self.caminho())

        # ---- scripts ---- #
        k = Cartao(g, t, "Scripts gravados", "Cada script é uma gravação. “Gravar novo script” leva você à "
                   "página Gravar já com o arquivo certo.")
        k.pack(fill="x", pady=(0, 12))
        self.lbl_jogo = tk.Label(k.corpo, text="", bg=c["card"], fg=c["accent"], font=t.f_negrito, anchor="w")
        self.lbl_jogo.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.arv_s = ttk.Treeview(k.corpo, columns=("nome", "info"), show="headings", height=4, selectmode="browse")
        self.arv_s.heading("nome", text="Script")
        self.arv_s.heading("info", text="Conteúdo")
        self.arv_s.column("nome", width=130, stretch=False)
        self.arv_s.column("info", width=380)
        self.arv_s.grid(row=1, column=0, columnspan=2, sticky="ew")
        b = tk.Frame(k.corpo, bg=c["card"])
        b.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        botao(b, "Gravar novo script…", self.novo_script, "Accent", True).pack(side="left")
        botao(b, "Testar este script", self.testar_script, "Ghost", True).pack(side="left", padx=6)
        botao(b, "Abrir na página Gravar", self.abrir_script, "Ghost", True).pack(side="left")
        botao(b, "Apagar", self.apagar_script, "Danger", True).pack(side="right")

        # ---- sequência ---- #
        s = Cartao(g, t, "Rotina em sequência (a lista inteira repete)",
                   "Em ordem. Entre os itens, use esperas: um tempo fixo, ou esperar um botão/NPC aparecer.")
        s.pack(fill="x", pady=(0, 12))
        self.arv_i = ttk.Treeview(s.corpo, columns=("n", "item"), show="headings", height=6, selectmode="browse")
        self.arv_i.heading("n", text="#")
        self.arv_i.heading("item", text="Item")
        self.arv_i.column("n", width=34, stretch=False)
        self.arv_i.column("item", width=470)
        self.arv_i.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.arv_i.bind("<Double-1>", lambda _e: self.editar_item())
        b = tk.Frame(s.corpo, bg=c["card"])
        b.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        botao(b, "+ Script…", self.add_script, "Ghost", True).pack(side="left")
        botao(b, "+ Esperar tempo…", self.add_espera, "Ghost", True).pack(side="left", padx=4)
        botao(b, "+ Esperar botão/NPC…", self.add_botao, "Ghost", True).pack(side="left")
        b2 = tk.Frame(s.corpo, bg=c["card"])
        b2.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        botao(b2, "Editar", self.editar_item, "Ghost", True).pack(side="left")
        botao(b2, "↑", lambda: self.mover(-1), "Ghost", True).pack(side="left", padx=4)
        botao(b2, "↓", lambda: self.mover(1), "Ghost", True).pack(side="left")
        botao(b2, "Remover", self.remover_item, "Danger", True).pack(side="right")
        self.v_voltas = tk.StringVar(value=str(int(self.rot.get("voltas", 0) or 0)))
        self.v_pausa_s = tk.StringVar(value=f"{float(self.rot.get('pausa_entre_scripts', 0.5)):g}")
        self.v_pausa_v = tk.StringVar(value=f"{float(self.rot.get('pausa_volta', 1.0)):g}")
        for v in (self.v_voltas, self.v_pausa_s, self.v_pausa_v):
            v.trace_add("write", lambda *_a: self._opcoes_mudaram())
        s.campo("Repetir a rotina (voltas; 0 = até parar)", numero(s.corpo, self.v_voltas, 0, 100000, 1, 8))
        s.campo("Tempo entre um script e outro (s)", numero(s.corpo, self.v_pausa_s, 0, 3600, 0.5, 8),
                "Vale para todos. Para um tempo específico, use “+ Esperar tempo”.")
        s.campo("Tempo entre uma volta e outra (s)", numero(s.corpo, self.v_pausa_v, 0, 3600, 0.5, 8))

        # ---- intervalos ---- #
        i = Cartao(g, t, "Em intervalos (entram sozinhos quando chega a hora)",
                   "Ex.: loja a cada 300 s. Só começam entre scripts (ou durante uma espera), nunca no meio de um.")
        i.pack(fill="x", pady=(0, 12))
        self.arv_v = ttk.Treeview(i.corpo, columns=("on", "txt"), show="headings", height=3, selectmode="browse")
        self.arv_v.heading("on", text="Ativo")
        self.arv_v.heading("txt", text="Intervalo")
        self.arv_v.column("on", width=50, stretch=False)
        self.arv_v.column("txt", width=450)
        self.arv_v.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.arv_v.bind("<Double-1>", lambda _e: self.alternar_intervalo())
        b = tk.Frame(i.corpo, bg=c["card"])
        b.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        botao(b, "+ Intervalo…", self.add_intervalo, "Ghost", True).pack(side="left")
        botao(b, "Ligar/desligar", self.alternar_intervalo, "Ghost", True).pack(side="left", padx=6)
        botao(b, "Editar", self.editar_intervalo, "Ghost", True).pack(side="left")
        botao(b, "Remover", self.remover_intervalo, "Danger", True).pack(side="right")

        # ---- executar ---- #
        e = Cartao(g, t, "Executar", "Se algo falhar (script, botão que não aparece, desconexão), a rotina para e "
                   "avisa. A volta completa conta nas estatísticas e toca o som.")
        e.pack(fill="x", pady=(0, 12))
        e.linha_cheia(marcar(e.corpo, "A tecla de reproduzir (F11) inicia/para a rotina em vez da gravação",
                             a.var("f11_rotina")))
        self.lbl_prob = tk.Label(e.corpo, text="", bg=c["card"], fg=c["warn"], font=t.f_pequena, anchor="w",
                                 justify="left", wraplength=520)
        e.linha_cheia(self.lbl_prob, (4, 0))
        b = tk.Frame(e.corpo, bg=c["card"])
        e.linha_cheia(b, (8, 0))
        self.btn_ini = botao(b, "▶ Iniciar rotina", self.iniciar, "Accent")
        self.btn_ini.pack(side="left")
        botao(b, "■ Parar", a.parar, "Danger").pack(side="left", padx=8)
        self.barra = BarraProgresso(e.corpo, t)
        e.linha_cheia(self.barra, (10, 0))
        self.recarregar()

    # ------------------------------------------------------------------ #
    def ao_mostrar(self) -> None:
        self.rot = rotina.ler(self.caminho())
        self.recarregar()

    def ao_estado(self, rodando: bool) -> None:
        self.btn_ini.state(["disabled"] if rodando else ["!disabled"])

    def ao_status(self, d: dict[str, Any]) -> None:
        self.barra.atualizar(d.get("progresso") if d else None)

    def _salvar(self) -> None:
        rotina.salvar(self.caminho(), self.rot)
        self.recarregar()

    def _opcoes_mudaram(self) -> None:
        def f(v: tk.StringVar, padrao: float) -> float:
            try:
                return max(0.0, float(v.get().replace(",", ".")))
            except ValueError:
                return padrao
        self.rot["voltas"] = int(f(self.v_voltas, 0))
        self.rot["pausa_entre_scripts"] = f(self.v_pausa_s, 0.5)
        self.rot["pausa_volta"] = f(self.v_pausa_v, 1.0)
        rotina.salvar(self.caminho(), self.rot)

    def scripts(self) -> dict[str, str]:
        return rotina.listar_scripts(self.caminho())

    def recarregar(self) -> None:
        sc = self.scripts()
        self.lbl_jogo.configure(text=f"Jogo: {self.app.jogos.nome_atual()}")
        for arv in (self.arv_s, self.arv_i, self.arv_v):
            for x in arv.get_children():
                arv.delete(x)
        for n, p in sc.items():
            self.arv_s.insert("", "end", iid=n, values=(n, resumo_gravacao(p)))
        for n, it in enumerate(self.rot["itens"]):
            self.arv_i.insert("", "end", iid=str(n), values=(n + 1, rotina.descrever(it)))
        for n, iv in enumerate(self.rot["intervalos"]):
            ant = f" · antes espera [{iv['antes_botao']}]" if iv.get("antes_botao") else ""
            self.arv_v.insert("", "end", iid=str(n), values=(
                "✔" if iv.get("ativo", True) else "—", f"{iv.get('script', '?')} a cada {float(iv.get('a_cada', 0)):g} s{ant}"))
        prob = rotina.validar(self.rot, set(sc)) if self.rot["itens"] else []
        self.lbl_prob.configure(text="\n".join("⚠ " + p for p in prob))

    # ---- scripts ---- #
    def _sel_script(self) -> Optional[str]:
        s = self.arv_s.selection()
        return s[0] if s else None

    def novo_script(self) -> None:
        n = pedir_texto(self.app.raiz, self.t, "Novo script", "Nome do script (ex.: coletar, loja):")
        n = rotina.nome_valido(n or "")
        if not n:
            return
        if n in self.scripts():
            messagebox.showinfo("Novo script", f"Já existe um script “{n}”.", parent=self.app.raiz)
            return
        self._apontar(rotina.caminho_do_script(self.caminho(), n), "gravar")
        self.app.log_texto(f"ℹ Grave o script “{n}” normalmente (F9 para terminar); ele fica na lista de scripts.\n", "aviso")

    def abrir_script(self) -> None:
        n = self._sel_script()
        if n:
            self._apontar(self.scripts()[n], "gravar")

    def testar_script(self) -> None:
        n = self._sel_script()
        if not n or self.app.exec.rodando:
            return
        self.app.g.gravacao = self.scripts()[n]
        self.app.rodar("reproduzir", __import__("autoclick.interface.comandos", fromlist=["x"]).reproduzir(self.app.g),
                       minimizar=True)

    def _apontar(self, arquivo: str, pagina: str) -> None:
        self.app.g.gravacao = arquivo
        os.makedirs(os.path.dirname(arquivo) or ".", exist_ok=True)
        self.app.jogo_mudou()
        self.app.ir(pagina)

    def apagar_script(self) -> None:
        n = self._sel_script()
        if not n:
            return
        usado = any(it.get("script") == n for it in self.rot["itens"]) or any(
            iv.get("script") == n for iv in self.rot["intervalos"])
        if messagebox.askyesno("Apagar script", f"Apagar o script “{n}”?" + (
                "\nEle está na rotina; a rotina ficará com um item inválido." if usado else ""), parent=self.app.raiz):
            try:
                os.remove(self.scripts()[n])
            except OSError:
                pass
            self.recarregar()

    # ---- itens da sequência ---- #
    def _sel_item(self) -> Optional[int]:
        s = self.arv_i.selection()
        return int(s[0]) if s else None

    def _num(self, titulo: str, msg: str, inicial: float, minimo: float = 0.0) -> Optional[float]:
        txt = pedir_texto(self.app.raiz, self.t, titulo, msg, f"{inicial:g}")
        if txt is None:
            return None
        try:
            return max(minimo, float(txt.replace(",", ".")))
        except ValueError:
            messagebox.showwarning(titulo, "Digite um número (ex.: 2,5).", parent=self.app.raiz)
            return None

    def _botoes(self) -> list[str]:
        nomes = list(listar_pngs(self.app.g.pasta))
        if self.app.g.jogo.strip() not in ("", "geral"):
            nomes += [n for n in listar_pngs(self.app.g.pasta_geral) if n not in nomes]
        return nomes

    def _pedir_script(self, inicial: str = "") -> Optional[str]:
        itens = list(self.scripts())
        if not itens:
            messagebox.showinfo("Script", "Grave ao menos um script primeiro.", parent=self.app.raiz)
            return None
        r = escolher_item(self.app.raiz, self.t, "Script", "Qual script?", ([inicial] if inicial in itens else []) +
                          [x for x in itens if x != inicial])
        return r if r in itens else None

    def _inserir(self, item: dict[str, Any]) -> None:
        i = self._sel_item()
        pos = len(self.rot["itens"]) if i is None else i + 1
        self.rot["itens"].insert(pos, item)
        self._salvar()
        self.arv_i.selection_set(str(pos))

    def add_script(self) -> None:
        n = self._pedir_script()
        if not n:
            return
        vezes = self._num("Repetições", "Quantas vezes seguidas este script roda?", 1, 1)
        if vezes is None:
            return
        item: dict[str, Any] = {"tipo": "script", "script": n, "vezes": int(vezes)}
        if messagebox.askyesno("Esperar antes?", "Este script depende de um botão/NPC ficar disponível antes de "
                               "começar?", parent=self.app.raiz):
            b = escolher_item(self.app.raiz, self.t, "Esperar antes", "Qual botão precisa aparecer antes?",
                              self._botoes())
            if b:
                item["antes_botao"] = b
                item["antes_timeout"] = self._num("Tempo máximo", "Esperar no máximo quantos segundos? "
                                                  "(se passar, a rotina para e avisa)", 60, 1) or 60
        self._inserir(item)

    def add_espera(self) -> None:
        v = self._num("Esperar", "Esperar quantos segundos?", 20, 0.1)
        if v is not None:
            self._inserir({"tipo": "esperar", "segundos": v})

    def add_botao(self) -> None:
        b = escolher_item(self.app.raiz, self.t, "Esperar botão", "Qual botão/NPC precisa aparecer?",
                          self._botoes())
        if not b:
            return
        v = self._num("Tempo máximo", "Esperar no máximo quantos segundos?", 60, 1)
        if v is None:
            return
        seguir = messagebox.askyesno("Se não aparecer", "Se o botão não aparecer a tempo, SEGUIR mesmo assim?\n\n"
                                     "Sim = segue a rotina · Não = para e avisa", parent=self.app.raiz)
        self._inserir({"tipo": "esperar_botao", "botao": b, "timeout": v, "ate": "aparecer",
                       "ao_estourar": "seguir" if seguir else "parar"})

    def editar_item(self) -> None:
        i = self._sel_item()
        if i is None:
            return
        it = self.rot["itens"][i]
        if it.get("tipo") == "script":
            n = self._pedir_script(str(it.get("script", "")))
            v = self._num("Repetições", "Quantas vezes seguidas?", float(it.get("vezes", 1)), 1) if n else None
            if n and v is not None:
                it["script"], it["vezes"] = n, int(v)
        elif it.get("tipo") == "esperar":
            v = self._num("Esperar", "Esperar quantos segundos?", float(it.get("segundos", 20)), 0.1)
            if v is not None:
                it["segundos"] = v
        else:
            v = self._num("Tempo máximo", "Esperar no máximo quantos segundos?", float(it.get("timeout", 60)), 1)
            if v is not None:
                it["timeout"] = v
        self._salvar()
        self.arv_i.selection_set(str(i))

    def mover(self, d: int) -> None:
        i = self._sel_item()
        if i is None or not 0 <= i + d < len(self.rot["itens"]):
            return
        L = self.rot["itens"]
        L[i], L[i + d] = L[i + d], L[i]
        self._salvar()
        self.arv_i.selection_set(str(i + d))

    def remover_item(self) -> None:
        i = self._sel_item()
        if i is not None:
            del self.rot["itens"][i]
            self._salvar()

    # ---- intervalos ---- #
    def _sel_iv(self) -> Optional[int]:
        s = self.arv_v.selection()
        return int(s[0]) if s else None

    def add_intervalo(self) -> None:
        n = self._pedir_script()
        if not n:
            return
        v = self._num("Intervalo", "Rodar este script a cada quantos segundos?", 300, 1)
        if v is None:
            return
        iv: dict[str, Any] = {"script": n, "a_cada": v, "ativo": True}
        if messagebox.askyesno("Esperar antes?", "Ele depende de um botão/NPC ficar disponível antes?",
                               parent=self.app.raiz):
            b = escolher_item(self.app.raiz, self.t, "Esperar antes", "Qual botão precisa aparecer?", self._botoes())
            if b:
                iv["antes_botao"] = b
                iv["antes_timeout"] = self._num("Tempo máximo", "Esperar no máximo quantos segundos?", 60, 1) or 60
        self.rot["intervalos"].append(iv)
        self._salvar()

    def editar_intervalo(self) -> None:
        i = self._sel_iv()
        if i is None:
            return
        v = self._num("Intervalo", "A cada quantos segundos?", float(self.rot["intervalos"][i].get("a_cada", 300)), 1)
        if v is not None:
            self.rot["intervalos"][i]["a_cada"] = v
            self._salvar()

    def alternar_intervalo(self) -> None:
        i = self._sel_iv()
        if i is not None:
            iv = self.rot["intervalos"][i]
            iv["ativo"] = not iv.get("ativo", True)
            self._salvar()

    def remover_intervalo(self) -> None:
        i = self._sel_iv()
        if i is not None:
            del self.rot["intervalos"][i]
            self._salvar()

    # ---- executar ---- #
    def iniciar(self) -> None:
        if self.app.exec.rodando:
            return
        prob = rotina.validar(self.rot, set(self.scripts()))
        if prob:
            messagebox.showwarning("Rotina", "Corrija antes de iniciar:\n\n" + "\n".join(prob), parent=self.app.raiz)
            return
        from . import comandos
        self.app.rodar("reproduzir", comandos.rotina(self.app.g, self.caminho()), minimizar=True)
