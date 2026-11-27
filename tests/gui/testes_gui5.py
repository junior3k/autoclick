"""GUI: página Rotinas (scripts, sequência, esperas, intervalos, executar, F11)."""
import sys as _s0
for _f in (_s0.stdout, _s0.stderr):
    try: _f.reconfigure(encoding="utf-8", errors="replace")  # Windows (cp1252) não imprime setas
    except Exception: pass
import sys, os, time, json, shutil, tempfile
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
ROOT = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp(); shutil.copytree(f"{ROOT}/proj", f"{tmp}/p"); os.chdir(f"{tmp}/p")
os.environ["PYTHONPATH"] = os.pathsep.join([RAIZ] + [x for x in sys.path if x]); os.environ["AUTOCLICK_SEM_OCR"] = "1"
from autoclick.interface.app import App
from autoclick.interface.dados import Geral
from autoclick.interface import pag_rotinas as PR
from autoclick import rotina as R, jogos as J
ok = 0
def check(n, c, extra=""):
    global ok
    print(("  OK   " if c else "  FALHOU ") + n + (f"  {extra}" if extra and not c else ""))
    if not c: sys.exit(1)
    ok += 1
g = Geral(); app = App(g, os.getcwd()); r = app.raiz
def bombear(s=0.2):
    t0 = time.time()
    while time.time() - t0 < s: r.update(); time.sleep(0.02)
bombear()
os.makedirs("gravacoes")
for n in ("coletar", "loja", "plantar"):
    json.dump({"janela": {"titulo": "Roblox"}, "cauda": 5, "eventos": [{"t": 0, "tipo": "clique", "x": 1, "y": 1}, {"t": 2, "tipo": "clique", "x": 2, "y": 2}]}, open(f"gravacoes/{n}.json", "w"))
app.ir("rotinas"); bombear(); pg = app.paginas["rotinas"]
resp = {"texto": [], "item": [], "sim": []}
PR.pedir_texto = lambda *a, **k: resp["texto"].pop(0) if resp["texto"] else None
PR.escolher_item = lambda *a, **k: resp["item"].pop(0) if resp["item"] else None
class MB:
    @staticmethod
    def askyesno(*a, **k): return resp["sim"].pop(0) if resp["sim"] else False
    showinfo = showwarning = showerror = staticmethod(lambda *a, **k: None)
PR.messagebox = MB

print("1) Scripts")
check("lista os scripts gravados", {"coletar", "loja", "plantar"} <= set(pg.arv_s.get_children()), str(pg.arv_s.get_children()))
check("mostra duração com a espera final", "0:07" in pg.arv_s.item("coletar", "values")[1], str(pg.arv_s.item("coletar", "values")))
check("caminho da rotina (geral)", pg.caminho() == "rotina.json")

print("2) Sequência")
resp["item"] = ["plantar"]; resp["texto"] = ["1"]; resp["sim"] = [False]; pg.add_script()
resp["item"] = ["coletar"]; resp["texto"] = ["3"]; resp["sim"] = [False]; pg.add_script()
resp["texto"] = ["20"]; pg.add_espera()
resp["item"] = ["npc_loja"]; resp["texto"] = ["45"]; resp["sim"] = [False]; pg.add_botao()
resp["item"] = ["loja"]; resp["texto"] = ["1"]; resp["sim"] = [True]; resp["item"].append("npc_loja"); resp["texto"].append("30"); pg.add_script()
it = R.ler("rotina.json")["itens"]
check("itens na ordem e salvos", [i["tipo"] for i in it] == ["script", "script", "esperar", "esperar_botao", "script"], str(it))
check("coletar ×3", it[1]["vezes"] == 3 and it[2]["segundos"] == 20)
check("esperar botão: para se não vier", it[3] == {"tipo": "esperar_botao", "botao": "npc_loja", "timeout": 45.0, "ate": "aparecer", "ao_estourar": "parar"}, str(it[3]))
check("script que espera botão antes", it[4]["antes_botao"] == "npc_loja" and it[4]["antes_timeout"] == 30.0, str(it[4]))
pg.arv.selection_set("i4"); pg.mover(-1)
check("mover para cima", [i["tipo"] for i in R.ler("rotina.json")["itens"]][3:] == ["script", "esperar_botao"])
pg.arv.selection_set("i2"); resp["texto"] = ["45"]; pg.editar_item()
check("editar tempo de espera", R.ler("rotina.json")["itens"][2]["segundos"] == 45.0)
pg.arv.selection_set("i3"); pg.remover_item(); pg.arv.selection_set("i3"); pg.remover_item()
check("remover itens", len(R.ler("rotina.json")["itens"]) == 3)
check("tabela mostra a descrição", "plantar" in pg.arv.item("i0", "values")[1])

