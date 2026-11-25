import sys, types, json, tempfile, io, contextlib, time, threading
from pathlib import Path
import numpy as np
try:
    import mss  # noqa
except Exception:
    sys.modules["mss"] = types.SimpleNamespace()
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from fachada import A
REAL_SLEEP = time.sleep
time.sleep = lambda s: REAL_SLEEP(0.001)
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

print("1) json: auto_detect")
def carrega(c):
    (tmp / "r.json").write_text(json.dumps(c), encoding="utf-8"); return A.carregar_regras(str(tmp / "r.json"))
r = carrega({"a": {"acao": "clicar", "auto_detect": True}, "b": {"acao": "clicar", "auto_detect": False}, "c": {"acao": "clicar"}})
check("true / false / ausente(None)", (r["a"].auto_detect, r["b"].auto_detect, r["c"].auto_detect) == (True, False, None))
res, _ = quieto(carrega, {"a": {"acao": "clicar", "auto_detect": "sim"}})
check("valor inválido => erro claro", isinstance(res, tuple) and "auto_detect" in res[1])

print("2) modos de varredura: auto_detect=false desliga o clique")
pasta = tmp / "botoes"; pasta.mkdir()
for n in ("maximo", "novamente"): (pasta / f"{n}.png").write_bytes(b"x")
cfg = tmp / "c.json"; cfg.write_text(json.dumps({"maximo": {"acao": "clicar", "auto_detect": True}, "novamente": {"acao": "clicar", "auto_detect": False}}), encoding="utf-8")
A.capturar = lambda m, r: (np.zeros((200, 300, 3), np.uint8), 1.0, 1.0, 0, 0)
sc = iter([[A.Hit(10, 10, 20, 20, "maximo"), A.Hit(50, 50, 20, 20, "novamente"), A.Hit(90, 90, 20, 20, "sem_regra")]])
def det(i, p, c):
    try: return next(sc)
    except StopIteration: raise KeyboardInterrupt
A.detectar_imagens = det
cl = []
A.clicar = lambda h, *a, **k: cl.append(h.rotulo) or True
sys.argv = ["x", "imagem", "--pasta", str(pasta), "--config", str(cfg), "--cooldown", "0", "--intervalo", "0", "--sem-recheck"]
quieto(A.main)
check("clica maximo e o botão sem regra; ignora o false", sorted(cl) == ["maximo", "sem_regra"], str(cl))

print("3) Vigia: intervalo, vezes, janela inativa, limite contínuo")
cl.clear()
regras = {"maximo": A.Regra(acao="clicar", auto_detect=True), "novamente": A.Regra(acao="clicar", auto_detect=True, vezes=1),
          "padrao": A.Regra(acao="clicar"), "torre": A.Regra(acao="arrastar", destino=(1, 1), auto_detect=True)}
v = A.VigiaBotoes(regras, str(pasta), 0.85, 1, None, None, False, threading.Lock(), cooldown=0.05, graca=0.2)
check("só entram botões 'clicar' com auto_detect true", v.nomes == ["maximo", "novamente"], str(v.nomes))
A.detectar_imagens = lambda i, p, c: [A.Hit(10, 10, 20, 20, "maximo"), A.Hit(50, 50, 20, 20, "novamente"), A.Hit(1, 1, 5, 5, "padrao")]
A.ainda_no_lugar = lambda *a, **k: True
v.varrer_uma_vez()
check("clicou maximo e novamente; ignorou o que não é auto_detect", sorted(cl) == ["maximo", "novamente"], str(cl))
check("fica 'ocupado' enquanto há botão à vista", v.ocupado())
v.varrer_uma_vez()
check("2ª varredura dentro do intervalo: não clica de novo", len(cl) == 2)
REAL_SLEEP(0.08); v.varrer_uma_vez()
check("depois do intervalo clica de novo (maximo), 'novamente' respeita vezes=1", sorted(cl) == ["maximo", "maximo", "novamente"], str(cl))
A.detectar_imagens = lambda i, p, c: []
v.varrer_uma_vez()
check("botão sumiu: não está mais ocupado", not v.ocupado())
cl.clear()
A.detectar_imagens = lambda i, p, c: [A.Hit(10, 10, 20, 20, "maximo")]
A.janela_ativa = lambda t: False
v2 = A.VigiaBotoes(regras, str(pasta), 0.85, 1, None, "Jogo", True, threading.Lock(), cooldown=0.0)
v2.varrer_uma_vez()
check("jogo fora de foco: não clica e não segura a reprodução", cl == [] and not v2.ocupado())
A.janela_ativa = lambda t: True; A.rect_da_janela = lambda t: (0, 0, 300, 200); A.geometria_monitor = lambda i: (0, 0, 1920, 1080)
v2.varrer_uma_vez()
check("jogo em foco: clica", cl == ["maximo"])
v3 = A.VigiaBotoes(regras, str(pasta), 0.85, 1, None, None, False, threading.Lock(), cooldown=0.0, max_continuo=0.05)
A.detectar_imagens = lambda i, p, c: [A.Hit(10, 10, 20, 20, "maximo")]
v3.varrer_uma_vez(); REAL_SLEEP(0.08)
_, s = quieto(v3.varrer_uma_vez)
check("botão preso à vista além do limite: suspende a vigia", "pausando a vigia" in s and not v3.ocupado())

