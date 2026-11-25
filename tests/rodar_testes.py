import sys, types, json, tempfile, os, io, contextlib
from pathlib import Path
import numpy as np, cv2

# ---- stubs (sem display / sem mouse real) ----
try:
    import mss  # noqa
except Exception:
    sys.modules["mss"] = types.SimpleNamespace()

import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from fachada import A
import time
time.sleep = lambda s: None  # testes rápidos

ok = 0
def check(nome, cond, extra=""):
    global ok
    print(("  OK   " if cond else "  FALHOU ") + nome + (f"  {extra}" if extra and not cond else ""))
    if not cond: sys.exit(1)
    ok += 1

tmp = Path(tempfile.mkdtemp())

print("1) Regras (botoes.json)")
cfg = tmp / "botoes.json"
cfg.write_text(json.dumps({
    "_comentario": "ignorado",
    "maximo": {"acao": "clicar"},
    "proxima": {"acao": "clicar", "intervalo": 2},
    "torre": {"acao": "arrastar", "destino": [980, 540]},
    "inicio_partida": {"acao": "inicio"},
}), encoding="utf-8")
r = A.carregar_regras(str(cfg))
check("4 regras (comentário ignorado)", set(r) == {"maximo", "proxima", "torre", "inicio_partida"})
check("arrastar: vezes=1 e confirmar_cinza=True por padrão", r["torre"].vezes == 1 and r["torre"].confirmar_cinza)
check("clicar: ilimitado, sem confirmar cinza", r["maximo"].vezes == 0 and not r["maximo"].confirmar_cinza)
check("intervalo lido", r["proxima"].intervalo == 2.0)
check("sem arquivo => {}", A.carregar_regras(str(tmp / "naoexiste.json")) == {})
for nome, conteudo in [("sem destino", {"t": {"acao": "arrastar"}}), ("acao ruim", {"t": {"acao": "voar"}}),
                       ("destino ruim", {"t": {"acao": "arrastar", "destino": [1]}})]:
    (tmp / "ruim.json").write_text(json.dumps(conteudo), encoding="utf-8")
    try: A.carregar_regras(str(tmp / "ruim.json")); check(f"erro claro: {nome}", False)
    except SystemExit as e: check(f"erro claro: {nome}", "ruim.json" in str(e.code))
(tmp / "ruim.json").write_text("{quebrado", encoding="utf-8")
try: A.carregar_regras(str(tmp / "ruim.json")); check("JSON quebrado", False)
except SystemExit as e: check("JSON quebrado => mensagem", "inválido" in str(e.code))

print("2) Confirmação de cinza")
colorido = np.zeros((100, 100, 3), np.uint8); colorido[:] = (30, 160, 230)   # laranja saturado
cinza = np.zeros((100, 100, 3), np.uint8); cinza[:] = (120, 120, 120)
h = A.Hit(10, 10, 50, 30, "torre")
antes, depois = A.saturacao_media(colorido, h), A.saturacao_media(cinza, h)
check("saturação alta no colorido, ~0 no cinza", antes > 100 and depois < 5, f"{antes:.0f}/{depois:.0f}")
check("colorido -> cinza = True", A.ficou_cinza(antes, depois, 0.5) is True)
check("colorido -> colorido = False", A.ficou_cinza(antes, antes, 0.5) is False)
check("já era cinza = None (não decide)", A.ficou_cinza(5.0, 5.0, 0.5) is None)
check("região fora da imagem não quebra", A.saturacao_media(colorido, A.Hit(500, 500, 10, 10, "x")) == 0.0)

print("3) Log CSV")
logp = tmp / "logs" / "acoes.csv"
reg = A.Registro(str(logp))
reg.log("arrasto", "torre", 200, 467, 980, 540, "confirmado"); reg.log("clique", "maximo", 200, 423); reg.fechar()
linhas = logp.read_text(encoding="utf-8").strip().splitlines()
check("cabeçalho + 2 linhas", len(linhas) == 3 and linhas[0].startswith("horario,t_seg,tipo,botao,x,y,x2,y2"))
check("coordenadas gravadas", ",arrasto,torre,200,467,980,540," in linhas[1])
reg2 = A.Registro(str(logp)); reg2.log("clique", "maximo", 1, 2); reg2.fechar()
check("append sem repetir cabeçalho", len(logp.read_text(encoding="utf-8").strip().splitlines()) == 4)

