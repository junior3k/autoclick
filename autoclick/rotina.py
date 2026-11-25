# pyright: basic
"""Rotinas: vários scripts gravados de um jogo, juntos.

Uma rotina (rotina.json do jogo) tem:
  itens      lista que roda em ordem e repete: {"tipo": "script", "script": "plantar", "vezes": 1,
             "antes_botao": "npc", "antes_timeout": 60}, {"tipo": "esperar", "segundos": 20} ou
             {"tipo": "esperar_botao", "botao": "npc_loja", "timeout": 60, "ate": "aparecer",
             "ao_estourar": "parar" | "seguir"}
  intervalos scripts que entram sozinhos quando chega a hora: {"script": "loja", "a_cada": 300,
             "ativo": true, "antes_botao": "npc_loja", "antes_timeout": 60}
  voltas     quantas vezes a lista repete (0 = até parar)
  pausa_entre_scripts, pausa_volta   segundos

O mouse é um só: scripts nunca rodam ao mesmo tempo. Os intervalos vencidos entram nos pontos
seguros (entre um script e outro, ou durante uma espera), nunca no meio de um script.
Se um script falha, a rotina PARA e avisa (nada de continuar às cegas).
A lógica não toca no mouse: quem executa são funções passadas por quem chama (testável).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Optional, cast

PADRAO: dict[str, Any] = {"itens": [], "intervalos": [], "voltas": 0,
                          "pausa_entre_scripts": 0.5, "pausa_volta": 1.0}


def ler(caminho: str) -> dict[str, Any]:
    try:
        d: Any = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return json.loads(json.dumps(PADRAO))
    r: dict[str, Any] = json.loads(json.dumps(PADRAO))
    if isinstance(d, dict):
        r.update(cast(dict[str, Any], d))
    return r


def salvar(caminho: str, rot: dict[str, Any]) -> None:
    p = Path(caminho)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rot, ensure_ascii=False, indent=2), encoding="utf-8")


def pasta_scripts(caminho_rotina: str) -> Path:
    return Path(caminho_rotina).parent / "gravacoes"


def listar_scripts(caminho_rotina: str) -> dict[str, str]:
    """nome -> arquivo. O gravacao.json antigo do jogo aparece como "principal"."""
    d: dict[str, str] = {}
    base = Path(caminho_rotina).parent
    if (base / "gravacao.json").is_file():
        d["principal"] = str(base / "gravacao.json")
    ps = pasta_scripts(caminho_rotina)
    if ps.is_dir():
        for f in sorted(ps.glob("*.json")):
            if not f.name.endswith(".bak.json"):
                d[f.stem] = str(f)
    return d


def caminho_do_script(caminho_rotina: str, nome: str) -> str:
    base = Path(caminho_rotina).parent
    if nome == "principal":
        return str(base / "gravacao.json")
    return str(pasta_scripts(caminho_rotina) / f"{nome}.json")


def nome_valido(nome: str) -> str:
    import re
    n = re.sub(r"[^A-Za-z0-9_\-À-ÿ ]+", "", nome).strip().replace(" ", "_")
    return n[:40]


def validar(rot: dict[str, Any], scripts: Optional[set[str]] = None) -> list[str]:
    """Problemas que impediriam a rotina de rodar (lista vazia = ok)."""
    p: list[str] = []
    itens = rot.get("itens", [])
    if not isinstance(itens, list) or not itens:
        return ["A rotina está vazia: adicione ao menos um script."]
    for n, it in enumerate(cast(list[Any], itens), 1):
        if not isinstance(it, dict):
            p.append(f"Item {n}: formato inválido.")
            continue
        t = it.get("tipo")
        if t == "script":
            nome = str(it.get("script", ""))
            if not nome:
                p.append(f"Item {n}: falta escolher o script.")
            elif scripts is not None and nome not in scripts:
                p.append(f"Item {n}: o script “{nome}” não existe.")
            if int(it.get("vezes", 1) or 0) < 1:
                p.append(f"Item {n}: “vezes” precisa ser 1 ou mais.")
        elif t == "esperar":
            if float(it.get("segundos", 0) or 0) <= 0:
                p.append(f"Item {n}: o tempo de espera precisa ser maior que zero.")
        elif t == "esperar_botao":
            if not str(it.get("botao", "")):
                p.append(f"Item {n}: falta o nome do botão a esperar.")
        else:
            p.append(f"Item {n}: tipo desconhecido “{t}”.")
    for n, iv in enumerate(cast(list[Any], rot.get("intervalos", [])), 1):
        if not isinstance(iv, dict) or float(iv.get("a_cada", 0) or 0) <= 0:
            p.append(f"Intervalo {n}: “a cada” precisa ser maior que zero.")
        elif scripts is not None and iv.get("ativo", True) and str(iv.get("script", "")) not in scripts:
            p.append(f"Intervalo {n}: o script “{iv.get('script', '')}” não existe.")
    return p


def descrever(it: dict[str, Any]) -> str:
    t = it.get("tipo")
    if t == "script":
        ant = f" (antes espera [{it['antes_botao']}])" if it.get("antes_botao") else ""
        return f"script {it.get('script', '?')} ×{int(it.get('vezes', 1) or 1)}{ant}"
    if t == "esperar":
        return f"esperar {float(it.get('segundos', 0)):g} s"
    if t == "esperar_botao":
        v = "sumir" if str(it.get("ate", "aparecer")) == "sumir" else "aparecer"
        return (f"esperar [{it.get('botao', '?')}] {v} (até {float(it.get('timeout', 60)):g} s; "
                f"se estourar: {'seguir' if it.get('ao_estourar') == 'seguir' else 'parar'})")
    return str(t)


Rodar = Callable[[str], str]                      # rodar(nome do script) -> ok | interrompida | falhou
EsperarBotao = Callable[[str, float, str], Optional[bool]]  # (botao, timeout, ate) -> True/False/None=abortou


class Rotina:
    """Executa a rotina. Tudo que mexe no mundo vem por parâmetro."""

    def __init__(self, rot: dict[str, Any], rodar: Rodar, esperar_botao: EsperarBotao,
                 abortou: Callable[[], bool] = lambda: False,
                 avisar: Callable[[str, str], None] = lambda m, t: None,
                 agora: Callable[[], float] = time.time,
                 dormir: Callable[[float], None] = time.sleep,
                 fim_de_volta: Callable[[int], None] = lambda n: None,
                 inicio_de_volta: Callable[[int], None] = lambda n: None,
                 log: Callable[[str], None] = print) -> None:
        self.rot, self.rodar, self.esperar_botao = rot, rodar, esperar_botao
        self.abortou, self.avisar, self.agora, self.dormir = abortou, avisar, agora, dormir
        self.fim_de_volta, self.inicio_de_volta, self.log = fim_de_volta, inicio_de_volta, log
        self.ultimo: dict[int, float] = {}
        self.execucoes: list[str] = []       # nomes dos scripts rodados, em ordem (para teste/estatística)
        self.resultado = "ok"

    # ---- utilidades ---- #
    def _dormir(self, seg: float) -> bool:
        """Dorme `seg` segundos em fatias. False se abortou."""
        fim = self.agora() + max(0.0, seg)
        while self.agora() < fim:
            if self.abortou():
                return False
            self.dormir(min(0.1, max(0.0, fim - self.agora())))
        return not self.abortou()

    def _falhar(self, motivo: str, texto: str) -> None:
        self.resultado = "falhou"
        self.log(f"✖ Rotina parada: {motivo}: {texto}")
        self.avisar("rotina parou", f"{motivo}: {texto}")

    def _esperar_botao(self, botao: str, timeout: float, ate: str, ao_estourar: str, contexto: str) -> bool:
        """True = pode seguir. False = a rotina deve parar (já avisou ou foi abortada)."""
        self.log(f"  aguardando [{botao}] {'sumir' if ate == 'sumir' else 'aparecer'} (até {timeout:g} s)…")
        r = self.esperar_botao(botao, timeout, ate)
        if r is None:
            self.resultado = "interrompida"
            return False
        if r is False:
            if ao_estourar == "seguir":
                self.log(f"  ⚠ [{botao}] não ficou disponível em {timeout:g} s; seguindo mesmo assim.")
                return True
            self._falhar("botão não apareceu", f"[{botao}] em {timeout:g} s ({contexto})")
            return False
        return True

    def _rodar_script(self, nome: str, vezes: int = 1, antes_botao: str = "", antes_timeout: float = 60.0) -> bool:
        if antes_botao and not self._esperar_botao(antes_botao, antes_timeout, "aparecer", "parar",
                                                   f"antes do script {nome}"):
            return False
        for v in range(max(1, vezes)):
            if self.abortou():
                self.resultado = "interrompida"
                return False
            self.log(f"▶ Script {nome}" + (f" ({v + 1}/{vezes})" if vezes > 1 else ""))
            self.execucoes.append(nome)
            r = self.rodar(nome)
            if r == "interrompida":
                self.resultado = "interrompida"
                return False
            if r != "ok":
                self._falhar("script falhou", nome)
                return False
            if not self._dormir(float(self.rot.get("pausa_entre_scripts", 0.5))):
                self.resultado = "interrompida"
                return False
        return True

    # ---- intervalos ---- #
    def vencidos(self) -> list[int]:
        agora = self.agora()
        out: list[tuple[float, int]] = []
        for i, iv in enumerate(cast(list[dict[str, Any]], self.rot.get("intervalos", []))):
            if not iv.get("ativo", True):
                continue
            ult = self.ultimo.setdefault(i, agora)
            falta = ult + float(iv.get("a_cada", 0)) - agora
            if falta <= 0:
                out.append((falta, i))
        return [i for _, i in sorted(out)]

    def _rodar_intervalos(self) -> bool:
        """Roda os intervalos vencidos (um por vez). False = rotina deve parar."""
        for i in self.vencidos():
            iv = cast(list[dict[str, Any]], self.rot["intervalos"])[i]
            self.ultimo[i] = self.agora()
            self.log(f"⏱ Intervalo: {iv.get('script')} (a cada {float(iv.get('a_cada', 0)):g} s)")
            if not self._rodar_script(str(iv.get("script", "")), 1, str(iv.get("antes_botao", "")),
                                      float(iv.get("antes_timeout", 60) or 60)):
                return False
        return True

    # ---- laço ---- #
    def executar(self) -> str:
        itens = cast(list[dict[str, Any]], self.rot.get("itens", []))
        voltas = int(self.rot.get("voltas", 0) or 0)
        volta = 0
        inicio = self.agora()
        for i in range(len(cast(list[Any], self.rot.get("intervalos", [])))):
            self.ultimo[i] = inicio
        while voltas == 0 or volta < voltas:
            volta += 1
            self.log(f"— Volta {volta}" + (f"/{voltas}" if voltas else "") + " da rotina —")
            self.inicio_de_volta(volta)
            for it in itens:
                if self.abortou():
                    self.resultado = "interrompida"
                    return self.resultado
                if not self._rodar_intervalos():
                    return self.resultado
                t = it.get("tipo")
                if t == "script":
                    if not self._rodar_script(str(it.get("script", "")), int(it.get("vezes", 1) or 1),
                                              str(it.get("antes_botao", "")),
                                              float(it.get("antes_timeout", 60) or 60)):
                        return self.resultado
                elif t == "esperar":
                    fim = self.agora() + float(it.get("segundos", 0))
                    self.log(f"  esperando {float(it.get('segundos', 0)):g} s")
                    while self.agora() < fim:  # durante a espera os intervalos vencidos podem entrar
                        if self.abortou():
                            self.resultado = "interrompida"
                            return self.resultado
                        if not self._rodar_intervalos():
                            return self.resultado
                        self.dormir(min(0.2, max(0.0, fim - self.agora())))
                elif t == "esperar_botao":
                    if not self._esperar_botao(str(it.get("botao", "")), float(it.get("timeout", 60) or 60),
                                               str(it.get("ate", "aparecer")), str(it.get("ao_estourar", "parar")),
                                               "item da rotina"):
                        return self.resultado
            self.fim_de_volta(volta)
            if voltas == 0 or volta < voltas:
                if not self._dormir(float(self.rot.get("pausa_volta", 1.0))):
                    self.resultado = "interrompida"
                    return self.resultado
        self.resultado = "ok"
        return self.resultado
