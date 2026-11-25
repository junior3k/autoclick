"""Fachada de testes: se comporta como o antigo módulo único (A.xxx), mas lê/escreve nos módulos do pacote."""
import importlib, sys, types
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import os as _o, tempfile as _t; _o.environ.setdefault("AUTOCLICK_HISTORICO", _o.path.join(_t.mkdtemp(), "s.jsonl")); _o.environ.setdefault("AUTOCLICK_CAPTURA_ERRO", "0")
NOMES = ["tipos", "windows", "captura", "deteccao", "regras", "acao", "gravacao", "reproducao", "varredura", "operacao", "condicoes", "cli"]
MODS = [importlib.import_module("autoclick." + n) for n in NOMES]

def _cands(n):
    return [n] if not n.startswith("_") else [n, n.lstrip("_")]

class _Fachada:
    def __getattr__(self, n):
        for c in _cands(n):
            for m in MODS:
                if c in vars(m):
                    return vars(m)[c]
        raise AttributeError(n)
    def __setattr__(self, n, v):
        achou = False
        for c in _cands(n):
            for m in MODS:
                if c in vars(m):
                    setattr(m, c, v); achou = True
            if achou: return
        raise AttributeError("nome inexistente nos módulos: " + n)

A = _Fachada()
