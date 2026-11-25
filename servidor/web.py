# pyright: basic
"""Camada HTTP.

Público (sem convite, sem chave):
  /download                              página com o botão Baixar
  /download/arquivo                      zip da última versão estável
  /download/api/v1/saude | manifesto | pacote/<versao>/<artefato> | relatorio (POST)
Administração (token do painel, caminho secreto):
  /<prefixo>/admin/...   /<prefixo>/painel

Os manipuladores usam só a API do Starlette (a base do FastAPI); `criar_app` devolve um app
FastAPI quando ele está instalado e Starlette puro caso contrário. Qualquer outro caminho: 404 vazio.
Limites por IP (folgados para uso normal) protegem o seu upload de casa contra robôs.
"""
from __future__ import annotations

import hmac
import html
import json
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import unquote

from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from starlette.routing import Route

from .limitador import Limitador
from .nucleo import ARTEFATOS, ErroNegocio, Nucleo, hash_token

PAINEL = Path(__file__).resolve().parent / "painel"
SITE = Path(__file__).resolve().parent / "site"
ICONE = Path(__file__).resolve().parent.parent / "autoclick" / "interface" / "recursos" / "icone.png"
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
       "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
CSP_SITE = "default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
SEGURANCA = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
             "Cache-Control": "no-store", "X-Frame-Options": "DENY"}


class Limites:
    """Limites por IP. Valores folgados: uso normal nunca chega perto."""

    def __init__(self, api: int = 300, downloads: int = 30, relatorios: int = 5, falhas_admin: int = 10) -> None:
        self.api = Limitador(max_pedidos=api, janela_pedidos=60.0)
        self.downloads = Limitador(max_pedidos=downloads, janela_pedidos=3600.0)
        self.relatorios = Limitador(max_pedidos=relatorios, janela_pedidos=3600.0)
        self.admin = Limitador(max_falhas=falhas_admin)


def _json(dados: Any, status: int = 200) -> Response:
    return JSONResponse(dados, status_code=status, headers=SEGURANCA)


def _erro(status: int, msg: str) -> Response:
    return _json({"erro": msg}, status)


def _nao_achei() -> Response:
    return PlainTextResponse("", status_code=404, headers=SEGURANCA)


def _bearer(req: Request) -> str:
    h = req.headers.get("authorization", "")
    return h[7:].strip() if h.lower().startswith("bearer ") else ""


def _pagina_html(n: Nucleo) -> str:
    v = n.download_atual()
    if v is None:
        corpo = '<p class="vazio">Ainda não há versão disponível para baixar. Volte em breve.</p>'
    else:
        mb = v["tamanho"] / 1048576
        notas = html.escape(v["notas"] or "").replace("\n", "<br>")
        corpo = (f'<a class="botao" href="/download/arquivo">⬇ Baixar para Windows</a>'
                 f'<p class="dica">Versão {html.escape(v["versao"])} · {mb:.0f} MB</p>'
                 '<ol><li>Extraia o <b>.zip</b> inteiro numa pasta (não rode de dentro do zip).</li>'
                 '<li>Dê dois cliques em <b>Autoclick.exe</b>.</li>'
                 '<li>Para atualizar depois: Configurações → Atualizações → Verificar.</li></ol>'
                 '<p class="dica">Se o Windows avisar “protegeu seu computador”: clique em '
                 '<b>Mais informações</b> e depois em <b>Executar assim mesmo</b>.</p>'
                 + (f'<details><summary>Novidades</summary><p>{notas}</p></details>' if notas else "")
                 + f'<details><summary>Conferir o arquivo</summary>SHA-256:<br><code>{html.escape(v["sha256"])}</code></details>')
    return ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex"><title>Autoclick Inteligente</title>'
            '<link rel="stylesheet" href="/download/pagina.css"></head><body><main>'
            '<img src="/download/icone.png" alt=""><h1>Autoclick Inteligente</h1>'
            f'<p class="sub">Automação de cliques que reconhece botões na tela</p>{corpo}</main></body></html>')


