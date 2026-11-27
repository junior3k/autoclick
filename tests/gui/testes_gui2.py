import sys as _s0
for _f in (_s0.stdout, _s0.stderr):
    try: _f.reconfigure(encoding="utf-8", errors="replace")  # Windows (cp1252) não imprime setas
    except Exception: pass
import sys, os, time, json, shutil, tempfile, zipfile, struct, zlib, threading, http.server, queue
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
ROOT = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp()
shutil.copytree(f"{ROOT}/proj", f"{tmp}/p")
os.chdir(f"{tmp}/p")
os.environ["PYTHONPATH"] = os.pathsep.join([os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))] + [x for x in sys.path if x])
os.environ["AUTOCLICK_SEM_OCR"] = "1"
import tkinter.messagebox as MB, tkinter.filedialog as FD
from autoclick.interface.app import App
from autoclick.interface.dados import Geral
import autoclick.interface.dados as DA, autoclick.interface.comandos as CM, autoclick.interface.edicao as ED
import autoclick.interface.app as APPMOD
assert "numpy" not in sys.modules and "cv2" not in sys.modules, "a janela não pode importar numpy/cv2"
ok = 0
def check(nome, cond, extra=""):
    global ok
    print(("  OK   " if cond else "  FALHOU ") + nome + (f"  {extra}" if extra and not cond else ""))
    if not cond: sys.exit(1)
    ok += 1

print("1) Funções puras novas")
ref = {"tela": {"largura": 1920, "altura": 1080}, "janela": {"rect": [0, 0, 1280, 720]}}
check("ambiente igual: sem aviso", DA.comparar_ambiente(ref, "Roblox", (1920, 1080), (1280, 720)) == [])
check("ambiente diferente: avisa tela e janela", len(DA.comparar_ambiente(ref, "Roblox", (1366, 768), (1000, 600))) == 2)
check("sem janela configurada: ignora a janela", len(DA.comparar_ambiente(ref, "", (1920, 1080), (1, 1))) == 0)
check("sem referência: nada", DA.comparar_ambiente(None, "x") == [])
check("teclas válidas", DA.teclas_validas("F8", "F9", "F10") is None)
check("tecla inválida", "pausa" in (DA.teclas_validas("lixo", "F9", "F10") or ""))
check("teclas repetidas", "diferentes" in (DA.teclas_validas("F8", "F8", "F10") or ""))
g0 = Geral(); env = DA.ambiente(g0)
check("env: teclas/captura/prévia", env["AUTOCLICK_TECLAS"] == "pausa=F8;parar=F9;gravar=F10;reproduzir=F11" and env["AUTOCLICK_CAPTURA_ERRO"] == "1" and env["AUTOCLICK_PREVIA"].endswith("previa_viva.png"))
g0.previa_viva = False; check("sem prévia: sem variável", "AUTOCLICK_PREVIA" not in DA.ambiente(g0))
g0.tela_parada = 90; check("argumentos --tela-parada (reproduzir)", "--tela-parada" in CM.reproduzir(g0) and "90" in CM.reproduzir(g0))
check("argumentos --tela-parada (automático)", "--tela-parada" in CM.automatico(g0))
h = DA.agregar_historico([{"fim": "2026-11-22T10:00:00", "total_acoes": 5, "partidas": 2, "duracao_seg": 60, "falhas": {"a": 2}},
                          {"fim": "2026-11-20T10:00:00", "total_acoes": 3, "duracao_seg": 30}], hoje="2026-11-22")
check("histórico agregado", h["acoes"] == 8 and h["partidas"] == 2 and h["falhas"] == 2 and h["por_dia"][-1] == ("11/22", 5) and h["por_dia"][-3] == ("11/20", 3), str(h))
check("duração formatada", DA.formatar_duracao(59) == "59s" and DA.formatar_duracao(125) == "2m05s" and DA.formatar_duracao(3700) == "1h01m")
check("comando pytesseract", DA.comando_instalar_pytesseract()[0] in ("uv", sys.executable) or "python" in DA.comando_instalar_pytesseract()[0])
check("winget só no Windows", DA.comando_instalar_tesseract() is None)

