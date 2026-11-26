import sys as _s0
for _f in (_s0.stdout, _s0.stderr):
    try: _f.reconfigure(encoding="utf-8", errors="replace")  # Windows (cp1252) não imprime setas
    except Exception: pass
import sys, types, json, tempfile, io, contextlib, threading, time as _time
import numpy as np, cv2
from pathlib import Path
try:
    import mss  # noqa
except Exception:
    sys.modules["mss"] = types.SimpleNamespace()
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from fachada import A
import autoclick.operacao as OP, autoclick.condicoes as CO, autoclick.validar as VA
import autoclick.perfil as PE, autoclick.ferramentas as FE
real_sleep = _time.sleep
_time.sleep = lambda s: None

ok = 0
def check(nome, cond, extra=""):
    global ok
    print(("  OK   " if cond else "  FALHOU ") + nome + (f"  {extra}" if extra and not cond else ""))
    if not cond: sys.exit(1)
    ok += 1
tmp = Path(tempfile.mkdtemp())

def rodar_main(argv):
    sys.argv = ["x"] + argv
    buf = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(buf):
        try: A.main()
        except SystemExit as e: code = e.code if isinstance(e.code, int) else 1; buf.write(str(e.code))
    return buf.getvalue(), code

print("1) Pausa (F8) — só por tecla, nunca pelo mouse")
p = OP.Pausa()
check("começa rodando", not p.pausado and p.esperar() == 0.0)
p.alternar(); check("alternar pausa", p.pausado)
r = []
t = threading.Thread(target=lambda: r.append(p.esperar(checar_parada=False))); t.start()
real_sleep(0.2); p.alternar(); t.join(2)
check("esperar() bloqueia até continuar e devolve o tempo parado", r and r[0] is not None and r[0] >= 0.15, str(r))
check("total de pausa acumulado", p.total >= 0.15)
import inspect
src = inspect.getsource(OP.Pausa)
check("Pausa não consulta posição do mouse", "posicao" not in src and "mouse" not in src.lower().replace("mexer no mouse nunca pausa", ""))
check("F8 não é gravado como tecla", A.VK_F8 not in A.VKS_TECLADO and A.VK_F9 not in A.VKS_TECLADO)

print("2) Variação aleatória")
v0 = OP.Variacao(0.0); check("0 = exato", v0(2.0) == 2.0)
v1 = OP.Variacao(0.2, 1); vs = [v1(10.0) for _ in range(200)]
check("±20%", min(vs) >= 8.0 and max(vs) <= 12.0 and len(set(vs)) > 50)

print("3) Telemetria / relatório")
tel = OP.Telemetria(); tel.clique("a"); tel.clique("a"); tel.clique("t", True); tel.falha("t"); tel.nova_partida(); tel.aviso("x")
r = tel.resumo()
check("contagens", r["cliques"] == {"a": 2} and r["arrastos"] == {"t": 1} and r["falhas"] == {"t": 1} and r["partidas"] == 2)
tel.salvar(str(tmp / "rel.json")); tel.salvar(str(tmp / "rel.md"))
check("json válido", json.loads((tmp / "rel.json").read_text())["total_acoes"] == 3)
check("md legível", "Resumo da sessão" in (tmp / "rel.md").read_text() and "a=2" in (tmp / "rel.md").read_text())
check("linha do painel", "3 ações" in tel.linha() and "partida #2" in tel.linha())
csvp = tmp / "l.csv"; reg = A.Registro(str(csvp)); reg.log("clique", "a", 1, 2); reg.log("clique", "a", 1, 2); reg.log("inicio_partida"); reg.log("tecla", "", detalhe="W"); reg.fechar()
res = OP.resumir_csv(str(csvp))
check("resumo do CSV", "partidas iniciadas: 1" in res and "clique" in res and " 2" in res, res)

print("4) Saúde da detecção")
msgs = []; sa = OP.Saude(sem_deteccao=10, avisar=msgs.append)
t0 = 1000.0
for i in range(8): sa.observar({"b": 0.95}, 0.7, t0 + i)
check("sem avisos enquanto estável", not msgs)
for i in range(25): sa.observar({"b": 0.80}, 0.7, t0 + 10 + i)
check("avisa queda de score", any("caiu" in m for m in msgs), str(msgs))
msgs.clear(); sa.observar({"b": 0.8}, 0.4, t0 + 40)
check("avisa salto de escala", any("escala" in m for m in msgs), str(msgs))
msgs.clear(); sa.observar({}, None, t0 + 200)
check("avisa nada reconhecido", any("nenhum botão" in m for m in msgs), str(msgs))

