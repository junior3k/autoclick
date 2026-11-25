"""Ponta a ponta: servidor real (uvicorn, localhost) + funções reais do cliente, tudo SEM convite."""
import io, json, os, shutil, socket, sys, tempfile, threading, time, urllib.request, urllib.error, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent

ok = 0
def check(n, c, extra=""):
    global ok
    print(("  OK   " if c else "  FALHOU ") + n + (f"  {extra}" if not c else ""))
    if not c: sys.exit(1)
    ok += 1

tmp = Path(tempfile.mkdtemp())
dados = tmp / "dados"; os.environ["AUTOCLICK_SERVIDOR_DADOS"] = str(dados)
def copia(destino):
    destino.mkdir(parents=True)
    shutil.copytree(RAIZ / "autoclick", destino / "autoclick", ignore=shutil.ignore_patterns("__pycache__"))
    for f in ("pyproject.toml", "autoclick_inteligente.py"):
        shutil.copy2(RAIZ / f, destino / f)
fonte = tmp / "fonte"; copia(fonte)
(fonte / "dist" / "Autoclick").mkdir(parents=True); (fonte / "dist" / "Autoclick" / "Autoclick.exe").write_bytes(b"MZ" + b"0" * 5000)
cliente = tmp / "cliente"; copia(cliente)

from servidor import operacao, publicar as pub
from servidor.nucleo import Nucleo
from servidor.web import criar_app, Limites
import uvicorn
from autoclick import atualizacao as A, relatorio as R

s = socket.socket(); s.bind(("127.0.0.1", 0)); porta = s.getsockname()[1]; s.close()
cfg, token = operacao.instalar(f"http://127.0.0.1:{porta}", porta, dados, raiz=fonte)
n = Nucleo(dados)
lim = Limites(api=25, downloads=3, relatorios=2)
srv_uv = uvicorn.Server(uvicorn.Config(criar_app(n, lim), host="127.0.0.1", port=porta, log_level="error"))
threading.Thread(target=srv_uv.run, daemon=True).start()
for _ in range(100):
    try: socket.create_connection(("127.0.0.1", porta), 0.2).close(); break
    except OSError: time.sleep(0.1)

RAIZ_URL = f"http://127.0.0.1:{porta}"
PUB, API, PREF = RAIZ_URL + "/download", RAIZ_URL + "/download/api/v1", RAIZ_URL + "/" + cfg.prefixo
cont = {"n": 0}
def req(caminho, metodo="GET", corpo=None, extra=None, base=RAIZ_URL, ip=None):
    cont["n"] += 1
    h = {"CF-Connecting-IP": ip or f"10.1.{cont['n'] // 8}.1"}   # cada ~8 pedidos vem de outro IP
    h.update(extra or {})
    r = urllib.request.Request(base + caminho, data=corpo, method=metodo, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=15) as x: return x.status, x.read(), dict(x.headers)
    except urllib.error.HTTPError as e: return e.code, e.read(), dict(e.headers)
def adm(caminho, metodo="GET", corpo=None, tok=None):
    st, b, _ = req(f"/{cfg.prefixo}/admin" + caminho, metodo, json.dumps(corpo).encode() if corpo is not None else None,
                   {"Authorization": f"Bearer {tok or token}"})
    return st, (json.loads(b) if b and b[:1] in b"[{" else b)

print("1) Rotas e isolamento")
check("endereços da config", cfg.pagina == PUB and cfg.base == API)
check("API embutida no programa", 'URL_PADRAO = "%s"' % API in (fonte / "autoclick" / "servidor_padrao.py").read_text())
check("raiz do domínio: 404 vazio", req("/")[:2] == (404, b""))
check("rota de outra API: 404 vazio", req("/api/v1/saude")[:2] == (404, b""))
check("docs desligados", req("/docs")[0] == 404 and req("/openapi.json")[0] == 404)
check("rotas antigas com convite não existem mais", req(f"/{cfg.prefixo}/v1/manifesto")[0] == 404)
st, b, h = req("/download/api/v1/saude"); check("saúde", st == 200 and json.loads(b) == {"ok": True})
check("cabeçalhos de segurança", h.get("x-content-type-options") == "nosniff")

