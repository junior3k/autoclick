import sys, types, json, tempfile, io, contextlib, time
from pathlib import Path

pos = {"x": 0, "y": 0}
try:
    import mss  # noqa
except Exception:
    sys.modules["mss"] = types.SimpleNamespace()
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from fachada import A
time.sleep = lambda s: None
sys.platform = "win32"   # só para passar a checagem; as chamadas do Windows são simuladas

def check(nome, cond, extra=""):
    print(("  OK   " if cond else "  FALHOU ") + nome + (f"  {extra}" if extra and not cond else ""))
    if not cond: sys.exit(1)

# ---- linha do tempo simulada: (esq, dir, f9, x, y) a cada iteração ----
passos = [
    (0, 0, 0, 50, 50),
    (1, 0, 0, 200, 467),   # aperta esquerdo em (200,467)
    (1, 0, 0, 600, 500),   # arrastando
    (0, 0, 0, 980, 540),   # solta em (980,540)  => arrasto
    (1, 0, 0, 300, 300),   # aperta
    (0, 0, 0, 301, 300),   # solta quase no mesmo lugar => clique
    (0, 1, 0, 700, 700),   # aperta DIREITO
    (0, 0, 0, 700, 700),   # solta => clique direito
    (0, 0, 1, 10, 10),     # F9
]
estado = {"i": -1, "atual": passos[0]}
def fake_tecla(vk):
    if vk == A.VK_F9:                      # 1ª consulta de cada iteração: avança o "tempo"
        estado["i"] = min(estado["i"] + 1, len(passos) - 1)
        estado["atual"] = passos[estado["i"]]
        pos["x"], pos["y"] = estado["atual"][3], estado["atual"][4]
        return bool(estado["atual"][2])
    if vk == A.VK_ESQUERDO: return bool(estado["atual"][0])
    if vk == A.VK_DIREITO: return bool(estado["atual"][1])
    return False
A._tecla_pressionada = fake_tecla
A.posicao = lambda: (pos["x"], pos["y"])
A.titulo_sob_ponto = lambda x, y: None
A.titulo_ativo = lambda: None
A.rect_da_janela = lambda t: None

print("A) gravar()")
tmp = Path(tempfile.mkdtemp()); arq = tmp / "g.json"
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    evs = A.gravar(str(arq), str(tmp / "sem_pasta"), 0.85, 1, None, 0, 0)
d = json.loads(arq.read_text(encoding="utf-8"))
check("3 eventos gravados", len(evs) == 3 and len(d["eventos"]) == 3, str(evs))
e1, e2, e3 = d["eventos"]
check("1º: arrasto esquerdo (200,467) -> (980,540)", (e1["tipo"], e1["mouse"], e1["x"], e1["y"], e1["x2"], e1["y2"]) == ("arrasto", "esquerdo", 200, 467, 980, 540))
check("2º: clique esquerdo em (300,300)", (e2["tipo"], e2["mouse"], e2["x"], e2["y"]) == ("clique", "esquerdo", 300, 300))
check("3º: clique direito em (700,700)", (e3["tipo"], e3["mouse"]) == ("clique", "direito"))
check("tempos crescentes", e1["t"] <= e2["t"] <= e3["t"])
check("imprimiu os eventos com coordenadas", "arrasto esquerdo (200,467) -> (980,540)" in buf.getvalue())
check("aviso de pasta sem imagens", "sem nome de botão" in buf.getvalue())

print("B) gravar -> gerar_regras (arrasto sobre a 'torre')")
evs2 = [dict(e1, botao="torre")]
cfg = tmp / "botoes.json"
with contextlib.redirect_stdout(io.StringIO()): A.gerar_regras(evs2, str(cfg), False)
check("destino do arrasto virou regra", json.loads(cfg.read_text(encoding="utf-8"))["torre"]["destino"] == [980, 540])

print("C) reproduzir()")
chamadas = []
A._enviar_mouse = lambda dx, dy, flags: chamadas.append(("btn", flags))
A.mover_suave = lambda x, y, duracao=0.3, passos=18: chamadas.append(("mv", x, y))
A._abortar = lambda: False
with contextlib.redirect_stdout(io.StringIO()):
    A.reproduzir(str(arq), 1000.0, 0)   # velocidade alta: não espera os tempos reais
D, U, RD, RU = A._LEFTDOWN, A._LEFTUP, A._RIGHTDOWN, A._RIGHTUP
esperado = [("mv", 200, 467), ("btn", D), ("mv", 980, 540), ("btn", U),
            ("mv", 300, 300), ("btn", D), ("btn", U),
            ("mv", 700, 700), ("btn", RD), ("btn", RU)]
