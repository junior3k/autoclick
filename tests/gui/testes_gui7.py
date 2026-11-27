"""GUI 0.14: interface enxuta (menu, abas de Configurações, "minimizar" desligado) e proteção das gravações."""
import sys as _s0
for _f in (_s0.stdout, _s0.stderr):
    try: _f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
import sys, os, time, json, shutil, tempfile
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
ROOT = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp(); shutil.copytree(f"{ROOT}/proj", f"{tmp}/p"); os.chdir(f"{tmp}/p")
os.environ["PYTHONPATH"] = os.pathsep.join([RAIZ] + [x for x in sys.path if x]); os.environ["AUTOCLICK_SEM_OCR"] = "1"
import tkinter.messagebox as MB
from autoclick.interface.app import App
from autoclick.interface import dados as D
from autoclick.interface.dados import Geral
ok = 0
def check(n, c, extra=""):
    global ok
    print(("  OK   " if c else "  FALHOU ") + n + (f"  {extra}" if extra and not c else ""))
    if not c: sys.exit(1)
    ok += 1

print("1) Padrão e migração de “minimizar”")
check("padrão desligado", Geral().minimizar is False)
novo = os.path.join(tmp, "novo.json")
check("instalação nova: desligado e já no layout atual", (lambda g: g.minimizar is False and g.layout_versao == 1)(D.carregar_geral(novo)))
antigo = os.path.join(tmp, "antigo.json")
json.dump({"minimizar": True, "janela": "Roblox"}, open(antigo, "w"))
g = D.carregar_geral(antigo)
check("arquivo antigo: zera o minimizar uma vez e mantém o resto", g.minimizar is False and g.janela == "Roblox" and g.layout_versao == 1)
g.minimizar = True; D.salvar_geral(g, antigo)
check("depois de migrado, a escolha do usuário vale", D.carregar_geral(antigo).minimizar is True)

print("2) Cópia de segurança da gravação")
arq = os.path.join(tmp, "coleta.json")
check("sem arquivo: 0 eventos e sem cópia", D.eventos_da_gravacao(arq) == 0 and D.copia_de_seguranca(arq) is None)
json.dump({"eventos": [{"t": 0.1}, {"t": 0.5}]}, open(arq, "w"))
check("conta os eventos", D.eventos_da_gravacao(arq) == 2)
bak = D.copia_de_seguranca(arq)
check("cópia em coleta.bak.json com o mesmo conteúdo", bak is not None and bak.endswith("coleta.bak.json")
      and open(bak).read() == open(arq).read())

print("3) Janela")
g = Geral(); app = App(g, os.getcwd()); r = app.raiz
def bombear(s=0.3):
    t0 = time.time()
    while time.time() - t0 < s: r.update(); time.sleep(0.02)
bombear()
check("menu: Gravar, Rotinas, Automático, Botões, Histórico, Configurações, Ajuda",
      list(app._nav) == ["gravar", "rotinas", "auto", "regras", "historico", "config", "ajuda"])
cf = app.paginas["config"]
check("Configurações tem 5 abas", [k for k, _ in cf.ABAS] == ["geral", "atalhos", "avisos", "jogos", "manutencao"])
app.ir("config"); bombear(0.2)
check("abre na aba Geral", cf._aba_atual == "geral" and cf._abas["geral"].winfo_ismapped())
check("“minimizar” está na primeira aba e desligado", cf.app.g.minimizar is False)
app.ir("jogos"); bombear(0.2)
check("ir('jogos') abre Configurações na aba Jogos", app.g.pagina == "config" and cf._aba_atual == "jogos"
      and app.subpaginas["jogos"].frame.winfo_ismapped())
check("outras abas ficam escondidas", not cf._abas["geral"].winfo_ismapped())
for k, _ in cf.ABAS:
    cf.abrir_aba(k); bombear(0.1)
    check(f"aba {k} abre", cf._abas[k].winfo_ismapped())
check("seletor de jogo no topo", "Jogo:" in app.mb_jogo.cget("text"))

print("4) Gravar não sobrescreve sem perguntar")
pg = app.paginas["gravar"]; app.g.gravacao = arq
perguntas = []
def pergunta(*a, **k): perguntas.append(a); return False
MB.askyesno = pergunta
chamadas = []
app.rodar = lambda *a, **k: chamadas.append(a) or True
pg.gravar()
check("gravação existente: pergunta e, se recusar, não grava", len(perguntas) == 1 and not chamadas and "coleta.json" in perguntas[0][1])
MB.askyesno = lambda *a, **k: True
os.remove(os.path.join(tmp, "coleta.bak.json"))
pg.gravar()
check("confirmando: faz a cópia e grava", len(chamadas) == 1 and os.path.isfile(os.path.join(tmp, "coleta.bak.json")))
chamadas.clear(); perguntas.clear(); MB.askyesno = pergunta
pg.gravar(perguntar=False)
check("pelo atalho de teclado: não abre janela, só guarda a cópia e grava", not perguntas and len(chamadas) == 1)
app.g.gravacao = os.path.join(tmp, "vazio.json"); chamadas.clear()
pg.gravar()
check("arquivo sem gravação: grava direto", not perguntas and len(chamadas) == 1)
print(f"\n{ok} verificações passaram (GUI 0.14).")
