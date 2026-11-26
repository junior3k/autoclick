"""Ferramentas de release: tag x versão, pacotes, manifesto assinado, site, e o cliente lendo o resultado."""
import sys as _s0
for _f in (_s0.stdout, _s0.stderr):
    try: _f.reconfigure(encoding="utf-8", errors="replace")  # Windows (cp1252) não imprime setas
    except Exception: pass
import http.server, json, os, shutil, sys, tempfile, threading, zipfile
from pathlib import Path
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from tools import montar_release as M, gerar_chave as GC
import autoclick.atualizacao as A
from autoclick import ed25519 as E, __version__

ok = 0
def check(nome, cond, extra=""):
    global ok
    print(("  OK   " if cond else "  FALHOU ") + nome + (f"  {extra}" if extra and not cond else ""))
    if not cond: sys.exit(1)
    ok += 1

tmp = Path(tempfile.mkdtemp())
SEM = E.gerar_semente(); PUB = E.chave_publica(SEM).hex()
dist = tmp / "dist" / "Autoclick"; (dist / "_internal").mkdir(parents=True)
(dist / "Autoclick.exe").write_bytes(b"MZ-fake-exe"); (dist / "_internal" / "x.dll").write_bytes(b"dll")
TAG = f"v{__version__}"

print("1) Tag x versão")
check("v + versão do código", M.versao_da_tag(TAG) == __version__ and M.conferir_tag(TAG) == __version__)
for ruim in ("0.1", "vx.y.z", "v1.2", "v1.2.3-beta"):
    try: M.versao_da_tag(ruim); check(f"tag '{ruim}' recusada", False)
    except M.ErroRelease: check(f"tag '{ruim}' recusada", True)
try: M.conferir_tag("v99.0.0"); check("tag diferente da versão do código é recusada", False)
except M.ErroRelease as e: check("tag diferente da versão do código é recusada", "não bate" in str(e))
check("notas vêm do CHANGELOG", len(M.notas_do_changelog(__version__)) > 10 and M.notas_do_changelog("0.0.1") == "")

print("2) Pacotes")
up = M.zip_atualizacao(dist, tmp / "up.zip"); dl = M.zip_download(dist, tmp / "dl.zip")
check("atualização: conteúdo na raiz do zip", "Autoclick.exe" in zipfile.ZipFile(up).namelist() and "_internal/x.dll" in zipfile.ZipFile(up).namelist())
check("download: pasta Autoclick/ + LEIA-ME", "Autoclick/Autoclick.exe" in zipfile.ZipFile(dl).namelist() and "Autoclick/LEIA-ME.txt" in zipfile.ZipFile(dl).namelist())
try: M.zip_atualizacao(tmp / "nada", tmp / "x.zip"); check("sem .exe, recusa", False)
except M.ErroRelease: check("sem .exe, recusa", True)

print("3) Montagem, assinatura e site")
saida = tmp / "_release"
r = M.montar(TAG, "usuario/repo", saida, SEM.hex(), dist, "ac.cabro.me", atual=None)
site, arq = saida / "site", saida / "arquivos"
check("arquivos da Release", (arq / f"autoclick_{__version__}_exe.zip").is_file() and (arq / "Autoclick.zip").is_file() and r["deploy"])
check("site completo", all((site / n).is_file() for n in ("index.html", "manifesto.json", "pagina.css", "icone.png", "CNAME", ".nojekyll")) and (site / "CNAME").read_text().strip() == "ac.cabro.me")
man = json.loads((site / "manifesto.json").read_text(encoding="utf-8"))
e = man["atualizacoes"]["exe"]
check("manifesto: versão, link da Release, canal", e["versao"] == __version__ and e["url"] == f"https://github.com/usuario/repo/releases/download/{TAG}/autoclick_{__version__}_exe.zip" and e["canal"] == "estavel")
check("manifesto: SHA-256 e tamanho do zip", e["sha256"] == M.sha256_de(arq / f"autoclick_{__version__}_exe.zip") and e["tamanho"] == (arq / f"autoclick_{__version__}_exe.zip").stat().st_size)
check("assinatura confere com a chave pública", E.verificar_hex(E.chave_publica(SEM).hex(), A.mensagem_do_pacote(e["versao"], "exe", e["sha256"], e["tamanho"]), e["assinatura"]))
html = (site / "index.html").read_text(encoding="utf-8")
check("página: botão para o download da Release, versão e SHA", f"releases/download/{TAG}/Autoclick.zip" in html and __version__ in html and M.sha256_de(arq / "Autoclick.zip") in html)
check("página sem script externo", "<script" not in html)
try: M.assinar_pacote("zz", "1.0.0", "exe", up); check("chave privada inválida recusada", False)
except M.ErroRelease: check("chave privada inválida recusada", True)