print("3) Opções e intervalos")
pg.v_pausa_s.set("4"); pg.v_voltas.set("2"); pg.v_pausa_v.set("9")
d = R.ler("rotina.json")
check("tempo entre scripts customizável (salvo)", d["pausa_entre_scripts"] == 4.0 and d["voltas"] == 2 and d["pausa_volta"] == 9.0)
resp["item"] = ["loja"]; resp["texto"] = ["300"]; resp["sim"] = [False]; pg.add_intervalo()
check("intervalo criado", R.ler("rotina.json")["intervalos"] == [{"script": "loja", "a_cada": 300.0, "ativo": True}])
pg.arv.selection_set("v0"); pg.alternar_intervalo()
check("liga/desliga intervalo", R.ler("rotina.json")["intervalos"][0]["ativo"] is False)
pg.alternar_intervalo(); pg.arv.selection_set("v0"); resp["texto"] = ["120"]; pg.editar_intervalo()
check("editar intervalo", R.ler("rotina.json")["intervalos"][0]["a_cada"] == 120.0 and "a cada 120" in pg.arv.item("v0", "values")[2])

print("4) Validação e execução")
check("sem problemas: nenhum aviso", pg.lbl_prob.cget("text") == "")
os.remove("gravacoes/plantar.json"); pg.recarregar()
check("script apagado: aviso na tela", "plantar" in pg.lbl_prob.cget("text"))
chamadas = []; app.rodar = lambda nome, argv, **k: chamadas.append((nome, argv)) or True
pg.iniciar()
check("com problema: não inicia", chamadas == [])
json.dump({"eventos": []}, open("gravacoes/plantar.json", "w")); pg.recarregar(); app.g.janela = "Roblox"
pg.iniciar()
nome, argv = chamadas[-1]
check("inicia pelo modo rotina com o arquivo da rotina", argv[0] == "rotina" and argv[argv.index("--arquivo") + 1] == "rotina.json" and "--loop" not in argv, str(argv))
check("passa opções comuns (janela, velocidade)", "--velocidade" in argv and "--janela" in argv, str(argv))

print("5) Por jogo")
j = J.criar("Caramel"); app.jogos.escolher("caramel"); bombear(0.2); app.ir("rotinas"); bombear(); pg = app.paginas["rotinas"]
check("rotina própria do jogo (vazia)", pg.caminho().replace("\\", "/") == "jogos/caramel/rotina.json" and pg.rot["itens"] == [] and not pg.arv_s.get_children())
resp["texto"] = ["Coleta Rápida!"]; pg.novo_script(); bombear(0.2)
check("novo script: aponta a gravação para o arquivo certo", app.g.gravacao.replace("\\", "/") == "jogos/caramel/gravacoes/Coleta_Rápida.json", app.g.gravacao)
check("e vai para a página Gravar", app.g.pagina == "gravar")
app.jogos.escolher("geral"); app.ir("rotinas"); bombear()
check("o geral continua com a rotina dele", len(app.paginas["rotinas"].rot["itens"]) == 3)

print("6) F11 e bandeja")
app.paginas["rotinas"].iniciar = lambda: chamadas.append(("F11-rotina", None))
app.g.f11_rotina = True; chamadas.clear()
app._tecla_antes_r = False
import autoclick.interface.app as AP
AP.tecla_global_pressionada = lambda t: True
app._tecla_t_r = 0; app._tick_tecla_reproduzir()
check("F11 inicia a rotina quando a opção está ligada", chamadas == [("F11-rotina", None)], str(chamadas))
chamadas.clear(); app.bandeja.eventos.put("reproduzir"); app._tick_bandeja()
check("bandeja também inicia a rotina", chamadas == [("F11-rotina", None)], str(chamadas))

