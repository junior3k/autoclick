"""Cliente de atualização contra um site estático FALSO (http.server): manifesto, assinatura, download."""
import sys as _s0
for _f in (_s0.stdout, _s0.stderr):
    try: _f.reconfigure(encoding="utf-8", errors="replace")  # Windows (cp1252) não imprime setas
    except Exception: pass
import hashlib, http.server, io, json, os, sys, tempfile, threading, zipfile
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import autoclick.atualizacao as A
from autoclick import ed25519 as E

ok = 0
def check(nome, cond, extra=""):
    global ok
    print(("  OK   " if cond else "  FALHOU ") + nome + (f"  {extra}" if extra and not cond else ""))
    if not cond: sys.exit(1)
    ok += 1

SEM = E.gerar_semente(); PUB = E.chave_publica(SEM).hex()
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("autoclick/__init__.py", '__version__ = "9.9.9"\n')
    z.writestr("autoclick/novo.py", "x = 1\n")
    z.writestr("botoes.json", "NAO DEVE SOBRESCREVER")
PACOTE = buf.getvalue(); SHA = hashlib.sha256(PACOTE).hexdigest()
estado = {"corromper": False, "ignorar_range": False, "parar_em": None, "chave_ok": True, "assinar_msg": None,
          "pedidos": []}

def manifesto(versao="9.9.9", artefato="fonte", minima="0", sha=SHA, tam=len(PACOTE), url=None,
              assinada=("9.9.9", "fonte", SHA, len(PACOTE))):
    msg = estado["assinar_msg"] or A.mensagem_do_pacote(*assinada)
    sig = E.assinar(SEM, msg).hex()
    url = url or f"http://127.0.0.1:{srv_http.server_port}/arquivos/pacote.zip"
    return {"mensagem": "aviso de teste", "atualizacoes": {artefato: {
        "versao": versao, "canal": "estavel", "artefato": artefato, "sha256": sha, "tamanho": tam, "minima": minima,
        "assinatura": sig, "notas": "novidades", "url": url}}}

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        estado["pedidos"].append(self.path)
        estado["cabecalhos"] = dict(self.headers)
        if self.path == "/manifesto.json":
            corpo = json.dumps(estado.get("manifesto") or manifesto()).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(corpo))); self.end_headers(); self.wfile.write(corpo)
        elif self.path.startswith("/arquivos/"):
            dados = PACOTE if not estado["corromper"] else PACOTE[:-1] + b"X"
            r = self.headers.get("Range"); ini = 0; cod = 200
            if r and not estado["ignorar_range"]:
                ini = int(r.split("=")[1].split("-")[0]); cod = 206
            parte = dados[ini:]
            self.send_response(cod); self.send_header("Content-Length", str(len(parte))); self.end_headers()
            if estado["parar_em"] is not None and ini == 0:
                self.wfile.write(parte[:estado["parar_em"]]); self.wfile.flush(); self.connection.close(); return
            self.wfile.write(parte)
        else:
            self.send_response(404); self.end_headers()

srv_http = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv_http.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv_http.server_port}"
S = A.Servidor(URL)
tmp = Path(tempfile.mkdtemp())

print("1) Convite e URL")
check("https ok, http público recusado, http local ok", A.url_permitida("https://x.com/a") and not A.url_permitida("http://x.com/a") and A.url_permitida("http://127.0.0.1:1/a") and not A.url_permitida("ftp://x"))
check("não há mais convite no módulo", not hasattr(A, "ler_convite") and not hasattr(A, "salvar_convite"))
check("http fora de localhost recusado", not A.Servidor("http://evil.com/x").valido and A.Servidor("https://ac.cabro.me").valido)
check("localhost http permitido (testes)", A.Servidor("http://127.0.0.1:1/x").valido)
os.environ["AUTOCLICK_SERVIDOR_URL"] = URL
sp = A.servidor_padrao()
check("servidor_padrao usa a URL embutida/ambiente", sp is not None and sp.url == URL)
check("não existem mais canal nem número de instalação", not hasattr(sp, "canal") and not hasattr(sp, "instalacao") and not hasattr(A, "id_instalacao"))
del os.environ["AUTOCLICK_SERVIDOR_URL"]
import autoclick.servidor_padrao as _SP
_url0 = _SP.URL_PADRAO; _SP.URL_PADRAO = ""   # o `gerar_chave --escrever` preenche este valor
try: check("sem URL nenhuma: None", A.servidor_padrao() is None)
finally: _SP.URL_PADRAO = _url0
print("1b) Quem pode hospedar o pacote")
check("GitHub e o próprio site", A.url_pacote_permitida("https://github.com/u/r/releases/download/v1/a.zip", S)
      and A.url_pacote_permitida("https://objects.githubusercontent.com/x", S) and A.url_pacote_permitida(f"{URL}/arquivos/a.zip", S))
