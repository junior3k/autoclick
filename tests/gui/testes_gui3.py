"""GUI + servidor real: importar convite, verificar, atualizar, enviar relatório."""
import sys, os, time, json, shutil, tempfile, socket, threading
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
ROOT = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp()
shutil.copytree(f"{ROOT}/proj", f"{tmp}/p")
os.environ["AUTOCLICK_SERVIDOR_DADOS"] = f"{tmp}/dados"
os.environ["AUTOCLICK_SEM_OCR"] = "1"
os.environ["PYTHONPATH"] = os.pathsep.join([RAIZ] + [x for x in sys.path if x])
fonte = f"{tmp}/fonte"; os.makedirs(fonte)
shutil.copytree(f"{RAIZ}/autoclick", f"{fonte}/autoclick", ignore=shutil.ignore_patterns("__pycache__"))
for f in ("pyproject.toml", "autoclick_inteligente.py"): shutil.copy2(f"{RAIZ}/{f}", fonte)
os.chdir(f"{tmp}/p")
shutil.copytree(f"{RAIZ}/autoclick", "autoclick", ignore=shutil.ignore_patterns("__pycache__"))
shutil.copy2(f"{RAIZ}/pyproject.toml", "pyproject.toml")

ok = 0
def check(n, c, extra=""):
    global ok
    print(("  OK   " if c else "  FALHOU ") + n + (f"  {extra}" if extra and not c else ""))
    if not c: sys.exit(1)
    ok += 1

from servidor import operacao, publicar as pub
from servidor.nucleo import Nucleo
from servidor.web import criar_app
import uvicorn
s = socket.socket(); s.bind(("127.0.0.1", 0)); porta = s.getsockname()[1]; s.close()
cfg, token = operacao.instalar(f"http://127.0.0.1:{porta}", porta, f"{tmp}/dados", raiz=fonte)
n = Nucleo(f"{tmp}/dados")
pub.publicar(n, "9.9.0", testes=False, canal="estavel", notas="novidades de teste", raiz=fonte, log=lambda m: None)
uv = uvicorn.Server(uvicorn.Config(criar_app(n), host="127.0.0.1", port=porta, log_level="error"))
threading.Thread(target=uv.run, daemon=True).start()
for _ in range(100):
    try: socket.create_connection(("127.0.0.1", porta), 0.2).close(); break
    except OSError: time.sleep(0.1)
import zipfile as _zf
os.environ["AUTOCLICK_SERVIDOR_URL"] = n.cfg.base

import tkinter.messagebox as MB, tkinter.filedialog as FD
from autoclick import atualizacao
atualizacao.chave_publica_embutida = lambda: n.chave_publica_hex()
from autoclick.interface.app import App
from autoclick.interface.dados import Geral
app = App(Geral(tema="escuro", atualizar_ao_abrir=False), os.getcwd()); r = app.raiz
def bombear(ate, limite=40.0):
    t0 = time.time()
    while time.time() - t0 < limite:
        r.update()
        if ate(): return True
        time.sleep(0.02)
    return False
cf = app.paginas["config"]; app.ir("config"); r.update(); ctl = cf.servidor_ctl
real_exec = app.exec
infos = []; MB.showinfo = lambda *a, **k: infos.append(a)
MB.showerror = lambda *a, **k: infos.append(a)
MB.askyesno = lambda *a, **k: True

print("1) Sem convite: o cartão já mostra o servidor")
check("mostra o servidor e o canal", "127.0.0.1" in ctl.lbl_srv.cget("text") and "estavel" in ctl.lbl_srv.cget("text"))
check("não existem botões de convite", not hasattr(ctl, "importar") and not hasattr(ctl, "colar"))

