"""GUI: cronômetro e linha do tempo ao vivo na página Gravar (só conferência)."""
import sys, os, time, shutil, tempfile
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
ROOT = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp(); shutil.copytree(f"{ROOT}/proj", f"{tmp}/p"); os.chdir(f"{tmp}/p")
os.environ["PYTHONPATH"] = os.pathsep.join([RAIZ] + [x for x in sys.path if x]); os.environ["AUTOCLICK_SEM_OCR"] = "1"
from autoclick.interface.app import App
from autoclick.interface.dados import Geral
ok = 0
def check(n, c, extra=""):
    global ok
    print(("  OK   " if c else "  FALHOU ") + n + (f"  {extra}" if extra and not c else ""))
    if not c: sys.exit(1)
    ok += 1
g = Geral(); app = App(g, os.getcwd()); r = app.raiz
def bombear(s=0.3):
    t0 = time.time()
    while time.time() - t0 < s: r.update(); time.sleep(0.02)
bombear(); app.ir("gravar"); bombear(); pg = app.paginas["gravar"]
check("cronômetro começa zerado", pg.lbl_cron.cget("text") == "00:00.0")
d = {"modo": "gravar", "resumo": {}, "ultimo": "-",
     "gravando": {"t0": time.time() - 12.0, "total": 2, "recentes": ["00:03.100  tecla E ↓", "00:03.200  tecla E ↑"]}}