print("2) Página pública (qualquer pessoa)")
st, b, h = req("/download")
check("sem versão: aviso amigável", st == 200 and "Ainda não há versão" in b.decode() and "Baixar" not in b.decode())
check("/download/arquivo sem versão: 404", req("/download/arquivo")[0] == 404)
pub.publicar(n, "0.9.0", testes=False, canal="beta", notas="novidades <b>teste</b>", raiz=fonte, log=lambda m: None)
zd = pub.montar_download(tmp / "dl.zip", fonte); pub.assinar_e_registrar(n, zd, "0.9.0", "download", "beta", "novidades <b>teste</b>")
check("em beta o site continua sem arquivo", "Ainda não há versão" in req("/download")[1].decode())
check("promover pelo painel", adm("/versoes/0.9.0/promover", "POST", {"canal": "estavel"})[0] == 200)
st, b, h = req("/download"); pagina = b.decode()
check("página com botão, versão e tamanho", st == 200 and 'href="/download/arquivo"' in pagina and "0.9.0" in pagina and "MB" in pagina)
check("notas escapadas (sem HTML injetado)", "&lt;b&gt;teste" in pagina and "<b>teste" not in pagina)
check("SHA-256 exibido", n.download_atual()["sha256"] in pagina)
check("CSP restritiva na página", "default-src 'none'" in h.get("content-security-policy", "") and "script-src" not in h.get("content-security-policy", ""))
check("css e ícone", req("/download/pagina.css")[0] == 200 and req("/download/icone.png")[1][:4] == b"\x89PNG")
check("/download/ com barra também", req("/download/")[0] == 200)
st, b, _ = req("/download/arquivo")
z = zipfile.ZipFile(io.BytesIO(b))
check("zip público: programa e LEIA-ME, nenhum convite", st == 200 and "Autoclick/Autoclick.exe" in z.namelist() and "Autoclick/LEIA-ME.txt" in z.namelist() and not any("servidor.json" in x or "chave" in x for x in z.namelist()))
st, b, _ = req("/download/arquivo", extra={"Range": "bytes=0-9"}); check("Range no download", st == 206 and len(b) == 10)
st, b, _ = req("/download/arquivo", ip="9.9.9.9"); req("/download/arquivo", ip="9.9.9.9"); req("/download/arquivo", ip="9.9.9.9")
check("limite folgado por IP contra robôs (429 só no excesso)", req("/download/arquivo", ip="9.9.9.9")[0] == 429 and req("/download/arquivo", ip="8.8.8.8")[0] == 200)

print("3) Cliente real, sem convite nem chave")
pubkey = n.chave_publica_hex()
S = A.Servidor(API, "estavel", "0123456789abcdef")
i = A.consultar(S, "0.5.0", "fonte", pubkey)
check("vê 0.9.0 com assinatura válida e sem nenhuma credencial", i["nova"] and i["versao"] == "0.9.0")
try: A.consultar(S, "0.5.0", "fonte", "00" * 32); check("chave pública errada recusada", False)
except A.ErroServidor as e: check("chave pública errada recusada (assinatura)", "ASSINATURA" in str(e))
z2, s2 = None, None
import hashlib
zf = tmp / "f2.zip"
with zipfile.ZipFile(zf, "w") as zz: zz.writestr("autoclick/__init__.py", '__version__ = "0.9.5"\n'); zz.writestr("botoes.json", "NAO")
pub.assinar_e_registrar(n, zf, "0.9.5", "fonte", "beta", "beta só")
check("estável não recebe beta", A.consultar(S, "0.5.0", "fonte", pubkey)["versao"] == "0.9.0")
Sb = A.Servidor(API, "beta", "0123456789abcdef")
check("quem marca 'receber beta' recebe", A.consultar(Sb, "0.5.0", "fonte", pubkey)["versao"] == "0.9.5")
st, _, _ = req("/download/api/v1/pacote/0.9.5/fonte"); check("download de beta sem pedir beta: 404", st == 404)
check("download de beta pedindo beta: ok", req("/download/api/v1/pacote/0.9.5/fonte?canal=beta")[0] == 200)
res = A.baixar_pacote(S, i, str(tmp / "d1"))
check("baixou e conferiu SHA-256", Path(res).stat().st_size == i["tamanho"])
st, b, _ = req("/download/api/v1/pacote/0.9.0/fonte", extra={"Range": "bytes=10-19"})
check("Range responde 206", st == 206 and len(b) == 10)
check("pacote 'download' não sai pela API de atualização", req("/download/api/v1/pacote/0.9.0/download")[0] == 404)
check("traversal: 404", req("/download/api/v1/pacote/..%2F..%2Fconfig.json/fonte")[0] == 404)
res = A.instalar_do_servidor(S, i, str(cliente))
check("instalou com autoteste", (cliente / "autoclick" / "__init__.py").read_text().count('"0.9.0"') == 1)
check("pacote não leva servidor/ nem tests/ nem dist/", not any((cliente / x).exists() for x in ("servidor", "tests", "dist")))
check("instalações anônimas contadas", n.resumo()["instalacoes"] >= 1)

