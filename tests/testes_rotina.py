"""Rotinas: vários scripts de um jogo, em sequência e em intervalos (lógica, com relógio falso)."""
import sys as _s0
for _f in (_s0.stdout, _s0.stderr):
    try: _f.reconfigure(encoding="utf-8", errors="replace")  # Windows (cp1252) não imprime setas
    except Exception: pass
import os, sys, tempfile, shutil, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ok = 0
def check(n, c, extra=""):
    global ok
    print(("  OK   " if c else "  FALHOU ") + n + (f"  {extra}" if extra and not c else ""))
    if not c: sys.exit(1)
    ok += 1
from autoclick import rotina as R

class Mundo:
    """Relógio falso: cada script dura `dur` segundos; dormir avança o tempo."""
    def __init__(s, dur=2.0): s.t = 0.0; s.dur = dur; s.ordem = []; s.falha = {}; s.botoes = {}; s.avisos = []; s.abortar_em = None; s.voltas = []; s.esperas = []
    def agora(s): return s.t
    def dormir(s, x): s.t += x
    def rodar(s, nome):
        s.ordem.append((round(s.t), nome)); s.t += s.dur
        return s.falha.get(nome, "ok")
    def botao(s, b, timeout, ate):
        s.esperas.append((b, timeout)); r = s.botoes.get(b, True)
        s.t += (0.5 if r else timeout); return r
    def abortou(s): return s.abortar_em is not None and s.t >= s.abortar_em
    def rotina(s, rot):
        return R.Rotina(rot, s.rodar, s.botao, s.abortou, lambda m, t: s.avisos.append((m, t)), s.agora, s.dormir,
                        lambda n: s.voltas.append(n), log=lambda m: None)
def rot(**kw):
    base = {"itens": [], "intervalos": [], "voltas": 1, "pausa_entre_scripts": 0, "pausa_volta": 0}; base.update(kw); return base
S = lambda n, v=1, **k: {"tipo": "script", "script": n, "vezes": v, **k}

print("1) Sequência")
m = Mundo(); r = m.rotina(rot(itens=[S("plantar"), S("coletar", 3), S("loja")]))
check("ordem e vezes", r.executar() == "ok" and [n for _, n in m.ordem] == ["plantar", "coletar", "coletar", "coletar", "loja"], str(m.ordem))
m = Mundo(); r = m.rotina(rot(itens=[S("a"), S("b")], voltas=3))
r.executar()
check("a lista inteira repete (3 voltas)", [n for _, n in m.ordem] == ["a", "b"] * 3 and m.voltas == [1, 2, 3], str(m.voltas))
m = Mundo(); r = m.rotina(rot(itens=[S("a")], voltas=2, pausa_volta=10))
r.executar()
check("pausa entre voltas", m.ordem[1][0] - m.ordem[0][0] == 12, str(m.ordem))
m = Mundo(); m.rotina(rot(itens=[S("a"), S("b")], pausa_entre_scripts=5)).executar()
check("pausa customizável entre scripts", m.ordem[1][0] - m.ordem[0][0] == 7)

print("2) Esperas")
m = Mundo(); m.rotina(rot(itens=[S("a"), {"tipo": "esperar", "segundos": 20}, S("b")])).executar()
check("esperar tempo fixo", m.ordem[1][0] - m.ordem[0][0] == 22, str(m.ordem))
m = Mundo(); r = m.rotina(rot(itens=[{"tipo": "esperar_botao", "botao": "npc", "timeout": 30}, S("a")]))
check("esperar botão disponível e seguir", r.executar() == "ok" and m.esperas == [("npc", 30.0)] and m.ordem[0][1] == "a")
m = Mundo(); m.botoes["npc"] = False; r = m.rotina(rot(itens=[{"tipo": "esperar_botao", "botao": "npc", "timeout": 30}, S("a")]))
check("botão não apareceu: PARA e avisa", r.executar() == "falhou" and not m.ordem and m.avisos and "npc" in m.avisos[0][1], str(m.avisos))
m = Mundo(); m.botoes["npc"] = False; r = m.rotina(rot(itens=[{"tipo": "esperar_botao", "botao": "npc", "timeout": 5, "ao_estourar": "seguir"}, S("a")]))
check("ao_estourar seguir: continua", r.executar() == "ok" and m.ordem[0][1] == "a" and not m.avisos)
m = Mundo(); m.botoes["loja_aberta"] = False; r = m.rotina(rot(itens=[S("a"), S("loja", antes_botao="loja_aberta", antes_timeout=10)]))
check("espera antes do script e para se não vier", r.executar() == "falhou" and [n for _, n in m.ordem] == ["a"] and m.avisos)
m = Mundo(); r = m.rotina(rot(itens=[S("loja", antes_botao="npc", antes_timeout=10)]))
check("antes_botao ok: roda o script", r.executar() == "ok" and m.ordem[0][1] == "loja" and m.esperas == [("npc", 10.0)])