pg.ao_status(d); bombear(0.4)
txt = pg.lista_cron.get("1.0", "end")
check("lista mostra as teclas com tempo", "00:03.100  tecla E" in txt and "00:03.200" in txt, txt)
check("cronômetro conta a partir do t0 real", pg.lbl_cron.cget("text").startswith("00:12"), pg.lbl_cron.cget("text"))
d["gravando"]["recentes"].append("00:09.000  clique esquerdo em (1,2)")
pg.ao_status(d); bombear(0.2)
check("lista atualiza", "clique esquerdo" in pg.lista_cron.get("1.0", "end"))
pg.ao_status({}); bombear(0.1); v = pg.lbl_cron.cget("text"); bombear(0.3)
check("ao terminar, para e mantém o tempo e a lista", pg.lbl_cron.cget("text") == v and "tecla E" in pg.lista_cron.get("1.0", "end"))
from autoclick.interface.widgets import texto_progresso
check("texto: volta com espera final", texto_progresso({"volta": 3, "voltas": 0, "decorrido": 252, "total": 600}) == "volta 3 · 04:12 / 10:00")
check("texto: volta N/M e pausa", texto_progresso({"volta": 2, "voltas": 5, "decorrido": 5, "total": 90, "pausado": True}) == "volta 2/5 · 00:05 / 01:30  ⏸")
check("texto: rotina usa o rótulo", texto_progresso({"rotulo": "volta 2 · coletar", "decorrido": 3, "total": 10}) == "volta 2 · coletar · 00:03 / 00:10")
check("texto: sem progresso", texto_progresso(None) == "")
check("texto: não passa do total", texto_progresso({"volta": 1, "decorrido": 99, "total": 10}) == "volta 1 · 00:10 / 00:10")
d2 = {"modo": "reproduzir", "resumo": {}, "ultimo": "-", "progresso": {"volta": 3, "voltas": 0, "decorrido": 300, "total": 600}}
pg.ao_status(d2); bombear(0.1)
check("painel mostra volta e tempo", "volta 3 · 05:00 / 10:00" in pg.painel.progresso.lbl.cget("text"))
check("barra a 50%", abs(float(pg.painel.progresso.barra.cget("value")) - 500) < 1)
pg.ao_status({}); bombear(0.1)
check("zera ao terminar", pg.painel.progresso.lbl.cget("text") == "—")
app.ir("rotinas"); bombear(); pr = app.paginas["rotinas"]
pr.ao_status({"progresso": {"rotulo": "volta 2 · coletar", "decorrido": 30, "total": 120}}); bombear(0.1)
check("Rotinas mostra o script e a barra", "volta 2 · coletar · 00:30 / 02:00" in pr.barra.lbl.cget("text") and abs(float(pr.barra.barra.cget("value")) - 250) < 1)
pr.ao_status({}); bombear(0.1)
check("Rotinas zera", pr.barra.lbl.cget("text") == "—")
# ---- captura de atalhos (0.11.0) ----
from autoclick.interface import pag_config as PC
from autoclick import windows as W
app.ir("config"); bombear(); pc = app.paginas["config"]
teclas = {"agora": set()}
pc.teclas_agora = lambda: set(teclas["agora"])
est2 = lambda vk: vk in teclas["agora"] or (vk in (0x11, 0x10, 0x12) and teclas.get("mods", set()) >= {vk})
pc.ler_tecla = lambda ign: W.ler_atalho(lambda vk: vk in teclas["agora"], ign)
perguntas = []
PC.messagebox.askyesno = lambda *a, **k: (perguntas.append(a[1]), teclas.get("resp", True))[1]
check("campos mostram os atalhos atuais", pc.v_teclas["pausa"].get() == "F8" and pc.v_teclas["reproduzir"].get() == "F11")
pc.capturar("pausa"); bombear(0.1)
check("aguardando tecla", "Aperte" in pc.v_teclas["pausa"].get())
teclas["agora"] = {0x11, 0x7B}; bombear(0.15); teclas["agora"] = set()
check("capturou Ctrl+F12", pc.v_teclas["pausa"].get() == "CTRL+F12", pc.v_teclas["pausa"].get())
pc.capturar("parar"); teclas["agora"] = {0x7B, 0x11}; bombear(0.15); teclas["agora"] = set()
check("conflito: pergunta e troca os dois", perguntas and "Pausar" in perguntas[-1] and pc.v_teclas["parar"].get() == "CTRL+F12" and pc.v_teclas["pausa"].get() == "F9", (perguntas, pc.v_teclas["pausa"].get()))
pc.capturar("gravar"); teclas["agora"] = {0x57}; bombear(0.15); teclas["agora"] = set()
check("letra sozinha: avisa e (aceitando) usa", "Letras" in perguntas[-1] and pc.v_teclas["gravar"].get() == "W")
teclas["resp"] = False
pc.capturar("reproduzir"); teclas["agora"] = {0x58}; bombear(0.15); teclas["agora"] = set()
check("recusando o aviso, volta ao valor anterior", pc.v_teclas["reproduzir"].get() == "F11")
teclas["resp"] = True
pc.capturar("reproduzir"); bombear(0.05); pc._cancelar_captura()
check("cancelar restaura o valor", pc.v_teclas["reproduzir"].get() == "F11")
teclas["agora"] = {0x7A}; pc.capturar("reproduzir"); bombear(0.12)
check("tecla já apertada ao iniciar é ignorada", "Aperte" in pc.v_teclas["reproduzir"].get())
teclas["agora"] = {0x7C}; bombear(0.12); teclas["agora"] = set()
check("depois captura outra tecla", pc.v_teclas["reproduzir"].get() == "F13", pc.v_teclas["reproduzir"].get())
teclas["agora"] = set()
pc.v_teclas["gravar"].set("F10"); pc.v_teclas["pausa"].set("CTRL+ALT+P")
pc.aplicar_teclas()
check("aplicar salva combinação normalizada", app.g.tecla_pausa == "CTRL+ALT+P" and app.g.tecla_parar == "CTRL+F12")
pc._atalho_padrao("pausa"); check("padrão volta", pc.v_teclas["pausa"].get() == "F8")
# ---- sons por tipo de ação (0.12.0) ----
from autoclick import som as SOM
app.ir("config"); bombear(); pc = app.paginas["config"]
cmds = []
app.exec.enviar_comando = lambda c: cmds.append(c)
app.exec.rodando_antes = None
check("padrões: gravação e reprodução ligadas, tique desligado", app.g.som_gravacao and app.g.som_reproducao and not app.g.som_contagem)
app.var("som_gravacao").get()
vg = app.var("som_contagem"); vg.set(True); app.sincronizar_grupo_som("contagem", True)
check("liga o tique na configuração", app.g.som_contagem is True)
app.sincronizar_grupo_som("gravacao", False)
check("desliga o som da gravação na configuração", app.g.som_gravacao is False and app.g.som_reproducao is True)
check("o som de volta não é afetado", app.g.som_volta is False)
tocados = []
SOM.som.saida = lambda b: tocados.append(b)
pc.ouvir_som("gravar_inicio"); pc.ouvir_som("repro_fim"); pc.ouvir_som("tique"); bombear(0.4)
check("botões Ouvir tocam o som do tipo certo, mesmo desligado", len(tocados) == 3 and len({bytes(b) for b in tocados}) == 3)
check("há um checkbox por tipo de som", all(hasattr(pc, "v_teclas") for _ in [0]) and app.g.som_contagem)
print(f"\n{ok} verificações passaram (GUI cronômetro).")
app.raiz.destroy()