check("outros hosts e http público recusados", not A.url_pacote_permitida("https://evil.com/a.zip", S)
      and not A.url_pacote_permitida("http://github.com/a.zip", S) and not A.url_pacote_permitida("ftp://github.com/a", S)
      and not A.url_pacote_permitida("https://github.com.evil.com/a.zip", S))
i = A.consultar(S, "0.5.0", "fonte", PUB)
check("nova versão reconhecida", i["nova"] and i["versao"] == "9.9.9" and not i["obrigatoria"])
check("pede só o manifesto estático (nada sobre quem usa)", estado["pedidos"][-1] == "/manifesto.json" and "?" not in estado["pedidos"][-1])
check("aviso do manifesto repassado", i["mensagem"] == "aviso de teste" and i["url"].endswith("/arquivos/pacote.zip"))
check("já na última: nada", not A.consultar(S, "9.9.9", "fonte", PUB)["nova"])
estado["manifesto"] = manifesto(minima="9.0.0")
check("versão mínima => obrigatória", A.consultar(S, "0.5.0", "fonte", PUB)["obrigatoria"])
estado["manifesto"] = None
for nome, mut in (("sha adulterado no manifesto", lambda m: m["atualizacoes"]["fonte"].__setitem__("sha256", "0" * 64)),
                  ("versão adulterada", lambda m: m["atualizacoes"]["fonte"].__setitem__("versao", "9.9.8")),
                  ("tamanho adulterado", lambda m: m["atualizacoes"]["fonte"].__setitem__("tamanho", 5)),
                  ("tipo de pacote adulterado", lambda m: m["atualizacoes"]["fonte"].__setitem__("artefato", "exe"))):
    m = manifesto(minima="0"); mut(m); estado["manifesto"] = m
    try: A.consultar(S, "0.5.0", "fonte", PUB); check(nome + " é recusado", False)
    except A.ErroServidor as e: check(nome + " é recusado", "ASSINATURA" in str(e))
estado["manifesto"] = manifesto(minima="0.1.0")
i2 = A.consultar(S, "0.5.0", "fonte", PUB)
check("mínima é metadado fora da assinatura (não muda o que é instalado)", i2["nova"] and i2["sha256"] == SHA)
estado["manifesto"] = manifesto(url="https://evil.com/pacote.zip")
try: A.consultar(S, "0.5.0", "fonte", PUB); check("manifesto com link de download estranho é recusado", False)
except A.ErroServidor as e: check("manifesto com link de download estranho é recusado", "não permitido" in str(e))
estado["manifesto"] = {"mensagem": "", "atualizacoes": {}}
check("sem pacote para este tipo: nada", not A.consultar(S, "0.5.0", "fonte", PUB)["nova"])
estado["manifesto"] = {"mensagem": "", "atualizacoes": {"fonte": {"versao": "9.9.9"}}}
try: A.consultar(S, "0.5.0", "fonte", PUB); check("manifesto incompleto", False)
except A.ErroServidor as e: check("manifesto incompleto", "incompleto" in str(e))
estado["manifesto"] = None
OUTRA = E.chave_publica(E.gerar_semente()).hex()
try: A.consultar(S, "0.5.0", "fonte", OUTRA); check("assinatura de outra chave recusada", False)
except A.ErroServidor: check("assinatura de outra chave recusada", True)
try: A.consultar(S, "0.5.0", "fonte", ""); check("sem chave embutida, recusa", False)
except A.ErroServidor as e: check("sem chave embutida, recusa", "chave de confiança" in str(e))
check("pedir outro tipo de pacote (exe) quando só há fonte: nada", not A.consultar(S, "0.5.0", "exe", PUB)["nova"])
i0 = A.consultar(S, "0.5.0", "fonte", PUB)
check("nenhuma credencial nem identificador de instalação enviados", "Authorization" not in estado["cabecalhos"] and "X-Instalacao" not in estado["cabecalhos"])
try: A.consultar(A.Servidor("http://127.0.0.1:1"), "0.5.0", "fonte", PUB); check("servidor fora do ar", False)
except A.ErroServidor as e: check("servidor fora do ar: mensagem amigável", "servidor" in str(e).lower() or "conex" in str(e).lower() or "internet" in str(e).lower(), str(e))