print("2) Janela: páginas, histórico, ajuda")
g = Geral(tema="escuro"); app = App(g, os.getcwd()); r = app.raiz
def bombear(seg=0.0, ate=None, limite=15.0):
    t0 = time.time()
    while True:
        r.update()
        if ate is not None and ate(): return True
        if time.time() - t0 > (limite if ate else seg): return ate is None
        time.sleep(0.02)
class FakeBandeja:
    disponivel = True
    def __init__(self): self.eventos = queue.Queue(); self.estados = []; self.baloes = []
    def definir_estado(self, e, d="", pausado=False): self.estados.append(e)
    def balao(self, t, x, n="aviso"): self.baloes.append((t, x)); return True
    def iniciar(self): return True
    def fechar(self): pass
app.bandeja = FakeBandeja()
check("menu com 7 itens", len(app._nav) == 7)
for k in ("historico", "ajuda", "config", "gravar"):
    app.ir(k); r.update()
check("cabeçalho da Ajuda", True)
ajuda = app.paginas["ajuda"]; ajuda.mostrar(3)
check("ajuda mostra o assunto", "Marcador" in ajuda.texto.get("1.0", "end") or "marcador" in ajuda.texto.get("1.0", "end"))
os.makedirs("historico", exist_ok=True)
open("historico/sessoes.jsonl", "w", encoding="utf-8").write(
    json.dumps({"fim": time.strftime("%Y-%m-%dT%H:%M:%S"), "modo": "reproduzir", "total_acoes": 7, "partidas": 3, "duracao_seg": 100, "motivo": "concluído"}) + "\nlixo\n")
app.ir("historico"); r.update()
hp = app.paginas["historico"]
check("histórico: totais", hp.totais["acoes"].cget("text") == "7" and hp.totais["sessoes"].cget("text") == "1" and hp.totais["tempo"].cget("text") == "1m40s")
check("histórico: lista", len(hp.arv.get_children()) == 1)

print("3) Bandeja e alertas")
app.exec.comando_base = [sys.executable, "-u", f"{ROOT}/fake_proc.py"]
fim = []
app.ir("auto")
assert app.rodar("imagem", [], ao_fim=lambda c: fim.append(c))
bombear(ate=lambda: "rodando" in app.bandeja.estados)
check("bandeja: rodando", "rodando" in app.bandeja.estados)
app.alternar_pausa(); bombear(ate=lambda: "pausado" in app.bandeja.estados)
check("bandeja: pausado", "pausado" in app.bandeja.estados)
app.bandeja.eventos.put("pausa"); bombear(ate=lambda: not app.exec.pausado)
check("menu da bandeja: continuar", not app.exec.pausado)
app.bandeja.eventos.put("parar"); bombear(ate=lambda: bool(fim) and not app.rodando)
check("menu da bandeja: parar", bool(fim) and app.bandeja.estados[-1] == "parado")
app.exec.comando_base = [sys.executable, "-u", "-c", "import os;print('[ALERTA] tela parada: a tela não muda');print('AMB', os.environ.get('AUTOCLICK_TECLAS'), os.environ.get('AUTOCLICK_FILHO'), os.environ.get('AUTOCLICK_WEBHOOK'))"]
app.g.tecla_pausa, app.g.webhook = "F6", "http://x/y"
fim.clear(); assert app.rodar("ferramenta", [], ao_fim=lambda c: fim.append(c)); bombear(ate=lambda: bool(fim))
check("[ALERTA] vira balão do Windows", any("a tela não muda" in b[1] for b in app.bandeja.baloes), str(app.bandeja.baloes))
log = app.log.get("1.0", "end")
check("filho recebe teclas, marca de filho e webhook", "AMB pausa=F6;parar=F9;gravar=F10;reproduzir=F11 1 http://x/y" in log, log[-300:])
app.g.webhook = ""; app.g.tecla_pausa = "F8"
app.g.notificar_windows = False; n = len(app.bandeja.baloes); app.notificar("a", "b")
check("notificação desligável", len(app.bandeja.baloes) == n); app.g.notificar_windows = True