print("3) Intervalos")
m = Mundo(dur=2); r = m.rotina(rot(itens=[S("coletar")], voltas=0, intervalos=[{"script": "loja", "a_cada": 10, "ativo": True}]))
m.abortar_em = 40; res = r.executar()
nomes = [n for _, n in m.ordem]
check("loja entra a cada ~10 s entre os coletares", res == "interrompida" and nomes.count("loja") >= 3 and nomes.count("coletar") > nomes.count("loja"), str(m.ordem))
check("intervalo nunca no meio de um script", all(m.ordem[i + 1][0] - m.ordem[i][0] >= 2 for i in range(len(m.ordem) - 1)))
check("primeira loja só depois de 10 s", [t for t, n in m.ordem if n == "loja"][0] >= 10)
m = Mundo(); r = m.rotina(rot(itens=[S("a")], intervalos=[{"script": "loja", "a_cada": 1, "ativo": False}], voltas=3))
r.executar()
check("intervalo inativo não roda", "loja" not in [n for _, n in m.ordem])
m = Mundo(); r = m.rotina(rot(itens=[{"tipo": "esperar", "segundos": 25}], voltas=1, intervalos=[{"script": "loja", "a_cada": 10, "ativo": True}]))
r.executar()
check("intervalos entram durante uma espera", [n for _, n in m.ordem].count("loja") == 2, str(m.ordem))
m = Mundo(); m.botoes["npc"] = False
r = m.rotina(rot(itens=[S("a")], voltas=0, intervalos=[{"script": "loja", "a_cada": 5, "ativo": True, "antes_botao": "npc", "antes_timeout": 3}]))
m.abortar_em = 100
check("intervalo que depende de botão e falha para tudo", r.executar() == "falhou" and m.avisos and "npc" in m.avisos[0][1])

print("4) Falha e parada")
m = Mundo(); m.falha["b"] = "falhou"; r = m.rotina(rot(itens=[S("a"), S("b"), S("c")], voltas=0))
check("script falhou: para e avisa", r.executar() == "falhou" and [n for _, n in m.ordem] == ["a", "b"] and m.avisos[0][0] == "rotina parou" and "b" in m.avisos[0][1])
m = Mundo(); m.falha["b"] = "interrompida"; r = m.rotina(rot(itens=[S("a"), S("b"), S("c")]))
check("F9 (interrompida): para sem alarme", r.executar() == "interrompida" and not m.avisos)
m = Mundo(); m.abortar_em = 3; r = m.rotina(rot(itens=[S("a"), S("b"), S("c")], voltas=0))
check("abortar entre scripts", r.executar() == "interrompida" and len(m.ordem) <= 3)
m = Mundo(); m.abortar_em = 5; r = m.rotina(rot(itens=[{"tipo": "esperar", "segundos": 600}]))
check("abortar durante uma espera", r.executar() == "interrompida" and m.t < 10)

print("5) Validação e arquivos")
check("rotina vazia", R.validar(rot()) == ["A rotina está vazia: adicione ao menos um script."])
p = R.validar(rot(itens=[S("x"), {"tipo": "esperar", "segundos": 0}, {"tipo": "esperar_botao"}, {"tipo": "xis"}, S("a", 0)],
                  intervalos=[{"script": "y", "a_cada": 0}]), {"a"})
check("acha todos os problemas", len(p) == 6 and any("não existe" in x for x in p), str(p))
check("rotina boa", R.validar(rot(itens=[S("a")], intervalos=[{"script": "a", "a_cada": 5}]), {"a"}) == [])
check("descrições", R.descrever(S("a", 2)) == "script a ×2" and "esperar 20 s" == R.descrever({"tipo": "esperar", "segundos": 20})
      and "npc" in R.descrever({"tipo": "esperar_botao", "botao": "npc", "timeout": 30}))
tmp = tempfile.mkdtemp(); rf = os.path.join(tmp, "jogos", "caramel", "rotina.json")
check("ler arquivo inexistente = padrão", R.ler(rf)["itens"] == [])
R.salvar(rf, rot(itens=[S("a")], voltas=5)); check("salvar e ler", R.ler(rf)["voltas"] == 5 and R.ler(rf)["itens"][0]["script"] == "a")
os.makedirs(os.path.join(tmp, "jogos", "caramel", "gravacoes")); open(os.path.join(tmp, "jogos", "caramel", "gravacoes", "loja.json"), "w").write("{}")
open(os.path.join(tmp, "jogos", "caramel", "gravacao.json"), "w").write("{}")
sc = R.listar_scripts(rf)
check("lista scripts (+ gravacao.json como principal)", set(sc) == {"principal", "loja"}, str(sc))
check("caminhos dos scripts", R.caminho_do_script(rf, "loja").endswith("gravacoes/loja.json".replace("/", os.sep)) and R.caminho_do_script(rf, "principal").endswith("gravacao.json"))
check("nome válido", R.nome_valido("Minha Coleta!/..") == "Minha_Coleta.." .replace("..", "") or R.nome_valido("Minha Coleta!/..") == "Minha_Coleta")
shutil.rmtree(tmp, ignore_errors=True)

