# pyright: basic
"""Monta tudo de uma versão para publicar no GitHub: pacotes, manifesto assinado e o site de download.

Usado pelo workflow .github/workflows/publicar.yml (e dá para rodar à mão para testar):

  python tools/montar_release.py --tag v0.13.0 --repo USUARIO/REPO --dominio ac.cabro.me \\
         --dist dist/Autoclick --saida _release

A chave privada vem da variável de ambiente AC_CHAVE_PRIVADA (64 caracteres hexadecimais).
Saída em --saida:  arquivos/ (vão para a Release)   site/ (vai para o GitHub Pages)   notas.md
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any, Optional

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from autoclick import ed25519  # noqa: E402
from autoclick.atualizacao import mais_nova, mensagem_do_pacote  # noqa: E402

LEIA_ME = """AUTOCLICK INTELIGENTE - como usar

1. Extraia ESTE .zip inteiro numa pasta (ex.: C:\\Autoclick). Nao rode de dentro do zip.
2. De dois cliques em Autoclick.exe.
   (Se o Windows avisar "protegeu seu computador": clique em "Mais informacoes" e depois
   "Executar assim mesmo".)
3. Para atualizar no futuro: Configuracoes > Atualizacoes > Verificar atualizacao.
   Seus botoes, perfis e gravacoes nunca sao apagados nas atualizacoes.
