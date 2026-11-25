"""Jogos do Roblox: camadas geral + jogo, migração, detecção por logs, estatísticas, bandeja, sons."""
import os, sys, json, tempfile, shutil, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ok = 0
def check(n, c, extra=""):
    global ok
    print(("  OK   " if c else "  FALHOU ") + n + (f"  {extra}" if extra and not c else ""))
    if not c: sys.exit(1)
    ok += 1

tmp = tempfile.mkdtemp(); os.chdir(tmp)
from autoclick import jogos as J

print("1) Cadastro")
check("só o geral no começo", [j.slug for j in J.listar()] == ["geral"])
a = J.criar("Blox Fruits", ids=["2753915549"])
b = J.criar("Blox Fruits")
check("slug sem acento e único", a.slug == "blox-fruits" and b.slug == "blox-fruits-2", f"{a.slug} {b.slug}")
check("pasta botoes criada", os.path.isdir("jogos/blox-fruits/botoes"))
check("lista: geral primeiro", [j.slug for j in J.listar()][0] == "geral")
check("ler devolve ids", J.ler("blox-fruits").ids == ["2753915549"])
check("jogo inexistente = None", J.ler("nada") is None)
check("arquivos do jogo", J.arquivos_do("blox-fruits")["config"].replace("\\", "/") == "jogos/blox-fruits/botoes.json")
check("arquivos do geral", J.arquivos_do("geral") == {"gravacao": "gravacao.json", "rotina": "rotina.json"})
check("não apaga o geral", J.apagar("geral") is False and J.apagar("blox-fruits-2") and not os.path.exists("jogos/blox-fruits-2"))
check("slugificar acento", J.slugificar("Pôr do Sol!") == "por-do-sol")

print("2) Migração de perfis")
os.makedirs("perfis")
json.dump({"modo": "imagem", "janela": "Roblox", "intervalo": 1.0, "variacao": 0.15}, open("perfis/roblox.json", "w"))
json.dump({"modo": "auto", "intervalo": 2.5, "cooldown": 7}, open("perfis/Pet Sim.json", "w"))
mov = J.migrar_perfis()
check("dois perfis movidos", sorted(mov) == ["Pet Sim", "roblox"], str(mov))
check("perfis/ ficou vazia", not os.listdir("perfis"))
check("roblox virou geral com opções", J.ler("geral").opcoes.get("variacao") == 0.15)
check("outro virou jogo", J.ler("pet-sim").opcoes == {"modo_auto": "auto", "intervalo": 2.5, "cooldown": 7})
check("perfil continua achável pelo terminal", J.perfil_em_jogos("roblox") is not None and J.perfil_em_jogos("Pet Sim") is not None)
check("migrar de novo não faz nada", J.migrar_perfis() == [])
from autoclick.perfil import localizar_perfil
check("--perfil acha em jogos/", str(localizar_perfil("roblox")).replace("\\", "/") == "jogos/geral/perfil.json")

print("3) Motor: geral + jogo")
import cv2, numpy as np
from autoclick import deteccao as D, regras as R
os.makedirs("botoes")
img = np.zeros((40, 60, 3), np.uint8); img[:, :30] = (200, 50, 50)
cv2.imwrite("botoes/desconectado.png", img)
cv2.imwrite("botoes/ok.png", img)
cv2.imwrite("jogos/blox-fruits/botoes/ok.png", np.full((30, 50, 3), 99, np.uint8))
cv2.imwrite("jogos/blox-fruits/botoes/so_do_jogo.png", img)
json.dump({"desconectado": {"acao": "clicar"}, "ok": {"acao": "clicar", "tentativas": 5}}, open("botoes.json", "w"))
json.dump({"ok": {"acao": "clicar", "tentativas": 2}, "especial": {"acao": "clicar"}}, open("jogos/blox-fruits/botoes.json", "w"))
for v in ("AUTOCLICK_GERAL_PASTA", "AUTOCLICK_GERAL_CONFIG"): os.environ.pop(v, None)
check("sem camada: só a pasta", [n for n, _ in D.carregar_templates("jogos/blox-fruits/botoes")] == ["ok", "so_do_jogo"])
os.environ["AUTOCLICK_GERAL_PASTA"] = "botoes"; os.environ["AUTOCLICK_GERAL_CONFIG"] = "botoes.json"
tp = dict(D.carregar_templates("jogos/blox-fruits/botoes"))
check("soma geral + jogo", sorted(tp) == ["desconectado", "ok", "so_do_jogo"], str(sorted(tp)))
check("jogo vence o geral (mesmo nome)", tp["ok"].shape[:2] == (30, 50))
rg = R.carregar_regras("jogos/blox-fruits/botoes.json")
check("regras somadas", sorted(rg) == ["desconectado", "especial", "ok"], str(sorted(rg)))
check("regra do jogo vence", rg["ok"].tentativas == 2 and R.carregar_regras("botoes.json")["ok"].tentativas == 5)
check("geral sozinho não duplica", sorted(R.carregar_regras("botoes.json")) == ["desconectado", "ok"])
for v in ("AUTOCLICK_GERAL_PASTA", "AUTOCLICK_GERAL_CONFIG"): os.environ.pop(v)