print("6) CLI e reprodução (estático)")
cli = open(os.path.join(os.path.dirname(__file__), "..", "autoclick", "cli.py"), encoding="utf-8").read()
check("modo rotina existe", '"rotina"' in cli and "rotina_exec" in cli)
rep = open(os.path.join(os.path.dirname(__file__), "..", "autoclick", "reproducao.py"), encoding="utf-8").read()
check("reproduzir devolve o resultado", ") -> str:" in rep and 'return "falhou"' in rep and 'return "ok"' in rep and "som: bool = True" in rep)

print("Janela do próprio Autoclick nunca é a janela do jogo")
from autoclick import windows as _WJ
check("título do Autoclick é reconhecido", _WJ.janela_propria("Autoclick Inteligente 0.13.3") and not _WJ.janela_propria("Roblox") and not _WJ.janela_propria(None))
print("Prévia (simular)")
_rot = {"itens": [{"tipo": "script", "script": "coleta", "vezes": 3}, {"tipo": "script", "script": "loja", "vezes": 1}],
        "intervalos": [], "pausa_entre_scripts": 0, "pausa_volta": 0, "voltas": 1}
_ev = R.simular(_rot, {"coleta": 25, "loja": 33})
_ord = [x for _, x in _ev if x.startswith("▶")]
check("simular respeita a ordem da lista (coleta ×3, depois loja)", [o.split()[1] for o in _ord] == ["coleta", "coleta", "coleta", "loja"], str(_ord))
check("simular soma as durações", [round(t) for t, x in _ev if x.startswith("▶")] == [0, 25, 50, 75])
_rot2 = dict(_rot, intervalos=[{"script": "loja", "a_cada": 60, "ativo": True}], pausa_entre_scripts=0.5)
_ev2 = R.simular(_rot2, {"coleta": 25, "loja": 33})
check("intervalo vencido entra no próximo ponto livre (entre itens)", any("intervalo" in x for _, x in _ev2), str(_ev2))
print("Fluxo da plantação: coleta, espera 300 s (×3) e loja DURANTE a 3ª espera")
E = lambda s, **k: {"tipo": "esperar", "segundos": s, **k}
fluxo = rot(itens=[S("coleta"), E(300), S("coleta"), E(300), S("coleta"), E(300, durante=["loja"])], voltas=2)
m = Mundo(); m.dur = 25
check("fluxo termina bem", m.rotina(fluxo).executar() == "ok")
ordem = [(t, n) for t, n in m.ordem]
check("ordem: coleta, coleta, coleta, loja, e recomeça", [n for _, n in ordem] == ["coleta", "coleta", "coleta", "loja"] * 2, str(ordem))
check("cada espera de 300 s conta do FIM do script (coletas a cada 325 s)", [t for t, n in ordem[:3]] == [0, 325, 650], str(ordem))
check("a loja roda logo depois da 3ª coleta", ordem[3] == (675, "loja"), str(ordem))
check("a 3ª espera completa os 300 s mesmo com a loja dentro (próximo ciclo em 650+25+300=975)", ordem[4] == (975, "coleta"), str(ordem))
m = Mundo(); m.dur = 400
m.rotina(rot(itens=[S("coleta"), E(300, durante=["loja"]), S("coleta")])).executar()
check("loja mais longa que a espera: termina por inteiro e a próxima coleta vem logo depois", [n for _, n in m.ordem] == ["coleta", "loja", "coleta"] and m.ordem[2][0] >= m.ordem[1][0] + 400, str(m.ordem))
check("validar acusa script inexistente na espera", any("loja" in x for x in R.validar(rot(itens=[E(10, durante=["loja"])]), {"coleta"})))
check("descrever mostra o que roda na espera", "enquanto espera: loja" in R.descrever(E(300, durante=["loja"])))
_ev = R.simular(fluxo, {"coleta": 25, "loja": 33}, 3600)
check("a prévia mostra a loja durante a espera", any("durante a espera" in x for _, x in _ev), str(_ev[:8]))
print(f"\n{ok} verificações passaram (rotinas).")
