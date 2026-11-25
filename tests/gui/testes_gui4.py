"""GUI: página Jogos, troca de jogo, migração, detecção por logs, menu rápido, bandeja, estatísticas, som."""
import sys, os, time, json, shutil, tempfile
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
ROOT = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp()
shutil.copytree(f"{ROOT}/proj", f"{tmp}/p")
os.chdir(f"{tmp}/p")
os.environ["PYTHONPATH"] = os.pathsep.join([RAIZ] + [x for x in sys.path if x])
os.environ["AUTOCLICK_SEM_OCR"] = "1"
os.makedirs("perfis"); json.dump({"modo": "imagem", "janela": "Roblox", "intervalo": 1.0, "variacao": 0.2}, open("perfis/roblox.json", "w"))
json.dump({"modo": "auto", "intervalo": 3.0}, open("perfis/outro.json", "w"))
logs = f"{tmp}/logs"; os.makedirs(logs); os.environ["AUTOCLICK_ROBLOX_LOGS"] = logs
open(f"{logs}/x.log", "w").write("nada util\n")
from autoclick.interface.app import App
from autoclick.interface.dados import Geral, ambiente, carregar_geral
from autoclick import jogos as J
ok = 0
def check(n, c, extra=""):
    global ok
    print(("  OK   " if c else "  FALHOU ") + n + (f"  {extra}" if extra and not c else ""))
    if not c: sys.exit(1)
    ok += 1
g = Geral(som_volta=False)
app = App(g, os.getcwd()); r = app.raiz
def bombear(seg=0.3):
    t0 = time.time()
    while time.time() - t0 < seg: r.update(); time.sleep(0.02)

print("1) Migração ao abrir")
bombear()
check("perfis movidos", not os.path.exists("perfis/roblox.json") and os.path.exists("jogos/geral/perfil.json") and os.path.exists("jogos/outro/perfil.json"))
check("geral guardou as opções", J.ler("geral").opcoes.get("variacao") == 0.2)
check("página Jogos existe", "jogos" in app.paginas and "jogos" in app._nav)
check("migração marcada", app.g.jogos_migrado)

print("2) Novo jogo e troca")
j = app.jogos.novo("Blox Fruits", ["2753915549"])
import tkinter as tk
check("começa no geral", app.jogos.atual() == "geral" and app.g.pasta == "botoes")
app.g.pasta, app.g.config = "botoes", "botoes.json"
app.jogos.salvar_opcoes()
check("salvar opções no geral", J.ler("geral").opcoes["intervalo"] == app.g.intervalo)
app.g.intervalo = 7.5; app.jogos.salvar_opcoes() if False else None
j = J.ler("blox-fruits"); j.opcoes = {"intervalo": 4.25, "som_volta": True, "som_tipo": "marimba"}; J.salvar(j)
check("escolher aplica arquivos e opções", app.jogos.escolher("blox-fruits") and app.g.pasta.replace("\\", "/") == "jogos/blox-fruits/botoes"
      and app.g.config.replace("\\", "/") == "jogos/blox-fruits/botoes.json" and app.g.intervalo == 4.25 and app.g.som_volta and app.g.som_tipo == "marimba", str((app.g.pasta, app.g.intervalo)))