print("4) Logs do Roblox")
logs = os.path.join(tmp, "logs"); os.makedirs(logs)
open(f"{logs}/a.log", "w").write("2026-11-01 info\n[FLog::Output] placeId:111111 universeId:222\n"
                                  "noise " * 3000 + "\n[game] Joining placeId:2753915549 token=abc123\n")
slug, i = J.detectar_por_logs(J.listar(), __import__("pathlib").Path(logs))
check("reconhece pelo id (o último vence)", slug == "blox-fruits" and i == "2753915549", f"{slug} {i}")
open(f"{logs}/b.log", "w").write("placeId:999000\n"); os.utime(f"{logs}/b.log", (time.time() + 5, time.time() + 5))
slug, i = J.detectar_por_logs(J.listar(), __import__("pathlib").Path(logs))
check("id desconhecido: devolve o id, sem jogo", slug is None and i == "999000")
check("sem pasta de logs: nada", J.detectar_por_logs(J.listar(), __import__("pathlib").Path(tmp) / "nao") == (None, ""))
os.environ["AUTOCLICK_ROBLOX_LOGS"] = logs
txt = J.coletar_pistas()
check("pistas: curtas e sem ruído", len(txt.splitlines()) < 12 and "noise" not in txt and "999000" in txt, txt)
check("pistas escondem token", "abc123" not in J.coletar_pistas())
os.environ.pop("AUTOCLICK_ROBLOX_LOGS")
check("ids_no_texto em ordem", J.ids_no_texto("placeId:1234 foo universeId=5678 /games/9999") == ["1234", "5678", "9999"])

print("4b) Place + universe e nome")
from pathlib import Path as P
lg = P(tmp) / "logs2"; lg.mkdir()
(lg / "j.log").write_text("[FLog::Output] ! Joining game 'x' place 120919334665902 at 10.0.0.1\n"
    "Report game_join_loadtime: placeid:120919334665902, join_time:5.2, universeid:9553887523, referral\n")
check("ids recentes: place e universe", J.ids_recentes(lg) == ["120919334665902", "9553887523"], str(J.ids_recentes(lg)))
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        corpo = {"/u/120919334665902": {"universeId": 9553887523},
                 "/g/9553887523": {"data": [{"name": "Caramel"}]}}.get(self.path)
        self.send_response(200 if corpo else 404); self.end_headers()
        if corpo: self.wfile.write(json.dumps(corpo).encode())
    def log_message(self, *a): pass
srv = HTTPServer(("127.0.0.1", 0), H); pt = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
J.API_UNIVERSO = f"http://127.0.0.1:{pt}/u/{{}}"; J.API_JOGOS = f"http://127.0.0.1:{pt}/g/{{}}"
check("nome pelo place id", J.nome_do_jogo(["120919334665902", "9553887523"]) == "Caramel")
check("nome só pelo universe id", J.nome_do_jogo(["9553887523"]) == "Caramel")
check("id desconhecido: None", J.nome_do_jogo(["1111111"]) is None)
srv.shutdown()
check("sem internet: None, sem erro", J.nome_do_jogo(["120919334665902"], timeout=1) is None)

print("5) Estatísticas")
sess = [{"jogo": "blox-fruits", "duracao_seg": 3600, "pausado_seg": 0, "partidas": 30, "total_acoes": 100, "cliques": {"ok": 60, "x": 40}},
        {"jogo": "blox-fruits", "duracao_seg": 3600, "pausado_seg": 1800, "partidas": 15, "total_acoes": 50, "cliques": {"ok": 50}},
        {"duracao_seg": 600, "partidas": 0, "total_acoes": 3}]
es = {r["jogo"]: r for r in J.estatisticas(sess)}
check("tempo ativo sem pausa", es["blox-fruits"]["segundos"] == 5400)
check("voltas por hora", es["blox-fruits"]["voltas_hora"] == 30.0, str(es["blox-fruits"]))
check("segundos por volta", es["blox-fruits"]["seg_por_volta"] == 120.0)
check("botões somados", es["blox-fruits"]["botoes"] == {"ok": 110, "x": 40})
check("sessão sem jogo = geral", "geral" in es and es["geral"]["voltas_hora"] == 0.0)
csv = J.csv_estatisticas(sess, {"blox-fruits": "Blox Fruits"})
check("CSV com cabeçalho e vírgula decimal", csv.startswith("jogo;sessoes") and "Blox Fruits;2;5400;45;30,0;120,0;150" in csv, csv)
os.environ["AUTOCLICK_JOGO"] = "blox-fruits"
check("slug ativo pelo ambiente", J.slug_ativo() == "blox-fruits")
os.environ.pop("AUTOCLICK_JOGO")
check("sem ambiente = geral", J.slug_ativo() == "geral")

