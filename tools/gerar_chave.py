# pyright: basic
"""Gera o par de chaves de assinatura das atualizações (rode UMA vez).

  python tools/gerar_chave.py                      mostra a chave privada e a pública
  python tools/gerar_chave.py --escrever --url https://ac.cabro.me
      também grava a pública e o endereço dentro do programa (autoclick/chave_publica.py e
      autoclick/servidor_padrao.py)

A chave PRIVADA vai só para o segredo AC_CHAVE_PRIVADA do GitHub (Settings > Secrets > Actions) e para
uma cópia fora do PC (gerenciador de senhas). Nunca a coloque no repositório.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from autoclick import ed25519  # noqa: E402


def escrever(pub_hex: str, url: str, raiz: Path = RAIZ) -> None:
    p = raiz / "autoclick" / "chave_publica.py"
    p.write_text(re.sub(r'(?m)^CHAVE_PUBLICA_HEX\s*=.*$', f'CHAVE_PUBLICA_HEX = "{pub_hex}"',
                        p.read_text(encoding="utf-8"), count=1), encoding="utf-8")
    if url:
        q = raiz / "autoclick" / "servidor_padrao.py"
        q.write_text(re.sub(r'(?m)^URL_PADRAO\s*=.*$', f'URL_PADRAO = "{url.rstrip("/")}"',
                            q.read_text(encoding="utf-8"), count=1), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--escrever", action="store_true", help="grava a chave pública (e a URL) no programa")
    ap.add_argument("--url", default="", help="endereço do site de downloads, ex.: https://ac.cabro.me")
    a = ap.parse_args(argv)
    semente = ed25519.gerar_semente()
    pub = ed25519.chave_publica(semente).hex()
    print("CHAVE PRIVADA (segredo AC_CHAVE_PRIVADA; guarde uma cópia; NUNCA commite):")
    print("  " + semente.hex())
    print("CHAVE PÚBLICA (vai dentro do programa; não é segredo):")
    print("  " + pub)
    if a.escrever:
        escrever(pub, a.url)
        print("\nGravado em autoclick/chave_publica.py" + (" e autoclick/servidor_padrao.py" if a.url else "")
              + ". Faça o commit desses arquivos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