check("sequência exata (ir, apertar, arrastar, soltar; direito usa botão direito)", chamadas == esperado, str(chamadas))

print("D) reproduzir() para quando aborta")
chamadas.clear(); A._abortar = lambda: True
with contextlib.redirect_stdout(io.StringIO()) as b:
    A.reproduzir(str(arq), 1000.0, 0)
check("abortou antes de qualquer ação", chamadas == [])
print("E) som a cada volta (liga/desliga no meio da execução)")
from autoclick.som import som as _som
_som.saida = lambda b: None; _som.tocados = 0; _som.definir(True)
A._abortar = lambda: False
voltas = {"n": 0}
_toca = _som.tocar
def _espia(forcar=False):
    voltas["n"] += 1
    r = _toca(forcar)
    if voltas["n"] == 3:
        _som.definir(False)   # desligado enquanto o loop roda: a volta 4 em diante fica muda
    return r
_som.tocar = _espia
with contextlib.redirect_stdout(io.StringIO()):
    A.reproduzir(str(arq), 1000.0, 0, 5, 0.0)
check("5 voltas concluídas, som tocou só nas 3 primeiras", voltas["n"] == 5 and _som.tocados == 3, f"{voltas} {_som.tocados}")
_som.tocar = _toca; _som.definir(False)
# ---- 0.10.1: F11 não é gravado, cronômetro e resumo (só conferência) ----
import autoclick.windows as _W, autoclick.gravacao as _G, autoclick.operacao as _O
_W.definir_teclas("F8", "F9", "F10", "F11")
check("F11 fora das teclas gravadas", 0x7A not in _W.VKS_TECLADO and 0x7B in _W.VKS_TECLADO)
_W.definir_teclas("F8", "F9", "F10", "F6")
check("tecla de reproduzir trocada sai da lista", 0x75 not in _W.VKS_TECLADO and 0x7A in _W.VKS_TECLADO)
_os.environ["AUTOCLICK_TECLAS"] = "pausa=F8;parar=F9;gravar=F10;reproduzir=F11"; _W.teclas_do_ambiente()
check("ambiente define reproduzir", 0x7A not in _W.VKS_TECLADO)
_os.environ.pop("AUTOCLICK_TECLAS"); _W.definir_teclas()
ev = [{"t": 1.0, "tipo": "tecla", "tecla": "E", "estado": "baixo"}, {"t": 1.1, "tipo": "tecla", "tecla": "E", "estado": "cima"},
      {"t": 5.5, "tipo": "tecla", "tecla": "E", "estado": "baixo"}, {"t": 6, "tipo": "clique"}]
r = _G.resumo_teclas(ev, 65.0)
check("resumo: total, mouse e teclas", "01:05.000" in r[0] and "1 clique" in r[0] and "2 tecla" in r[0], r)
check("resumo: tempos por tecla", "E: 2×" in r[1] and "00:01.000" in r[1] and "00:05.500" in r[1], r)
tl = _O.Telemetria(); check("sem gravação: info vazia", tl.gravacao_info() is None)
tl.gravacao_iniciar(123.0)
for i in range(50): tl.gravacao_evento(f"l{i}")
gi = tl.gravacao_info()
check("cronômetro: t0 e últimas 40 linhas", gi and gi["t0"] == 123.0 and gi["total"] == 50 and len(gi["recentes"]) == 40 and gi["recentes"][-1] == "l49")
# ---- 0.10.2: progresso da volta (inclui a espera final) ----
from autoclick import operacao as _OP2
arq2 = Path(tempfile.mkdtemp()) / "p.json"
arq2.write_text(json.dumps({"versao": 2, "cauda": 30, "eventos": [{"t": 0.0, "tipo": "clique", "mouse": "esquerdo", "x": 1, "y": 1, "x2": 1, "y2": 1, "duracao": 0.05, "botao": None}, {"t": 60.0, "tipo": "clique", "mouse": "esquerdo", "x": 2, "y": 2, "x2": 2, "y2": 2, "duracao": 0.05, "botao": None}]}))
vistos = []
_toca2 = _som.tocar
def _espia2(forcar=False):
    vistos.append(_OP2.tel().progresso_info())
    return _toca2(forcar)
_som.tocar = _espia2; _som.definir(True)
with contextlib.redirect_stdout(io.StringIO()):
    A.reproduzir(str(arq2), 1000.0, 0, 2, 0.0)
