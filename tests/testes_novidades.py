"""Mensagens de erro claras da atualização e “O que mudou”."""
import os, sys, tempfile, shutil, socket, threading, errno, zipfile, urllib.error, json
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ok = 0
def check(n, c, extra=""):
    global ok
    print(("  OK   " if c else "  FALHOU ") + n + (f"  {extra}" if extra and not c else ""))
    if not c: sys.exit(1)
    ok += 1
from autoclick import atualizacao as A, novidades as N
tmp = tempfile.mkdtemp(); os.chdir(tmp)

print("1) Mensagens em português")
d = A.descrever_erro
check("sem internet (DNS)", "Sem conexão com a internet" in d(urllib.error.URLError(socket.gaierror(-2, "x"))))
check("servidor recusou", "fora do ar" in d(urllib.error.URLError(ConnectionRefusedError())))
check("timeout", "demorou demais" in d(socket.timeout()) and "demorou demais" in d(urllib.error.URLError(socket.timeout())))
check("conexão caiu", "caiu" in d(ConnectionResetError()))
check("zip inválido", "inválido" in d(zipfile.BadZipFile("x")) and "Nada foi instalado" in d(zipfile.BadZipFile("x")))
check("sem permissão", "permissão" in d(PermissionError(13, "x")))
check("sem espaço", "espaço em disco" in d(OSError(errno.ENOSPC, "x")))
check("erro desconhecido sugere relatório", "Salvar relatório" in d(RuntimeError("boom")))
check("ErroServidor passa direto", d(A.ErroServidor("já está pronta")) == "já está pronta")
check("HTTP 429", "Muitas tentativas" in A.mensagem_http(429))
check("HTTP 502/503", "fora do ar" in A.mensagem_http(502) and "502" in A.mensagem_http(502))
check("HTTP 404", "não está mais disponível" in A.mensagem_http(404))
real = shutil.disk_usage
shutil.disk_usage = lambda p: type("U", (), {"free": 10 * 1048576})()
try:
    A.conferir_espaco(tmp, 20 * 1048576); falhou = None
except A.ErroServidor as e: falhou = str(e)
shutil.disk_usage = real
check("espaço insuficiente diz quanto falta", falhou and "Sem espaço em disco" in falhou and "60 MB" in falhou and "10 MB" in falhou, str(falhou))
A.conferir_espaco(tmp, 1000)
check("espaço suficiente não reclama", True)

print("2) Servidores de verdade")
class H(BaseHTTPRequestHandler):
    codigo = 502
    def do_GET(self): self.send_response(H.codigo); self.end_headers()
    def log_message(self, *a): pass
srv = HTTPServer(("127.0.0.1", 0), H); porta = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
S = A.Servidor(f"http://127.0.0.1:{porta}")
for cod, trecho in ((502, "fora do ar"), (429, "Muitas tentativas"), (404, "não está mais disponível"), (500, "fora do ar")):
    H.codigo = cod
    try: A.consultar(S, "0.1.0"); m = ""
    except A.ErroServidor as e: m = str(e)
    check(f"consultar com HTTP {cod}", trecho in m, m)
srv.shutdown()
s2 = socket.socket(); s2.bind(("127.0.0.1", 0)); p2 = s2.getsockname()[1]; s2.close()
try: A.consultar(A.Servidor(f"http://127.0.0.1:{p2}"), "0.1.0"); m = ""
except A.ErroServidor as e: m = str(e)
check("porta fechada: servidor fora do ar", "fora do ar" in m, m)
try: A.consultar(A.Servidor("http://nao-existe.invalid"), "0.1.0"); m = ""
except A.ErroServidor as e: m = str(e)
check("domínio inexistente: sem internet", "internet" in m or "servidor" in m, m)

print("3) Pacote: pastas protegidas e troca do .exe")
check("jogos/ é dado do usuário", "jogos" in A.PROTEGIDOS and "jogos" in A.EXCLUIR_DIRS and not A._permitido("jogos/x/botoes.json"))
check("troca do exe reabre por padrão", 'start ""' in A.script_troca_exe(1, "a", "b"))
check("troca ao fechar não reabre", 'start ""' not in A.script_troca_exe(1, "a", "b", reabrir=False))

print("4) O que mudou")
check("instalação nova: só registra", N.decidir("", "1.0") == "primeira")
check("mesma versão: nada", N.decidir("1.0", "1.0") == "nada")
check("versão diferente: mostra", N.decidir("0.8.0", "0.9.0") == "mostrar")
check("sem nada guardado: vazio", N.ler(tmp, "0.9.0") == "")
open("CHANGELOG.md", "w", encoding="utf-8").write("# H\n\n## 0.9.0\n- Jogos\n- Sons\n\n## 0.8.0\n- antigo\n")
check("lê a seção do CHANGELOG", N.ler(tmp, "0.9.0") == "- Jogos\n- Sons" and N.ler(tmp, "0.8.0") == "- antigo")
N.guardar(tmp, "0.9.0", "notas do servidor")
check("notas do servidor têm prioridade", N.ler(tmp, "0.9.0") == "notas do servidor")
check("notas de outra versão não valem", N.ler(tmp, "0.8.0") == "- antigo")
check("versão com ponto não vira regex", N.secao_do_changelog("## 0x9y0\n- x\n", "0.9.0") == "")

print(f"\n{ok} verificações passaram (mensagens e novidades).")
os.chdir("/"); shutil.rmtree(tmp, ignore_errors=True)