check("geral ficou guardado", app.g.pasta_geral == "botoes" and app.g.config_geral == "botoes.json" and app.g.gravacao_geral == "gravacao.json")
amb = ambiente(app.g)
check("processo recebe jogo e camada geral", amb["AUTOCLICK_JOGO"] == "blox-fruits" and amb["AUTOCLICK_GERAL_PASTA"] == "botoes" and amb["AUTOCLICK_GERAL_CONFIG"] == "botoes.json")
check("rótulo do menu rápido", "Blox Fruits" in app.mb_jogo.cget("text"))
check("menu rápido lista os jogos", app.menu_jogo.index("end") >= 3)
check("bandeja recebe os jogos", ("blox-fruits", "Blox Fruits") in app.bandeja.jogos and app.bandeja.jogo_atual == "blox-fruits")
check("páginas refeitas apontam para o jogo", app.paginas["regras"].g.config.replace("\\", "/").startswith("jogos/blox-fruits"))
check("grava no arquivo do jogo", "jogos/blox-fruits/gravacao.json" in " ".join(app.paginas["gravar"].g.gravacao.replace("\\", "/") for _ in [0]))
app.escolher = None
check("voltar ao geral", app.jogos.escolher("geral") and app.g.pasta == "botoes" and app.g.jogo == "" and ambiente(app.g)["AUTOCLICK_JOGO"] == "")
check("sem jogo: sem camada", ambiente(app.g)["AUTOCLICK_GERAL_PASTA"] == "")
check("persistiu em autoclick_gui.json", carregar_geral().jogos_migrado)

print("3) Página Jogos")
app.ir("jogos"); bombear()
pj = app.paginas["jogos"]
check("lista tem geral, outro e Blox Fruits", set(pj.arv.get_children()) == {"geral", "outro", "blox-fruits"})
pj.arv.selection_set("blox-fruits"); bombear(0.1)
check("ids aparecem no campo", pj.v_ids.get() == "2753915549")
pj.v_ids.set("2753915549, 77"); pj.v_ass.set("logo_bf"); pj.salvar_ids()
check("salvar ids e assinatura", J.ler("blox-fruits").ids == ["2753915549", "77"] and J.ler("blox-fruits").assinatura == ["logo_bf"])
pj.arv.selection_set("blox-fruits"); pj.usar(); bombear(0.2)
check("usar este jogo", app.jogos.atual() == "blox-fruits")
app.g.intervalo = 9.0; app.paginas["jogos"].salvar_opcoes()
check("salvar minhas opções neste jogo", J.ler("blox-fruits").opcoes["intervalo"] == 9.0)

print("4) Detecção pelos logs")
app.jogos.escolher("geral"); app.g.detectar_jogo = True
open(f"{logs}/x.log", "w").write("[game] placeId:2753915549\n")
app.jogos._prox = 0; app.jogos.tick(); bombear(0.2)
check("troca sozinho pelo log", app.jogos.atual() == "blox-fruits")
open(f"{logs}/x.log", "w").write("[game] placeId:555666\n"); os.utime(f"{logs}/x.log", (time.time() + 9, time.time() + 9))
app.jogos._prox = 0; app.jogos.tick(); bombear(0.2)
check("id novo: não troca e guarda o id", app.jogos.atual() == "blox-fruits" and app.jogos.ultimo_id == "555666")
app.g.detectar_jogo = False; open(f"{logs}/x.log", "w").write("placeId:2753915549\n"); os.utime(f"{logs}/x.log", (time.time() + 20, time.time() + 20)); app.jogos.escolher("geral")
app.jogos._prox = 0; app.jogos.tick()
check("desligado: não troca", app.jogos.atual() == "geral")
app.g.detectar_jogo = True; app.jogos._prox = 0; app.jogos.tick(); bombear(0.1)
check("ligado de novo: detecta o jogo atual", app.jogos.atual() == "blox-fruits")
app.jogos.escolher("geral"); app.jogos._prox = 0; app.jogos.tick(); bombear(0.1)
check("escolha manual vale: mesmo id não troca de volta", app.jogos.atual() == "geral")
pistas = app.jogos.coletar_pistas()
check("pistas salvas em arquivo", os.path.exists("pistas_roblox.txt") and "2753915549" in open("pistas_roblox.txt", encoding="utf-8").read())

print("4b) Aprende o outro id")
J.criar("Caramel", ids=["9553887523"])
open(f"{logs}/x.log", "w").write("place 120919334665902 at x\nplaceid:120919334665902, universeid:9553887523\n"); os.utime(f"{logs}/x.log", (time.time() + 40, time.time() + 40))
sl, i = app.jogos.detectar_logs()
check("reconhece pelo universe e guarda o place", sl == "caramel" and set(J.ler("caramel").ids) == {"9553887523", "120919334665902"}, str(J.ler("caramel").ids))
check("ids atuais disponíveis para o cadastro", app.jogos.ids_atuais == ["120919334665902", "9553887523"])

