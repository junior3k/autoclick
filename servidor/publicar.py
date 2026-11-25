# pyright: basic
"""Publicação de versões: sobe o número, testa, empacota, assina e registra (tudo de uma vez)."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Callable, Optional

from autoclick import ed25519
from autoclick.atualizacao import mensagem_do_pacote, versao_tupla

from .config import RAIZ
from .nucleo import ErroNegocio, Nucleo, VERSAO_OK

# O que vai para o pacote "fonte" (nada do servidor, dos testes nem dos dados dos usuários).
INCLUIR_PASTAS = ("autoclick", "perfis")
INCLUIR_ARQS = ("autoclick_inteligente.py", "pyproject.toml", "iniciar.bat", "iniciar.vbs",
                "construir_exe.bat", "autoclick.spec", "botoes.exemplo.json", "CHANGELOG.md")


def _init_py(raiz: Path) -> Path:
    return raiz / "autoclick" / "__init__.py"


def ler_versao(raiz: Path = RAIZ) -> str:
    raiz = Path(raiz)
    m = re.search(r'__version__\s*=\s*"([^"]+)"', _init_py(raiz).read_text(encoding="utf-8"))
    if not m:
        raise ErroNegocio("não achei __version__ em autoclick/__init__.py")
    return m.group(1)


def definir_versao(nova: str, raiz: Path = RAIZ) -> None:
    raiz = Path(raiz)
    if not VERSAO_OK.match(nova):
        raise ErroNegocio("versão deve ser como 0.6.0")
    p = _init_py(raiz)
    p.write_text(re.sub(r'(__version__\s*=\s*)"[^"]+"', rf'\1"{nova}"', p.read_text(encoding="utf-8"), count=1),
                 encoding="utf-8")
    t = raiz / "pyproject.toml"
    if t.is_file():
        t.write_text(re.sub(r'(?m)^(version\s*=\s*)"[^"]+"', rf'\1"{nova}"', t.read_text(encoding="utf-8"), count=1),
                     encoding="utf-8")


def proxima(versao: str, parte: str) -> str:
    a = list(versao_tupla(versao)) + [0, 0, 0]
    maior, menor, corr = a[0], a[1], a[2]
    if parte == "maior":
        return f"{maior + 1}.0.0"
    if parte == "menor":
        return f"{maior}.{menor + 1}.0"
    return f"{maior}.{menor}.{corr + 1}"


def notas_do_changelog(versao: str, raiz: Path = RAIZ) -> str:
    """Texto da seção '## <versao>' do CHANGELOG.md (vazio se não houver)."""
    raiz = Path(raiz)
    p = raiz / "CHANGELOG.md"
    if not p.is_file():
        return ""
    texto = p.read_text(encoding="utf-8")
    m = re.search(rf"(?ms)^##\s*\[?v?{re.escape(versao)}\]?[^\n]*\n(.*?)(?=^##\s|\Z)", texto)
    return m.group(1).strip() if m else ""


def montar_fonte(destino: Path, raiz: Path = RAIZ) -> Path:
    raiz = Path(raiz)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for pasta in INCLUIR_PASTAS:
            for f in sorted((raiz / pasta).rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc":
                    z.write(f, f.relative_to(raiz).as_posix())
        for nome in INCLUIR_ARQS:
            if (raiz / nome).is_file():
                z.write(raiz / nome, nome)
    return destino


def montar_exe(destino: Path, raiz: Path = RAIZ) -> Path:
    origem = raiz / "dist" / "Autoclick"
    if not (origem / "Autoclick.exe").is_file():
        raise ErroNegocio("dist/Autoclick/Autoclick.exe não existe: rode construir_exe.bat antes (no Windows)")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(origem.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(origem).as_posix())
    return destino


SUITES = ("rodar_testes", "testes_gravacao", "testes_escala", "testes_novos", "testes_auto", "testes_operacao",
          "testes_robustez", "testes_manutencao", "testes_edicao", "testes_som", "testes_ed25519", "testes_cliente_servidor",
          "testes_servidor_nucleo", "testes_servidor_e2e", "testes_jogos", "testes_novidades", "testes_rotina")


def construir_exe(raiz: Path = RAIZ, log: Callable[[str], None] = print) -> None:
    """Gera dist/Autoclick (PyInstaller via uv). Só funciona no Windows com uv instalado."""
    import shutil
    raiz = Path(raiz)
    uv = shutil.which("uv")
    if not uv:
        raise ErroNegocio("não achei o 'uv' no PATH para construir o .exe")
    log("construindo o .exe (leva alguns minutos)…")
    r = subprocess.run([uv, "run", "--with", "pyinstaller", "pyinstaller", "autoclick.spec", "--noconfirm",
                        "--clean"], cwd=raiz, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        log((r.stdout + r.stderr)[-1500:])
        raise ErroNegocio("a construção do .exe falhou (veja acima)")
    ex = raiz / "botoes.exemplo.json"
    if ex.is_file() and (raiz / "dist" / "Autoclick").is_dir():
        shutil.copy2(ex, raiz / "dist" / "Autoclick" / ex.name)


LEIA_ME = """AUTOCLICK INTELIGENTE - como usar

1. Extraia ESTE .zip inteiro numa pasta (ex.: C:\\Autoclick). Nao rode de dentro do zip.
2. De dois cliques em Autoclick.exe.
   (Se o Windows avisar "protegeu seu computador": clique em "Mais informacoes" e depois
   "Executar assim mesmo".)