print("4) gerar_regras a partir da gravação")
gcfg = tmp / "gerado.json"
gcfg.write_text(json.dumps({"maximo": {"acao": "clicar", "intervalo": 9}}), encoding="utf-8")
evs = [
    {"tipo": "clique", "x": 1, "y": 1, "x2": 1, "y2": 1, "botao": "maximo"},
    {"tipo": "clique", "x": 5, "y": 5, "x2": 5, "y2": 5, "botao": "torre"},
    {"tipo": "arrasto", "x": 5, "y": 5, "x2": 980, "y2": 540, "botao": "torre"},
    {"tipo": "clique", "x": 9, "y": 9, "x2": 9, "y2": 9, "botao": None},
]
buf = io.StringIO()
with contextlib.redirect_stdout(buf): A.gerar_regras(evs, str(gcfg), False)
g = json.loads(gcfg.read_text(encoding="utf-8"))
check("arrasto vira destino [980,540], vezes 1", g["torre"] == {"acao": "arrastar", "destino": [980, 540], "vezes": 1})
check("regra existente mantida", g["maximo"] == {"acao": "clicar", "intervalo": 9})
check("avisa evento sem nome", "sem nome" in buf.getvalue())
with contextlib.redirect_stdout(io.StringIO()): A.gerar_regras(evs, str(gcfg), True)
check("--sobrescrever troca a regra", json.loads(gcfg.read_text(encoding="utf-8"))["maximo"] == {"acao": "clicar"})

print("5) Identificar botão no clique (gravação)")
import threading
trava = threading.Lock()
conhecidos = {"torre": ((100, 100, 200, 160), time.time()), "velho": ((0, 0, 50, 50), time.time() - 99)}
check("clique dentro do botão -> nome", A._identificar(150, 130, trava, conhecidos) == "torre")
check("clique fora -> None", A._identificar(900, 900, trava, conhecidos) is None)
check("botão visto há muito tempo é ignorado", A._identificar(20, 20, trava, conhecidos) is None)

print("6) clicar() com arrasto: ordem dos eventos do mouse")
ev6 = []
pos6 = {"x": 500, "y": 500}
def _mv(x, y, duracao=0, passos=0): pos6["x"], pos6["y"] = int(x), int(y); ev6.append(("move", int(x), int(y)))
A.mover_suave = _mv
A.mover_real = lambda x, y: _mv(x, y)
A.posicao = lambda: (pos6["x"], pos6["y"])
A.tamanho_tela = lambda: (1920, 1080)
A.checar_failsafe = lambda: None
A._enviar_mouse = lambda dx, dy, fl: ev6.append(("down",) if fl == A._LEFTDOWN else ("up",))
hit = A.Hit(190, 450, 20, 30, "torre")
res = A.clicar(hit, 1.0, 1.0, 0, 0, foco=False, estacionar=False, arrastar_para=(980, 540), hold=0.15)
iddown = ev6.index(("down",)); idup = ev6.index(("up",))
mov_entre = [e for e in ev6[iddown:idup] if e[0] == "move"]
check("retornou True", res is True)
check("apertou, moveu até (980,540) e só então soltou", iddown < idup and mov_entre and mov_entre[-1][1:] == (980, 540))
ev6.clear(); A.clicar(hit, 1.0, 1.0, 0, 0, foco=False, estacionar=False)
iddown = ev6.index(("down",)); idup = ev6.index(("up",))
check("clique simples: nenhum movimento entre apertar e soltar", not [e for e in ev6[iddown:idup] if e[0] == "move"])
ev6.clear()
res = A.clicar(hit, 1.0, 1.0, 0, 0, foco=False, estacionar=False, confirmar=lambda: False)
check("botão mudou: cancela sem apertar o mouse", res is False and ("down",) not in ev6)
ev6.clear()
class Boom(Exception): pass
calls = {"n": 0}
def _mv_boom(x, y, duracao=0, passos=0):
    _mv(x, y)
    if ev6.count(("down",)) and passos == 35: raise Boom()
A.mover_suave = _mv_boom
try: A.clicar(hit, 1.0, 1.0, 0, 0, foco=False, estacionar=False, arrastar_para=(980, 540))
except Boom: pass
check("erro no meio do arrasto: o botão do mouse é SOLTO (não fica preso)", ev6[-1] == ("up",))
A.mover_suave = _mv
check("offset acompanha a escala do botão", A.ponto_de_clique(A.Hit(100, 100, 20, 20, "x", 1.0, 0.5), 10, 0) == (115, 110))