print("4) config.json (aviso e versão mínima)")
raiz2 = tmp / "r2"; shutil.copytree(RAIZ, raiz2, ignore=shutil.ignore_patterns("__pycache__", ".git", "dist", "_release"))
(raiz2 / "site" / "config.json").write_text(json.dumps({"mensagem": "Manutenção <b>hoje</b>", "minima": "0.1.0"}))
M.montar(TAG, "usuario/repo", tmp / "_r2", SEM.hex(), dist, "", raiz=raiz2)
m2 = json.loads((tmp / "_r2" / "site" / "manifesto.json").read_text(encoding="utf-8"))
check("aviso e mínima entram no manifesto", m2["mensagem"].startswith("Manutenção") and m2["atualizacoes"]["exe"]["minima"] == "0.1.0")
h2 = (tmp / "_r2" / "site" / "index.html").read_text(encoding="utf-8")
check("aviso aparece na página com HTML escapado", "Manutenção &lt;b&gt;hoje&lt;/b&gt;" in h2 and "<b>hoje</b>" not in h2)
check("sem domínio, sem CNAME", not (tmp / "_r2" / "site" / "CNAME").exists())

print("5) Não regride o site")
atual = tmp / "atual.json"
atual.write_text(json.dumps({"atualizacoes": {"exe": {"versao": "99.0.0"}}}))
check("site já numa versão mais nova: deploy=False", not M.montar(TAG, "u/r", tmp / "_r3", SEM.hex(), dist, atual=atual)["deploy"])
atual.write_text(json.dumps({"atualizacoes": {"exe": {"versao": "0.0.1"}}}))
check("site numa versão mais velha: deploy=True", M.montar(TAG, "u/r", tmp / "_r4", SEM.hex(), dist, atual=atual)["deploy"])
atual.write_text("lixo"); check("manifesto atual ilegível: publica", M.montar(TAG, "u/r", tmp / "_r5", SEM.hex(), dist, atual=atual)["deploy"])
check("reaproveita os zips já existentes (republicar o site)", M.montar(TAG, "usuario/repo", saida, SEM.hex(), None)["deploy"]
      and json.loads((site / "manifesto.json").read_text())["atualizacoes"]["exe"]["assinatura"] == e["assinatura"])

print("6) O cliente lê o que foi gerado")
manifesto_json = site / "manifesto.json"
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=str(saida), **k)
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_port}"
# servimos o site na raiz /site e os arquivos em /arquivos; o link da Release é trocado pelo local (não é assinado)
m = json.loads(manifesto_json.read_text(encoding="utf-8")); m["atualizacoes"]["exe"]["url"] = f"{base}/arquivos/autoclick_{__version__}_exe.zip"
manifesto_json.write_text(json.dumps(m))
S = A.Servidor(f"{base}/site")
info = A.consultar(S, "0.0.1", "exe", PUB)
check("cliente reconhece a versão nova assinada", info["nova"] and info["versao"] == __version__ and info["artefato"] == "exe")
pac = A.baixar_pacote(S, info, str(tmp / "baixados"))
check("baixa e confere SHA-256", Path(pac).read_bytes() == (arq / f"autoclick_{__version__}_exe.zip").read_bytes())
check("já na última versão: nada", not A.consultar(S, __version__, "exe", PUB)["nova"])
try: A.consultar(S, "0.0.1", "exe", E.chave_publica(E.gerar_semente()).hex()); check("chave diferente recusa", False)
except A.ErroServidor: check("chave diferente recusa", True)
srv.shutdown()

print("7) gerar_chave")
fake = tmp / "fake"; (fake / "autoclick").mkdir(parents=True)
(fake / "autoclick" / "chave_publica.py").write_text('"""x"""\nCHAVE_PUBLICA_HEX = ""\n')
(fake / "autoclick" / "servidor_padrao.py").write_text('"""x"""\nURL_PADRAO = ""\n')
GC.escrever(PUB, "https://ac.cabro.me/", fake)
check("grava a pública e a URL (sem barra final)", f'"{PUB}"' in (fake / "autoclick" / "chave_publica.py").read_text() and 'URL_PADRAO = "https://ac.cabro.me"' in (fake / "autoclick" / "servidor_padrao.py").read_text())
print(f"\n{ok} verificações passaram (release).")
