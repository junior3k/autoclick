# pyright: basic
"""Instalação e operação do servidor no PC de casa."""
from __future__ import annotations

import hashlib
import secrets
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from autoclick import ed25519

from . import config as cfgmod
from .config import Config, RAIZ
from .nucleo import Nucleo, hash_token
from .publicar import escrever_chave_publica, escrever_url_padrao


def instalar(dominio: str, porta: int = 8765, dados: Optional[Path] = None,
             raiz: Path = RAIZ) -> tuple[Config, str]:
    """Primeira instalação: gera chaves, prefixo único e token do painel. Devolve (config, token).
    Seguro para repetir: não sobrescreve chaves nem prefixo já existentes."""
    dados = Path(dados) if dados else cfgmod.pasta_dados()
    dados.mkdir(parents=True, exist_ok=True)
    priv, pub = dados / "chave_privada.txt", dados / "chave_publica.txt"
    if not priv.is_file():
        semente = ed25519.gerar_semente()
        priv.write_text(semente.hex(), encoding="utf-8")
        try:
            priv.chmod(0o600)
        except OSError:
            pass
        pub.write_text(ed25519.chave_publica(semente).hex(), encoding="utf-8")
    elif not pub.is_file():
        pub.write_text(ed25519.chave_publica(bytes.fromhex(priv.read_text().strip())).hex(), encoding="utf-8")
    token = ""
    if cfgmod.existe(dados):
        cfg = cfgmod.carregar(dados)
        if dominio:
            cfg.dominio = dominio
    else:
        cfg = Config(prefixo="ac-" + secrets.token_hex(6), dominio=dominio, porta=porta)
    if not cfg.admin_token_hash:
        token = "at_" + secrets.token_urlsafe(32)
        cfg.admin_token_hash = hash_token(token)
    if porta:
        cfg.porta = porta
    cfgmod.salvar(cfg, dados)
    escrever_chave_publica(pub.read_text(encoding="utf-8").strip(), raiz)
    escrever_url_padrao(cfg.base, raiz)
    return cfg, token


def novo_token(dados: Optional[Path] = None) -> str:
    cfg = cfgmod.carregar(dados)
    token = "at_" + secrets.token_urlsafe(32)
    cfg.admin_token_hash = hash_token(token)
    cfgmod.salvar(cfg, dados)
    return token


def trecho_cloudflared(cfg: Config) -> str:
    host = cfg.origem.replace("https://", "").replace("http://", "").strip("/")
    return (f"  # adicione em 'ingress:' ANTES da regra final (http_status:404) do config.yml:\n"
            f"  - hostname: {host}\n"
            f"    path: ^/(download|{cfg.prefixo})(/|$)\n"
            f"    service: http://127.0.0.1:{cfg.porta}\n")


def agendar_backup_diario(n: Nucleo, parar: threading.Event, hora_s: int = 24 * 3600,
                          log: Callable[[str], None] = print) -> threading.Thread:
    """Thread que faz backup ao subir e depois a cada 24 h."""
    def laco() -> None:
        while not parar.is_set():
            try:
                log(f"backup: {n.backup().name}")
            except Exception as e:  # noqa: BLE001
                log(f"backup falhou: {e}")
            parar.wait(hora_s)
    t = threading.Thread(target=laco, daemon=True, name="backup")
    t.start()
    return t


def registrar_tarefa(raiz: Path = RAIZ) -> str:
    """Cria a tarefa do Agendador do Windows que sobe o servidor no logon (só Windows)."""
    bat = raiz / "iniciar_servidor.vbs"
    cmd = ["schtasks", "/Create", "/F", "/SC", "ONLOGON", "/RL", "LIMITED", "/TN", "AutoclickServidor",
           "/TR", f'wscript.exe "{bat}"']
    r = subprocess.run(cmd, capture_output=True, text=True)
    return (r.stdout + r.stderr).strip() or f"código {r.returncode}"