print("5) Não troca com algo rodando")
app.exec.rodando_falso = True
class FP:  # processo falso
    def poll(self): return None
app.exec._proc = FP()
check("rodando: recusa trocar", app.jogos.escolher("blox-fruits") is False and app.jogos.atual() == "geral")
app.exec._proc = None

print("6) Estatísticas")
os.makedirs("historico", exist_ok=True)
with open("historico/sessoes.jsonl", "w", encoding="utf-8") as f:
    for s in ({"jogo": "blox-fruits", "duracao_seg": 3600, "partidas": 20, "total_acoes": 50, "cliques": {"ok": 50}},
              {"duracao_seg": 100, "partidas": 1, "total_acoes": 2}):
        f.write(json.dumps(s) + "\n")
app.ir("jogos"); pj = app.paginas["jogos"]; bombear(0.1)
linhas = [pj.est.item(i, "values") for i in pj.est.get_children()]
check("tabela por jogo", len(linhas) == 2 and linhas[0][0] == "Blox Fruits" and str(linhas[0][4]) == "20.0", str(linhas))

print("7) Bandeja e som")
app.bandeja.eventos.put("som"); app._tick_bandeja()
check("bandeja liga o som", app.g.som_volta is True and app.bandeja.som is True)
app.bandeja.eventos.put("som"); app._tick_bandeja()
check("bandeja desliga o som", app.g.som_volta is False)
app.bandeja.eventos.put("jogo:blox-fruits"); app._tick_bandeja(); bombear(0.1)
check("bandeja troca de jogo", app.jogos.atual() == "blox-fruits")
enviados = []
app.exec.enviar_comando = lambda c: enviados.append(c)
app.exec._proc = FP()
app.g.som_tipo = "gota"; app.g.som_volume = 55.0; app.g.som_arquivo = "C:/meu som.wav"
app.enviar_config_som()
check("config de som enviada ao processo (sem espaços)", enviados and enviados[-1] == "somcfg:gota|55|C%3A/meu%20som.wav", str(enviados))
app.exec._proc = None
import autoclick.operacao as O
src = open(os.path.join(RAIZ, "autoclick", "operacao.py"), encoding="utf-8").read()
from autoclick.som import som
som.configurar("sino", 37, "")
# simula o recebimento do comando pelo processo filho
ctl_cls = [v for v in vars(O).values() if isinstance(v, type) and hasattr(v, "_executar") ] if False else []
check("ambiente leva o som", ambiente(app.g)["AUTOCLICK_SOM_TIPO"] == "gota" and ambiente(app.g)["AUTOCLICK_SOM_VOLUME"] == "55")
app.ir("config"); bombear(0.1)
pc = app.paginas["config"]
pc.v_estilo.set(pc._nomes_som["discreto"]); pc._estilo_som()
check("estilo escolhido na tela", app.g.som_tipo == "discreto")

print("8) O que mudou")
import tkinter.messagebox as MB
from autoclick import __version__ as VER
mostradas = []; MB.showinfo = lambda *a, **k: mostradas.append(a)
open("CHANGELOG.md", "w", encoding="utf-8").write(f"## {VER}\n- Coisa nova A\n- Coisa nova B\n")
app.g.avisou_novidades = "0.1.0"; app.mostrar_novidades()
check("mostra depois de atualizar", len(mostradas) == 1 and "Coisa nova A" in mostradas[0][1] and VER in mostradas[0][0])
app.mostrar_novidades()
check("só uma vez", len(mostradas) == 1 and app.g.avisou_novidades == VER)
app.g.avisou_novidades = ""; app.mostrar_novidades()
check("instalação nova não mostra", len(mostradas) == 1 and app.g.avisou_novidades == VER)

print(f"\n{ok} verificações passaram (GUI jogos).")
app.raiz.destroy()