"""
VERSAO_OK = re.compile(r"^\d+\.\d+\.\d+$")


class ErroRelease(Exception):
    pass


def versao_do_codigo(raiz: Path = RAIZ) -> str:
    m = re.search(r'__version__\s*=\s*"([^"]+)"', (raiz / "autoclick" / "__init__.py").read_text(encoding="utf-8"))
    if not m:
        raise ErroRelease("não achei __version__ em autoclick/__init__.py")
    return m.group(1)


def versao_da_tag(tag: str) -> str:
    v = tag[1:] if tag[:1] in ("v", "V") else tag
    if not VERSAO_OK.match(v):
        raise ErroRelease(f"a tag '{tag}' não é do tipo v0.13.0")
    return v


def conferir_tag(tag: str, raiz: Path = RAIZ) -> str:
    """A tag precisa ser igual à versão do código (v0.13.0 <-> 0.13.0). Devolve a versão."""
    v, codigo = versao_da_tag(tag), versao_do_codigo(raiz)
    if v != codigo:
        raise ErroRelease(f"a tag {tag} não bate com a versão do código ({codigo}). "
                          "Ajuste autoclick/__init__.py e pyproject.toml, ou crie a tag certa.")
    return v


def notas_do_changelog(versao: str, raiz: Path = RAIZ) -> str:
    p = raiz / "CHANGELOG.md"
    if not p.is_file():
        return ""
    m = re.search(rf"(?ms)^##\s*\[?v?{re.escape(versao)}\]?[^\n]*\n(.*?)(?=^##\s|\Z)", p.read_text(encoding="utf-8"))
    return m.group(1).strip() if m else ""


def zip_atualizacao(origem: Path, destino: Path) -> Path:
    """Conteúdo de dist/Autoclick na raiz do zip (é o que o programa aplica ao se atualizar)."""
    if not (origem / "Autoclick.exe").is_file():
        raise ErroRelease(f"{origem}/Autoclick.exe não existe: construa o .exe antes")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(origem.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(origem).as_posix())
    return destino


def zip_download(origem: Path, destino: Path) -> Path:
    """Pasta Autoclick/ completa + LEIA-ME (é o que o amigo baixa na página)."""
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(origem.rglob("*")):
            if f.is_file():
                z.write(f, "Autoclick/" + f.relative_to(origem).as_posix())
        z.writestr("Autoclick/LEIA-ME.txt", LEIA_ME)
    return destino


def sha256_de(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def assinar_pacote(semente_hex: str, versao: str, artefato: str, zip_path: Path) -> dict[str, Any]:
    try:
        semente = bytes.fromhex(semente_hex.strip())
    except ValueError:
        semente = b""
    if len(semente) != 32:
        raise ErroRelease("a chave privada (AC_CHAVE_PRIVADA) não tem 64 caracteres hexadecimais")
    sha, tam = sha256_de(zip_path), zip_path.stat().st_size
    assin = ed25519.assinar(semente, mensagem_do_pacote(versao, artefato, sha, tam)).hex()
    return {"versao": versao, "artefato": artefato, "sha256": sha, "tamanho": tam, "assinatura": assin}


def url_da_release(repo: str, tag: str, nome: str) -> str:
    return f"https://github.com/{repo}/releases/download/{tag}/{nome}"


def montar_manifesto(info: dict[str, Any], url: str, notas: str, config: dict[str, Any]) -> dict[str, Any]:
    return {"mensagem": str(config.get("mensagem", "")),
            "atualizacoes": {info["artefato"]: {**info, "url": url, "canal": "estavel", "notas": notas,
                                                "minima": str(config.get("minima", "0") or "0")}}}


def pagina_html(versao: str, tamanho: int, sha: str, notas: str, url_download: str, mensagem: str = "") -> str:
    e = html.escape
    aviso = f'<p class="aviso">{e(mensagem)}</p>' if mensagem else ""
    notas_html = (f'<details><summary>Novidades</summary><p>{e(notas).replace(chr(10), "<br>")}</p></details>'
                  if notas else "")
    return ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex"><title>Autoclick Inteligente</title>'
            '<link rel="icon" href="icone.png"><link rel="stylesheet" href="pagina.css"></head><body><main>'
            '<img src="icone.png" alt=""><h1>Autoclick Inteligente</h1>'
            '<p class="sub">Automação de cliques que reconhece botões na tela</p>' + aviso +
            f'<a class="botao" href="{e(url_download)}">⬇ Baixar para Windows</a>'
            f'<p class="dica">Versão {e(versao)} · {tamanho / 1048576:.0f} MB</p>'
            '<ol><li>Extraia o <b>.zip</b> inteiro numa pasta (não rode de dentro do zip).</li>'
            '<li>Dê dois cliques em <b>Autoclick.exe</b>.</li>'
            '<li>Para atualizar depois: Configurações → Atualizações → Verificar.</li></ol>'
            '<p class="dica">Se o Windows avisar “protegeu seu computador”: clique em '
            '<b>Mais informações</b> e depois em <b>Executar assim mesmo</b>.</p>' + notas_html +
            f'<details><summary>Conferir o arquivo</summary>SHA-256:<br><code>{e(sha)}</code></details>'
            '</main></body></html>')


def versao_do_manifesto(caminho: Optional[Path]) -> str:
    """Versão do manifesto que já está no ar ('' se não há ou está ilegível)."""
    if caminho is None or not caminho.is_file():
        return ""
    try:
        d = json.loads(caminho.read_text(encoding="utf-8"))
        return str(d["atualizacoes"]["exe"]["versao"])
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def montar(tag: str, repo: str, saida: Path, semente_hex: str, dist: Optional[Path] = None,
           dominio: str = "", raiz: Path = RAIZ, atual: Optional[Path] = None) -> dict[str, Any]:
    """Gera arquivos/, site/ e notas.md. `dist` None = reaproveita os zips já existentes em arquivos/.
    Devolve {"versao", "deploy"}; deploy=False se o site já está numa versão mais nova (não regride)."""
    versao = conferir_tag(tag, raiz)
    arq = saida / "arquivos"
    site = saida / "site"
    arq.mkdir(parents=True, exist_ok=True)
    nome_up, nome_dl = f"autoclick_{versao}_exe.zip", "Autoclick.zip"
    if dist is not None:
        zip_atualizacao(dist, arq / nome_up)
        zip_download(dist, arq / nome_dl)
    for n in (nome_up, nome_dl):
        if not (arq / n).is_file():
            raise ErroRelease(f"falta {arq / n}")
    notas = notas_do_changelog(versao, raiz)
    (saida / "notas.md").write_text(notas or f"Autoclick Inteligente {versao}", encoding="utf-8")
    config: dict[str, Any] = {}
    cfg = raiz / "site" / "config.json"
    if cfg.is_file():
        config = json.loads(cfg.read_text(encoding="utf-8"))
    info = assinar_pacote(semente_hex, versao, "exe", arq / nome_up)
    manifesto = montar_manifesto(info, url_da_release(repo, tag, nome_up), notas, config)
    no_ar = versao_do_manifesto(atual)
    deploy = not (no_ar and mais_nova(no_ar, versao))
    if site.exists():
        shutil.rmtree(site)
    site.mkdir(parents=True)
    for nome in ("pagina.css", "icone.png"):
        shutil.copy2(raiz / "site" / nome, site / nome)
    (site / "manifesto.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    (site / "index.html").write_text(pagina_html(
        versao, (arq / nome_dl).stat().st_size, sha256_de(arq / nome_dl), notas,
        url_da_release(repo, tag, nome_dl), str(config.get("mensagem", ""))), encoding="utf-8")
    (site / ".nojekyll").write_text("", encoding="utf-8")
    if dominio:
        (site / "CNAME").write_text(dominio.strip() + "\n", encoding="utf-8")
    return {"versao": versao, "deploy": deploy, "no_ar": no_ar}


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--repo", help="USUARIO/REPO (para o link da Release)")
    ap.add_argument("--dist", help="pasta dist/Autoclick já construída (omita para reaproveitar arquivos/)")
    ap.add_argument("--saida", default="_release")
    ap.add_argument("--dominio", default="")
    ap.add_argument("--atual", help="manifesto.json que está no ar hoje (impede publicar versão mais velha)")
    ap.add_argument("--so-conferir-tag", action="store_true", help="só confere se a tag bate com a versão do código")
    a = ap.parse_args(argv)
    try:
        if a.so_conferir_tag:
            print(conferir_tag(a.tag))
            return 0
        if not a.repo:
            raise ErroRelease("informe --repo USUARIO/REPO")
        chave = os.environ.get("AC_CHAVE_PRIVADA", "")
        r = montar(a.tag, a.repo, Path(a.saida), chave, Path(a.dist) if a.dist else None, a.dominio,
                   atual=Path(a.atual) if a.atual else None)
    except ErroRelease as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1
    print(f"versão {r['versao']} montada em {a.saida}; publicar o site: {'sim' if r['deploy'] else 'NÃO'}"
          + ("" if r["deploy"] else f" (o site já está na {r['no_ar']}, mais nova)"))
    saida_gh = os.environ.get("GITHUB_OUTPUT")
    if saida_gh:
        with open(saida_gh, "a", encoding="utf-8") as f:
            f.write(f"deploy={'true' if r['deploy'] else 'false'}\nversao={r['versao']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