print("7) Editor: espera final")
from autoclick.interface import editor_gravacao as EG
json.dump({"janela": {}, "eventos": [{"t": 0, "tipo": "clique", "x": 1, "y": 1, "x2": 1, "y2": 1, "mouse": "esquerdo", "duracao": 0.05}]}, open("antiga.json", "w"))
ed = EG.EditorGravacao(app, "antiga.json"); bombear(0.1)
check("gravação antiga: sem espera final", "sem espera final" in ed.lbl.cget("text"))
ed._numero = lambda *a, **k: 180.0
ed.espera_final()
check("definir espera final marca como alterado", "alterações não salvas" in ed.lbl.cget("text") and "180" in ed.lbl.cget("text"))
check("salva a espera final no arquivo", ed.salvar() and json.load(open("antiga.json"))["cauda"] == 180.0)
check("após salvar não fica sujo", "não salvas" not in ed.lbl.cget("text"))
from autoclick.interface.dados import resumo_gravacao
check("resumo soma a espera final", "3:00" in resumo_gravacao("antiga.json"), resumo_gravacao("antiga.json"))
ed.j.destroy()

print("10) Importar gravação e layout")
app.ir("rotinas"); bombear(); pg = app.paginas["rotinas"]
import tkinter.filedialog as _FD
os.makedirs("fora", exist_ok=True)
json.dump({"janela": {"titulo": "Jogo X"}, "eventos": [{"t": 0, "tipo": "clique", "x": 5, "y": 5}]}, open("fora/minha gravação.json", "w"))
json.dump({"nada": 1}, open("fora/lixo.json", "w"))
_FD.askopenfilenames = lambda *a, **k: ("fora/minha gravação.json", "fora/lixo.json")
PR.filedialog = _FD
pg.importar_script(); bombear()
check("importou a gravação válida como script", any(n.startswith("minha_grava") for n in pg.scripts()), str(list(pg.scripts())))
check("ignorou o .json que não é gravação", not any("lixo" in n for n in pg.scripts()))
pg.importar_script(); bombear()
check("importar de novo não sobrescreve (nome novo)", sum(n.startswith("minha_grava") for n in pg.scripts()) == 2)
def _sobrepostos(w):
    vistos, ruins = {}, []
    for f in w.winfo_children():
        for c in f.winfo_children() if isinstance(f, tk.Frame) else []:
            pass
    return ruins
import tkinter as tk
def _celulas(corpo):
    seen = {}
    for w in corpo.grid_slaves():
        i = w.grid_info(); seen.setdefault((int(i["row"]), int(i["column"])), []).append(w)
    return [k for k, v in seen.items() if len(v) > 1]
def _corpos(w):
    for f in w.winfo_children():
        if f.__class__.__name__ == "Cartao": yield f.corpo
        else: yield from _corpos(f)
corpos = list(_corpos(pg.frame))
check("os cartões da página foram achados", len(corpos) >= 3, str(len(corpos)))
check("nenhum widget em cima de outro dentro dos cartões", all(not _celulas(c) for c in corpos), str([_celulas(c) for c in corpos]))