print("3) Download")
info = A.consultar(S, "0.5.0", "fonte", PUB)
p = A.baixar_pacote(S, info, str(tmp / "d1"))
check("baixa e confere", Path(p).read_bytes() == PACOTE)
estado["corromper"] = True
try: A.baixar_pacote(S, info, str(tmp / "d2")); check("pacote corrompido é recusado", False)
except A.ErroServidor as e: check("pacote corrompido é recusado", "SHA-256" in str(e) and not list((tmp / "d2").glob("*.zip")))
estado["corromper"] = False; estado["parar_em"] = 40
try: A.baixar_pacote(S, info, str(tmp / "d3")); check("queda no meio avisa", False)
except A.ErroServidor: check("queda no meio avisa", (tmp / "d3").glob("*.part") is not None)
parcial = list((tmp / "d3").glob("*.part"))
check("sobra o arquivo parcial", len(parcial) == 1 and parcial[0].stat().st_size == 40)
estado["parar_em"] = None; estado["pedidos"].clear()
prog = []
p = A.baixar_pacote(S, info, str(tmp / "d3"), lambda a, b: prog.append((a, b)))
check("retoma de onde parou (Range)", Path(p).read_bytes() == PACOTE and any(h for h in estado["pedidos"]) and prog and prog[-1][0] == len(PACOTE))
parcial = tmp / "d4"; parcial.mkdir(); (parcial / "autoclick_9.9.9_fonte.zip.part").write_bytes(PACOTE[:30])
estado["ignorar_range"] = True
p = A.baixar_pacote(S, info, str(parcial))
check("servidor sem Range: recomeça do zero", Path(p).read_bytes() == PACOTE)
estado["ignorar_range"] = False
try: A.baixar_pacote(S, info, str(tmp / "d5"), cancelar=lambda: True); check("cancelar", False)
except A.ErroServidor as e: check("cancelar interrompe", "cancelado" in str(e))

print("4) Instalar com autoteste e reversão")
raiz = tmp / "proj"; (raiz / "autoclick").mkdir(parents=True)
(raiz / "autoclick" / "__init__.py").write_text('__version__ = "0.5.0"\n'); (raiz / "botoes.json").write_text("MEU")
res = A.instalar_do_servidor(S, info, str(raiz), comando_autoteste=[sys.executable, "-c", "print('9.9.9')"])
check("instalou e preservou os dados", (raiz / "autoclick" / "novo.py").is_file() and (raiz / "botoes.json").read_text() == "MEU" and "9.9.9" in (raiz / "autoclick" / "__init__.py").read_text())
(raiz / "autoclick" / "__init__.py").write_text('__version__ = "0.5.0"\n'); (raiz / "autoclick" / "novo.py").unlink()
try:
    A.instalar_do_servidor(S, info, str(raiz), comando_autoteste=[sys.executable, "-c", "import sys; sys.exit(3)"])
    check("autoteste falhou => reverte", False)
except A.ErroServidor as e:
    check("autoteste falhou => reverte", "restaurada" in str(e) and "0.5.0" in (raiz / "autoclick" / "__init__.py").read_text())
try:
    A.instalar_do_servidor(S, info, str(raiz), comando_autoteste=[sys.executable, "-c", "print('1.0.0')"])
    check("versão instalada diferente da assinada => reverte", False)
except A.ErroServidor as e:
    check("versão instalada diferente da assinada => reverte", "difere" in str(e) and "0.5.0" in (raiz / "autoclick" / "__init__.py").read_text())
ok_, _ = A.autoteste(str(raiz), "0.5.0", [sys.executable, "-c", "print('0.5.0')"])
check("autoteste ok", ok_)

print("5) Troca do .exe (texto do script)")
sc = A.script_troca_exe(4321, "C:\\app\\_atualizacao\\novo", "C:\\app")
check("espera o PID, copia e reabre", 'set "PID=4321"' in sc and "tasklist" in sc and sc.count("robocopy") == 3 and 'start "" "C:\\app' in sc and "Autoclick.exe" in sc)
check("não toca nos dados do usuário", all(x in sc for x in ('"botoes"', '"perfis"', '"botoes.json"', '"autoclick_instalacao.txt"')))
check("usa CRLF", "\r\n" in sc and "\n\n" not in sc.replace("\r\n", "\n").rstrip("\n") + "")
zp = tmp / "exe.zip"
with zipfile.ZipFile(zp, "w") as z:
    z.writestr("Autoclick/Autoclick.exe", "MZ"); z.writestr("Autoclick/_internal/x.dll", "d"); z.writestr("Autoclick/botoes.json", "NAO")
dest = tmp / "instalado"; dest.mkdir()
cmd = A.preparar_troca_exe(str(zp), str(dest), pid=1)
check("prepara pasta e script", (dest / "_atualizacao" / "novo" / "Autoclick.exe").is_file() and Path(cmd).is_file())
srv_http.shutdown()
print(f"\n{ok} verificações passaram (cliente x site estático falso).")
