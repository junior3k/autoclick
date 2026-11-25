# pyright: basic
"""Configuração do servidor e localização dos dados."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

RAIZ = Path(__file__).resolve().parent.parent


def pasta_dados() -> Path:
    """Onde ficam banco, pacotes, chaves e backups (padrão: servidor/dados)."""
    return Path(os.environ.get("AUTOCLICK_SERVIDOR_DADOS") or (RAIZ / "servidor" / "dados"))


@dataclass
class Config:
    host: str = "127.0.0.1"          # só a própria máquina: o cloudflared é quem expõe
    porta: int = 8765
    prefixo: str = ""                # ex.: ac-3fa9c1d2b7: TODAS as rotas ficam sob /<prefixo>/
    dominio: str = ""                # ex.: updates.seudominio.com (ou http://127.0.0.1:8765 em testes)
    admin_token_hash: str = ""       # SHA-256 do token do painel (o token em si não é guardado)
    confiar_cf_ip: bool = True       # usar CF-Connecting-IP (o túnel entrega o IP real do visitante)
    limite_relatorio_kb: int = 5120
    retencao_backups: int = 14
    aviso: str = ""                  # mensagem exibida aos clientes (ex.: manutenção)

    @property
    def origem(self) -> str:
        d = self.dominio.strip().rstrip("/")
        if not d:
            d = "SEU-DOMINIO"
        if not d.lower().startswith(("http://", "https://")):
            d = "https://" + d
        return d

    @property
    def pagina(self) -> str:
        """Link público de download (qualquer pessoa pode abrir)."""
        return f"{self.origem}/download"

    @property
    def base(self) -> str:
        """Endereço da API que o programa usa (embutido no .exe)."""
        return f"{self.pagina}/api/v1"

    @property
    def painel(self) -> str:
        return f"{self.origem}/{self.prefixo}/painel"


def arquivo_config(dados: Optional[Path] = None) -> Path:
    return (dados or pasta_dados()) / "config.json"


def existe(dados: Optional[Path] = None) -> bool:
    return arquivo_config(dados).is_file()


def carregar(dados: Optional[Path] = None) -> Config:
    p = arquivo_config(dados)
    if not p.is_file():
        raise FileNotFoundError("servidor ainda não instalado: rode  python -m servidor instalar")
    bruto = json.loads(p.read_text(encoding="utf-8"))
    campos = Config.__dataclass_fields__
    return Config(**{k: v for k, v in bruto.items() if k in campos})


def salvar(cfg: Config, dados: Optional[Path] = None) -> None:
    p = arquivo_config(dados)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")