print("2) Verificar e atualizar")
ctl.verificar(silencioso=True)
check("achou 0.9.0 e avisou no rodapé", bombear(lambda: "9.9.0" in app.lbl_versao.cget("text")), app.lbl_versao.cget("text"))
check("silencioso não instala sozinho", '"9.9.0"' not in open("autoclick/__init__.py").read())
ctl.atualizar()
check("instalou com autoteste", bombear(lambda: "instalada" in ctl.lbl.cget("text")), ctl.lbl.cget("text"))
check("arquivos novos e dados preservados", '"9.9.0"' in open("autoclick/__init__.py").read() and os.path.isfile("botoes.json"))
check("pacote baixado foi limpo", not os.path.isdir(atualizacao.pasta_baixados(os.getcwd())) or not os.listdir(atualizacao.pasta_baixados(os.getcwd())))
nv = json.load(open("_atualizacao/novidades.json", encoding="utf-8"))
check("novidades guardadas para o próximo início", nv["versao"] == "9.9.0" and "novidades de teste" in nv["notas"], str(nv))
check("backup feito", len(atualizacao.listar_backups(os.getcwd())) >= 1)
check("id de instalação criado ao lado do programa", os.path.isfile("autoclick_instalacao.txt") and n.resumo()["instalacoes"] == 1)
app.g.canal_beta = True; ctl.pintar(); check("canal beta opcional aparece", "beta" in ctl.lbl_srv.cget("text")); app.g.canal_beta = False; ctl.pintar()

print("2b) Pronta: oferece só quando ocioso e instala ao fechar")
perguntas = []; MB.askyesno = lambda *a, **k: (perguntas.append(a), False)[1]
ctl.verificar(silencioso=True)
check("de novo baixada e pronta", bombear(lambda: ctl.pronto is not None))
app.exec = type("E", (), {"rodando": True})()
ctl._ocioso_desde = time.time() - 60; ctl.tick()
check("rodando: não pergunta", not perguntas and ctl._ocioso_desde == 0.0)
app.exec = real_exec
ctl.tick(); ctl._ocioso_desde = time.time() - 31; ctl.tick()
check("parado há 30 s: pergunta uma vez", len(perguntas) == 1 and "9.9.0" in perguntas[0][1], str(perguntas))
ctl._ocioso_desde = time.time() - 60; ctl.tick()
check("recusou: não pergunta de novo", len(perguntas) == 1 and ctl.pronto is not None)
antes = len(atualizacao.listar_backups(os.getcwd()))
app.g.atualizar_ao_fechar = False; ctl.ao_fechar()
check("opção desligada: não instala ao fechar", ctl.pronto is not None and len(atualizacao.listar_backups(os.getcwd())) == antes)
time.sleep(1.2)  # o nome do backup tem segundos
app.g.atualizar_ao_fechar = True; ctl.ao_fechar()
check("ligada: instala ao fechar (com backup)", ctl.pronto is None and len(atualizacao.listar_backups(os.getcwd())) > antes)
MB.askyesno = lambda *a, **k: True

print("3) Relatório")
os.makedirs("logs", exist_ok=True); open("logs/autoclick.log", "w").write("linha de log\n")
ctl.enviar_relatorio()
check("relatório enviado", bombear(lambda: "Relatório enviado" in ctl.lbl.cget("text")), ctl.lbl.cget("text"))
lista = n.listar_relatorios(); check("servidor recebeu", len(lista) == 1 and lista[0]["instalacao"] == open("autoclick_instalacao.txt").read()[:8])
import zipfile; z = zipfile.ZipFile(n.caminho_relatorio(lista[0]["id"]))
check("relatório com log e sem segredos", "autoclick.log" in z.namelist() and "webhook" not in z.read("config.json").decode())

print("4) Servidor fora do ar")
uv.should_exit = True; time.sleep(1.0)
ctl.verificar()
check("erro claro", bombear(lambda: "✖" in ctl.lbl.cget("text")), ctl.lbl.cget("text"))

print("5) Som por volta liga/desliga durante a execução")
enviados = []
class FakeExec:
    rodando = True
    def enviar_comando(self, c): enviados.append(c)
real = app.exec; app.exec = FakeExec()
app.g.som_volta = False; app._pintar_som()
check("botão mostra desligado", "desligado" in app.btn_som.cget("text"))
app.alternar_som()
check("ligou: botão, config e comando ao processo", app.g.som_volta and "ligado" in app.btn_som.cget("text") and enviados == ["som:1"])
check("checkbox da Configurações acompanha", all(bool(v.get()) for v in app._vars_som))
app.alternar_som(); check("desligou durante a execução", enviados == ["som:1", "som:0"] and not app.g.som_volta)
app.exec = real
app.fechar(forcar=True)
print(f"\n{ok} verificações passaram (GUI + servidor).")
