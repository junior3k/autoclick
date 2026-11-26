import sys as _s0
for _f in (_s0.stdout, _s0.stderr):
    try: _f.reconfigure(encoding="utf-8", errors="replace")  # Windows (cp1252) não imprime setas
    except Exception: pass
import sys, os, json, zipfile, tempfile, logging
from pathlib import Path
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import autoclick.atualizacao as AT, autoclick.registro_log as RL
ok = 0
def check(nome, cond, extra=""):
    global ok
    print(("  OK   " if cond else "  FALHOU ") + nome + (f"  {extra}" if extra and not cond else ""))
    if not cond: sys.exit(1)
    ok += 1
tmp = Path(tempfile.mkdtemp())

print("1) Versões")
check("comparação", AT.mais_nova("0.6.0", "0.5.0") and AT.mais_nova("1.0", "0.9.9") and not AT.mais_nova("0.5.0", "0.5") and AT.mais_nova("v0.5.1", "0.5.0") and not AT.mais_nova("0.4", "0.5.0"))
check("manifesto sem http recusado", AT.verificar("arquivo.json", "0.5.0")[0] is False)

print("2) Aplicar pacote com backup e proteção")
raiz = tmp / "proj"; (raiz / "autoclick").mkdir(parents=True); (raiz / "botoes").mkdir()
(raiz / "autoclick" / "__init__.py").write_text("velho", encoding="utf-8")
(raiz / "botoes.json").write_text('{"meu": 1}', encoding="utf-8")
(raiz / "botoes" / "a.png").write_bytes(b"png")
pacote = tmp / "novo.zip"
with zipfile.ZipFile(pacote, "w") as z:
    z.writestr("autoclick_inteligente/autoclick/__init__.py", "novo")
    z.writestr("autoclick_inteligente/autoclick/novo.py", "x = 1")
    z.writestr("autoclick_inteligente/autoclick/__pycache__/x.pyc", "lixo")
    z.writestr("autoclick_inteligente/botoes.json", "SOBRESCREVERIA")
    z.writestr("autoclick_inteligente/botoes/a.png", "SOBRESCREVERIA")
    z.writestr("autoclick_inteligente/pyproject.toml", "[project]")
    z.writestr("autoclick_inteligente/malware.exe", "x")
    z.writestr("autoclick_inteligente/autoclick/../../fora.py", "escapou")
r = AT.aplicar_zip(str(pacote), str(raiz))
check("arquivos novos instalados", (raiz / "autoclick" / "__init__.py").read_text() == "novo" and (raiz / "autoclick" / "novo.py").is_file() and (raiz / "pyproject.toml").is_file())
check("dados do usuário intactos", (raiz / "botoes.json").read_text() == '{"meu": 1}' and (raiz / "botoes" / "a.png").read_bytes() == b"png")
check("exe e pycache ignorados", not (raiz / "malware.exe").exists() and not (raiz / "autoclick" / "__pycache__").exists())
check("zip slip barrado", not (tmp / "fora.py").exists() and not (raiz.parent / "fora.py").exists())
check("backup do que foi trocado", r["backup"] and (Path(r["backup"]) / "autoclick" / "__init__.py").read_text() == "velho")
check("listar_pacote reflete a instalação", "autoclick/novo.py" in AT.listar_pacote(str(pacote)) and "botoes.json" not in AT.listar_pacote(str(pacote)))
n = AT.restaurar_backup(r["backup"], str(raiz))
check("restaurar volta o antigo", n == 1 and (raiz / "autoclick" / "__init__.py").read_text() == "velho")
check("lista backups", len(AT.listar_backups(str(raiz))) == 1)
ruim = tmp / "ruim.zip"
with zipfile.ZipFile(ruim, "w") as z: z.writestr("qualquer.txt", "x")
try: AT.aplicar_zip(str(ruim), str(raiz)); check("pacote estranho recusado", False)
except ValueError: check("pacote estranho recusado", True)

print("3) Log rotativo")
os.chdir(tmp)
RL.iniciar("logs", "t.log", maximo=300, copias=2)
for i in range(60): RL.escrever(f"linha {i} " + "x" * 30)
RL.fechar()
arqs = sorted(p.name for p in (tmp / "logs").iterdir())
check("rotaciona e limita as cópias", "t.log" in arqs and "t.log.1" in arqs and "t.log.3" not in arqs, str(arqs))
import io
orig = io.StringIO(); RL.iniciar("logs", "u.log")
t = RL._Tee(orig, logging.INFO); t.write("oi\nmeio"); t.write(" fim\n")
RL.fechar()
txt = (tmp / "logs" / "u.log").read_text(encoding="utf-8")
check("tee repassa e registra por linhas", orig.getvalue() == "oi\nmeio fim\n" and "oi" in txt and "meio fim" in txt)
os.environ["AUTOCLICK_FILHO"] = "1"; check("filho não grava log", RL.sou_filho())
print(f"\n{ok} verificações passaram (manutenção).")