def criar_app(n: Nucleo, limites: Optional[Limites] = None) -> Any:
    lim = limites or Limites()
    p = "/" + n.cfg.prefixo
    if not n.cfg.prefixo:
        raise RuntimeError("servidor sem prefixo: rode  python -m servidor instalar")

    def ip_de(req: Request) -> str:
        if n.cfg.confiar_cf_ip:
            v = req.headers.get("cf-connecting-ip")
            if v:
                return v.strip()[:64]
        return req.client.host if req.client else "?"

    def limitado(l: Limitador, req: Request) -> Optional[Response]:
        return None if l.permitir(ip_de(req)) else _erro(429, "muitos pedidos; tente mais tarde")

    # --- público -------------------------------------------------------- #
    async def pagina(req: Request) -> Response:
        r = limitado(lim.api, req)
        if r:
            return r
        return Response(_pagina_html(n), media_type="text/html; charset=utf-8",
                        headers={**SEGURANCA, "Content-Security-Policy": CSP_SITE})

    def fixo(arq: Path, tipo: str) -> Callable[[Request], Any]:
        async def h(req: Request) -> Response:
            if not arq.is_file():
                return _nao_achei()
            return Response(arq.read_bytes(), media_type=tipo,
                            headers={**SEGURANCA, "Cache-Control": "public, max-age=3600"})
        return h

    async def arquivo(req: Request) -> Response:
        r = limitado(lim.downloads, req)
        if r:
            return r
        v = n.download_atual()
        if v is None:
            return _nao_achei()
        arq = n.caminho_pacote(v)
        if not arq.is_file():
            return _nao_achei()
        n.evento("download_site", None, f"{v['versao']}")
        return FileResponse(arq, media_type="application/zip", filename=f"Autoclick-{v['versao']}.zip",
                            headers=SEGURANCA)

    async def saude(req: Request) -> Response:
        r = limitado(lim.api, req)
        return r or _json({"ok": True})

    async def manifesto(req: Request) -> Response:
        r = limitado(lim.api, req)
        if r:
            return r
        q = req.query_params
        artefato = q.get("artefato", "fonte")
        if artefato not in ("fonte", "exe"):
            return _erro(400, "artefato inválido")
        canal = "beta" if q.get("canal") == "beta" else "estavel"
        inst = req.headers.get("x-instalacao", "")
        return _json(n.manifesto(inst, canal, q.get("atual", "0")[:20], artefato, q.get("so", "")))

    async def pacote(req: Request) -> Response:
        r = limitado(lim.api, req)
        if r:
            return r
        canal = "beta" if req.query_params.get("canal") == "beta" else "estavel"
        v = n.pode_baixar(canal, req.path_params["versao"], req.path_params["artefato"])
        if v is None:
            return _nao_achei()
        arq = n.caminho_pacote(v)
        if not arq.is_file():
            return _nao_achei()
        rg = req.headers.get("range", "")
        if not rg or rg.startswith("bytes=0-"):
            n.evento("download", req.headers.get("x-instalacao", "")[:8] or None, f"{v['versao']} {v['artefato']}")
        return FileResponse(arq, media_type="application/zip", filename=f"autoclick_{v['versao']}_{v['artefato']}.zip",
                            headers=SEGURANCA)

    async def relatorio(req: Request) -> Response:
        r = limitado(lim.relatorios, req)
        if r:
            return r
        limite = n.cfg.limite_relatorio_kb * 1024
        try:
            tam = int(req.headers.get("content-length", "0"))
        except ValueError:
            tam = 0
        if tam <= 0 or tam > limite:
            return _erro(413, "relatório vazio ou grande demais")
        corpo = bytearray()
        async for bloco in req.stream():
            corpo += bloco
            if len(corpo) > limite:
                return _erro(413, "relatório grande demais")
        if bytes(corpo[:2]) != b"PK":
            return _erro(400, "esperado um arquivo .zip")
        resumo = unquote(req.headers.get("x-resumo", ""))[:300]
        try:
            res = n.salvar_relatorio(req.headers.get("x-instalacao", ""), bytes(corpo), resumo)
        except ErroNegocio as e:
            return _erro(400, str(e))
        return _json({"ok": True, "id": res["id"]})

    # --- administração (token) ----------------------------------------- #
    def admin_ou_erro(req: Request) -> Optional[Response]:
        n.atualizar_cfg()
        ip = ip_de(req)
        if lim.admin.bloqueado(ip):
            return _erro(429, "muitas tentativas")
        tok = _bearer(req)
        esperado = n.cfg.admin_token_hash
        if not tok or not esperado or not hmac.compare_digest(hash_token(tok), esperado):
            lim.admin.falha(ip)
            return _erro(401, "token inválido")
        lim.admin.sucesso(ip)
        return None

    def admin(func: Callable[..., Any]) -> Callable[[Request], Any]:
        async def envoltorio(req: Request) -> Response:
            err = admin_ou_erro(req)
            if err:
                return err
            corpo: dict[str, Any] = {}
            if req.method in ("POST", "PUT", "PATCH"):
                try:
                    bruto = await req.body()
                    corpo = json.loads(bruto.decode("utf-8")) if bruto else {}
                    if not isinstance(corpo, dict):
                        return _erro(400, "corpo deve ser um objeto JSON")
                except ValueError:
                    return _erro(400, "JSON inválido")
            try:
                return _json(func(req, corpo))
            except ErroNegocio as e:
                return _erro(400, str(e))
        return envoltorio

    def ident(req: Request) -> str:
        return req.path_params["ident"]

    def a_status(req: Request, c: dict[str, Any]) -> Any:
        r = n.resumo()
        r["aviso"] = n.cfg.aviso
        return r

    def a_versoes(req: Request, c: dict[str, Any]) -> Any:
        return [{k: v[k] for k in v if k != "arquivo"} for v in n.listar_versoes()]

    def a_promover(req: Request, c: dict[str, Any]) -> Any:
        return {"pacotes": n.promover(ident(req), str(c.get("canal", "estavel")))}

    def a_retirar(req: Request, c: dict[str, Any]) -> Any:
        return {"pacotes": n.retirar(ident(req))}

    def a_percentual(req: Request, c: dict[str, Any]) -> Any:
        try:
            valor = int(c.get("valor", 0))
        except (TypeError, ValueError):
            raise ErroNegocio("percentual inválido")
        n.definir_percentual(ident(req), valor); return {"ok": True}

    def a_minima(req: Request, c: dict[str, Any]) -> Any:
        n.definir_minima(ident(req), str(c.get("minima", "0"))); return {"ok": True}

    def a_notas(req: Request, c: dict[str, Any]) -> Any:
        n.definir_notas(ident(req), str(c.get("notas", ""))); return {"ok": True}

    def a_relatorios(req: Request, c: dict[str, Any]) -> Any:
        return n.listar_relatorios()

    def a_apagar_relatorio(req: Request, c: dict[str, Any]) -> Any:
        n.apagar_relatorio(int(ident(req))); return {"ok": True}

    def a_eventos(req: Request, c: dict[str, Any]) -> Any:
        return n.eventos(200)

    def a_backup(req: Request, c: dict[str, Any]) -> Any:
        return {"arquivo": n.backup().name, "backups": n.listar_backups()}

    def a_aviso(req: Request, c: dict[str, Any]) -> Any:
        from . import config as cfgmod
        n.cfg.aviso = str(c.get("texto", ""))[:300]
        cfgmod.salvar(n.cfg, n.dados)
        n._cfg_mtime = n._mtime_cfg()
        return {"ok": True}

    async def baixar_relatorio(req: Request) -> Response:
        err = admin_ou_erro(req)
        if err:
            return err
        try:
            arq = n.caminho_relatorio(int(req.path_params["ident"]))
        except ValueError:
            return _nao_achei()
        if arq is None:
            return _nao_achei()
        return FileResponse(arq, media_type="application/zip", filename=arq.name, headers=SEGURANCA)

    def estatico(nome: str, tipo: str) -> Callable[[Request], Any]:
        async def h(req: Request) -> Response:
            arq = PAINEL / nome
            if not arq.is_file():
                return _nao_achei()
            return Response(arq.read_bytes(), media_type=tipo,
                            headers={**SEGURANCA, "Content-Security-Policy": CSP})
        return h

    D = "/download"
    rotas = [
        Route(D, pagina, methods=["GET"]),
        Route(D + "/", pagina, methods=["GET"]),
        Route(D + "/pagina.css", fixo(SITE / "pagina.css", "text/css; charset=utf-8"), methods=["GET"]),
        Route(D + "/icone.png", fixo(ICONE, "image/png"), methods=["GET"]),
        Route(D + "/arquivo", arquivo, methods=["GET"]),
        Route(D + "/api/v1/saude", saude, methods=["GET"]),
        Route(D + "/api/v1/manifesto", manifesto, methods=["GET"]),
        Route(D + "/api/v1/pacote/{versao}/{artefato}", pacote, methods=["GET"]),
        Route(D + "/api/v1/relatorio", relatorio, methods=["POST"]),
        Route(f"{p}/painel", estatico("index.html", "text/html; charset=utf-8"), methods=["GET"]),
        Route(f"{p}/painel.js", estatico("painel.js", "text/javascript; charset=utf-8"), methods=["GET"]),
        Route(f"{p}/painel.css", estatico("painel.css", "text/css; charset=utf-8"), methods=["GET"]),
        Route(f"{p}/admin/status", admin(a_status), methods=["GET"]),
        Route(f"{p}/admin/versoes", admin(a_versoes), methods=["GET"]),
        Route(f"{p}/admin/versoes/{{ident}}/promover", admin(a_promover), methods=["POST"]),
        Route(f"{p}/admin/versoes/{{ident}}/retirar", admin(a_retirar), methods=["POST"]),
        Route(f"{p}/admin/versoes/{{ident}}/percentual", admin(a_percentual), methods=["POST"]),
        Route(f"{p}/admin/versoes/{{ident}}/minima", admin(a_minima), methods=["POST"]),
        Route(f"{p}/admin/versoes/{{ident}}/notas", admin(a_notas), methods=["POST"]),
        Route(f"{p}/admin/relatorios", admin(a_relatorios), methods=["GET"]),
        Route(f"{p}/admin/relatorios/{{ident}}", baixar_relatorio, methods=["GET"]),
        Route(f"{p}/admin/relatorios/{{ident}}/apagar", admin(a_apagar_relatorio), methods=["POST"]),
        Route(f"{p}/admin/eventos", admin(a_eventos), methods=["GET"]),
        Route(f"{p}/admin/backup", admin(a_backup), methods=["POST"]),
        Route(f"{p}/admin/aviso", admin(a_aviso), methods=["POST"]),
    ]

    async def sem_rota(req: Request, exc: Exception) -> Response:
        return _nao_achei()

    handlers: dict[Any, Any] = {404: sem_rota, 405: sem_rota}
    try:
        from fastapi import FastAPI  # pyright: ignore[reportMissingImports]
        return FastAPI(routes=rotas, exception_handlers=handlers, docs_url=None, redoc_url=None,
                       openapi_url=None)
    except ImportError:
        from starlette.applications import Starlette
        return Starlette(routes=rotas, exception_handlers=handlers)