print("6) Bandeja")
from autoclick.interface.bandeja import itens_do_menu, CMD_JOGO, CMD_SOM, CMD_PAUSA
m = itens_do_menu(False, False, True, [("geral", "Roblox (geral)"), ("blox-fruits", "Blox Fruits")], "blox-fruits")
txt = [t for _, t, _ in m]
check("menu tem pausa, reproduzir, som e jogos", "Pausar o loop" in txt and "Reproduzir a gravação" in txt and "Som ao concluir a volta" in txt and "Jogo: Blox Fruits" in txt, str(txt))
check("jogo atual marcado, som marcado", [x for x in m if x[1] == "Jogo: Blox Fruits"][0][2] and [x for x in m if x[0] == CMD_SOM][0][2])
m2 = itens_do_menu(True, True, False, [], "")
check("rodando/pausado muda os textos", [t for _, t, _ in m2 if "Parar a reprodução" in t] and [t for _, t, _ in m2 if "Continuar" in t])
check("ids de jogos não colidem", len({c for c, _, _ in m if c}) == len([c for c, _, _ in m if c]) and all(c >= CMD_JOGO for c, t, _ in m if t.startswith("Jogo")))

print("7) Sons")
from autoclick import som as S
import wave, io
tam = {}
for t in S.TIPOS:
    w = S.gerar_wav(0.2, t)
    with wave.open(io.BytesIO(w)) as f: tam[t] = f.getnframes()
    check(f"estilo {t} gera WAV válido", tam[t] > 1000)
check("estilos diferentes", len(set(tam.values())) == len(tam), str(tam))
a = S.gerar_wav(0.05); b = S.gerar_wav(0.5)
def pico(w):
    with wave.open(io.BytesIO(w)) as f: d = f.readframes(f.getnframes())
    import struct; return max(abs(x) for x in struct.unpack("<%dh" % (len(d) // 2), d))
check("volume muda a amplitude", pico(b) > pico(a) * 5)
x = S.Som(True); tocou = []
x.saida = lambda wv: tocou.append(wv)
x.configurar("marcimba-inexistente", 50); x.tocar()
check("estilo inválido cai no sino", len(tocou) == 1)
x.configurar("gota", 0); x.tocar()
check("volume 0 = silêncio", pico(tocou[-1]) == 0)
open("meu.wav", "wb").write(S.gerar_wav(0.3, "marimba"))
x.configurar("arquivo", 50, os.path.abspath("meu.wav")); x.tocar()
check("usa o .wav do usuário", tocou[-1] == open("meu.wav", "rb").read())
x.configurar("arquivo", 50, "nao-existe.wav"); x.tocar()
check("arquivo sumido cai no sino", len(tocou) == 4 and tocou[-1][:4] == b"RIFF")
open("lixo.wav", "wb").write(b"nao e wav"); x.configurar("arquivo", 50, "lixo.wav"); x.tocar()
check("arquivo inválido cai no sino", tocou[-1][:4] == b"RIFF" and len(tocou[-1]) > 1000)
from autoclick import operacao as O
from autoclick.som import som as SOM
O.Controle(None, None, "reproduzir").executar("somcfg:gota|55|C%3A/meu%20som.wav")
check("comando somcfg chega ao som do processo", (SOM.tipo, SOM.volume, SOM.arquivo) == ("gota", 55.0, "C:/meu som.wav"), str((SOM.tipo, SOM.volume, SOM.arquivo)))
O.Controle(None, None, "reproduzir").executar("somcfg:lixo")
check("somcfg inválido é ignorado", SOM.tipo == "gota")

print("8) Detectar pela tela")
from autoclick import ferramentas as F, captura as CAP
tela = np.zeros((200, 300, 3), np.uint8); logo = np.random.RandomState(1).randint(0, 255, (30, 40, 3)).astype(np.uint8)
tela[50:80, 100:140] = logo
cv2.imwrite("jogos/blox-fruits/botoes/logo_bf.png", logo)
j = J.ler("blox-fruits"); j.assinatura = ["logo_bf"]; J.salvar(j)
os.environ["AUTOCLICK_GERAL_PASTA"] = "botoes"
CAP.capturar = lambda m, r=None: (tela, 1.0, 0, 0, 0)
F.m_captura.capturar = CAP.capturar
check("reconhece o jogo pela assinatura", F.detectar_jogo(1, None, 0.85, "det.txt") == "blox-fruits" and open("det.txt").read() == "blox-fruits")
tela[:] = 0
check("nada na tela: vazio", F.detectar_jogo(1, None, 0.85, "det.txt") is None and open("det.txt").read() == "")

print(f"\n{ok} verificações passaram (jogos).")
shutil.rmtree(tmp, ignore_errors=True)
