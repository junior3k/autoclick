# pyright: basic
"""Linha de comando do servidor:  python -m servidor <comando>"""
from __future__ import annotations

import argparse
import json
import sys
import threading

from . import config as cfgmod
from . import operacao, publicar as pub
from .nucleo import ErroNegocio, Nucleo


def _tabela(linhas: list[dict], colunas: list[str]) -> None:
    if not linhas:
        print("(vazio)")
        return
    larg = {c: max(len(c), *(len(str(l.get(c) or "")) for l in linhas)) for c in colunas}
    print("  ".join(c.upper().ljust(larg[c]) for c in colunas))
    for l in linhas:
        print("  ".join(str(l.get(c) or "").ljust(larg[c]) for c in colunas))


def _parser() -> argparse.ArgumentParser:
    raiz = argparse.ArgumentParser(prog="servidor", description="Servidor de atualizações do Autoclick")
    s = raiz.add_subparsers(dest="cmd", required=True)
    i = s.add_parser("instalar", help="primeira instalação: chaves, prefixo secreto e token do painel")
    i.add_argument("--dominio", default="", help="ex.: updates.seudominio.com")
    i.add_argument("--porta", type=int, default=8765)
    i.add_argument("--tarefa", action="store_true", help="registra no Agendador do Windows (iniciar no logon)")
    r = s.add_parser("rodar", help="sobe o servidor (uvicorn)")
    r.add_argument("--porta", type=int)
    s.add_parser("status", help="resumo e endereços")
    s.add_parser("link", help="mostra o link público de download e a API")
    s.add_parser("versoes", help="lista versões publicadas")
    p = s.add_parser("publicar", help="testa, empacota, assina e publica a versão atual (--exe também constrói o .exe)")
    p.add_argument("--versao"); p.add_argument("--subir", choices=["corrigir", "menor", "maior"], default="corrigir")
    p.add_argument("--exe", action="store_true"); p.add_argument("--sem-testes", action="store_true")
    p.add_argument("--canal", default="beta", choices=["beta", "estavel"])
    p.add_argument("--notas", default=""); p.add_argument("--minima", default="0")
    pr = s.add_parser("promover"); pr.add_argument("versao"); pr.add_argument("--canal", default="estavel")
    rt = s.add_parser("retirar"); rt.add_argument("versao")
    pc = s.add_parser("percentual"); pc.add_argument("versao"); pc.add_argument("valor", type=int)
    mi = s.add_parser("minima", help="versão mínima obrigatória"); mi.add_argument("versao"); mi.add_argument("minima")
    s.add_parser("backup"); s.add_parser("relatorios"); s.add_parser("eventos"); s.add_parser("novo-token")
    s.add_parser("exportar-chave", help="mostra a chave pública")
    av = s.add_parser("aviso", help="mensagem mostrada aos clientes (vazio limpa)"); av.add_argument("texto", nargs="?", default="")
    return raiz


def _rodar(n: Nucleo, porta: int | None) -> int:
    try:
        import uvicorn
        from .web import criar_app
    except ImportError as e:
        print(f"Falta instalar dependências do servidor: {e}\n  uv sync --extra servidor")
        return 2
    if not n.cfg.prefixo:
        print("Servidor não instalado. Rode: python -m servidor instalar")
        return 2
    parar = threading.Event()
    operacao.agendar_backup_diario(n, parar)
    print(f"Servidor em http://{n.cfg.host}:{porta or n.cfg.porta}/{n.cfg.prefixo}/  (Ctrl+C para parar)")
    try:
        uvicorn.run(criar_app(n), host=n.cfg.host, port=porta or n.cfg.porta, log_level="warning",
                    proxy_headers=False, server_header=False)
    finally:
        parar.set()
    return 0


def principal(argv: list[str] | None = None) -> int:
    a = _parser().parse_args(argv)
    try:
        if a.cmd == "instalar":
            cfg, token = operacao.instalar(a.dominio, a.porta)
            n = Nucleo()
            print(f"Chave pública: {n.chave_publica_hex()}\n(gravada em autoclick/chave_publica.py)")
            print(f"Link público de download: {cfg.pagina}")
            print(f"API (embutida no programa): {cfg.base}")
            if token:
                print(f"\nTOKEN DO PAINEL (aparece só agora, guarde!):\n  {token}")
            print(f"\nPainel (secreto): {cfg.painel}")
            print("\nCloudflared:\n" + operacao.trecho_cloudflared(cfg))
            print(f"Guarde uma cópia SEGURA de {n.arquivo_chave_privada()} (sem ela não dá para publicar).")
            if a.tarefa:
                print("Agendador:", operacao.registrar_tarefa())
            return 0
        if not cfgmod.existe():
            print("Servidor não instalado. Rode: python -m servidor instalar --dominio SEU.DOMINIO")
            return 2
        if a.cmd == "novo-token":
            print("Novo token do painel (o anterior deixou de valer):\n  " + operacao.novo_token())
            return 0
        n = Nucleo()
        try:
            if a.cmd == "rodar":
                return _rodar(n, a.porta)
            if a.cmd == "status":
                print(json.dumps(n.resumo(), indent=2, ensure_ascii=False))
            elif a.cmd == "link":
                print(f"Link público de download: {n.cfg.pagina}\nAPI do programa: {n.cfg.base}\nPainel: {n.cfg.painel}")
            elif a.cmd == "versoes":
                _tabela(n.listar_versoes(), ["versao", "artefato", "canal", "percentual", "minima", "publicada"])
            elif a.cmd == "publicar":
                pub.publicar(n, a.versao, a.subir, a.exe, not a.sem_testes, a.canal, a.notas, a.minima)
            elif a.cmd == "promover":
                print(f"{n.promover(a.versao, a.canal)} pacote(s) -> {a.canal}")
            elif a.cmd == "retirar":
                print(f"{n.retirar(a.versao)} pacote(s) retirados")
            elif a.cmd == "percentual":
                n.definir_percentual(a.versao, a.valor); print("ok")
            elif a.cmd == "minima":
                n.definir_minima(a.versao, a.minima); print("ok")
            elif a.cmd == "backup":
                print(n.backup())
            elif a.cmd == "relatorios":
                _tabela(n.listar_relatorios(), ["id", "criado", "amigo", "tamanho", "resumo"])
            elif a.cmd == "eventos":
                _tabela(n.eventos(50), ["t", "tipo", "amigo", "detalhe"])
            elif a.cmd == "exportar-chave":
                print(n.chave_publica_hex())
            elif a.cmd == "aviso":
                n.cfg.aviso = a.texto; cfgmod.salvar(n.cfg, n.dados); print("ok")
        finally:
            n.fechar()
        return 0
    except ErroNegocio as e:
        print(f"Erro: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(principal())
