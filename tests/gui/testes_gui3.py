"""GUI + site estático falso (manifesto assinado + pacote): verificar, atualizar, salvar relatório."""
import sys, os, time, json, shutil, tempfile, socket, threading
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
ROOT = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp()
shutil.copytree(f"{ROOT}/proj", f"{tmp}/p")
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

import hashlib, http.server, zipfile as _zf
from autoclick import ed25519 as ED, atualizacao
SEM = ED.gerar_semente(); PUB = ED.chave_publica(SEM).hex()
# pacote "fonte" da versão 9.9.0 (o código atual com a versão trocada)
pac_zip = f"{tmp}/pacote.zip"
with _zf.ZipFile(pac_zip, "w", _zf.ZIP_DEFLATED) as z:
    for dp, _, fs in os.walk(f"{fonte}/autoclick"):
        for f in fs:
            full = os.path.join(dp, f); rel = os.path.relpath(full, fonte).replace(os.sep, "/")
            dados = open(full, "rb").read()
            if rel == "autoclick/__init__.py":
                import re as _re; dados = _re.sub(rb'__version__\s*=\s*"[^"]+"', b'__version__ = "9.9.0"', dados)
            z.writestr(rel, dados)
    z.write(f"{fonte}/pyproject.toml", "pyproject.toml")
PACOTE = open(pac_zip, "rb").read(); SHA = hashlib.sha256(PACOTE).hexdigest()
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path == "/manifesto.json":
            sig = ED.assinar(SEM, atualizacao.mensagem_do_pacote("9.9.0", "fonte", SHA, len(PACOTE))).hex()
            corpo = json.dumps({"mensagem": "", "atualizacoes": {"fonte": {
                "versao": "9.9.0", "artefato": "fonte", "canal": "estavel", "sha256": SHA, "tamanho": len(PACOTE),
                "minima": "0", "assinatura": sig, "notas": "novidades de teste",
                "url": f"http://127.0.0.1:{porta}/arquivos/p.zip"}}}).encode()
        elif self.path.startswith("/arquivos/"):
            corpo = PACOTE
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header("Content-Length", str(len(corpo))); self.end_headers(); self.wfile.write(corpo)
httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); porta = httpd.server_port
threading.Thread(target=httpd.serve_forever, daemon=True).start()
os.environ["AUTOCLICK_SERVIDOR_URL"] = f"http://127.0.0.1:{porta}"

import tkinter.messagebox as MB, tkinter.filedialog as FD
atualizacao.chave_publica_embutida = lambda: PUB
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

print("1) Sem convite: o cartão já mostra de onde vêm as atualizações")
check("mostra o endereço, sem canal beta", "127.0.0.1" in ctl.lbl_srv.cget("text") and "beta" not in ctl.lbl_srv.cget("text") and not hasattr(app.g, "canal_beta"))
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
check("nenhum número de instalação é criado", not os.path.isfile("autoclick_instalacao.txt"))

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

print("3) Relatório (salvo em arquivo, nada é enviado)")
os.makedirs("logs", exist_ok=True); open("logs/autoclick.log", "w").write("linha de log\n")
destino = f"{tmp}/meu_relatorio.zip"; FD.asksaveasfilename = lambda *a, **k: destino
ctl.salvar_relatorio()
check("relatório salvo", os.path.isfile(destino) and "salvo" in ctl.lbl.cget("text"), ctl.lbl.cget("text"))
import zipfile; z = zipfile.ZipFile(destino)
check("relatório com log e sem segredos", "autoclick.log" in z.namelist() and "webhook" not in z.read("config.json").decode())
FD.asksaveasfilename = lambda *a, **k: ""; os.remove(destino); ctl.salvar_relatorio()
check("cancelar não cria arquivo", not os.path.exists(destino))
check("não há mais botão de enviar", not hasattr(ctl, "enviar_relatorio"))

print("4) Servidor fora do ar")
httpd.shutdown(); httpd.server_close(); time.sleep(0.5)
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
print(f"\n{ok} verificações passaram (GUI + site estático).")