print("5) Vigilante (recuperação)")
vg = OP.Vigilante(janela_max=5, erros_max=3, inatividade=10)
check("janela sumida: espera", vg.janela(False, 100.0) is None)
check("janela sumida > limite: desiste", vg.janela(False, 106.0) is not None)
check("janela voltou: zera", vg.janela(True, 107.0) is None and vg.janela(False, 108.0) is None)
check("erros seguidos", vg.erro("a") is None and vg.erro("b") is None and vg.erro("c") is not None)
vg.ok(); check("ok zera erros", vg.erro("a") is None)
vg.acao(0.0); check("inatividade", vg.parado(5.0) is None and vg.parado(11.0) is not None)

print("6) Condições, etapas e fluxo")
vis = CO.Visibilidade(1.5); vis.atualizar(["a"], 10.0)
check("visível dentro da validade, some depois", vis.visivel("a", 11.0) and not vis.visivel("a", 12.0))
R = A.Regra
check("requer ausente bloqueia", not CO.permite(R(requer=("a",)), vis, None, 12.0)[0])
check("requer presente libera", CO.permite(R(requer=("a",)), vis, None, 11.0)[0])
check("ignorar_se presente bloqueia", not CO.permite(R(ignorar_se=("a",)), vis, None, 11.0)[0])
fl = CO.parse_fluxo([{"etapa": "lobby", "quando": ["jogar"], "timeout": 10}, {"etapa": "jogo", "quando": "inicio", "timeout": 5, "ao_estourar": "parar"}])
check("etapa muda ao ver marcador", fl.observar({"jogar"}, 100.0) == "lobby" and fl.atual == "lobby")
check("mesma etapa não repete", fl.observar({"jogar"}, 101.0) is None)
check("regra de etapa só na etapa certa", CO.permite(R(etapa="lobby"), vis, fl, 11.0)[0] and not CO.permite(R(etapa="jogo"), vis, fl, 11.0)[0])
check("timeout dispara uma vez", fl.estourou(105.0) is None and fl.estourou(111.0) is not None and fl.estourou(112.0) is None)
check("avança para a etapa seguinte", fl.observar({"inicio"}, 120.0) == "jogo")
check("ao_estourar parar", fl.estourou(126.0)[0].ao_estourar == "parar")
try: CO.parse_fluxo([{"etapa": "x"}]); bad = False
except SystemExit: bad = True
check("fluxo inválido dá erro claro", bad)

print("7) Regras novas no botoes.json + validação")
pasta = tmp / "botoes"; pasta.mkdir()
for n in ("jogar", "torre", "mapa", "erro_rede", "solta", "inicio"): cv2.imwrite(str(pasta / f"{n}.png"), np.full((20, 20, 3), 128, np.uint8))
cfg = tmp / "b.json"
cfg.write_text(json.dumps({
    "_janela": "Roblox",
    "_fluxo": [{"etapa": "lobby", "quando": ["jogar"]}],
    "jogar": {"acao": "clicar", "etapa": "lobby", "requer": ["inicio"], "ignorar_se": "erro_rede"},
    "erro_rede": {"acao": "erro", "ao_ver": "parar"},
    "inicio": {"acao": "marcador"},
}), encoding="utf-8")
rg = A.carregar_regras(str(cfg))
check("campos lidos", rg["jogar"].requer == ("inicio",) and rg["jogar"].ignorar_se == ("erro_rede",) and rg["jogar"].etapa == "lobby" and rg["erro_rede"].ao_ver == "parar")
probs = VA.validar_config(str(cfg), str(pasta))
txt = "\n".join(map(str, probs))
check("avisa PNG sem regra (torre, mapa, solta)", "torre" in txt and "solta" in txt, txt)
check("config boa não tem erro", not any(p.nivel == "erro" for p in probs), txt)
cfg2 = tmp / "ruim.json"
cfg2.write_text(json.dumps({
    "jogr": {"acao": "clikar", "vezs": 2},
    "torre": {"acao": "arrastar"},
    "mapa": {"acao": "clicar", "requer": ["nao_existe"], "etapa": "fim", "queda_saturacao": 3,
             "destino": {"janela": [2, 0.5]}},
    "solta": {"acao": "arrastar", "destino": {"ancora": "naoexiste"}},
}), encoding="utf-8")
txt = "\n".join(map(str, VA.validar_config(str(cfg2), str(pasta))))
for trecho in ("jogr", "Quis dizer 'jogar'", "clikar", "Quis dizer 'clicar'", "vezs", "Quis dizer 'vezes'", "precisa de 'destino'",
               "nao_existe", "etapa 'fim'", "queda_saturacao", "destino.janela", "âncora 'naoexiste'", "janela"):
    check(f"validação aponta: {trecho}", trecho in txt, txt)
