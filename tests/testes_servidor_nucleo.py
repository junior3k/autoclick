import os, sys, tempfile, hashlib, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
from autoclick import ed25519 as E
from autoclick.atualizacao import mensagem_do_pacote
from servidor.nucleo import Nucleo, ErroNegocio
from servidor.config import Config

ok = 0
def check(n, c):
    global ok
    print(("  OK   " if c else "  FALHOU ") + n)
    if not c: sys.exit(1)
    ok += 1
def erro(f):
    try: f()
    except ErroNegocio: return True
    return False

d = Path(tempfile.mkdtemp())
n = Nucleo(d)
sem = E.gerar_semente(); n.arquivo_chave_publica.write_text(E.chave_publica(sem).hex())
def pacote(v, art="fonte", conteudo=b"x"):
    z = d / f"{v}-{art}.zip"
    with zipfile.ZipFile(z, "w") as f: f.writestr("a.txt", conteudo + v.encode())
    sha = hashlib.sha256(z.read_bytes()).hexdigest()
    return z, E.assinar(sem, mensagem_do_pacote(v, art, sha, z.stat().st_size)).hex()
A1, A2 = "a" * 16, "b" * 16

print("endereços públicos")
c = Config(prefixo="ac-x", dominio="ac.cabro.me")
check("página e API", c.pagina == "https://ac.cabro.me/download" and c.base == "https://ac.cabro.me/download/api/v1")
check("painel fica no caminho secreto", c.painel == "https://ac.cabro.me/ac-x/painel")

print("versões e canais (sem convite)")
z, s = pacote("0.6.0")
check("assinatura ruim recusada", erro(lambda: n.registrar_versao(z, "0.6.0", "fonte", "00" * 64)))
n.registrar_versao(z, "0.6.0", "fonte", s, "beta", "notas")
check("versão repetida", erro(lambda: n.registrar_versao(z, "0.6.0", "fonte", s)))
check("estável não vê beta", n.escolher_atualizacao(A1, "estavel", "0.5.0", "fonte") is None)
check("quem pede beta vê", n.escolher_atualizacao(A1, "beta", "0.5.0", "fonte")["versao"] == "0.6.0")
check("download respeita o canal", n.pode_baixar("estavel", "0.6.0", "fonte") is None and n.pode_baixar("beta", "0.6.0", "fonte"))
n.promover("0.6.0")
check("promovida: estável vê, sem identificação nenhuma", n.escolher_atualizacao("", "estavel", "0.5.0", "fonte")["versao"] == "0.6.0")
check("já atualizado", n.escolher_atualizacao(A1, "estavel", "0.6.0", "fonte") is None)
check("artefato exe sem pacote", n.escolher_atualizacao(A1, "estavel", "0.5.0", "exe") is None)
z2, s2 = pacote("0.7.0"); n.registrar_versao(z2, "0.7.0", "fonte", s2, "estavel")
n.definir_percentual("0.7.0", 1)
quem = [i for i in range(400) if Nucleo.no_grupo(f"{i:016x}", "0.7.0", 1)]
check("rollout 1% determinístico e raro", 0 < len(quem) < 20)
dentro, fora = f"{quem[0]:016x}", next(f"{i:016x}" for i in range(400) if i not in quem)
check("no grupo recebe 0.7.0", n.escolher_atualizacao(dentro, "estavel", "0.6.0", "fonte")["versao"] == "0.7.0")
check("fora do grupo fica em 0.6.0", n.escolher_atualizacao(fora, "estavel", "0.5.0", "fonte")["versao"] == "0.6.0")
n.retirar("0.7.0")
check("retirada some", n.escolher_atualizacao(dentro, "estavel", "0.6.0", "fonte") is None)
m = n.manifesto(A1, "estavel", "0.5.0", "fonte", "win32")
check("manifesto sem nome/chave e sem caminho de arquivo", m["atualizacao"]["versao"] == "0.6.0" and "arquivo" not in m["atualizacao"] and "nome" not in m)
check("caminho do pacote", n.caminho_pacote(n.listar_versoes()[-1]).is_file())

print("instalações anônimas")
n.manifesto(A2, "beta", "0.6.0", "fonte", "win32"); n.manifesto("lixo", "estavel", "0.6.0", "fonte")
r = n.resumo()
check("conta só ids válidos", r["instalacoes"] == 2 and r["instalacoes_ativas_24h"] == 2 and r["ativas_por_versao"] == {"0.5.0": 1, "0.6.0": 1})

print("página de download")
check("sem pacote 'download': nada", n.download_atual() is None)
zd, sd = pacote("0.6.0", "download")
n.registrar_versao(zd, "0.6.0", "download", sd, "beta")
check("download em beta não aparece no site", n.download_atual() is None)
check("'download' nunca é servido como atualização", n.pode_baixar("beta", "0.6.0", "download") is None)
n.promover("0.6.0"); check("estável aparece", n.download_atual()["versao"] == "0.6.0")

print("relatórios (anônimos, com teto)")
rel = n.salvar_relatorio(A1, b"PK" + b"0" * 100, "erro")
check("salvo e listado", n.caminho_relatorio(rel["id"]).is_file() and n.listar_relatorios()[0]["instalacao"] == "a" * 8)
check("anônimo também", n.salvar_relatorio("", b"PK1")["id"] > 0)
check("relatório grande", erro(lambda: n.salvar_relatorio(A1, b"0" * (6 * 1024 * 1024))))
import servidor.nucleo as N
N.MAX_RELATORIOS = 3
for _ in range(6): n.salvar_relatorio(A1, b"PK2")
check("teto: só os mais recentes ficam", len(n.listar_relatorios()) == 3 and len(list(n.relatorios_dir.glob("*.zip"))) == 3)
for x in n.listar_relatorios(): n.apagar_relatorio(x["id"])
check("apagados", n.listar_relatorios() == [])

print("backup")
for _ in range(3): n.backup()
check("backup", len(n.listar_backups()) >= 1)
check("eventos", len(n.eventos()) > 4)
check("sem restos de convite", not any(hasattr(n, a) for a in ("criar_amigo", "autenticar", "revogar", "convite", "nova_chave")))
print(f"\n{ok} verificações passaram (servidor/núcleo).")