print("4) Atalho global de gravação")
APPMOD.tecla_global_pressionada = lambda nome: True
app.exec.comando_base = [sys.executable, "-u", f"{ROOT}/fake_proc.py"]
app._tecla_antes = False; app._tecla_t = 0.0
app._tick_tecla_gravar()
check("F10 inicia a gravação", app.rodando and app.exec.nome == "gravar")
bombear(0.3)
APPMOD.tecla_global_pressionada = lambda nome: False; app._tick_tecla_gravar(); bombear(0.1)
APPMOD.tecla_global_pressionada = lambda nome: True; app._tecla_t = 0.0
app._tick_tecla_gravar()
check("F10 de novo para a gravação", bombear(ate=lambda: not app.rodando))
APPMOD.tecla_global_pressionada = lambda nome: False

print("4b) Atalho global de reprodução e som por volta")
APPMOD.tecla_global_pressionada = lambda nome: nome == app.g.tecla_reproduzir
app.exec.comando_base = [sys.executable, "-u", f"{ROOT}/fake_proc.py"]
_grav_orig = app.g.gravacao; app.g.gravacao = "nao_existe.json"; app._tecla_antes_r = False; app._tecla_t_r = 0.0
app._tick_tecla_reproduzir()
check("sem gravação: avisa e não inicia", not app.rodando and "não há gravação" in app.log.get("1.0", "end"))
open("gravacao_f11.json", "w").write("[]"); app.g.gravacao = "gravacao_f11.json"
app._tecla_antes_r = False; app._tecla_t_r = 0.0
app._tick_tecla_reproduzir()
check("F11 inicia a reprodução", app.rodando and app.exec.nome == "reproduzir")
bombear(0.3)
APPMOD.tecla_global_pressionada = lambda nome: False; app._tick_tecla_reproduzir(); bombear(0.1)
# o som liga/desliga com a função rodando: o comando chega ao processo
enviados = []; orig_env = app.exec.enviar_comando
app.exec.enviar_comando = lambda c: (enviados.append(c), orig_env(c))
antes = app.g.som_volta
app.alternar_som(); app.alternar_som()
check("alternar_som manda som:1/som:0 ao processo em execução",
      enviados == (["som:1", "som:0"] if not antes else ["som:0", "som:1"]), str(enviados))
check("botão da barra reflete o estado", app.btn_som.cget("text").startswith("🔔") == app.g.som_volta)
app.g.som_volta = True; app.sincronizar_som()
check("Configurações acompanham o botão", all(bool(v.get()) for v in app._vars_som))
APPMOD.tecla_global_pressionada = lambda nome: nome == app.g.tecla_reproduzir; app._tecla_t_r = 0.0
app._tick_tecla_reproduzir()
check("F11 de novo para a reprodução", bombear(ate=lambda: not app.rodando))
APPMOD.tecla_global_pressionada = lambda nome: False
app.g.som_volta = False; app.sincronizar_som(); app.exec.enviar_comando = orig_env
app.g.gravacao = _grav_orig
check("rodapé lista o atalho", "F11" in app.lbl_teclas.cget("text"))
check("ícone da janela carregado", app._icone is not None)

print("5) Regras: desfazer/refazer e alterações não salvas")
rg = app.paginas["regras"]; app.ir("regras"); r.update()
rg.arvore.selection_set("maximo"); r.update()
orig = open("botoes.json", encoding="utf-8").read()
check("sem alterações: nada a salvar", rg.pode_sair())
rg.v["intervalo"].set("33"); r.update()
check("campo editado = sujo", rg._sujo())
resp = {"v": None}
MB.askyesnocancel = lambda *a, **k: resp["v"]
resp["v"] = None
rg.arvore.selection_set("torre"); r.update()
check("cancelar mantém o botão atual", rg.sel == "maximo" and rg.arvore.selection() == ("maximo",))
resp["v"] = False
rg.arvore.selection_set("torre"); r.update()
check("descartar troca de botão sem salvar", rg.sel == "torre" and open("botoes.json", encoding="utf-8").read() == orig)
rg.arvore.selection_set("maximo"); r.update(); rg.v["intervalo"].set("44"); r.update()
resp["v"] = True
rg.arvore.selection_set("torre"); r.update()
novo = open("botoes.json", encoding="utf-8").read()
check("salvar ao trocar grava a regra", novo != orig and json.loads(novo)["maximo"]["intervalo"] == 44)
check("botão Desfazer habilitado", "disabled" not in rg.btn_des.state())
rg.desfazer(); r.update()
check("desfazer volta o arquivo", open("botoes.json", encoding="utf-8").read() == orig)
check("refazer habilitado", "disabled" not in rg.btn_ref.state())
rg.refazer(); r.update()
check("refazer reaplica", json.loads(open("botoes.json", encoding="utf-8").read())["maximo"]["intervalo"] == 44)
app._atalho_historico("desfazer"); r.update()
check("Ctrl+Z na página", open("botoes.json", encoding="utf-8").read() == orig)
app.g.pagina = "regras"; rg.arvore.selection_set("maximo"); r.update(); rg.v["intervalo"].set("55"); r.update()
resp["v"] = None
app.ir("config"); r.update()
check("trocar de página com alterações pergunta e pode cancelar", app.g.pagina == "regras")
resp["v"] = False; app.ir("config"); r.update()
check("…e descartando, troca", app.g.pagina == "config")