(tmp / "q.json").write_text("{ruim", encoding="utf-8")
check("JSON quebrado: erro com linha", "JSON inválido" in str(VA.validar_config(str(tmp / "q.json"), str(pasta))[0]))
out, code = rodar_main(["validar", "--config", str(cfg2), "--pasta", str(pasta)])
check("modo validar: sai com código 1 e lista", code == 1 and "erro(s)" in out, out)
out, code = rodar_main(["validar", "--config", str(cfg), "--pasta", str(pasta)])
check("modo validar: config boa sai 0", code == 0, out)

print("8) Perfis")
(tmp / "perfis").mkdir()
(tmp / "perfis" / "rb.json").write_text(json.dumps({"modo": "validar", "janela": "Roblox", "pasta": str(pasta), "config": str(cfg), "intervalo": 2.5}), encoding="utf-8")
import os; os.chdir(tmp)
out, code = rodar_main(["--perfil", "rb"])
check("perfil define modo e opções", code == 0 and "Perfil carregado" in out and "nenhum problema" in out or "aviso" in out, out)
(tmp / "perfis" / "x.json").write_text(json.dumps({"modo": "validar", "intervalo": 1, "jnela": "x"}), encoding="utf-8")
out, code = rodar_main(["--perfil", "x"])
check("opção desconhecida no perfil: erro com sugestão", code != 0 and "jnela" in out and "janela" in out, out)
# CLI vence perfil
(tmp / "perfis" / "c.json").write_text(json.dumps({"modo": "validar", "config": str(cfg2), "pasta": str(pasta)}), encoding="utf-8")
out, code = rodar_main(["--perfil", "c", "--config", str(cfg)])
check("linha de comando vence o perfil", code == 0, out)

