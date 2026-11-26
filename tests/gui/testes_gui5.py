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
pg.arv_i.selection_set("4"); pg.mover(-1)
check("mover para cima", [i["tipo"] for i in R.ler("rotina.json")["itens"]][3:] == ["script", "esperar_botao"])
pg.arv_i.selection_set("2"); resp["texto"] = ["45"]; pg.editar_item()
check("editar tempo de espera", R.ler("rotina.json")["itens"][2]["segundos"] == 45.0)
pg.arv_i.selection_set("3"); pg.remover_item(); pg.arv_i.selection_set("3"); pg.remover_item()
check("remover itens", len(R.ler("rotina.json")["itens"]) == 3)
check("tabela mostra a descrição", "script plantar" in pg.arv_i.item("0", "values")[1])

print("3) Opções e intervalos")
pg.v_pausa_s.set("4"); pg.v_voltas.set("2"); pg.v_pausa_v.set("9")
d = R.ler("rotina.json")
check("tempo entre scripts customizável (salvo)", d["pausa_entre_scripts"] == 4.0 and d["voltas"] == 2 and d["pausa_volta"] == 9.0)
resp["item"] = ["loja"]; resp["texto"] = ["300"]; resp["sim"] = [False]; pg.add_intervalo()
check("intervalo criado", R.ler("rotina.json")["intervalos"] == [{"script": "loja", "a_cada": 300.0, "ativo": True}])
pg.arv_v.selection_set("0"); pg.alternar_intervalo()
check("liga/desliga intervalo", R.ler("rotina.json")["intervalos"][0]["ativo"] is False)
pg.alternar_intervalo(); pg.arv_v.selection_set("0"); resp["texto"] = ["120"]; pg.editar_intervalo()
check("editar intervalo", R.ler("rotina.json")["intervalos"][0]["a_cada"] == 120.0 and "loja a cada 120" in pg.arv_v.item("0", "values")[1])

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

print(f"\n{ok} verificações passaram (GUI rotinas).")
app.raiz.destroy()