print("11) Lista única (sequência + intervalos)")
app.ir("rotinas"); bombear(); pg = app.paginas["rotinas"]
ant_i = len(pg.rot["itens"]); ant_v = len(pg.rot["intervalos"])
resp["item"] = ["Na sequência (repete a cada volta)", "coletar"]; resp["texto"] = ["2"]; resp["sim"] = [False]; pg.mais_script()
check("+ Script 'na sequência' vai para a sequência", len(pg.rot["itens"]) == ant_i + 1 and len(pg.rot["intervalos"]) == ant_v)
resp["item"] = ["A cada X segundos (entra sozinho)", "loja"]; resp["texto"] = ["900"]; resp["sim"] = [False]; pg.mais_script()
check("+ Script 'a cada X s' vira intervalo", len(pg.rot["intervalos"]) == ant_v + 1 and pg.rot["intervalos"][-1]["a_cada"] == 900.0)
vals = pg.arv.item(f"v{len(pg.rot['intervalos']) - 1}", "values")
check("intervalo aparece na lista única com 'a cada 900 s (15 min)'", "900" in vals[2] and "15 min" in vals[2], str(vals))
ids = pg.arv.get_children()
check("grupos: sequência antes dos intervalos", ids.index("gi") < ids.index("i0") < ids.index("gv") < ids.index("v0"), str(ids))
pg.arv.selection_set("gv"); bombear(0.05)
check("título de grupo não fica selecionado", "gv" not in pg.arv.selection())
n_iv = len(pg.rot["intervalos"]); pg.arv.selection_set(f"v{n_iv - 1}"); pg.remover()
check("Remover age no intervalo selecionado", len(pg.rot["intervalos"]) == n_iv - 1)
n_it = len(pg.rot["itens"]); pg.arv.selection_set(f"i{n_it - 1}"); pg.remover()
check("Remover age no item da sequência", len(pg.rot["itens"]) == n_it - 1)
pg.arv.selection_set("v0"); atv = pg.rot["intervalos"][0].get("ativo", True); pg.duplo_clique()
check("duplo clique no intervalo liga/desliga", pg.rot["intervalos"][0].get("ativo", True) != atv)
pg.alternar_intervalo()
chamadas.clear(); testados = []
pg.testar_script = lambda: testados.append(pg._sel_script())
pg.arv.selection_set("i0"); pg.testar_da_lista()
check("Testar script da lista usa o script da linha", testados == [pg.rot["itens"][0]["script"]], str(testados))
n_b = len(pg.scripts()); pg._alternar_biblioteca(); bombear(0.05)
check("biblioteca recolhe", not pg.cartao_lib.winfo_ismapped() and "▸" in pg.btn_lib.cget("text") and f"({n_b})" in pg.btn_lib.cget("text"))
pg._alternar_biblioteca(); bombear(0.05)
check("e abre de novo", pg.cartao_lib.winfo_ismapped())

print("12) Prévia e barra fixa")
app.ir("rotinas"); bombear(); pg = app.paginas["rotinas"]
prev = pg.txt_previa.get("1.0", "end")
check("a prévia mostra o que a rotina fará", "volta 1" in prev and "▶" in prev, prev[:200])
check("a barra de execução não está dentro da área rolável", str(pg.btn_ini.winfo_toplevel()) and pg.rol.corpo not in pg.btn_ini.winfo_toplevel().winfo_children() and not str(pg.btn_ini).startswith(str(pg.rol.corpo)))
pg.ao_status({"progresso": {"volta": 1, "voltas": 2, "total": 10.0, "decorrido": 3.0}}); bombear(0.05)
check("a barra de progresso aparece só com progresso", pg.barra.winfo_manager() == "pack")
pg.ao_status({}); bombear(0.05)
check("e some quando termina", pg.barra.winfo_manager() == "")

print("13) Esperar com script durante a espera e Duplicar")
app.ir("rotinas"); bombear(); pg = app.paginas["rotinas"]
n0 = len(pg.rot["itens"])
resp["texto"] = ["300"]; resp["sim"] = [True, False]; resp["item"] = ["loja"]; pg.add_espera()
novo = pg.rot["itens"][-1] if pg.rot["itens"][-1].get("tipo") == "esperar" else [x for x in pg.rot["itens"] if x.get("tipo") == "esperar"][-1]
check("esperar guarda o script que roda durante a espera", novo.get("durante") == ["loja"] and novo["segundos"] == 300.0, str(novo))
idx = pg.rot["itens"].index(novo)
check("a lista mostra 'enquanto espera: loja'", "enquanto espera: loja" in pg.arv.item(f"i{idx}", "values")[3], str(pg.arv.item(f"i{idx}", "values")))
resp["texto"] = ["300"]; resp["sim"] = [False]; pg.arv.selection_set(f"i{idx}"); pg.editar_item()
check("editar e responder 'nenhum' limpa o que roda durante a espera", pg.rot["itens"][idx].get("durante") == [])
pg.arv.selection_set(f"i{idx}"); n1 = len(pg.rot["itens"]); pg.duplicar()
check("Duplicar cria uma cópia logo abaixo", len(pg.rot["itens"]) == n1 + 1 and pg.rot["itens"][idx + 1] == pg.rot["itens"][idx] and pg.rot["itens"][idx + 1] is not pg.rot["itens"][idx])

print(f"\n{ok} verificações passaram (GUI rotinas).")
app.raiz.destroy()