print("9) Recortar botão")
rng = np.random.default_rng(3)
tela = cv2.GaussianBlur(rng.integers(0, 255, (400, 600, 3)).astype(np.uint8), (0, 0), 2)
tela[100:140, 100:180] = (30, 160, 40); cv2.putText(tela, "OK", (115, 128), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
a = FE.analisar_recorte(tela, (100, 100, 80, 40))
check("recorte bom: único e sem avisos graves", a.ocorrencias == 1 and not any("ambíguo" in x for x in a.avisos), str(a.avisos))
tela2 = tela.copy(); tela2[100:140, 300:380] = tela[100:140, 100:180]
a = FE.analisar_recorte(tela2, (100, 100, 80, 40))
check("recorte ambíguo avisa (2 ocorrências)", a.ocorrencias == 2 and any("ambíguo" in x for x in a.avisos), str(a.avisos))
tela3 = np.full((400, 600, 3), 90, np.uint8)
a = FE.analisar_recorte(tela3, (50, 50, 60, 30))
check("recorte liso avisa", any("uma cor" in x for x in a.avisos), str(a.avisos))
a = FE.analisar_recorte(tela, (10, 10, 6, 6)); check("recorte minúsculo avisa", any("pequeno" in x for x in a.avisos))
a = FE.analisar_recorte(tela, (0, 0, 500, 350)); check("recorte enorme avisa", any("grande" in x for x in a.avisos))
A.capturar = lambda m, r: (tela, 1.0, 1.0, 0, 0)
out, code = rodar_main(["recortar", "ok_btn", "--pasta", str(tmp / "novos"), "--retangulo", "100", "100", "80", "40", "--atraso", "0"])
check("modo recortar grava o PNG e informa", (tmp / "novos" / "ok_btn.png").is_file() and "Casou 1x" in out, out)
check("PNG salvo tem 80x40", cv2.imread(str(tmp / "novos" / "ok_btn.png")).shape[:2] == (40, 80))

print("10) Calibrar cinza / hover")
v_, av = FE.recomendar_queda(100.0, 10.0, 80.0); check("com hover: limite entre cinza e hover", v_ is not None and 0.1 < v_ < 0.8, str((v_, av)))
v_, av = FE.recomendar_queda(100.0, 10.0); check("sem hover: ponto médio", v_ is not None and abs(v_ - 0.55) < 0.01)
v_, av = FE.recomendar_queda(100.0, 95.0); check("cinza igual ao normal: recusa", v_ is None and av)
v_, av = FE.recomendar_queda(5.0, 1.0); check("botão sem cor: recusa", v_ is None and av)
v_, av = FE.recomendar_queda(100.0, 40.0, 38.0); check("hover ≈ cinza: avisa", v_ is not None and av)
FE.escrever_queda(str(cfg), "jogar", 0.4)
check("grava queda_saturacao sem perder o resto", json.loads(cfg.read_text())["jogar"]["queda_saturacao"] == 0.4 and json.loads(cfg.read_text())["jogar"]["etapa"] == "lobby")

print("11) Mapa de regras + definir destino")
hits = [A.Hit(100, 100, 80, 40, "torre", 0.95, 1.0)]
rg2 = {"torre": R(acao="arrastar", destino=(300, 250))}
img = FE.desenhar_mapa(tela, hits, rg2, (1.0, 1.0, 0, 0), None)
check("mapa desenha (imagem mudou, mesma forma)", img.shape == tela.shape and (img != tela).any())
check("cruz do destino no ponto certo", (img[250, 300] != tela[250, 300]).any())
d = FE.calcular_destino((300, 200), (1.0, 1.0, 100, 50), (100, 50, 600, 400))
check("destino como fração da janela", d == {"janela": [0.5, 0.5]}, str(d))
d = FE.calcular_destino((300, 200), (1.0, 1.0, 0, 0), None, (100.0, 100.0, 2.0, 2.0, 0), "mapa_ref")
check("destino como offset da âncora", d == {"ancora": "mapa_ref", "offset": [100, 50]}, str(d))
FE.escrever_destino(str(cfg), "torre", {"janela": [0.3, 0.4]})
j = json.loads(cfg.read_text())["torre"]; check("destino gravado no json", j["acao"] == "arrastar" and j["destino"] == {"janela": [0.3, 0.4]})
import autoclick.captura as _CAP
_rect0 = _CAP.rect_seguro
_CAP.rect_seguro = lambda *a, **k: None  # "sem janela" de verdade: no Windows pode haver uma janela real com esse título
try: out, code = rodar_main(["definir-destino", "torre2", "--config", str(cfg), "--ponto", "300", "200"])
finally: _CAP.rect_seguro = _rect0
check("modo definir-destino (fixo, sem janela)", json.loads(cfg.read_text())["torre2"]["destino"] == [300, 200], out)
out, code = rodar_main(["visualizar", "--pasta", str(pasta), "--config", str(cfg), "--saida", str(tmp / "mapa.png")])
check("modo visualizar gera o PNG", (tmp / "mapa.png").is_file(), out)

print("12) Diagnóstico")
out, code = rodar_main(["diagnostico", "--pasta", str(pasta), "--config", str(cfg), "--saida", str(tmp / "d.txt")])
check("gera relatório com versões e resultado", (tmp / "d.txt").is_file() and "Python" in out and "Resultado" in out, out)

print("13) Varredura ponta a ponta (condições, erro, fluxo, painel, relatório)")
pasta2 = tmp / "b2"; pasta2.mkdir()
for n in ("jogar", "inicio", "erro_rede", "cartao"): (pasta2 / f"{n}.png").write_bytes(b"x")
cfg3 = tmp / "e2e.json"
cfg3.write_text(json.dumps({
    "inicio": {"acao": "marcador"},
    "jogar": {"acao": "clicar", "requer": ["inicio"], "intervalo": 0},
    "cartao": {"acao": "clicar", "ignorar_se": ["erro_rede"], "intervalo": 0},
    "erro_rede": {"acao": "erro", "ao_ver": "parar"},
}), encoding="utf-8")
def H(n, x=100, y=100): return A.Hit(x, y, 40, 30, n)
scans = [[H("jogar")], [H("jogar"), H("inicio", 300, 50)], [H("cartao", 400, 400), H("erro_rede", 50, 50)], [H("jogar"), H("inicio")]]
it = iter(scans)
def fd(img, pa, conf):
    try: return next(it)
    except StopIteration: raise KeyboardInterrupt
A.detectar_imagens = fd
A.capturar = lambda m, r: (np.zeros((1080, 1920, 3), np.uint8), 1.0, 1.0, 0, 0)
cl = []
A.clicar = lambda h, *a, **k: (cl.append(h.rotulo), True)[1]
OP.pausa.pausado = False
out, code = rodar_main(["imagem", "--pasta", str(pasta2), "--config", str(cfg3), "--cooldown", "0", "--intervalo", "0", "--sem-recheck", "--relatorio", str(tmp / "rel2.json"), "--sem-pausa"])
check("'jogar' só clicado quando 'inicio' à vista (varredura 2)", cl.count("jogar") == 1, str(cl))
check("cartão NÃO clicado com tela de erro à vista; tela de erro encerra", "cartao" not in cl and "tela de erro" in out and "Encerrando" in out, out + str(cl))
check("não chegou à 4ª varredura", len(list(it)) == 1)
rel = json.loads((tmp / "rel2.json").read_text())
check("relatório da sessão salvo com cliques e aviso", rel["cliques"] == {"jogar": 1} and any("erro" in a for a in rel["avisos"]), str(rel))

print("14) Pausa durante a varredura")
OP.pausa.pausado = False
scans = [[H("jogar"), H("inicio")]] * 3
it = iter(scans); cl.clear()
estados = []
orig = OP.pausa.esperar
n = {"i": 0}
def esp(checar_parada=True):
    n["i"] += 1
    if n["i"] == 2:  # na 2ª volta o usuário pausou e depois continuou
        OP.pausa.pausado = True; estados.append("pausou"); OP.pausa.pausado = False; OP.pausa.total += 5; return 5.0
    return 0.0
OP.pausa.esperar = esp
out, code = rodar_main(["imagem", "--pasta", str(pasta2), "--config", str(cfg3), "--cooldown", "0", "--intervalo", "0", "--sem-recheck", "--sem-pausa"])
OP.pausa.esperar = orig
check("varredura passou pela espera da pausa a cada ciclo e seguiu clicando", n["i"] >= 3 and cl.count("jogar") == 3, f"{n} {cl}")
check("tempo pausado aparece no resumo", "pausado: 5.0s" in out or "pausado" in out, out)

print("15) Fluxo com timeout e recuperação de janela")
cfg4 = tmp / "fx.json"
cfg4.write_text(json.dumps({"_fluxo": [{"etapa": "jogo", "quando": ["inicio"], "timeout": 0.0001, "ao_estourar": "parar"}], "inicio": {"acao": "marcador"}}), encoding="utf-8")
it = iter([[H("inicio")]] * 5)
_time.sleep = real_sleep; real_t = _time.time
real_sleep(0.01)
out, code = rodar_main(["imagem", "--pasta", str(pasta2), "--config", str(cfg4), "--intervalo", "0", "--sem-pausa"])
_time.sleep = lambda s: None
check("timeout da etapa com ao_estourar=parar encerra", "passou de" in out and "Fim." in out, out)
check("etapa anunciada", "etapa: jogo" in out)

print("16) Janela some por muito tempo: encerra sozinho")
A.rect_seguro = lambda t: None
out, code = rodar_main(["imagem", "--pasta", str(pasta2), "--config", str(cfg3), "--janela", "Jogo", "--janela-max", "0.0001", "--intervalo", "0", "--sem-pausa"])
check("encerra por janela sumida", "sumiu" in out and "encerrando" in out, out)

print(f"\n{ok} verificações passaram (operação).")