print("4) Administração")
check("admin sem token: 401", req(f"/{cfg.prefixo}/admin/status")[0] == 401)
check("admin token errado: 401", adm("/status", tok="at_errado")[0] == 401)
st, r = adm("/status"); check("admin com token", st == 200 and r["instalacoes"] >= 1 and r["pagina"] == PUB and r["download"] == "0.9.0")
check("token não está em claro", token not in (dados / "config.json").read_text())
st, b, h = req(f"/{cfg.prefixo}/painel"); check("painel serve HTML com CSP", st == 200 and b"Painel Autoclick" in b and b"Amigos" not in b and "script-src 'self'" in h.get("content-security-policy", ""))
adm("/versoes/0.9.0/minima", "POST", {"minima": "0.9.0"})
check("mínima torna obrigatória", A.consultar(S, "0.5.0", "fonte", pubkey)["obrigatoria"] is True)
adm("/versoes/0.9.0/retirar", "POST", {}); 
check("retirada: some do cliente", A.consultar(S, "0.5.0", "fonte", pubkey)["nova"] is False)
check("percentual inválido: 400", adm("/versoes/0.9.0/percentual", "POST", {"percentual": 0})[0] == 400)
adm("/aviso", "POST", {"texto": "manutenção às 22h"})
check("aviso chega ao cliente", A.consultar(S, "0.5.0", "fonte", pubkey)["mensagem"] == "manutenção às 22h")
st, r = adm("/backup", "POST", {}); check("backup", st == 200 and r["backups"])
st, ev = adm("/eventos"); check("eventos", st == 200 and {"publicada", "download_site"} <= {e["tipo"] for e in ev})
cod = [req(f"/{cfg.prefixo}/admin/status", extra={"Authorization": "Bearer x"}, ip="7.7.7.7")[0] for _ in range(12)]
check("força bruta no admin: 401 e depois 429", cod[0] == 401 and cod[-1] == 429, str(cod))
check("JSON inválido: 400", req(f"/{cfg.prefixo}/admin/aviso", "POST", b"{x", {"Authorization": f"Bearer {token}"})[0] == 400)

antigo = token
token = operacao.novo_token(dados)
check("novo-token vale na hora, sem reiniciar o servidor", adm("/status")[0] == 200)
check("o token antigo deixa de valer", adm("/status", tok=antigo)[0] == 401)

print("5) Relatórios sem convite (com limites)")
bio = io.BytesIO(); zipfile.ZipFile(bio, "w").writestr("log.txt", "erro")
H = {"X-Resumo": "falha%20na%20tela", "Content-Type": "application/zip", "X-Instalacao": "0123456789abcdef"}
st, b, _ = req("/download/api/v1/relatorio", "POST", bio.getvalue(), H, ip="6.6.6.6")
check("envio aceito sem credencial", st == 200)
check("não-zip: 400", req("/download/api/v1/relatorio", "POST", b"x" * 50, ip="6.6.6.5")[0] == 400)
try: cod413 = req("/download/api/v1/relatorio", "POST", b"PK" + b"0" * (6 * 1024 * 1024), ip="6.6.6.4")[0]
except (urllib.error.URLError, ConnectionError): cod413 = 413
check("grande demais: 413", cod413 == 413)
req("/download/api/v1/relatorio", "POST", bio.getvalue(), H, ip="6.6.6.6")
check("limite por IP: 3º envio na hora é 429", req("/download/api/v1/relatorio", "POST", bio.getvalue(), H, ip="6.6.6.6")[0] == 429)
st, lista = adm("/relatorios"); check("painel lista", st == 200 and lista[0]["instalacao"] == "01234567" and lista[-1]["resumo"] == "falha na tela")
st, b, _ = req(f"/{cfg.prefixo}/admin/relatorios/{lista[0]['id']}", extra={"Authorization": f"Bearer {token}"}); check("painel baixa o zip", st == 200 and b[:2] == b"PK")
check("sem token não baixa relatório", req(f"/{cfg.prefixo}/admin/relatorios/{lista[0]['id']}")[0] == 401)
S2 = A.Servidor(API, "estavel", "0123456789abcdef")
(tmp / "p").mkdir(); (tmp / "p" / "logs").mkdir(); (tmp / "p" / "logs" / "autoclick.log").write_text("linha")
zr = R.montar(str(tmp / "rel.zip"), str(tmp / "p"))
import autoclick.atualizacao as AA
num = R.enviar(S2, zr, "teste do cliente")
check("função do cliente envia e recebe o número", num > 0 and any(r["resumo"] == "teste do cliente" for r in adm("/relatorios")[1]))
check("relatório do cliente sem webhook/segredos", b"webhook" not in zipfile.ZipFile(zr).read("config.json"))

print("6) Limite geral por IP")
cod = [req("/download/api/v1/saude", ip="5.5.5.5")[0] for _ in range(30)]
check("uso normal passa; excesso de robô leva 429", cod[:25].count(200) == 25 and 429 in cod[25:])

srv_uv.should_exit = True
print(f"\n{ok} verificações passaram (servidor ponta a ponta).")
