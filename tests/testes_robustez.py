import sys, types, json, tempfile, os, threading, time, http.server
import numpy as np
from pathlib import Path
try:
    import mss  # noqa
except Exception:
    sys.modules["mss"] = types.SimpleNamespace()
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import autoclick.robustez as RB, autoclick.windows as W, autoclick.regras as R, autoclick.validar as VA
import autoclick.operacao as OP
from autoclick.tipos import Hit

ok = 0
def check(nome, cond, extra=""):
    global ok
    print(("  OK   " if cond else "  FALHOU ") + nome + (f"  {extra}" if extra and not cond else ""))
    if not cond: sys.exit(1)
    ok += 1
tmp = Path(tempfile.mkdtemp()); os.chdir(tmp)

print("1) Tela parada")
v = RB.VigiaTela(60, "avisar", 1, None, None)
a = np.zeros((10, 10, 3), np.uint8); b = a.copy()
desde, avisou, disp = v.verificar(None, a, 0.0, None, False)
check("primeiro quadro: nada", (desde, avisou, disp) == (None, False, False))
desde, avisou, disp = v.verificar(a, b, 10.0, None, False)
check("igual: começa a contar", desde == 10.0 and not disp)
desde, avisou, disp = v.verificar(a, b, 50.0, desde, avisou)
check("antes do limite: não dispara", not disp)
desde, avisou, disp = v.verificar(a, b, 71.0, desde, avisou)
check("passou do limite: dispara", disp and avisou)
desde, avisou, disp = v.verificar(a, b, 100.0, desde, avisou)
check("não repete o alerta", not disp)
c = a + 80
desde, avisou, disp = v.verificar(a, c, 110.0, desde, avisou)
check("tela mudou: zera", desde is None and not avisou)
check("tamanhos diferentes: zera", v.verificar(a, np.zeros((5, 5, 3), np.uint8), 1.0, 1.0, True) == (None, False, False))
check("reduzir pega amostra", RB.reduzir(np.zeros((480, 640, 4), np.uint8)).shape == (20, 27, 3))

print("2) Reconexão com limite")
L = RB.LimiteReconexao(3, 100)
check("3 tentativas ok", all(L.registrar(t) for t in (0, 10, 20)))
check("4ª em 100s: desiste", not L.registrar(30))
check("depois da janela: volta a permitir", RB.LimiteReconexao(1, 10).registrar(0) and True)
L2 = RB.LimiteReconexao(1, 10); L2.registrar(0)
check("janela expira", L2.registrar(50))

print("3) Regras: reconectar")
cfg = tmp / "b.json"
cfg.write_text(json.dumps({"desconectado": {"acao": "erro", "ao_ver": "reconectar", "reconectar_com": "reconectar"},
                           "reconectar": {"acao": "clicar"}}), encoding="utf-8")
rg = R.carregar_regras(str(cfg))
check("campo lido", rg["desconectado"].ao_ver == "reconectar" and rg["desconectado"].reconectar_com == "reconectar")
pasta = tmp / "botoes"; pasta.mkdir()
for n in ("desconectado", "reconectar"):
    import cv2; cv2.imwrite(str(pasta / f"{n}.png"), np.random.randint(0, 255, (30, 60, 3), np.uint8))
probs = VA.validar_config(str(cfg), str(pasta), None)
check("validar aceita", not [p for p in probs if p.nivel == "erro"], str(probs))
cfg.write_text(json.dumps({"desconectado": {"acao": "erro", "ao_ver": "reconectar", "reconectar_com": "reconectr"},
                           "reconectar": {"acao": "clicar"}}), encoding="utf-8")
probs = VA.validar_config(str(cfg), str(pasta), None)
check("validar acusa botão inexistente com sugestão", any("reconectar_com" in p.msg and "reconectar" in p.msg for p in probs), str(probs))

print("4) Histórico e alerta")
os.environ["AUTOCLICK_HISTORICO"] = str(tmp / "h" / "s.jsonl")
OP.nova_telemetria().clique("maximo")
RB.registrar_sessao("reproduzir", "concluído")
RB.registrar_sessao("imagem", "erro: X")
h = RB.ler_historico()
check("duas sessões", len(h) == 2 and h[0]["modo"] == "reproduzir" and h[1]["motivo"] == "erro: X")
check("traz ações", h[0]["total_acoes"] == 1 and "fim" in h[0])
os.environ["AUTOCLICK_CAPTURA_ERRO"] = "0"
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    RB.alerta("teste", "algo houve")
check("alerta imprime linha marcada", "[ALERTA] teste: algo houve" in buf.getvalue())
check("alerta vira aviso da telemetria", any("algo houve" in x for x in OP.tel().avisos))

