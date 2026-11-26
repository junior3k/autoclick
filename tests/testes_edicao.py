import sys as _s0
for _f in (_s0.stdout, _s0.stderr):
    try: _f.reconfigure(encoding="utf-8", errors="replace")  # Windows (cp1252) não imprime setas
    except Exception: pass
import sys, json, tempfile
from pathlib import Path
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import autoclick.interface.edicao as E
ok = 0
def check(n, c, x=""):
    global ok
    print(("  OK   " if c else "  FALHOU ") + n + (f" {x}" if x and not c else ""))
    if not c: sys.exit(1)
    ok += 1
ev = [{"t": 0.0, "tipo": "clique", "mouse": "esquerdo", "x": 1, "y": 2, "botao": "jogar"},
      {"t": 2.0, "tipo": "tecla", "tecla": "A", "vk": 65, "estado": "baixo"},
      {"t": 2.1, "tipo": "tecla", "tecla": "A", "vk": 65, "estado": "cima"},
      {"t": 5.0, "tipo": "arrasto", "x": 1, "y": 1, "x2": 9, "y2": 9, "botao": ""}]
check("descrever", E.descrever(ev[0]) == ("Clique", "esquerdo em (1, 2) [jogar]") and E.descrever(ev[3])[0] == "Arrasto")
check("duração", E.duracao(ev) == 5.0)
n = E.apagar(ev, [1]); check("apagar não altera o original", len(n) == 3 and len(ev) == 4)
n, ap = E.deslocar(ev, 3, 4.0); check("inserir espera desloca os seguintes", n[3]["t"] == 9.0 and n[2]["t"] == 2.1 and ap == 4.0)
n, ap = E.deslocar(ev, 3, -10.0); check("encurtar para no evento anterior", n[3]["t"] == 2.1 and round(ap, 2) == -2.9, str(ap))
n = E.definir_tempo(ev, 0, 3.0); check("definir tempo reordena", [e["tipo"] for e in n][:2] == ["tecla", "tecla"] and n[2]["t"] == 3.0)
n = E.inserir_marcador(ev, 3, "ok", 12, "sumir", "parar")
check("marcador antes do evento", n[3]["tipo"] == "aguardar" and n[3]["t"] == 5.0 and n[4]["tipo"] == "arrasto" and n[3]["ate"] == "sumir")
check("marcador no fim", E.inserir_marcador(ev, 99, "x")[-1]["tipo"] == "aguardar")
try: E.inserir_marcador(ev, 0, "x", ao_estourar="explodir"); check("valida ao_estourar", False)
except ValueError: check("valida ao_estourar", True)
n = E.cortar_antes(ev, 1); check("cortar início zera o tempo", n[0]["t"] == 0.0 and n[-1]["t"] == 3.0 and len(n) == 3)
check("cortar fim", len(E.cortar_depois(ev, 1)) == 2)
n = E.duplicar(ev, [1, 2]); check("duplicar repete com ritmo e desloca o resto", len(n) == 6 and n[-1]["t"] > 5.0 and sum(e["tipo"] == "tecla" for e in n) == 4)
check("problemas: tecla presa", E.problemas(E.apagar(ev, [2])) != [] and E.problemas(ev) == [])
check("problemas: marcador vazio", E.problemas([{"t": 0, "tipo": "aguardar"}]) != [])
h = E.Historia(ev); h.mudar(E.apagar(ev, [0])); h.mudar(E.apagar(h.atual, [0]))
check("historia desfaz/refaz", len(h.atual) == 2 and h.desfazer() and len(h.atual) == 3 and h.desfazer() and len(h.atual) == 4 and not h.desfazer() and h.refazer() and len(h.atual) == 3)
h.mudar([]); check("nova mudança limpa o refazer", not h.pode_refazer)
tmp = Path(tempfile.mkdtemp()); arq = str(tmp / "g.json")
Path(arq).write_text(json.dumps({"versao": 2, "janela": {"titulo": "X"}, "eventos": ev}), encoding="utf-8")
d, e = E.carregar(arq); bak = E.salvar(arq, d, E.apagar(e, [0]))
novo = json.loads(Path(arq).read_text())
check("salvar mantém metadados, grava backup", novo["janela"]["titulo"] == "X" and len(novo["eventos"]) == 3 and novo["editado"] and bak and len(json.loads(Path(bak).read_text())["eventos"]) == 4)
E.salvar(arq, d, e[:1]); check("backup original não é sobrescrito", len(json.loads(Path(bak).read_text())["eventos"]) == 4)
Path(arq).write_text("{}", encoding="utf-8")
try: E.carregar(arq); check("rejeita não-gravação", False)
except ValueError: check("rejeita não-gravação", True)
print(f"\n{ok} verificações passaram (edição).")
