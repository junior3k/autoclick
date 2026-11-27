# pyright: basic
"""Página Rotinas: vários scripts gravados do jogo, juntos (sequência + intervalos)."""
from __future__ import annotations

import json
import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Optional

from .. import jogos, rotina
from .dados import duracao_gravacao, listar_pngs, resumo_gravacao
from .dialogos import escolher_item, pedir_texto
from .pagina import Pagina
from .widgets import BarraProgresso, Cartao, ListaRica, Rolavel, botao, entrada, marcar, numero


class PaginaRotinas(Pagina):
    chave = "rotinas"
    titulo = "Rotinas"
    subtitulo = ""

    # ------------------------------------------------------------------ #
    def caminho(self) -> str:
        return jogos.arquivos_do(self.app.jogos.atual()).get("rotina", "rotina.json")

    def construir(self) -> None:
        a, c, t = self.app, self.t.c, self.t
        self.rot: dict[str, Any] = rotina.ler(self.caminho())

        # ---- barra de execução: FIXA no topo (não rola com a página) ---- #
        e = tk.Frame(self.frame, bg=c["card"], highlightthickness=1, highlightbackground=c["border"])
        e.pack(fill="x", pady=(0, 10))
        topo = tk.Frame(e, bg=c["card"])
        topo.pack(fill="x", padx=16, pady=10)
        self.lbl_jogo = tk.Label(topo, text="", bg=c["card"], fg=c["accent"], font=t.f_negrito, anchor="w")
        self.lbl_jogo.pack(side="left")
        self.btn_ini = botao(topo, "▶ Iniciar rotina", self.iniciar, "Accent")
        self.btn_ini.pack(side="right", padx=8)
        self.barra = BarraProgresso(e, t)
        self.barra.configure(bg=c["card"])
        self.barra.lbl.configure(bg=c["card"])
        self._barra_visivel = False

        self.rol = Rolavel(self.frame, t)
        self.rol.pack(fill="both", expand=True)
        g = self.rol.corpo

        # ---- a rotina: uma lista só ---- #
        s = Cartao(g, t, "Sua rotina", "")
        s.pack(fill="x", pady=(0, 12))
        b = tk.Frame(s.corpo, bg=c["card"])
        s.linha_cheia(b, 0)
        botao(b, "+ Script…", self.mais_script, "Accent", True).pack(side="left")
        botao(b, "+ Esperar tempo…", self.add_espera, "Ghost", True).pack(side="left", padx=4)
        botao(b, "+ Esperar botão/NPC…", self.add_botao, "Ghost", True).pack(side="left")
        b2 = tk.Frame(s.corpo, bg=c["card"])
        s.linha_cheia(b2, (6, 0))
        botao(b2, "Editar", self.editar, "Ghost", True).pack(side="left")
        botao(b2, "↑", lambda: self.mover(-1), "Ghost", True).pack(side="left", padx=4)
        botao(b2, "↓", lambda: self.mover(1), "Ghost", True).pack(side="left")
        botao(b2, "Duplicar", self.duplicar, "Ghost", True).pack(side="left", padx=(4, 0))
        botao(b2, "Ligar/desligar", self.alternar_intervalo, "Ghost", True).pack(side="left", padx=4)
        botao(b2, "Testar script", self.testar_da_lista, "Ghost", True).pack(side="left")
        botao(b2, "Remover", self.remover, "Danger", True).pack(side="right")
        self.arv = ListaRica(s.corpo, t, [("n", "#", 44, False, False), ("oque", "O quê", 230, True, False),
                                          ("quando", "Quando", 170, False, True), ("det", "Detalhes", 230, True, False)],
                             "A rotina está vazia: use “+ Script…” para começar.")
        s.linha_cheia(self.arv, (8, 0))
        self.arv.bind("<Double-1>", lambda _e: self.duplo_clique())
        self.v_voltas = tk.StringVar(value=str(int(self.rot.get("voltas", 0) or 0)))
        self.v_pausa_s = tk.StringVar(value=f"{float(self.rot.get('pausa_entre_scripts', 0.5)):g}")
        self.v_pausa_v = tk.StringVar(value=f"{float(self.rot.get('pausa_volta', 1.0)):g}")
        for v in (self.v_voltas, self.v_pausa_s, self.v_pausa_v):
            v.trace_add("write", lambda *_a: self._opcoes_mudaram())
        op = tk.Frame(s.corpo, bg=c["card"])
        s.linha_cheia(op, (8, 0))
        for rotulo, var, mx, passo in (("Voltas (0 = até parar)", self.v_voltas, 100000, 1),
                                      ("Entre scripts (s)", self.v_pausa_s, 3600, 0.5),
                                      ("Entre voltas (s)", self.v_pausa_v, 3600, 0.5)):
            tk.Label(op, text=rotulo, bg=c["card"], fg=c["muted"], font=t.f_pequena).pack(side="left", padx=(0, 6))
            numero(op, var, 0, mx, passo, 7).pack(side="left", padx=(0, 18))
        self.lbl_prob = tk.Label(s.corpo, text="", bg=c["card"], fg=c["warn"], font=t.f_pequena, anchor="w",
                                 justify="left", wraplength=520)
        s.linha_cheia(self.lbl_prob, (6, 0))
        s.bind("<Configure>", lambda ev: self.lbl_prob.configure(wraplength=max(200, ev.width - 60)), add="+")
        s.linha_cheia(marcar(s.corpo, "A tecla de reproduzir (F11) inicia/para a rotina em vez da gravação",
                             a.var("f11_rotina")), (6, 0))
        self.lbl_janela = tk.Label(s.corpo, text="", bg=c["card"], fg=c["muted"], font=t.f_pequena, anchor="w")
        s.linha_cheia(self.lbl_janela, (2, 0))

        # ---- prévia: o que vai acontecer (sem rodar nada) ---- #
        pv = Cartao(g, t, "O que vai acontecer", "")
        pv.pack(fill="x", pady=(0, 12))
        self.txt_previa = tk.Text(pv.corpo, height=11, bg=c["field"], fg=c["text"], font=("Consolas", 9),
                                  relief="flat", highlightthickness=1, highlightbackground=c["border"],
                                  wrap="none", state="disabled", padx=10, pady=8)
        self.txt_previa.tag_configure("volta", foreground=c["muted"])
        self.txt_previa.tag_configure("inter", foreground=c["warn"])
        self.txt_previa.tag_configure("hora", foreground=c["accent"])
        pv.linha_cheia(self.txt_previa, (6, 0))

        # ---- biblioteca de scripts (recolhível) ---- #
        self._lib_aberta = True
        self.btn_lib = botao(g, "", self._alternar_biblioteca, "Ghost", True)
        self.btn_lib.pack(anchor="w", pady=(0, 6))
        k = Cartao(g, t, "", "Cada script é uma gravação. Grave um novo aqui, ou traga gravações .json que você já "
                   "fez na página Gravar (“Importar gravação…”).")
        self.cartao_lib = k
        k.pack(fill="x", pady=(0, 12))
        self.arv_s = ListaRica(k.corpo, t, [("nome", "Script", 150, False, False), ("info", "Conteúdo", 380, True, False)],
                               "Nenhum script ainda: grave um novo ou importe uma gravação .json.")
        k.linha_cheia(self.arv_s, (8, 0))
        b = tk.Frame(k.corpo, bg=c["card"])
        k.linha_cheia(b, (8, 0))
        botao(b, "Gravar novo script…", self.novo_script, "Accent", True).pack(side="left")
        botao(b, "Importar gravação…", self.importar_script, "Ghost", True).pack(side="left", padx=6)
        botao(b, "Apagar", self.apagar_script, "Danger", True).pack(side="right")
        b = tk.Frame(k.corpo, bg=c["card"])
        k.linha_cheia(b, (6, 0))
        botao(b, "Testar este script", self.testar_script, "Ghost", True).pack(side="left")
        botao(b, "Abrir na página Gravar", self.abrir_script, "Ghost", True).pack(side="left", padx=6)
        self.recarregar()

    def _alternar_biblioteca(self) -> None:
        self._lib_aberta = not self._lib_aberta
        if self._lib_aberta:
            self.cartao_lib.pack(fill="x", pady=(0, 12))
        else:
            self.cartao_lib.pack_forget()
        self._rotulo_biblioteca()

    def _rotulo_biblioteca(self) -> None:
        self.btn_lib.configure(text=("▾" if self._lib_aberta else "▸") + f" Biblioteca de scripts ({len(self.scripts())})")

    # ------------------------------------------------------------------ #
    def ao_mostrar(self) -> None:
        self.rot = rotina.ler(self.caminho())
        self.recarregar()
        self.rol.canvas.yview_moveto(0)

    def ao_estado(self, rodando: bool) -> None:
        self.btn_ini.state(["disabled"] if rodando else ["!disabled"])

    def ao_status(self, d: dict[str, Any]) -> None:
        p = d.get("progresso") if d else None
        self.barra.atualizar(p)
        if p and not self._barra_visivel:        # a barra só aparece enquanto há progresso
            self.barra.pack(fill="x", padx=16, pady=(0, 10))
            self._barra_visivel = True
        elif not p and self._barra_visivel:
            self.barra.pack_forget()
            self._barra_visivel = False

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

    @staticmethod
    def _linha_item(n: int, it: dict[str, Any]) -> tuple[Any, ...]:
        t = it.get("tipo")
        if t == "script":
            det = (f"espera [{it['antes_botao']}] até {float(it.get('antes_timeout', 60)):g} s"
                   if it.get("antes_botao") else "")
            return (n + 1, f"▶ {it.get('script', '?')} ×{int(it.get('vezes', 1) or 1)}", "na sequência", det)
        if t == "esperar":
            dur = ", ".join(str(x) for x in (it.get("durante") or []))
            return (n + 1, f"   esperar {float(it.get('segundos', 0)):g} s", "na sequência",
                    f"enquanto espera: {dur}" if dur else "")
        v = "sumir" if str(it.get("ate", "aparecer")) == "sumir" else "aparecer"
        return (n + 1, f"   esperar [{it.get('botao', '?')}] {v}", "na sequência",
                f"até {float(it.get('timeout', 60)):g} s · se estourar: "
                f"{'seguir' if it.get('ao_estourar') == 'seguir' else 'parar'}")

    @staticmethod
    def _linha_intervalo(iv: dict[str, Any]) -> tuple[Any, ...]:
        seg = float(iv.get("a_cada", 0) or 0)
        quando = f"a cada {seg:g} s" + (f" ({seg / 60:g} min)" if seg >= 120 else "")
        ativo = iv.get("ativo", True)
        det = (f"espera [{iv['antes_botao']}]" if iv.get("antes_botao") else "") + ("" if ativo else " · desligado")
        return ("✔" if ativo else "—", f"▶ {iv.get('script', '?')}", quando, det.strip(" ·"))

    def recarregar(self) -> None:
        sc = self.scripts()
        self.lbl_jogo.configure(text=f"Rotina: {self.app.jogos.nome_atual()}")
        for arv in (self.arv_s, self.arv):
            for x in arv.get_children():
                arv.delete(x)
        for n, p in sc.items():
            self.arv_s.insert("", "end", iid=n, values=(n, resumo_gravacao(p)))
        self.arv.insert("", "end", iid="gi", values=("", "NA SEQUÊNCIA — repete a cada volta", "", ""), tags=("grupo",))
        for n, it in enumerate(self.rot["itens"]):
            self.arv.insert("", "end", iid=f"i{n}", values=self._linha_item(n, it),
                            tags=("ok",) if it.get("tipo") == "script" else ("neutro",))
        self.arv.insert("", "end", iid="gv", values=("", "ENTRAM SOZINHOS — quando chega a hora", "", ""), tags=("grupo",))
        for n, iv in enumerate(self.rot["intervalos"]):
            self.arv.insert("", "end", iid=f"v{n}", values=self._linha_intervalo(iv),
                            tags=("warn",) if iv.get("ativo", True) else ("warn", "off"))
        j = self.app.g.janela.strip()
        self.lbl_janela.configure(text=f"Janela do jogo: {j}" if j else "")
        self._rotulo_biblioteca()
        self._atualizar_previa(sc)
        prob = rotina.validar(self.rot, set(sc)) if self.rot["itens"] else []
        for chave, rotulo in (("pausa_entre_scripts", "Tempo entre um script e outro"), ("pausa_volta", "Tempo entre uma volta e outra")):
            v = float(self.rot.get(chave, 0) or 0)
            if v >= 60:
                prob.append(f"“{rotulo}” está em {v:g} s (≈ {v / 60:.1f} min): a rotina vai ficar parada esse tempo sem fazer nada.")
        if self.rot["itens"] and not prob and not self.app.g.janela.strip() and not self._algum_titulo(sc):
            prob.append("Nenhum script guarda a janela do jogo e a janela não está definida em Configurações: "
                        "a rotina não saberia onde clicar. Defina a janela em Configurações.")
        self.lbl_prob.configure(text="\n".join("⚠ " + p for p in prob))

    def _atualizar_previa(self, sc: dict[str, str]) -> None:
        if not self.rot["itens"]:
            texto: list[tuple[str, str]] = [("A rotina está vazia: adicione scripts para ver a prévia.\n", "volta")]
        else:
            dur = {n: duracao_gravacao(p) for n, p in sc.items()}
            texto = []
            for seg, linha in rotina.simular(self.rot, dur, 3600.0, 70):
                hora = f"{int(seg) // 3600:d}:{int(seg) % 3600 // 60:02d}:{int(seg) % 60:02d}"
                tag = "volta" if linha.startswith(("—", "…")) else "inter" if "intervalo" in linha else ""
                texto.append((hora + "  ", "hora"))
                texto.append((linha + "\n", tag))
        self.txt_previa.configure(state="normal")
        self.txt_previa.delete("1.0", "end")
        for trecho, tag in texto:
            self.txt_previa.insert("end", trecho, tag)
        self.txt_previa.configure(state="disabled")

    @staticmethod
    def _algum_titulo(sc: dict[str, str]) -> bool:

        for caminho in sc.values():
            try:
                d: Any = json.loads(open(caminho, encoding="utf-8").read())
                t = (d.get("janela") or {}).get("titulo")
                if t and not str(t).lower().startswith("autoclick inteligente"):
                    return True
            except (OSError, ValueError, AttributeError):
                continue
        return False

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

    def importar_script(self) -> None:
        """Traz para a rotina gravações .json já feitas (da página Gravar ou de outro jogo)."""
        arqs = filedialog.askopenfilenames(
            parent=self.app.raiz, title="Importar gravação(ões)", filetypes=[("Gravação (.json)", "*.json")],
            initialdir=os.path.dirname(os.path.abspath(self.app.g.gravacao)) if self.app.g.gravacao else None)
        if not arqs:
            return
        trazidos: list[str] = []
        recusados: list[str] = []
        for arq in arqs:
            try:
                d: Any = json.loads(open(arq, encoding="utf-8").read())
                ok = isinstance(d, dict) and isinstance(d.get("eventos"), list) and bool(d["eventos"])
            except (OSError, ValueError):
                ok = False
            if not ok:
                recusados.append(os.path.basename(arq))
                continue
            base = rotina.nome_valido(os.path.splitext(os.path.basename(arq))[0]) or "script"
            nome, k = base, 2
            while nome in self.scripts():
                nome, k = f"{base}_{k}", k + 1
            destino = rotina.caminho_do_script(self.caminho(), nome)
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            shutil.copyfile(arq, destino)
            trazidos.append(nome)
        self.recarregar()
        if trazidos:
            self.arv_s.selection_set(trazidos[0])
            self.app.log_texto("✔ Importado para a rotina: " + ", ".join(trazidos) + ".\n", "ok")
        if recusados:
            messagebox.showwarning("Importar gravação", "Não parecem gravações (sem eventos) e foram ignorados:\n\n"
                                   + "\n".join(recusados), parent=self.app.raiz)

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
    def _sel(self, prefixo: str) -> Optional[int]:
        sel = self.arv.selection()
        return int(sel[0][1:]) if sel and sel[0].startswith(prefixo) else None

    def _sel_item(self) -> Optional[int]:
        return self._sel("i")

    def _sel_iv(self) -> Optional[int]:
        return self._sel("v")

    def _selecionar(self, prefixo: str, n: int) -> None:
        self.arv.selection_set(f"{prefixo}{n}")

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
        self._selecionar("i", pos)

    def mais_script(self) -> None:
        """+ Script: escolhe o script e QUANDO ele roda (na sequência ou a cada X segundos)."""
        q = escolher_item(self.app.raiz, self.t, "Quando roda?", "Quando este script roda?",
                          ["Na sequência (repete a cada volta)", "A cada X segundos (entra sozinho)"])
        if not q:
            return
        if q.startswith("A cada"):
            self.add_intervalo()
        else:
            self.add_script()

    def editar(self) -> None:
        if self._sel_iv() is not None:
            self.editar_intervalo()
        else:
            self.editar_item()

    def remover(self) -> None:
        if self._sel_iv() is not None:
            self.remover_intervalo()
        else:
            self.remover_item()

    def duplo_clique(self) -> None:
        if self._sel_iv() is not None:
            self.alternar_intervalo()
        else:
            self.editar_item()

    def testar_da_lista(self) -> None:
        """Testa o script da linha selecionada (item da sequência ou intervalo)."""
        i, v = self._sel_item(), self._sel_iv()
        nome = (self.rot["itens"][i].get("script") if i is not None and self.rot["itens"][i].get("tipo") == "script"
                else self.rot["intervalos"][v].get("script") if v is not None else None)
        if nome and nome in self.scripts():
            self.arv_s.selection_set(nome)
            self.testar_script()

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
            self._inserir({"tipo": "esperar", "segundos": v, "durante": self._pedir_durante([])})

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

    def _pedir_durante(self, atual: list[str]) -> list[str]:
        """Scripts que rodam durante uma espera (ex.: vender na loja enquanto as plantas nascem)."""
        txt = (f"Hoje roda durante a espera: {', '.join(atual)}.\n\n" if atual else "") + \
              "Rodar algum script durante essa espera?\n(ele termina por inteiro e a espera só acaba depois do " \
              "tempo total)\n\nSim = escolher · Não = nenhum"
        if not messagebox.askyesno("Durante a espera", txt, parent=self.app.raiz):
            return []
        lista: list[str] = []
        while True:
            n = self._pedir_script(lista[-1] if lista else (atual[0] if atual else ""))
            if not n:
                break
            lista.append(n)
            if not messagebox.askyesno("Durante a espera", f"Rodar: {', '.join(lista)}.\n\nAdicionar mais um script?",
                                       parent=self.app.raiz):
                break
        return lista

    def duplicar(self) -> None:
        i = self._sel_item()
        if i is None:
            return
        self.rot["itens"].insert(i + 1, json.loads(json.dumps(self.rot["itens"][i])))
        self._salvar()
        self._selecionar("i", i + 1)

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
                it["durante"] = self._pedir_durante([str(x) for x in (it.get("durante") or [])])
        else:
            v = self._num("Tempo máximo", "Esperar no máximo quantos segundos?", float(it.get("timeout", 60)), 1)
            if v is not None:
                it["timeout"] = v
        self._salvar()
        self._selecionar("i", i)

    def mover(self, d: int) -> None:
        i = self._sel_item()
        if i is None or not 0 <= i + d < len(self.rot["itens"]):
            return
        L = self.rot["itens"]
        L[i], L[i + d] = L[i + d], L[i]
        self._salvar()
        self._selecionar("i", i + d)

    def remover_item(self) -> None:
        i = self._sel_item()
        if i is not None:
            del self.rot["itens"][i]
            self._salvar()

    # ---- intervalos ---- #
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
        self._selecionar("v", len(self.rot["intervalos"]) - 1)

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
