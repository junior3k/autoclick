# pyright: basic
"""Regras do servidor (sem HTTP): versões, canais, liberação gradual, instalações anônimas, relatórios, backup.

A chave PRIVADA de assinatura nunca é usada aqui: o servidor só guarda e entrega pacotes que
já chegaram assinados (a assinatura é conferida ao registrar). Assinar é papel de
`servidor.publicar`, que roda na linha de comando.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from autoclick import ed25519
from autoclick.atualizacao import mais_nova, mensagem_do_pacote, versao_tupla

from . import config as cfgmod
from .banco import Banco

CANAIS = ("beta", "estavel")
ARTEFATOS = ("fonte", "exe", "download")  # download = o zip da página pública (não é atualização)
INSTALACAO_OK = re.compile(r"^[0-9a-f]{16}$")
MAX_RELATORIOS = 300
VERSAO_OK = re.compile(r"^\d+(\.\d+){1,3}$")


class ErroNegocio(Exception):
    """Erro de regra com mensagem pronta para o administrador."""


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_token(token: str) -> str:
    return hashlib.sha256(("admin:" + token).encode("utf-8")).hexdigest()


class Nucleo:
    def __init__(self, dados: Optional[Path] = None) -> None:
        self.dados = Path(dados) if dados else cfgmod.pasta_dados()
        self.dados.mkdir(parents=True, exist_ok=True)
        self.pacotes = self.dados / "pacotes"
        self.relatorios_dir = self.dados / "relatorios"
        self.backups_dir = self.dados / "backups"
        for p in (self.pacotes, self.relatorios_dir, self.backups_dir):
            p.mkdir(parents=True, exist_ok=True)
        self.banco = Banco(self.dados / "banco.sqlite")
        self.cfg = cfgmod.carregar(self.dados) if cfgmod.existe(self.dados) else cfgmod.Config()
        self._cfg_mtime = self._mtime_cfg()

    def _mtime_cfg(self) -> float:
        try:
            return cfgmod.arquivo_config(self.dados).stat().st_mtime
        except OSError:
            return 0.0

    def atualizar_cfg(self) -> None:
        """Relê config.json se mudou em disco (ex.: `servidor.bat novo-token` ou `aviso` com o servidor
        rodando): assim não é preciso reiniciar o servidor para valer."""
        m = self._mtime_cfg()
        if m != self._cfg_mtime and cfgmod.existe(self.dados):
            self.cfg = cfgmod.carregar(self.dados)
            self._cfg_mtime = m

    # ------------------------------------------------------------------ #
    # chaves de assinatura
    # ------------------------------------------------------------------ #
    @property
    def arquivo_chave_publica(self) -> Path:
        return self.dados / "chave_publica.txt"

    def chave_publica_hex(self) -> str:
        p = self.arquivo_chave_publica
        return p.read_text(encoding="utf-8").strip() if p.is_file() else ""

    def arquivo_chave_privada(self) -> Path:
        return Path(os.environ.get("AUTOCLICK_CHAVE_PRIVADA") or (self.dados / "chave_privada.txt"))

    def carregar_chave_privada(self) -> bytes:
        p = self.arquivo_chave_privada()
        if not p.is_file():
            raise ErroNegocio(f"chave privada não encontrada em {p}. Rode: python -m servidor instalar")
        semente = bytes.fromhex(p.read_text(encoding="utf-8").strip())
        if ed25519.chave_publica(semente).hex() != self.chave_publica_hex():
            raise ErroNegocio("a chave privada não corresponde à chave pública instalada")
        return semente

    # ------------------------------------------------------------------ #
    # eventos
    # ------------------------------------------------------------------ #
    def evento(self, tipo: str, amigo: Optional[str] = None, detalhe: str = "") -> None:
        self.banco.executar("INSERT INTO eventos (t, tipo, amigo, detalhe) VALUES (?,?,?,?)",
                            (agora(), tipo, amigo, detalhe[:500]))
        self.banco.executar("DELETE FROM eventos WHERE id <= (SELECT MAX(id) FROM eventos) - 5000")

    def eventos(self, limite: int = 100) -> list[dict[str, Any]]:
        return self.banco.todos("SELECT * FROM eventos ORDER BY id DESC LIMIT ?", (max(1, min(limite, 1000)),))

    # ------------------------------------------------------------------ #
    # instalações (anônimas: um número aleatório que cada programa gera; sem convite nem chave)
    # ------------------------------------------------------------------ #
    @staticmethod
    def instalacao_valida(inst: str) -> bool:
        return bool(INSTALACAO_OK.match(inst or ""))

    def registrar_visto(self, inst: str, versao: str, so: str, canal: str) -> None:
        """Conta a instalação (só se mandou um número válido; sem número, fica anônima e não conta)."""
        if not self.instalacao_valida(inst):
            return
        self.banco.executar(
            "INSERT INTO instalacoes (id, visto, versao, so, canal, primeira) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET visto=excluded.visto, versao=excluded.versao, so=excluded.so, "
            "canal=excluded.canal", (inst, agora(), versao[:20], so[:20], canal, agora()))

    # ------------------------------------------------------------------ #
    # versões
    # ------------------------------------------------------------------ #
    def registrar_versao(self, zip_path: Path, versao: str, artefato: str, assinatura_hex: str,
                         canal: str = "beta", notas: str = "", minima: str = "0",
                         percentual: int = 100) -> dict[str, Any]:
        """Guarda um pacote JÁ ASSINADO. Confere hash e assinatura antes de aceitar."""
        if not VERSAO_OK.match(versao):
            raise ErroNegocio("versão deve ser como 0.6.0")
        if artefato not in ARTEFATOS:
            raise ErroNegocio("artefato deve ser 'fonte' ou 'exe'")
        if canal not in CANAIS:
            raise ErroNegocio("canal deve ser 'beta' ou 'estavel'")
        if not VERSAO_OK.match(minima) and minima != "0":
            raise ErroNegocio("versão mínima inválida")
        if not 1 <= percentual <= 100:
            raise ErroNegocio("percentual deve ficar entre 1 e 100")
        if self.banco.um("SELECT id FROM versoes WHERE versao = ? AND artefato = ?", (versao, artefato)):
            raise ErroNegocio(f"a versão {versao} ({artefato}) já foi publicada; versões não mudam. "
                              "Aumente o número da versão.")
        h = hashlib.sha256()
        with open(zip_path, "rb") as f:
            for bloco in iter(lambda: f.read(1 << 20), b""):
                h.update(bloco)
        sha, tam = h.hexdigest(), Path(zip_path).stat().st_size
        pub = self.chave_publica_hex()
        if not pub or not ed25519.verificar_hex(pub, mensagem_do_pacote(versao, artefato, sha, tam),
                                                assinatura_hex):
            raise ErroNegocio("assinatura inválida para este pacote; não foi publicado")
        destino = self.pacotes / versao / f"{artefato}.zip"
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(zip_path, destino)
        i = self.banco.executar(
            "INSERT INTO versoes (versao, artefato, canal, arquivo, sha256, tamanho, assinatura, notas, "
            "minima, percentual, publicada) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (versao, artefato, canal, str(destino.relative_to(self.dados)).replace("\\", "/"), sha, tam,
             assinatura_hex, notas, minima, percentual, agora()))
        self.evento("publicada", None, f"{versao} {artefato} ({canal})")
        return self.banco.um("SELECT * FROM versoes WHERE id = ?", (i,)) or {}

    def listar_versoes(self) -> list[dict[str, Any]]:
        v = self.banco.todos("SELECT * FROM versoes")
        v.sort(key=lambda r: (versao_tupla(r["versao"]), r["artefato"]), reverse=True)
        return v

    def _versoes_de(self, versao: str) -> list[dict[str, Any]]:
        v = self.banco.todos("SELECT * FROM versoes WHERE versao = ?", (versao,))
        if not v:
            raise ErroNegocio(f"versão {versao} não encontrada")
        return v

    def promover(self, versao: str, canal: str = "estavel") -> int:
        if canal not in CANAIS:
            raise ErroNegocio("canal deve ser 'beta' ou 'estavel'")
        n = len(self._versoes_de(versao))
        self.banco.executar("UPDATE versoes SET canal = ? WHERE versao = ?", (canal, versao))
        self.evento("promovida", None, f"{versao} -> {canal}")
        return n

    def retirar(self, versao: str) -> int:
        n = len(self._versoes_de(versao))
        self.banco.executar("UPDATE versoes SET canal = 'retirada' WHERE versao = ?", (versao,))
        self.evento("retirada", None, versao)
        return n

    def definir_percentual(self, versao: str, pct: int) -> None:
        if not 1 <= pct <= 100:
            raise ErroNegocio("percentual deve ficar entre 1 e 100")
        self._versoes_de(versao)
        self.banco.executar("UPDATE versoes SET percentual = ? WHERE versao = ?", (pct, versao))
        self.evento("percentual", None, f"{versao} = {pct}%")

    def definir_minima(self, versao: str, minima: str) -> None:
        if minima != "0" and not VERSAO_OK.match(minima):
            raise ErroNegocio("versão mínima inválida")
        self._versoes_de(versao)
        self.banco.executar("UPDATE versoes SET minima = ? WHERE versao = ?", (minima, versao))
        self.evento("minima", None, f"{versao} exige {minima}")

    def definir_notas(self, versao: str, notas: str) -> None:
        self._versoes_de(versao)
        self.banco.executar("UPDATE versoes SET notas = ? WHERE versao = ?", (notas[:5000], versao))

    @staticmethod
    def no_grupo(inst: str, versao: str, percentual: int) -> bool:
        """Liberação gradual determinística: a mesma instalação sempre cai do mesmo lado."""
        if percentual >= 100:
            return True
        b = int(hashlib.sha256(f"{inst}:{versao}".encode()).hexdigest()[:8], 16) % 100
        return b < percentual

    @staticmethod
    def _visiveis(canal: str) -> tuple[str, ...]:
        return ("beta", "estavel") if canal == "beta" else ("estavel",)

    def escolher_atualizacao(self, inst: str, canal: str, versao_atual: str,
                             artefato: str) -> Optional[dict[str, Any]]:
        """A versão mais nova que ESTA instalação pode receber (ou None)."""
        visiveis = self._visiveis(canal)
        candidatas = [
            v for v in self.banco.todos("SELECT * FROM versoes WHERE artefato = ?", (artefato,))
            if v["canal"] in visiveis
            and (v["canal"] == "beta" or self.no_grupo(inst or "anonimo", v["versao"], v["percentual"]))
        ]
        if not candidatas:
            return None
        melhor = max(candidatas, key=lambda v: versao_tupla(v["versao"]))
        return melhor if mais_nova(melhor["versao"], versao_atual) else None

    def pode_baixar(self, canal: str, versao: str, artefato: str) -> Optional[dict[str, Any]]:
        v = self.banco.um("SELECT * FROM versoes WHERE versao = ? AND artefato = ?", (versao, artefato))
        if v is None or artefato == "download":
            return None
        return v if v["canal"] in self._visiveis(canal) else None

    def download_atual(self) -> Optional[dict[str, Any]]:
        """O zip que a página pública oferece: o 'download' estável mais novo."""
        v = [r for r in self.banco.todos("SELECT * FROM versoes WHERE artefato = 'download' AND canal = 'estavel'")]
        return max(v, key=lambda r: versao_tupla(r["versao"])) if v else None

    def manifesto(self, inst: str, canal: str, versao_atual: str, artefato: str, so: str = "") -> dict[str, Any]:
        self.atualizar_cfg()
        self.registrar_visto(inst, versao_atual, so, canal)
        v = self.escolher_atualizacao(inst, canal, versao_atual, artefato) if artefato in ("fonte", "exe") else None
        saida: dict[str, Any] = {"atualizacao": None, "mensagem": self.cfg.aviso}
        if v is not None:
            saida["atualizacao"] = {k: v[k] for k in ("versao", "artefato", "canal", "sha256", "tamanho",
                                                       "assinatura", "notas", "minima", "publicada")}
        return saida

    def caminho_pacote(self, v: dict[str, Any]) -> Path:
        p = (self.dados / v["arquivo"]).resolve()
        p.relative_to(self.dados.resolve())  # nunca sair da pasta de dados
        return p

    # ------------------------------------------------------------------ #
    # relatórios enviados pelos amigos
    # ------------------------------------------------------------------ #
    def salvar_relatorio(self, inst: str, dados: bytes, resumo: str = "") -> dict[str, Any]:
        limite = self.cfg.limite_relatorio_kb * 1024
        if not dados or len(dados) > limite:
            raise ErroNegocio(f"relatório vazio ou maior que {self.cfg.limite_relatorio_kb} KB")
        nome = f"{datetime.now():%Y%m%d-%H%M%S}_{secrets.token_hex(4)}.zip"
        destino = self.relatorios_dir / nome
        destino.write_bytes(dados)
        quem = inst if self.instalacao_valida(inst) else "anonimo"
        i = self.banco.executar(
            "INSERT INTO relatorios (instalacao, criado, arquivo, resumo, tamanho) VALUES (?,?,?,?,?)",
            (quem, agora(), nome, resumo[:300], len(dados)))
        self.evento("relatorio", quem[:8], resumo[:120])
        # teto de armazenamento: guarda só os MAX_RELATORIOS mais recentes (spam não enche o disco)
        for r in self.banco.todos("SELECT id FROM relatorios ORDER BY id DESC LIMIT -1 OFFSET ?", (MAX_RELATORIOS,)):
            self.apagar_relatorio(r["id"])
        return {"id": i, "arquivo": nome}

    def listar_relatorios(self) -> list[dict[str, Any]]:
        return self.banco.todos(
            "SELECT id, criado, resumo, tamanho, substr(instalacao, 1, 8) AS instalacao FROM relatorios "
            "ORDER BY id DESC LIMIT 200")

    def caminho_relatorio(self, ident: int) -> Optional[Path]:
        r = self.banco.um("SELECT arquivo FROM relatorios WHERE id = ?", (ident,))
        if r is None:
            return None
        p = (self.relatorios_dir / r["arquivo"]).resolve()
        p.relative_to(self.relatorios_dir.resolve())
        return p if p.is_file() else None

    def apagar_relatorio(self, ident: int) -> bool:
        p = self.caminho_relatorio(ident)
        if p is not None:
            p.unlink()
        self.banco.executar("DELETE FROM relatorios WHERE id = ?", (ident,))
        return True

    # ------------------------------------------------------------------ #
    # backup e resumo
    # ------------------------------------------------------------------ #
    def backup(self) -> Path:
        """Copia o banco e a configuração para backups/ e mantém só os mais recentes.
        (Os pacotes já são arquivos; a chave PRIVADA nunca vai para backups: guarde-a à parte.)"""
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        destino = self.backups_dir / f"banco_{ts}.sqlite"
        self.banco.copiar_para(destino)
        if cfgmod.existe(self.dados):
            shutil.copy2(cfgmod.arquivo_config(self.dados), self.backups_dir / f"config_{ts}.json")
        for prefixo in ("banco_", "config_"):
            arqs = sorted(self.backups_dir.glob(prefixo + "*"), reverse=True)
            for velho in arqs[max(1, self.cfg.retencao_backups):]:
                velho.unlink()
        self.evento("backup", None, destino.name)
        return destino

    def listar_backups(self) -> list[str]:
        return [p.name for p in sorted(self.backups_dir.glob("banco_*.sqlite"), reverse=True)]

    def resumo(self) -> dict[str, Any]:
        limite_dia = datetime.now(timezone.utc).timestamp() - 86400
        inst = self.banco.todos("SELECT visto, versao FROM instalacoes")
        ativas = 0
        por_versao: dict[str, int] = {}
        for a in inst:
            try:
                if datetime.fromisoformat(a["visto"]).timestamp() >= limite_dia:
                    ativas += 1
                    por_versao[a["versao"]] = por_versao.get(a["versao"], 0) + 1
            except ValueError:
                pass
        espaco = sum(f.stat().st_size for f in self.pacotes.rglob("*") if f.is_file())
        versoes = self.listar_versoes()
        dl = self.download_atual()
        return {"instalacoes": len(inst), "instalacoes_ativas_24h": ativas, "ativas_por_versao": por_versao,
                "versoes": len({v["versao"] for v in versoes}),
                "ultima_estavel": next((v["versao"] for v in versoes if v["canal"] == "estavel"), None),
                "ultima_beta": next((v["versao"] for v in versoes if v["canal"] == "beta"), None),
                "download": dl["versao"] if dl else None,
                "pacotes_mb": round(espaco / 1048576, 1),
                "relatorios": len(self.listar_relatorios()), "backups": len(self.listar_backups()),
                "chave_publica": self.chave_publica_hex(), "prefixo": self.cfg.prefixo,
                "base": self.cfg.base, "pagina": self.cfg.pagina}

    def fechar(self) -> None:
        self.banco.fechar()