print("6) Editor de gravação")
from autoclick.interface.editor_gravacao import EditorGravacao
shutil.copy("gravacao.json", "g_orig.json")
ed = EditorGravacao(app, "gravacao.json"); r.update()
n0 = len(ed.eventos)
check("lista todos os eventos", len(ed.arv.get_children()) == n0 and n0 >= 3)
ed.arv.selection_set("0"); ed.apagar(); r.update()
check("apagar", len(ed.eventos) == n0 - 1 and "alterações não salvas" in ed.lbl.cget("text"))
ed.desfazer(); r.update(); check("desfazer", len(ed.eventos) == n0)
ed.refazer(); r.update(); check("refazer", len(ed.eventos) == n0 - 1)
ed.desfazer(); ed.arv.selection_set("1"); r.update()
ed._aplicar(ED.inserir_marcador(ed.eventos, 1, "maximo", 12, "aparecer", "parar"), [1]); r.update()
check("marcador na lista", ed.arv.item("1", "values")[1] == "Marcador")
MB.askyesno = lambda *a, **k: True
ed.arv.selection_set("1"); ed.cortar_antes(); r.update()
check("cortar antes", ed.eventos[0]["tipo"] == "aguardar" and ed.eventos[0]["t"] == 0.0)
ed.desfazer()
ed.salvar(); r.update()
salvo = json.load(open("gravacao.json", encoding="utf-8"))
check("salvo com marcador e .bak", any(e["tipo"] == "aguardar" for e in salvo["eventos"]) and os.path.isfile("gravacao.json.bak"))
ed.j.destroy()
shutil.copy("g_orig.json", "gravacao.json")

print("7) Configurações: atalhos, webhook, atualização, instalador")
cf = app.paginas["config"]; app.ir("config"); r.update()
avisos = []; MB.showwarning = lambda t, m, **k: avisos.append(m); MB.showinfo = lambda t, m, **k: avisos.append(m)
cf.v_teclas["pausa"].set("lixo"); cf.aplicar_teclas()
check("atalho inválido é recusado", avisos and app.g.tecla_pausa == "F8")
cf.v_teclas["pausa"].set("f6"); cf.v_teclas["parar"].set("F7"); cf.aplicar_teclas()
check("atalhos aplicados e rodapé atualizado", app.g.tecla_pausa == "F6" and "F6" in app.lbl_teclas.cget("text"))
app.g.tecla_pausa, app.g.tecla_parar = "F8", "F9"; app.atualizar_rodape_teclas()
pacote = os.path.abspath("novo.zip")
with zipfile.ZipFile(pacote, "w") as z:
    z.writestr("autoclick/__init__.py", "x"); z.writestr("autoclick/extra.py", "y"); z.writestr("botoes.json", "NAO")
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        corpo = json.dumps({"versao": "9.9.9", "url": f"http://127.0.0.1:{self.server.server_port}/p.zip", "notas": "novidades"}).encode() if self.path == "/m.json" else open(pacote, "rb").read()
        self.send_response(200); self.end_headers(); self.wfile.write(corpo)
    def do_POST(self):
        self.rfile.read(int(self.headers['Content-Length'])); self.send_response(204); self.end_headers()
    def log_message(self, *a): pass