print("4) reproduzir(): clica nos auto_detect e só então segue a gravação")
sys.platform = "win32"
ordem = []
cfgr = tmp / "r2.json"; cfgr.write_text(json.dumps({"maximo": {"acao": "clicar", "auto_detect": True}, "outro": {"acao": "clicar"}}), encoding="utf-8")
rec = {"eventos": [{"t": 0.0, "tipo": "clique", "mouse": "esquerdo", "x": 5, "y": 6, "x2": 5, "y2": 6, "duracao": 0.05}]}
arq = tmp / "g.json"; arq.write_text(json.dumps(rec), encoding="utf-8")
vis = {"n": 0}
def det_seq(i, p, c):
    vis["n"] += 1
    return [A.Hit(10, 10, 20, 20, "maximo")] if vis["n"] <= 4 else []
A.detectar_imagens = det_seq
A.clicar = lambda h, *a, **k: ordem.append("auto") or True
vis_no_replay = []
A._enviar_mouse = lambda dx, dy, fl: (ordem.append("replay"), vis_no_replay.append(vis["n"])) if fl == A._LEFTDOWN else None
A.mover_suave = lambda *a, **k: None
A._abortar = lambda: False
_, s = quieto(A.reproduzir, str(arq), 1.0, 0, config=str(cfgr), pasta=str(pasta), checar_janela=False,
              intervalo_vigia=0.01, graca=0.15)
check("clicou no botão antes do clique da gravação", ordem == ["auto", "replay"], str(ordem))
check("a gravação ESPEROU o botão sumir (só rodou depois da 5ª varredura, a vazia)", vis_no_replay and vis_no_replay[0] >= 5, str(vis_no_replay))
check("avisou o auto_detect e contou os cliques", "auto_detect ligado para: maximo" in s and "clique(s) automático(s)" in s, s)
ordem.clear(); vis["n"] = 0
_, s = quieto(A.reproduzir, str(arq), 1.0, 0, config=str(cfgr), pasta=str(pasta), checar_janela=False, auto_detect=False)
check("auto_detect=False (--sem-auto-detect): só a gravação", ordem == ["replay"], str(ordem))
ordem.clear()
cfg_sem = tmp / "r3.json"; cfg_sem.write_text(json.dumps({"x": {"acao": "clicar"}}), encoding="utf-8")
_, s = quieto(A.reproduzir, str(arq), 1.0, 0, config=str(cfg_sem), pasta=str(pasta), checar_janela=False)
check("sem nenhum auto_detect no json: nada muda e a vigia nem liga", ordem == ["replay"] and "auto_detect ligado" not in s)
# F9 enquanto espera o botão sumir
ordem.clear(); vis["n"] = -10**6
A.detectar_imagens = lambda i, p, c: [A.Hit(10, 10, 20, 20, "maximo")]
cont = {"n": 0}
def abortar():
    cont["n"] += 1; return cont["n"] > 40