print("5) Captura no erro (mss falso)")
import autoclick.captura as C
os.environ["AUTOCLICK_CAPTURA_ERRO"] = "1"; os.environ["AUTOCLICK_PASTA_ERROS"] = str(tmp / "erros")
C.capturar = lambda monitor, regiao=None: (np.full((40, 60, 3), 7, np.uint8), 1.0, 1.0, 0, 0)
RB.m_captura.capturar = C.capturar
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    p = RB.capturar_erro("tela parada!", 1)
check("png salvo com nome seguro", p is not None and Path(p).is_file() and "tela_parada" in p, str(p))

print("6) Webhook")
recebido = {}
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        recebido["corpo"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.send_response(204); self.end_headers()
    def log_message(self, *a): pass
srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_port}/hook"
okk, msg = RB.enviar_webhook_sync("Titulo", "Texto", url)
check("POST entregue", okk and "Titulo" in recebido["corpo"]["content"], msg)
check("sem URL", RB.enviar_webhook_sync("a", "b", "")[0] is False)
check("URL inválida", RB.enviar_webhook_sync("a", "b", "ftp://x")[0] is False)
check("telegram mal formado", RB.enviar_webhook_sync("a", "b", "telegram:abc")[0] is False)
recebido.clear(); os.environ["AUTOCLICK_WEBHOOK"] = url
RB.enviar_webhook("T2", "X"); time.sleep(0.6)
check("envio em segundo plano", recebido.get("corpo", {}).get("content", "").startswith("T2"))
os.environ["AUTOCLICK_WEBHOOK"] = ""

print("7) Prévia ao vivo")
arq = tmp / "previa.png"; os.environ["AUTOCLICK_PREVIA"] = str(arq)
RB.previa.atualizar(np.zeros((400, 800, 3), np.uint8), [Hit(10, 10, 50, 20, "btn", 0.9)])
check("png criado e reduzido", arq.is_file() and cv2.imread(str(arq)).shape[1] == 560)
os.environ["AUTOCLICK_PREVIA"] = ""
t0 = RB.previa._ultimo; RB.previa.atualizar(np.zeros((9, 9, 3), np.uint8), [])
check("sem arquivo: não faz nada", RB.previa._ultimo == t0)

print("8) Atalhos configuráveis")
check("nome->vk", W.vk_de_nome("F8") == 0x77 and W.vk_de_nome("f12") == 0x7B and W.vk_de_nome("x") == ord("X") and W.vk_de_nome("lixo") is None)
W.definir_teclas("F6", "F7", "F11")
check("trocou", W.VK_F8 == 0x75 and W.VK_F9 == 0x76 and W.VK_F10 == 0x7A and W.NOME_PAUSA == "F6")
check("teclas de atalho saem da gravação", 0x75 not in W.VKS_TECLADO and 0x77 in W.VKS_TECLADO)
os.environ["AUTOCLICK_TECLAS"] = "pausa=F2;parar=F3;gravar=F4"; W.teclas_do_ambiente()
check("via ambiente", W.VK_F8 == 0x71 and W.VK_F9 == 0x72 and W.NOME_PARAR == "F3")
W.definir_teclas("lixo", "F9"); 
check("inválida volta ao padrão", W.VK_F8 == 0x77 and W.NOME_PAUSA == "F8")
W.definir_teclas()

print("9) Resolução")
dados = {"tela": {"largura": 1920, "altura": 1080, "dpi": 144}, "janela": {"titulo": "X", "rect": [0, 0, 1280, 720]}}
W.tamanho_tela = lambda: (1366, 768); W.dpi_sistema = lambda: 96
RB.m_captura.rect_seguro = lambda t: (0, 0, 1000, 600)
av = RB.conferir_resolucao(dados, "X")
check("tela, DPI e janela diferentes", len(av) == 3, str(av))
dados2 = {"tela": {"largura": 1366, "altura": 768, "dpi": 96}, "janela": {"titulo": "X", "rect": [0, 0, 1000, 600]}}
check("igual: sem avisos", RB.conferir_resolucao(dados2, "X") == [])
check("sem metadados: sem avisos", RB.conferir_resolucao({}, None) == [])