print("7) Fluxo completo do main: uma vez por partida + confirmação + reinício")
pasta = tmp / "botoes"; pasta.mkdir()
for n in ("maximo", "torre", "inicio_partida", "proxima"): (pasta / f"{n}.png").write_bytes(b"x")
cfg2 = tmp / "fluxo.json"
cfg2.write_text(json.dumps({
    "maximo": {"acao": "clicar"},
    "torre": {"acao": "arrastar", "destino": [980, 540], "vezes": 1, "tentativas": 3},
    "inicio_partida": {"acao": "inicio"},
}), encoding="utf-8")
def H(n, x=200, y=450): return A.Hit(x, y, 40, 30, n)
M, T, I = H("maximo", 200, 300), H("torre", 200, 450), H("inicio_partida", 600, 50)
scans = [
    [M, T],        # 1: arrasta a torre -> NÃO fica cinza (1ª tentativa falha)
    [M, T],        # 2: tenta de novo -> fica cinza (feito)
    [M, T],        # 3: torre NÃO pode ser arrastada de novo (vezes=1)
    [M, T, I],     # 4: início de partida aparece -> zera -> torre pode de novo
    [M, T, I],     # 5: início continua visível -> NÃO zera de novo; torre já feita nesta partida
]
it = iter(scans)
def fake_detectar(img, pasta_, conf):
    try: return next(it)
    except StopIteration: raise KeyboardInterrupt
A.detectar_imagens = fake_detectar
A.capturar = lambda m, r: (np.zeros((1080, 1920, 3), np.uint8), 1.0, 1.0, 0, 0)
chamadas = []
def fake_clicar(h, *a, **k):
    chamadas.append((h.rotulo, k.get("arrastar_para"))); return True
A.clicar = fake_clicar
respostas_cinza = iter([(False, 90.0), (True, 5.0), (True, 5.0)])
A.saturacao_media = lambda img, h: 120.0
A.verificar_cinza = lambda h, antes, regra, mon, reg: next(respostas_cinza)
logf = tmp / "fluxo.csv"
sys.argv = ["x", "imagem", "--pasta", str(pasta), "--config", str(cfg2), "--cooldown", "0",
            "--intervalo", "0", "--log", str(logf), "--sem-recheck"]
buf = io.StringIO()
with contextlib.redirect_stdout(buf): A.main()
saida = buf.getvalue()
arrastos = [c for c in chamadas if c[0] == "torre"]
cliques_max = [c for c in chamadas if c[0] == "maximo"]
check("torre arrastada 3x no total (falha, sucesso, nova partida)", len(arrastos) == 3, str(arrastos))
check("sempre com destino (980,540)", all(c[1] == (980, 540) for c in arrastos))
check("maximo clicado em todas as 5 varreduras, sem destino", len(cliques_max) == 5 and all(c[1] is None for c in cliques_max))
check("falha de cinza foi reportada com nova tentativa", "nova tentativa (1/3)" in saida)
check("início zerou UMA vez só", saida.count("nova partida detectada") == 1)
log = logf.read_text(encoding="utf-8")
check("log tem arrasto_nao_confirmado, arrasto e inicio_partida",
      "arrasto_nao_confirmado" in log and ",arrasto,torre," in log and "inicio_partida" in log)

print("8) Desistir após N tentativas")
it = iter([[T]] * 6)
chamadas.clear()
respostas_cinza = iter([(False, 90.0)] * 10)
A.verificar_cinza = lambda h, antes, regra, mon, reg: next(respostas_cinza)
cfg3 = tmp / "desiste.json"; cfg3.write_text(json.dumps({"torre": {"acao": "arrastar", "destino": [1, 2], "tentativas": 2}}), encoding="utf-8")
sys.argv = ["x", "imagem", "--pasta", str(pasta), "--config", str(cfg3), "--cooldown", "0", "--intervalo", "0", "--sem-recheck"]
buf = io.StringIO()
with contextlib.redirect_stdout(buf): A.main()
check("tentou só 2 vezes e desistiu", len(chamadas) == 2 and "desisti" in buf.getvalue(), buf.getvalue())

print(f"\n{ok} verificações passaram.")