A._abortar = abortar
_, s = quieto(A.reproduzir, str(arq), 1.0, 0, config=str(cfgr), pasta=str(pasta), checar_janela=False, intervalo_vigia=0.01, graca=0.5)
check("F9 com o botão à vista: interrompe sem executar a gravação", "replay" not in ordem and "interrompida" in s, f"{ordem} {s}")


sys.platform = REAL_PLATFORM
print("5) json: escolha / grupo / reiniciar_loop")
r = carrega({"carta": {"acao": "clicar", "auto_detect": True, "escolha": "ultimo"},
             "c2": {"acao": "clicar", "grupo": "trial"}, "jn": {"acao": "clicar", "reiniciar_loop": True}})
check("escolha lida; grupo sem escolha => 'primeiro'; reiniciar_loop", r["carta"].escolha == "ultimo" and r["c2"].escolha == "primeiro" and r["c2"].grupo == "trial" and r["jn"].reiniciar_loop)
for nome, c in [("escolha inválida", {"a": {"acao": "clicar", "escolha": "melhor"}}), ("reiniciar_loop inválido", {"a": {"acao": "clicar", "reiniciar_loop": 1}})]:
    res, _ = quieto(carrega, c)
    check(f"erro claro: {nome}", isinstance(res, tuple) and "r.json" in res[1])

print("6) Escolhedor: 1 de 3 cartas, uma vez por aparição")
cartas = [A.Hit(40, 210, 26, 26, "carta"), A.Hit(260, 208, 26, 26, "carta"), A.Hit(480, 210, 26, 26, "carta")]
rg = {"carta": A.Regra(acao="clicar", auto_detect=True, escolha="primeiro")}
e = A.Escolhedor(rearme=2.0, retentar_apos=8.0)
out = e.filtrar(cartas, rg, 100.0)
check("3 cartas à vista => libera só UMA (a mais à esquerda)", len(out) == 1 and out[0].x == 40, str(out))
check("sem ter clicado (cancelado) continua liberando uma", len(e.filtrar(cartas, rg, 100.5)) == 1)
e.travar(out[0], rg, 101.0)
check("depois do clique: nenhuma carta liberada enquanto elas estão lá", e.filtrar(cartas, rg, 102.0) == [] and e.filtrar(cartas, rg, 105.0) == [])
check("sumiram por menos que o rearme: ainda travado", e.filtrar([], rg, 106.0) == [] and e.filtrar(cartas, rg, 106.5) == [])
e.filtrar([], rg, 110.0); e.filtrar([], rg, 112.5)
check("sumiram por >= 2s: nova aparição libera uma de novo", len(e.filtrar(cartas, rg, 113.0)) == 1)
e2 = A.Escolhedor(); e2.travar(cartas[0], rg, 200.0)
check("clique perdido (continuam à vista depois de 8s): tenta de novo", e2.filtrar(cartas, rg, 201.0) == [] and len(e2.filtrar(cartas, rg, 209.0)) == 1)
rg_u = {"carta": A.Regra(acao="clicar", escolha="ultimo")}
check("escolha 'ultimo' = a mais à direita", A.Escolhedor().filtrar(cartas, rg_u, 0)[0].x == 480)
rg_a = {"carta": A.Regra(acao="clicar", escolha="aleatorio")}
vistos = {A.Escolhedor().filtrar(cartas, rg_a, 0)[0].x for _ in range(60)}
check("escolha 'aleatorio' varia entre as cartas", len(vistos) == 3, str(vistos))
mix = [A.Hit(1, 1, 5, 5, "carta_a"), A.Hit(9, 1, 5, 5, "carta_b"), A.Hit(50, 50, 5, 5, "maximo")]
rg_g = {"carta_a": A.Regra(acao="clicar", escolha="primeiro", grupo="trial"), "carta_b": A.Regra(acao="clicar", escolha="primeiro", grupo="trial"), "maximo": A.Regra(acao="clicar")}
out = A.Escolhedor().filtrar(mix, rg_g, 0)
check("PNGs diferentes no mesmo grupo disputam UMA escolha; botão fora do grupo passa direto", sorted(h.rotulo for h in out) == ["carta_a", "maximo"], str(out))