_som.tocar = _toca2; _som.definir(False)
check("progresso presente em cada volta", len(vistos) == 2 and all(v for v in vistos), vistos)
check("total = (último + espera final) / velocidade", abs(vistos[0]["total"] - 90.0 / 1000.0) < 1e-6 and vistos[1]["volta"] == 2 and vistos[0]["voltas"] == 2, vistos)
check("progresso some ao terminar", _OP2.tel().progresso_info() is None)
# ---- 0.12.0: sons por tipo de ação nos pontos certos ----
from autoclick import gravacao as _GR, reproducao as _RP
_evs = []
_orig_ev = _GR.m_som.tocar_evento
_GR.m_som.tocar_evento = lambda e, forcar=False: _evs.append(e) or False
estado["i"] = -1
with contextlib.redirect_stdout(io.StringIO()):
    A.gravar(str(tmp / "g2.json"), str(tmp / "sem_pasta"), 0.85, 1, None, 0, 2)
check("gravar: tique, tique, início, fim (nessa ordem)", _evs == ["tique", "tique", "gravar_inicio", "gravar_fim"], _evs)
_evs.clear()
with contextlib.redirect_stdout(io.StringIO()):
    A.reproduzir(str(arq2), 1000.0, 2, 1, 0.0)
check("reproduzir: tique, tique, início, fim", _evs == ["tique", "tique", "repro_inicio", "repro_fim"], _evs)
_evs.clear()
with contextlib.redirect_stdout(io.StringIO()):
    _RP.reproduzir(str(arq2), 1000.0, 2, loop=1, som=False)
check("reproduzir com som=False (rotinas) fica mudo", _evs == [], _evs)
_GR.m_som.tocar_evento = _orig_ev

# ---- 0.11.0: atalhos com combinações ----
W2 = _W
check("analisa combinação", W2.analisar_atalho("ctrl + f11") == (("CTRL",), 0x7A) and W2.analisar_atalho("ctrl+f11") == (("CTRL",), 0x7A))
check("ordem canônica dos modificadores", W2.normalizar_atalho("shift+alt+ctrl+g") == "CTRL+ALT+SHIFT+G")
check("teclas extras", W2.normalizar_atalho("pageup") == "PAGEUP" and W2.normalizar_atalho("num5") == "NUM5" and W2.normalizar_atalho("insert") == "INSERT")
check("inválidos", all(W2.normalizar_atalho(x) is None for x in ("", "ctrl+", "ctrl+ctrl+F1", "foo+F1", "Enter", "F25", "ctrl", "a+b")))
down = set()
est = lambda vk: vk in down
a = W2.analisar_atalho("ctrl+F11")
down = {0x7A}; check("combinação sem Ctrl não dispara", not W2.atalho_pressionado(a, est))
down = {0x7A, 0x11}; check("Ctrl+F11 dispara", W2.atalho_pressionado(a, est))
down = {0x7A, 0x11, 0x10}; check("Ctrl+Shift+F11 não dispara Ctrl+F11", not W2.atalho_pressionado(a, est))
down = {0x7A, 0x10}; check("F11 simples ignora modificadores", W2.atalho_pressionado(W2.analisar_atalho("F11"), est))
down = {0x7B, 0x11, 0x12}; check("lê combinação apertada", W2.ler_atalho(est) == "CTRL+ALT+F12")
down = {0x11}; check("modificador sozinho não vale", W2.ler_atalho(est) is None)
down = {0x41, 0x7B}; check("ignora o que já estava apertado", W2.ler_atalho(est, {0x41}) == "F12")
W2.definir_teclas("Ctrl+F8", "Alt+F9", "F10", "Shift+F11")
check("definir_teclas com combinações", W2.NOME_PAUSA == "CTRL+F8" and W2.NOME_PARAR == "ALT+F9" and W2._atalhos["reproduzir"] == (("SHIFT",), 0x7A))
check("tecla principal dos atalhos fora da gravação", 0x77 not in W2.VKS_TECLADO and 0x78 not in W2.VKS_TECLADO and 0x7A not in W2.VKS_TECLADO)
down = {0x78, 0x12}; _tp = W2.tecla_pressionada; W2.tecla_pressionada = est
check("parar por Alt+F9 (abortar)", W2.pressionada("parar") and not W2.pressionada("pausa"))
W2.tecla_pressionada = _tp; W2.definir_teclas()
from autoclick.interface import dados as _D
check("teclas_validas aceita combinação", _D.teclas_validas("Ctrl+F8", "F9", "F10", "F11") is None)
check("duplicadas (mesmo normalizado)", "diferentes" in (_D.teclas_validas("ctrl+f8", "CTRL+F8", "F10", "F11") or ""))
check("inválida", _D.teclas_validas("lixo", "F9", "F10") is not None)
check("aviso para letra sozinha", _D.aviso_atalho("W") and not _D.aviso_atalho("Ctrl+W") and not _D.aviso_atalho("F8"))
print("\nTudo certo.")