3. Para atualizar no futuro: Configuracoes > Atualizacoes > Verificar atualizacao.
   Seus botoes, perfis e gravacoes nunca sao apagados nas atualizacoes.
"""


def montar_download(destino: Path, raiz: Path = RAIZ) -> Path:
    """Zip da página pública: a pasta Autoclick/ completa (programa + LEIA-ME)."""
    origem = Path(raiz) / "dist" / "Autoclick"
    if not (origem / "Autoclick.exe").is_file():
        raise ErroNegocio("dist/Autoclick/Autoclick.exe não existe")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(origem.rglob("*")):
            if f.is_file():
                z.write(f, "Autoclick/" + f.relative_to(origem).as_posix())
        z.writestr("Autoclick/LEIA-ME.txt", LEIA_ME)
    return destino


def rodar_testes(raiz: Path = RAIZ, log: Callable[[str], None] = print) -> bool:
    """Roda as suítes do núcleo e do servidor (as da janela exigem tela e rodam no CI)."""
    raiz = Path(raiz)
    achou, falhas = False, []
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    for nome in SUITES:
        script = raiz / "tests" / f"{nome}.py"
        if not script.is_file():
            continue
        achou = True
        r = subprocess.run([sys.executable, str(script)], cwd=raiz, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env)
        if r.returncode != 0:
            falhas.append(nome)
            ruins = [l for l in (r.stdout + r.stderr).splitlines() if "FALHOU" in l or "Error" in l or "Traceback" in l]
            log(f"  ✖ {nome}\n" + "\n".join(ruins[:6] or (r.stdout + r.stderr).splitlines()[-6:]))
        else:
            log(f"  ✔ {nome}")
    if not achou:
        log("  (pasta tests/ não encontrada: testes ignorados)")
    if falhas:
        log("  Suítes com falha: " + ", ".join(falhas))
    return not falhas


def escrever_url_padrao(url: str, raiz: Path = RAIZ) -> None:
    """Embute o endereço da API no programa (autoclick/servidor_padrao.py)."""
    p = Path(raiz) / "autoclick" / "servidor_padrao.py"
    txt = p.read_text(encoding="utf-8")
    p.write_text(re.sub(r'(?m)^URL_PADRAO\s*=.*$', f'URL_PADRAO = "{url}"', txt, count=1), encoding="utf-8")


def escrever_chave_publica(pub_hex: str, raiz: Path = RAIZ) -> None:
    p = Path(raiz) / "autoclick" / "chave_publica.py"
    txt = p.read_text(encoding="utf-8")
    p.write_text(re.sub(r'(?m)^CHAVE_PUBLICA_HEX\s*=.*$', f'CHAVE_PUBLICA_HEX = "{pub_hex}"', txt, count=1),
                 encoding="utf-8")


def assinar_e_registrar(n: Nucleo, zip_path: Path, versao: str, artefato: str, canal: str,
                        notas: str, minima: str = "0") -> dict:
    semente = n.carregar_chave_privada()
    sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    assin = ed25519.assinar(semente, mensagem_do_pacote(versao, artefato, sha, zip_path.stat().st_size)).hex()
    return n.registrar_versao(zip_path, versao, artefato, assin, canal, notas, minima)


def publicar(n: Nucleo, versao: Optional[str] = None, parte: str = "corrigir", com_exe: bool = False,
             testes: bool = True, canal: str = "beta", notas: str = "", minima: str = "0",
             raiz: Path = RAIZ, log: Callable[[str], None] = print) -> list[str]:
    """Fluxo completo. Devolve as versões/artefatos publicados."""
    raiz = Path(raiz)
    atual = ler_versao(raiz)
    alvo = versao or atual
    ja = {v["versao"] for v in n.listar_versoes()}
    if alvo in ja:
        if versao:
            raise ErroNegocio(f"a versão {alvo} já foi publicada. Use outro número ou --subir.")
        alvo = proxima(alvo, parte)
        log(f"versão {atual} já publicada; usando {alvo}")
    if alvo != atual:
        definir_versao(alvo, raiz)
        log(f"versão do código: {atual} -> {alvo}")
    pub = n.chave_publica_hex()
    if not pub:
        raise ErroNegocio("servidor não instalado (sem chave pública). Rode: python -m servidor instalar")
    escrever_chave_publica(pub, raiz)
    escrever_url_padrao(n.cfg.base, raiz)
    if testes:
        log("rodando testes…")
        if not rodar_testes(raiz, log):
            raise ErroNegocio("os testes falharam; nada foi publicado (use --sem-testes para ignorar)")
    notas = notas or notas_do_changelog(alvo, raiz)
    feitos: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        log("empacotando (fonte)…")
        z = montar_fonte(t / "fonte.zip", raiz)
        assinar_e_registrar(n, z, alvo, "fonte", canal, notas, minima)
        feitos.append(f"{alvo} fonte")
        if com_exe:
            construir_exe(raiz, log)
            log("empacotando (exe)…")
            assinar_e_registrar(n, montar_exe(t / "exe.zip", raiz), alvo, "exe", canal, notas, minima)
            feitos.append(f"{alvo} exe")
            assinar_e_registrar(n, montar_download(t / "download.zip", raiz), alvo, "download", canal, notas, minima)
            feitos.append(f"{alvo} download (página pública)")
    log(f"publicado no canal '{canal}': {', '.join(feitos)}. Para liberar a todos (e atualizar a página de download): servidor.bat promover {alvo}")
    return feitos