print("7) main: 3 cartas na tela => 1 clique só; reiniciar_loop zera a partida")
cfgc = tmp / "cartas.json"
cfgc.write_text(json.dumps({"carta": {"acao": "clicar", "auto_detect": True, "escolha": "primeiro", "offset": [55, 0]},
                            "maximo": {"acao": "clicar", "vezes": 1}, "jn": {"acao": "clicar", "reiniciar_loop": True}}), encoding="utf-8")
for n in ("carta", "jn"): (pasta / f"{n}.png").write_bytes(b"x")
JN = A.Hit(300, 300, 40, 20, "jn")
sc = iter([cartas + [A.Hit(5, 5, 10, 10, "maximo")], cartas + [A.Hit(5, 5, 10, 10, "maximo")], [JN], [A.Hit(5, 5, 10, 10, "maximo")]])
def det2(i, p, c):
    try: return next(sc)
    except StopIteration: raise KeyboardInterrupt
A.detectar_imagens = det2
cl = []
A.clicar = lambda h, *a, **k: cl.append((h.rotulo, h.x, k.get("arrastar_para"))) or True
sys.argv = ["x", "imagem", "--pasta", str(pasta), "--config", str(cfgc), "--cooldown", "0", "--intervalo", "0", "--sem-recheck"]
_, s = quieto(A.main)
check("só UMA carta clicada, a da esquerda", [c for c in cl if c[0] == "carta"] == [("carta", 40, None)], str(cl))
check("jn clicado e ciclo reiniciado (maximo 'vezes 1' liberado de novo na nova partida)",
      "ciclo reiniciado" in s and [c[0] for c in cl].count("maximo") == 2, f"{cl}\n{s}")

print("8) reproduzir(): Jogar Novamente reinicia a gravação e NÃO é clicado de novo")
sys.platform = "win32"
cfgj = tmp / "jn.json"; cfgj.write_text(json.dumps({"jn": {"acao": "clicar", "auto_detect": True, "reiniciar_loop": True}}), encoding="utf-8")
rec = {"eventos": [
    {"t": 0.0, "tipo": "clique", "mouse": "esquerdo", "x": 10, "y": 1, "x2": 10, "y2": 1, "duracao": 0.05, "botao": "jn"},
    {"t": 0.2, "tipo": "clique", "mouse": "esquerdo", "x": 20, "y": 1, "x2": 20, "y2": 1, "duracao": 0.05, "botao": "A"},
    {"t": 0.6, "tipo": "clique", "mouse": "esquerdo", "x": 30, "y": 1, "x2": 30, "y2": 1, "duracao": 0.05, "botao": "B"}]}
arq = tmp / "g2.json"; arq.write_text(json.dumps(rec), encoding="utf-8")
ordem = []; t_ini = {"t": None}
def det3(i, p, c):
    if t_ini["t"] is None: t_ini["t"] = time.time()
    d = time.time() - t_ini["t"]
    return [A.Hit(5, 5, 20, 20, "jn")] if 0.35 < d < 0.40 else []
A.detectar_imagens = det3
A.clicar = lambda h, *a, **k: ordem.append("auto:" + h.rotulo) or True
A.mover_suave = lambda x, y, *a, **k: ordem.append(f"mv{x}")
A._enviar_mouse = lambda dx, dy, fl: None
A._abortar = lambda: False
_, s = quieto(A.reproduzir, str(arq), 1.0, 0, loop=2, pausa_loop=0, config=str(cfgj), pasta=str(pasta), checar_janela=False, intervalo_vigia=0.01, graca=0.05)
vistos = [o for o in ordem]
check("1ª volta: jn, A; vigia clica jn; 2ª volta recomeça SEM o jn gravado: A, B",
      vistos == ["mv10", "mv20", "auto:jn", "mv20", "mv30"], str(vistos) + "\n" + s)
check("avisou o reinício e o clique pulado", "recomeçando a gravação do início" in s and "pulado" in s, s)
sys.platform = REAL_PLATFORM
print("\nauto_detect / escolha / reiniciar OK.")