srv = http.server.HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
app.g.url_atualizacao = f"http://127.0.0.1:{srv.server_port}/m.json"
MB.askyesno = lambda *a, **k: True
cf.verificar_atualizacao()
check("verificar + baixar + instalar", bombear(ate=lambda: "atualizado" in cf.lbl_up.cget("text")), cf.lbl_up.cget("text"))
check("pacote instalado, dados preservados, backup feito", os.path.isfile("autoclick/extra.py") and "NAO" not in open("botoes.json", encoding="utf-8").read())
shutil.rmtree("autoclick"); shutil.rmtree("backup", ignore_errors=True)
FD.askopenfilename = lambda *a, **k: pacote
cf.lbl_up.configure(text="")  # o texto da etapa anterior também diz "atualizado"
cf.aplicar_zip()
check("aplicar .zip local", bombear(ate=lambda: "atualizado" in cf.lbl_up.cget("text") and os.path.isfile("autoclick/extra.py")))
shutil.rmtree("autoclick")
DA_cmd = lambda: [sys.executable, "-c", "print('instalando-ok')"]
import autoclick.interface.pag_config as PC
PC.comando_instalar_pytesseract = DA_cmd
fim.clear(); app.exec.comando_base = None
cf.instalar_pytesseract()
check("instalador roda o comando e atualiza", bombear(ate=lambda: "instalando-ok" in app.log.get("1.0", "end")) and bombear(ate=lambda: not app.rodando))
app.g.webhook = f"http://127.0.0.1:{srv.server_port}/m.json"; cf.testar_webhook()
check("teste de webhook responde", bombear(ate=lambda: "Webhook respondeu" in app.log.get("1.0", "end")))

print("8) Visão ao vivo")
def png(path, w=40, h=20):
    raw = b"".join(b"\x00" + b"\x20\x80\x40" * w for _ in range(h))
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
pv = app._previas[0]; check("widgets de prévia registrados", len(app._previas) >= 1)
app.ir("auto"); r.update()
pv = app.paginas["auto"].previa
png(DA.ARQ_PREVIA); pv.atualizar(True); r.update()
check("prévia carrega o PNG", pv._img is not None and pv._img.width() == 40)
pv.limpar(); check("limpar", pv._img is None)
os.remove(DA.ARQ_PREVIA)

print("9) Gravar: aviso de ambiente e referência")
gp = app.paginas["gravar"]; app.ir("gravar"); r.update()
d = json.load(open("gravacao.json", encoding="utf-8")); d["tela"] = {"largura": 111, "altura": 222}; json.dump(d, open("gravacao.json", "w", encoding="utf-8"))
DA.tamanho_da_tela = lambda: (1920, 1080); import autoclick.interface.pag_gravacao as PG
PG.tamanho_da_tela = DA.tamanho_da_tela
gp.verificar_ambiente()
check("aviso amarelo aparece", "Ambiente diferente" in gp.lbl_amb.cget("text") and gp.btn_amb.winfo_manager() == "pack")
gp.usar_tamanho_atual()
check("usar tamanho atual limpa o aviso", gp.lbl_amb.cget("text") == "" and json.load(open("gravacao.json", encoding="utf-8"))["tela"]["largura"] == 1920)

print("10) Layout no tamanho mínimo")
r.geometry("900x640"); app.ir("config"); r.update(); bombear(0.4)
for k in ("gravar", "rotinas", "regras", "auto", "historico", "config", "ajuda"):
    app.ir(k); bombear(0.15)
    pb = [(n, b.winfo_width()) for n, b in (("chip", app.chip), ("pausa", app.btn_pausa), ("parar", app.btn_parar))]
    check(f"{k}: 3 controles iguais e visíveis", max(w for _, w in pb) - min(w for _, w in pb) <= 1 and app._dir.winfo_rootx() + app._dir.winfo_width() <= r.winfo_rootx() + r.winfo_width(), str(pb))
print(f"\n{ok} verificações passaram (GUI 2).")
app.exec.parar(); app.exec.matar()