print("10) Marcador de verificação e erros na reprodução")
import autoclick.reproducao as RP, autoclick.deteccao as DT
W.abortar = lambda: False
RP.m_windows.abortar = lambda: False
RP.m_captura.rect_seguro = lambda t: None
RP.m_captura.capturar = lambda m, r=None: (np.zeros((20, 20, 3), np.uint8), 1.0, 1.0, 0, 0)
estado = {"vistos": False}
RP.m_deteccao.detectar_imagens = lambda img, pasta, conf: [Hit(1, 1, 5, 5, "jogar")] if estado["vistos"] else []
_sl = time.sleep; time.sleep = lambda s: None
RP.time.sleep = lambda s: None
import threading as _t
def liga(): estado["vistos"] = True
r, esp = RP._aguardar_marcador({"botao": "jogar", "timeout": 5}, "p", 0.8, 1, None, None) if False else (None, 0)
estado["vistos"] = True
r, esp = RP._aguardar_marcador({"botao": "jogar", "timeout": 5}, "p", 0.8, 1, None, None)
check("já visível: ok na hora", r is True)
estado["vistos"] = False
t0 = time.time(); RP.time.time = lambda c=iter([i * 2.0 for i in range(100)]): next(c)
r, esp = RP._aguardar_marcador({"botao": "jogar", "timeout": 5}, "p", 0.8, 1, None, None)
check("nunca aparece: estoura o tempo", r is False and esp >= 5, f"{r} {esp}")
estado["vistos"] = True; RP.time.time = time.time
r, esp = RP._aguardar_marcador({"botao": "jogar", "timeout": 5, "ate": "sumir"}, "p", 0.8, 1, None, None) if False else (None, 0)
RP.time.time = lambda c=iter([i * 2.0 for i in range(100)]): next(c)
r, esp = RP._aguardar_marcador({"botao": "jogar", "timeout": 5, "ate": "sumir"}, "p", 0.8, 1, None, None)
check("esperar sumir: estoura se continua visível", r is False)
RP.time.time = time.time
estado["vistos"] = False
r, esp = RP._aguardar_marcador({"botao": "jogar", "timeout": 5, "ate": "sumir"}, "p", 0.8, 1, None, None)
check("esperar sumir: ok se não está", r is True)
W.abortar = lambda: True; RP.m_windows.abortar = W.abortar
r, esp = RP._aguardar_marcador({"botao": "jogar", "timeout": 5}, "p", 0.8, 1, None, None)
check("F9 durante o marcador aborta", r is None)
W.abortar = lambda: False; RP.m_windows.abortar = W.abortar

from autoclick.regras import Regra
rg = {"desc": Regra(acao="erro", ao_ver="reconectar", reconectar_com="rec"), "rec": Regra(acao="clicar"),
      "queda": Regra(acao="erro", ao_ver="parar")}
vg = RP.VigiaBotoes(rg, "p", 0.8, 1, None, None, False, threading.Lock())
check("botão de reconectar entra na vigia", "rec" in vg.regras and "desc" in vg.erros)
check("nomes incluem telas de erro", "desc" in vg.nomes and "queda" in vg.nomes)
os.environ["AUTOCLICK_CAPTURA_ERRO"] = "0"
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    vg._tratar_erros([Hit(0, 0, 5, 5, "desc")], 100.0, None)
check("reconectar pede reinício do ciclo", vg.pegar_reinicio() == "(reconexão)")
with contextlib.redirect_stdout(buf):
    vg._tratar_erros([Hit(0, 0, 5, 5, "desc")], 110.0, None)
check("mesma tela em <30s não repete", vg.pegar_reinicio() is None)
W.PARADA.clear()
with contextlib.redirect_stdout(buf):
    vg._tratar_erros([Hit(0, 0, 5, 5, "queda")], 200.0, None)
check("ao_ver parar aciona a parada", W.PARADA.is_set()); W.PARADA.clear()

print(f"\n{ok} verificações passaram (robustez).")
