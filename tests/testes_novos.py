import sys as _s0
for _f in (_s0.stdout, _s0.stderr):
    try: _f.reconfigure(encoding="utf-8", errors="replace")  # Windows (cp1252) não imprime setas
    except Exception: pass
import sys, types, json, tempfile, io, contextlib, time, ctypes, threading
from pathlib import Path
import numpy as np
try:
    import mss  # noqa
except Exception:
    sys.modules["mss"] = types.SimpleNamespace()
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from fachada import A
time.sleep = lambda s: None
REAL_PLATFORM = sys.platform

def check(nome, cond, extra=""):
    print(("  OK   " if cond else "  FALHOU ") + nome + (f"  {extra}" if extra and not cond else ""))
    if not cond: sys.exit(1)

def quieto(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try: r = fn(*a, **k)
        except SystemExit as e: r = ("EXIT", str(e.code))
    return r, buf.getvalue()

tmp = Path(tempfile.mkdtemp())

print("1) botoes.json: novas formas de destino")
def carrega(conteudo):
    (tmp / "r.json").write_text(json.dumps(conteudo), encoding="utf-8")
    return A.carregar_regras(str(tmp / "r.json"))
r = carrega({"a": {"acao": "arrastar", "destino": {"janela": [0.62, 0.5]}},
             "b": {"acao": "arrastar", "destino": {"ancora": "mapa_ref", "offset": [320, -140]}},
             "c": {"acao": "arrastar", "destino": [980, 540]}, "mapa_ref": {"acao": "ancora"}})
check("destino por fração da janela", r["a"].destino_janela == (0.62, 0.5) and r["a"].destino is None)
check("destino por âncora", r["b"].destino_ancora == ("mapa_ref", 320, -140))
check("destino fixo continua funcionando (compatível)", r["c"].destino == (980, 540))
check("ação 'ancora' aceita", r["mapa_ref"].acao == "ancora")
for nome, conteudo in [("fração fora de 0-1", {"t": {"acao": "arrastar", "destino": {"janela": [1.5, 0.2]}}}),
                       ("dict sem janela/ancora", {"t": {"acao": "arrastar", "destino": {"x": 1}}}),
                       ("offset da âncora ruim", {"t": {"acao": "arrastar", "destino": {"ancora": "a", "offset": [1]}}}),
                       ("destino texto", {"t": {"acao": "arrastar", "destino": "oi"}})]:
    res, _ = quieto(carrega, conteudo)
    check(f"erro claro: {nome}", isinstance(res, tuple) and res[0] == "EXIT" and "r.json" in res[1], str(res))
(tmp / "j.json").write_text(json.dumps({"_janela": "Roblox", "x": {"acao": "clicar"}}), encoding="utf-8")
check('"_janela" lido do json', A.carregar_janela_config(str(tmp / "j.json")) == "Roblox")
check("sem arquivo => None", A.carregar_janela_config(str(tmp / "nao.json")) is None)

print("2) resolver_destino")
rj = A.Regra(acao="arrastar", destino_janela=(0.5, 0.25))
ra = A.Regra(acao="arrastar", destino_ancora=("mapa_ref", 100, -50))
rf = A.Regra(acao="arrastar", destino=(980, 540))
check("fixo", A.resolver_destino(rf, None, {}, 0.0) == ((980, 540), ""))
check("janela: acompanha posição e tamanho", A.resolver_destino(rj, (100, 50, 800, 600), {}, 0)[0] == (500, 200)
      and A.resolver_destino(rj, (300, 80, 400, 300), {}, 0)[0] == (500, 155))
check("janela não encontrada => None + motivo", A.resolver_destino(rj, None, {}, 0)[0] is None)
anc = {"mapa_ref": (520.0, 370.0, 0.5, 0.5, 100.0)}
check("âncora: ponto + offset * escala", A.resolver_destino(ra, None, anc, 101.0)[0] == (570, 345))
anc2 = {"mapa_ref": (900.0, 100.0, 0.5, 0.5, 101.0)}
check("âncora moveu (câmera) => destino acompanha", A.resolver_destino(ra, None, anc2, 102.0)[0] == (950, 75))
check("âncora velha (>5s) => None", A.resolver_destino(ra, None, anc, 110.0)[0] is None)
check("âncora ausente => None", A.resolver_destino(ra, None, {}, 0)[0] is None)

print("3) main com --janela: destino por janela e por âncora, mover/redimensionar")
pasta = tmp / "botoes"; pasta.mkdir()
for n in ("torre", "mina", "mapa_ref", "inicio_partida"): (pasta / f"{n}.png").write_bytes(b"x")
cfg = tmp / "jogo.json"
cfg.write_text(json.dumps({
    "torre": {"acao": "arrastar", "vezes": 1, "destino": {"ancora": "mapa_ref", "offset": [100, -50]}},
    "mina": {"acao": "arrastar", "vezes": 1, "destino": {"janela": [0.5, 0.25]}},
    "inicio_partida": {"acao": "inicio"}}), encoding="utf-8")   # mapa_ref SEM regra: deve virar âncora sozinho
RA, RB = (100, 50, 800, 600), (300, 80, 400, 300)
rects = iter([RA, RA, RB, RB, RB, RB])
A.rect_da_janela = lambda t: next(rects)
A.geometria_monitor = lambda i: (0, 0, 1920, 1080)
A.capturar = lambda m, reg: (np.zeros((1080, 1920, 3), np.uint8), 1.0, 1.0, reg[0] if reg else 0, reg[1] if reg else 0)
ANC = A.Hit(400, 300, 40, 40, "mapa_ref", 1.0, 0.5)
T, M, I = A.Hit(10, 10, 40, 30, "torre"), A.Hit(10, 80, 40, 30, "mina"), A.Hit(50, 5, 20, 20, "inicio_partida")
scans = iter([[T, M], [ANC, T, M], [ANC, T, M, I]])
def det(img, p, c):
    A._esc.atual = A._esc.atual or 1.0      # como a detecção real: aprende a escala
    try: return next(scans)
    except StopIteration: raise KeyboardInterrupt
A.detectar_imagens = det
chamadas = []
A.clicar = lambda h, *a, **k: chamadas.append((h.rotulo, k.get("arrastar_para"))) or True
A.saturacao_media = lambda img, h: 120.0
A.verificar_cinza = lambda h, antes, regra, mon, reg: (True, 5.0)
A.configurar_escala(); A._esc.atual = 1.0
sys.argv = ["x", "imagem", "--pasta", str(pasta), "--config", str(cfg), "--janela", "Jogo",
            "--cooldown", "0", "--intervalo", "0", "--sem-recheck"]
_, saida = quieto(A.main)
check("1ª varredura: mina vai para a fração da janela (500,200); torre espera a âncora",
      chamadas[0] == ("mina", (500, 200)) and "destino indisponível" in saida, str(chamadas))
check("2ª: torre vai para âncora + offset*escala = (570,345)", chamadas[1] == ("torre", (570, 345)), str(chamadas))
check("nova partida, janela movida/menor: torre (770,375) e mina (500,155)",
      chamadas[2:] == [("torre", (770, 375)), ("mina", (500, 155))], str(chamadas))
check("a âncora nunca é clicada", all(c[0] != "mapa_ref" for c in chamadas))
check("detectou o redimensionamento e previu a nova escala (1.0 -> 0.5)",
      "janela redimensionada" in saida and abs(A._esc.atual - 0.5) < 1e-6, saida)

res, _ = quieto(lambda: (sys.argv.__setitem__(slice(None), ["x", "imagem", "--pasta", str(pasta), "--config",
      str(tmp / "so_janela.json")]), A.main()))
(tmp / "so_janela.json").write_text(json.dumps({"mina": {"acao": "arrastar", "destino": {"janela": [0.5, 0.5]}}}), encoding="utf-8")
res, _ = quieto(lambda: (sys.argv.__setitem__(slice(None), ["x", "imagem", "--pasta", str(pasta), "--config", str(tmp / "so_janela.json")]), A.main()))
check("destino por janela sem --janela => erro explicando", isinstance(res, tuple) and "--janela" in res[1], str(res))

print("4) regiao_da_janela recorta ao monitor")
A.geometria_monitor = lambda i: (0, 0, 1920, 1080)
check("janela dentro do monitor", A.regiao_da_janela((100, 50, 800, 600), 1) == (100, 50, 800, 600))
check("janela saindo da tela é recortada", A.regiao_da_janela((1800, 1000, 400, 300), 1) == (1800, 1000, 120, 80))
check("janela quase toda fora => None", A.regiao_da_janela((1915, 0, 400, 300), 1) is None)
A.geometria_monitor = lambda i: (-1920, 0, 1920, 1080)
check("monitor à esquerda (coordenadas negativas)", A.regiao_da_janela((-1500, 100, 400, 300), 1) == (420, 100, 400, 300))

print("5) Teclado: nomes, estruturas e SendInput")
check("F9 (parada) não é monitorada", A.VK_F9 not in A.VKS_TECLADO and 0x57 in A.VKS_TECLADO and 0xA0 in A.VKS_TECLADO)
check("nomes", [A.nome_tecla(v) for v in (0x57, 0x31, 0x70, 0x20, 0x25, 0x65, 0xFE)] == ["W", "1", "F1", "Espaço", "Esquerda", "Num5", "VK_FE"])
check("INPUT tem 40 bytes e KEYBDINPUT 24 (layout 64-bit do Windows)",
      ctypes.sizeof(A._Input) == 40 and ctypes.sizeof(A._KeybdInput) == 24, f"{ctypes.sizeof(A._Input)}/{ctypes.sizeof(A._KeybdInput)}")
enviados = []
class FakeU:
    def MapVirtualKeyW(self, vk, t): return {0x57: 0x11, 0x25: 0x4B}.get(vk, 0)
    def SendInput(self, n, ref, size): enviados.append((ref._obj, size))
A._api = lambda: (FakeU(), None)
A._enviar_tecla(0x57, True); A._enviar_tecla(0x57, False); A._enviar_tecla(0x25, True); A._enviar_tecla(0x99, True)
(e1, s1), (e2, _), (e3, _), (e4, _) = enviados
check("W baixo: tipo teclado, scancode 0x11, flag SCANCODE", e1.type == 1 and e1.u.ki.wScan == 0x11 and e1.u.ki.dwFlags == 0x8 and s1 == 40)
check("W cima: flag KEYUP", e2.u.ki.dwFlags == 0x8 | 0x2)
check("seta (tecla estendida): EXTENDEDKEY", e3.u.ki.dwFlags == 0x8 | 0x1)
check("sem scancode: usa o código virtual", e4.u.ki.wVk == 0x99 and e4.u.ki.dwFlags == 0)
mon = A.MonitorTeclado()
estados = {"premidas": {0x57}}
A._tecla_pressionada = lambda vk: vk in estados["premidas"]
check("apertou W", mon.varrer(1.0) == [("baixo", 0x57)])
check("segurando: sem novo evento", mon.varrer(1.1) == [])
estados["premidas"] = {0xA0}
check("soltou W e apertou Shift", sorted(mon.varrer(1.2)) == sorted([("cima", 0x57), ("baixo", 0xA0)]))

print("6) --log registra as teclas do usuário")
logp = tmp / "teclas.csv"; reg = A.Registro(str(logp))
parar = threading.Event(); seq = {"n": 0}
def tecla_seq(vk):
    if vk == 0x57:
        seq["n"] += 1
        if seq["n"] > 3: parar.set()
        return seq["n"] == 1
    return False
A._tecla_pressionada = tecla_seq
A._monitorar_teclado_no_log(parar, reg); reg.fechar()
txt = logp.read_text(encoding="utf-8")
check("linhas 'tecla W baixo' e 'tecla W cima' no CSV", ",tecla,W,,,,,baixo" in txt and ",tecla,W,,,,,cima" in txt, txt)

print("7) gravar(): teclas, janela (fração) e âncora")
sys.platform = "win32"
pos = {"x": 0, "y": 0}
A.posicao = lambda: (pos["x"], pos["y"])
A.titulo_sob_ponto = lambda x, y: "Jogo"
A.titulo_ativo = lambda: "Jogo"
A.rect_da_janela = lambda t: (100, 50, 800, 600)
# (esq, f9, x, y, teclas)
passos = [(0, 0, 50, 50, set()), (0, 0, 50, 50, {0x57}), (0, 0, 50, 50, {0x57, 0xA0}), (0, 0, 50, 50, {0xA0}),
          (1, 0, 200, 467, set()), (1, 0, 400, 400, set()), (0, 0, 570, 345, set()),
          (0, 0, 570, 345, {0x45}), (0, 1, 10, 10, {0x45})]
est = {"i": -1}
def tecla_g(vk):
    if vk == A.VK_F9:
        est["i"] = min(est["i"] + 1, len(passos) - 1)
        if est["i"] == 1: threading.Event().wait(0.35)   # dá tempo da varredura de fundo ver a âncora
        p = passos[est["i"]]; pos["x"], pos["y"] = p[2], p[3]
        return bool(p[1])
    p = passos[est["i"]]
    if vk == A.VK_ESQUERDO: return bool(p[0])
    return vk in p[4]
A._tecla_pressionada = tecla_g
pg = tmp / "pg"; pg.mkdir(); (pg / "mapa_ref.png").write_bytes(b"x")
A.capturar = lambda m, r: (np.zeros((10, 10, 3), np.uint8), 1.0, 1.0, 0, 0)
A.detectar_imagens = lambda img, p, c: [A.Hit(400, 300, 40, 40, "mapa_ref", 1.0, 0.5)]
arq = tmp / "g.json"
evs, saida = quieto(A.gravar, str(arq), str(pg), 0.85, 1, None, 0, 0, janela=None, ancora="mapa_ref", teclado=True)
d = json.loads(arq.read_text(encoding="utf-8"))
teclas = [(e["tecla"], e["estado"]) for e in d["eventos"] if e["tipo"] == "tecla"]
check("teclas gravadas em ordem (W↓ Shift↓ W↑ Shift↑ E↓) e E solta no fim",
      teclas == [("W", "baixo"), ("Shift", "baixo"), ("W", "cima"), ("Shift", "cima"), ("E", "baixo"), ("E", "cima")], str(teclas))
ts = [e["t"] for e in d["eventos"]]
check("eventos ordenados no tempo", ts == sorted(ts))
check("F9 não entra na gravação", all(e.get("vk") != A.VK_F9 for e in d["eventos"]))
arr = next(e for e in d["eventos"] if e["tipo"] == "arrasto")
check("janela detectada e salva", d["janela"]["titulo"] == "Jogo" and d["janela"]["rect"] == [100, 50, 800, 600])
check("pontos como fração da janela", (arr["fx"], arr["fy"]) == (0.125, 0.695) and (arr["fx2"], arr["fy2"]) == (0.5875, 0.49167), str(arr))
check("destino do arrasto relativo à âncora (dx=300, dy=50)", arr.get("ancora") == {"nome": "mapa_ref", "dx": 300, "dy": 50}, str(arr))
print("   gerar_regras a partir disso:")
arr["botao"] = "torre"
cg = tmp / "gerado.json"
_, saida = quieto(A.gerar_regras, [arr], str(cg), False, "Jogo")
g = json.loads(cg.read_text(encoding="utf-8"))
check("torre: destino por âncora", g["torre"]["destino"] == {"ancora": "mapa_ref", "offset": [300, 50]}, str(g))
check("mapa_ref vira regra 'ancora' (nunca clicada)", g["mapa_ref"] == {"acao": "ancora"})
arr2 = dict(arr); arr2.pop("ancora"); arr2["botao"] = "mina"
cg2 = tmp / "gerado2.json"; quieto(A.gerar_regras, [arr2], str(cg2), False, "Jogo")
g2 = json.loads(cg2.read_text(encoding="utf-8"))
check("sem âncora: destino por fração da janela + _janela", g2["mina"]["destino"] == {"janela": [0.5875, 0.49167]} and g2["_janela"] == "Jogo", str(g2))
arr3 = {k: v for k, v in arr2.items() if not k.startswith("f")}; arr3["botao"] = "x"
cg3 = tmp / "gerado3.json"; _, s3 = quieto(A.gerar_regras, [arr3], str(cg3), False, None)
check("sem janela: destino fixo + aviso", json.loads(cg3.read_text(encoding="utf-8"))["x"]["destino"] == [570, 345] and "FIXA" in s3)
est["i"] = -1
arq2 = tmp / "g2.json"
quieto(A.gravar, str(arq2), str(tmp / "sem"), 0.85, 1, None, 0, 0, teclado=False)
check("--sem-teclado: nenhuma tecla gravada", not [e for e in json.loads(arq2.read_text(encoding="utf-8"))["eventos"] if e["tipo"] == "tecla"])

print("7b) tempo depois da última ação (cauda) é gravado")
passos = [(0, 0, 50, 50, set()), (1, 0, 60, 60, set()), (0, 0, 60, 60, set()), (0, 0, 60, 60, set()), (0, 1, 60, 60, set())]
est["i"] = -1
def tecla_c(vk):
    if vk == A.VK_F9:
        est["i"] = min(est["i"] + 1, len(passos) - 1)
        if est["i"] == 3: threading.Event().wait(0.5)    # ficou 0,5 s parado depois do clique
        p = passos[est["i"]]; pos["x"], pos["y"] = p[2], p[3]
        return bool(p[1])
    p = passos[est["i"]]
    return bool(p[0]) if vk == A.VK_ESQUERDO else vk in p[4]
A._tecla_pressionada = tecla_c
arq3 = tmp / "g3.json"
quieto(A.gravar, str(arq3), str(tmp / "sem"), 0.85, 1, None, 0, 0, teclado=False)
d3 = json.loads(arq3.read_text(encoding="utf-8"))
ult = max(e["t"] for e in d3["eventos"])
check("cauda gravada (espera depois do último clique)", 0.4 <= d3["cauda"] <= 1.5, str(d3.get("cauda")))
check("duracao_total = último evento + cauda", abs(d3["duracao_total"] - (ult + d3["cauda"])) < 0.02, str(d3))

print("8) reproduzir(): loop, janela ativa, teclas, coordenadas pela janela")
rec = {"janela": {"titulo": "Jogo"}, "eventos": [
    {"t": 0.0, "tipo": "tecla", "tecla": "W", "vk": 0x57, "estado": "baixo"},
    {"t": 0.1, "tipo": "clique", "mouse": "esquerdo", "x": 999, "y": 999, "x2": 999, "y2": 999, "duracao": 0.05,
     "fx": 0.5, "fy": 0.5, "fx2": 0.5, "fy2": 0.5, "botao": "torre"},
    {"t": 0.2, "tipo": "tecla", "tecla": "W", "vk": 0x57, "estado": "cima"}]}
arqr = tmp / "r.json"; arqr.write_text(json.dumps(rec), encoding="utf-8")
log = []
A._enviar_mouse = lambda dx, dy, fl: log.append(("btn", fl))
A.mover_suave = lambda x, y, duracao=0.3, passos=18: log.append(("mv", x, y))
A._enviar_tecla = lambda vk, baixo: log.append(("key", vk, baixo))
A.janela_ativa = lambda t: True
A.achar_janela = lambda t: 1
A.focar_hwnd = lambda h: True
A.rect_da_janela = lambda t: (100, 100, 400, 200)
abortar = {"f": lambda: False}
A._abortar = lambda: abortar["f"]()
def rodar(**k):
    log.clear()
    return quieto(A.reproduzir, str(arqr), 1000.0, 0, **k)
_, s = rodar()
um = [("key", 0x57, True), ("mv", 300, 200), ("btn", A._LEFTDOWN), ("btn", A._LEFTUP), ("key", 0x57, False)]
check("uma volta: tecla, clique NO PONTO DA JANELA ATUAL (300,200), tecla", log == um, str(log))
rodar(loop=3, pausa_loop=0)
check("--loop 3 = três voltas", log == um * 3, str(len(log)))
cont = {"n": 0}
def abortar_apos():
    return sum(1 for e in log if e[0] == "btn") >= 8     # 4 cliques = 4 voltas
abortar["f"] = abortar_apos
_, s = rodar(loop=0, pausa_loop=0)
check("--loop sem número repete até abortar (F9)", sum(1 for e in log if e == ("btn", A._LEFTDOWN)) >= 4 and "interrompida" in s, s)
abortar["f"] = lambda: False
_, s = rodar(loop=None)
check("sem --loop: uma volta só", log == um)
_, s = rodar(teclas=False)
check("--sem-teclado: ignora as teclas da gravação", [e for e in log if e[0] == "key"] == [])
# --- janela ativa ---
estado_j = {"n": 0}
def ativa_depois(t):
    # só a thread principal conta: a vigia (outra thread) também consulta a janela, e no Windows
    # ela chega primeiro; o teste mede a ESPERA da reprodução, não a da vigia.
    if threading.current_thread() is not threading.main_thread():
        return False
    estado_j["n"] += 1
    return estado_j["n"] > 3
A.janela_ativa = ativa_depois
_, s = rodar()
check("janela inativa: espera, traz para frente e só então age (sequência completa)", log == um and "não está ativa" in s and "continuando" in s, s)
A.janela_ativa = lambda t: False; A.achar_janela = lambda t: None
n_abort = {"n": 0}
def abortar_na_espera():
    if threading.current_thread() is not threading.main_thread():
        return False
    n_abort["n"] += 1
    return n_abort["n"] > 3
abortar["f"] = abortar_na_espera
_, s = rodar()
check("F9 enquanto espera a janela: nenhuma ação executada", log == [] and "interrompida" in s, f"{log} {s}")
abortar["f"] = lambda: False
_, s = rodar(espera_janela=0.05)
check("janela nunca ativa: desiste após o tempo, sem agir", log == [] and "não ficou ativa" in s, s)
_, s = rodar(checar_janela=False)
check("--sem-checar-janela: age mesmo sem a janela ativa", log == um)
A.janela_ativa = lambda t: True; A.achar_janela = lambda t: 1
# tecla presa é solta se abortar no meio
abortar["f"] = lambda: any(e[0] == "mv" for e in log)
_, s = rodar()
check("abortou com tecla apertada: ela é SOLTA (não fica presa)", log[0] == ("key", 0x57, True) and log[-1] == ("key", 0x57, False), str(log))
abortar["f"] = lambda: False
rec2 = {"eventos": [{"t": 0, "tipo": "clique", "mouse": "esquerdo", "x": 10, "y": 20, "x2": 10, "y2": 20, "duracao": 0.05}]}
arqr.write_text(json.dumps(rec2), encoding="utf-8")
_, s = rodar()
check("gravação sem janela: avisa, e usa coordenadas absolutas", "Aviso" in s and ("mv", 10, 20) in log, s)
print("   cauda na reprodução")
import time as _t
def rodar1(**k):
    log.clear()
    return quieto(A.reproduzir, str(arqr), 1.0, 0, **k)
rec3 = {"janela": {"titulo": "Jogo"}, "cauda": 0.6, "eventos": [
    {"t": 0.0, "tipo": "clique", "mouse": "esquerdo", "x": 1, "y": 1, "x2": 1, "y2": 1, "duracao": 0.05, "fx": 0.5, "fy": 0.5, "fx2": 0.5, "fy2": 0.5}]}
arqr.write_text(json.dumps(rec3), encoding="utf-8")
t0 = _t.time(); _, s = rodar1(); dt = _t.time() - t0
check("uma volta dura até o fim da gravação (>= 0,6 s), não só até o último clique", dt >= 0.6 and "aguardando o fim da gravação" in s, f"{dt:.2f} {s}")
t0 = _t.time(); rodar1(loop=2, pausa_loop=0); dt2 = _t.time() - t0
check("cada volta do loop espera a cauda (2 voltas >= 1,2 s)", dt2 >= 1.2, f"{dt2:.2f}")
rec3.pop("cauda"); arqr.write_text(json.dumps(rec3), encoding="utf-8")
t0 = _t.time(); _, s = rodar1(); dt = _t.time() - t0
check("gravação antiga (sem cauda): como antes, sem espera", dt < 0.5 and "aguardando o fim" not in s, f"{dt:.2f}")
rec3["cauda"] = 30; arqr.write_text(json.dumps(rec3), encoding="utf-8")
abortar["f"] = lambda: sum(1 for e in log if e[0] == "btn") >= 2 and _t.time() - t0 > 0.3
t0 = _t.time(); _, s = rodar1(); dt = _t.time() - t0
check("F9 durante a espera final interrompe na hora", dt < 3 and "interrompida" in s, f"{dt:.2f}")
abortar["f"] = lambda: False
sys.platform = REAL_PLATFORM
print("\nTudo certo (novos recursos).")
