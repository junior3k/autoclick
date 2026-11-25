# pyright: basic
"""Atualização do programa: verificar uma nova versão e aplicar um pacote .zip com backup.

Não há servidor próprio: você informa a URL de um "manifesto" JSON
    {"versao": "0.6.0", "url": "https://.../autoclick.zip", "notas": "o que mudou"}
(pode ser um arquivo no GitHub/Drive/seu site) ou aplica um .zip que já baixou.
Seus dados nunca são sobrescritos (botoes/, botoes.json, perfis/, gravações, histórico...).
Só a biblioteca padrão.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from . import ed25519

PROTEGIDOS = ("botoes", "botoes.json", "perfis", "jogos", "pistas_roblox.txt", "jogo_detectado.txt", "historico", "erros", "logs", "backup",
              "autoclick_gui.json", "autoclick_instalacao.txt", "_atualizacao", "diagnostico.txt", "preview.png", "mapa_regras.png",
              ".venv", "uv.lock", ".git")
RAIZ_PERMITIDA = (".py", ".toml", ".bat", ".vbs", ".spec", ".md", ".yml")


def versao_tupla(v: str) -> tuple[int, ...]:
    partes: list[int] = []
    for p in v.strip().lstrip("vV").split("."):
        num = "".join(ch for ch in p if ch.isdigit())
        partes.append(int(num) if num else 0)
    return tuple(partes)


def mais_nova(remota: str, local: str) -> bool:
    a, b = list(versao_tupla(remota)), list(versao_tupla(local))
    n = max(len(a), len(b))
    return a + [0] * (n - len(a)) > b + [0] * (n - len(b))


def esta_congelado() -> bool:
    """True no .exe do PyInstaller (não dá para trocar arquivos de código nele)."""
    return bool(getattr(sys, "frozen", False))


def verificar(url_manifesto: str, versao_atual: str, timeout: float = 10.0) -> tuple[bool, dict[str, Any]]:
    """Lê o manifesto. Devolve (ok, info): info tem 'nova' (bool), 'versao', 'url', 'notas' ou 'erro'."""
    if not url_manifesto.strip().lower().startswith(("http://", "https://")):
        return False, {"erro": "informe uma URL http(s) para o manifesto de atualização"}
    try:
        req = urllib.request.Request(url_manifesto.strip(), headers={"User-Agent": "autoclick"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            dados = json.loads(r.read().decode("utf-8"))
        if not isinstance(dados, dict) or "versao" not in dados:
            return False, {"erro": "manifesto inválido (falta o campo \"versao\")"}
        return True, {"nova": mais_nova(str(dados["versao"]), versao_atual),
                      "versao": str(dados["versao"]), "url": str(dados.get("url", "")),
                      "notas": str(dados.get("notas", ""))}
    except Exception as e:
        return False, {"erro": f"{type(e).__name__}: {e}"}


def baixar(url: str, destino: str, timeout: float = 60.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "autoclick"})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(destino, "wb") as f:
        shutil.copyfileobj(r, f)
    return destino


def _caminho_seguro(raiz: Path, rel: str) -> Optional[Path]:
    """Impede 'zip slip' (../) e caminhos absolutos."""
    p = (raiz / rel).resolve()
    try:
        p.relative_to(raiz.resolve())
    except ValueError:
        return None
    return p


def _entradas_uteis(z: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, str]]:
    nomes = [i for i in z.infolist() if not i.is_dir()]
    prefixo = ""
    topos = {i.filename.split("/", 1)[0] for i in nomes if "/" in i.filename}
    if len(topos) == 1 and all("/" in i.filename for i in nomes):
        prefixo = next(iter(topos)) + "/"  # pacote com uma pasta-raiz: remove
    saida: list[tuple[zipfile.ZipInfo, str]] = []
    for i in nomes:
        rel = i.filename[len(prefixo):] if prefixo and i.filename.startswith(prefixo) else i.filename
        if rel and "__pycache__" not in rel and not rel.endswith(".pyc"):
            saida.append((i, rel))
    return saida


def listar_pacote(zip_path: str) -> list[str]:
    """Arquivos do pacote que SERÃO instalados (já sem os protegidos/fora de lugar)."""
    with zipfile.ZipFile(zip_path) as z:
        return [rel for _, rel in _entradas_uteis(z) if _permitido(rel)]


def _permitido(rel: str) -> bool:
    topo = rel.split("/", 1)[0]
    if topo in PROTEGIDOS:
        return False
    if "/" not in rel:
        return rel.lower().endswith(RAIZ_PERMITIDA)
    return topo in ("autoclick", ".github", "tests")


def aplicar_zip(zip_path: str, raiz: str, backup: bool = True) -> dict[str, Any]:
    """Instala o pacote sobre `raiz`, guardando em backup/AAAA-MM-DD_HH-MM-SS o que foi trocado.

    Devolve {"instalados": [...], "ignorados": [...], "backup": caminho|None}.
    Lança ValueError se o pacote não parece ser deste programa.
    """
    if esta_congelado():
        raise ValueError("este é o programa empacotado (.exe): baixe o novo .exe em vez de atualizar por aqui")
    base = Path(raiz)
    with zipfile.ZipFile(zip_path) as z:
        entradas = _entradas_uteis(z)
        if not any(rel.startswith("autoclick/") and rel.endswith("__init__.py") for _, rel in entradas):
            raise ValueError("o .zip não contém a pasta autoclick/ (não parece um pacote do programa)")
        pasta_bkp = base / "backup" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        instalados: list[str] = []
        ignorados: list[str] = []
        usou_backup = False
        for info, rel in entradas:
            if not _permitido(rel):
                ignorados.append(rel)
                continue
            alvo = _caminho_seguro(base, rel)
            if alvo is None:
                ignorados.append(rel)
                continue
            if backup and alvo.is_file():
                b = pasta_bkp / rel
                b.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(alvo, b)
                usou_backup = True
            alvo.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as origem, open(alvo, "wb") as dest:
                shutil.copyfileobj(origem, dest)
            instalados.append(rel)
    return {"instalados": instalados, "ignorados": ignorados,
            "backup": str(pasta_bkp) if usou_backup else None}


def atualizar_de_url(url_zip: str, raiz: str) -> dict[str, Any]:
    fd, tmp = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    try:
        baixar(url_zip, tmp)
        return aplicar_zip(tmp, raiz)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def restaurar_backup(pasta_backup: str, raiz: str) -> int:
    """Desfaz uma atualização copiando de volta os arquivos do backup. Devolve quantos."""
    origem, base, n = Path(pasta_backup), Path(raiz), 0
    for f in origem.rglob("*"):
        if f.is_file():
            alvo = _caminho_seguro(base, str(f.relative_to(origem)).replace("\\", "/"))
            if alvo is not None:
                alvo.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, alvo)
                n += 1
    return n


def listar_backups(raiz: str) -> list[str]:
    p = Path(raiz) / "backup"
    return sorted((str(d) for d in p.iterdir() if d.is_dir()), reverse=True) if p.is_dir() else []


# =========================================================================== #
# Atualização por servidor público (assinatura Ed25519, sem convite)
# =========================================================================== #
PREFIXO_ASSINATURA = "autoclick-v1"
HOSTS_LOCAIS = ("127.0.0.1", "localhost", "::1", "[::1]")


class ErroServidor(Exception):
    """Falha ao falar com o servidor de atualizações (mensagem já pensada para o usuário)."""

    def __init__(self, mensagem: str, status: int = 0) -> None:
        super().__init__(mensagem)
        self.status = status


def chave_publica_embutida() -> str:
    try:
        from .chave_publica import CHAVE_PUBLICA_HEX
    except ImportError:
        return ""
    return str(CHAVE_PUBLICA_HEX).strip()


def mensagem_do_pacote(versao: str, artefato: str, sha256: str, tamanho: int) -> bytes:
    """Texto exato que é assinado (na publicação) e conferido (no cliente).

    Cobre TUDO o que define o que será instalado: versão, tipo, conteúdo (SHA-256) e tamanho.
    Canal, versão mínima e notas são só metadados de organização e ficam FORA da assinatura:
    assim o servidor web pode promover/retirar versões sem nunca possuir a chave privada.
    """
    return f"{PREFIXO_ASSINATURA}|{versao}|{artefato}|{sha256}|{int(tamanho)}".encode("utf-8")


def url_permitida(url: str) -> bool:
    """Somente HTTPS (ou http para a própria máquina, usado em testes)."""
    p = urllib.parse.urlparse(url.strip())
    if p.scheme == "https" and p.netloc:
        return True
    return p.scheme == "http" and (p.hostname or "") in [h.strip("[]") for h in HOSTS_LOCAIS]


class Servidor:
    """Endereço base da API (ex.: https://ac.cabro.me/download/api/v1). Sem convite nem chave:
    qualquer instalação pode consultar e baixar. `instalacao` é um número aleatório local (só
    serve para contar instalações ativas; não identifica ninguém)."""

    def __init__(self, url: str, canal: str = "estavel", instalacao: str = "") -> None:
        self.url = url.strip().rstrip("/")
        self.canal = canal if canal in ("estavel", "beta") else "estavel"
        self.instalacao = instalacao

    @property
    def valido(self) -> bool:
        return url_permitida(self.url)


ARQ_INSTALACAO = "autoclick_instalacao.txt"


def id_instalacao(raiz: str = ".") -> str:
    """Número aleatório desta instalação (criado na primeira vez e guardado ao lado do programa)."""
    p = Path(raiz) / ARQ_INSTALACAO
    try:
        v = p.read_text(encoding="utf-8").strip()
        if re.fullmatch(r"[0-9a-f]{16}", v):
            return v
    except OSError:
        pass
    v = os.urandom(8).hex()
    try:
        p.write_text(v, encoding="utf-8")
    except OSError:
        pass
    return v


def servidor_padrao(canal: str = "estavel", raiz: str = ".") -> Optional[Servidor]:
    """O servidor embutido no programa (ou o de AUTOCLICK_SERVIDOR_URL). None se não houver."""
    url = os.environ.get("AUTOCLICK_SERVIDOR_URL", "").strip()
    if not url:
        try:
            from .servidor_padrao import URL_PADRAO
            url = URL_PADRAO
        except ImportError:
            url = ""
    if not url:
        return None
    srv = Servidor(url, canal, id_instalacao(raiz))
    return srv if srv.valido else None


def _pedir(srv: Servidor, caminho: str, params: Optional[dict[str, str]] = None, metodo: str = "GET",
           corpo: Optional[bytes] = None, cabecalhos: Optional[dict[str, str]] = None,
           timeout: float = 15.0) -> Any:
    """Abre uma resposta HTTP do servidor (o chamador fecha). Traduz erros em ErroServidor."""
    if not srv.valido:
        raise ErroServidor("este programa não tem um servidor de atualizações configurado")
    url = srv.url + caminho
    if params:
        url += "?" + urllib.parse.urlencode(params)
    from . import __version__
    h = {"User-Agent": f"autoclick/{__version__}"}
    if srv.instalacao:
        h["X-Instalacao"] = srv.instalacao
    h.update(cabecalhos or {})
    req = urllib.request.Request(url, data=corpo, method=metodo, headers=h)
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise ErroServidor(mensagem_http(e.code), e.code)
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise ErroServidor(descrever_erro(e))


def mensagem_http(codigo: int) -> str:
    if codigo == 429:
        return "Muitas tentativas seguidas. Aguarde alguns minutos e tente de novo."
    if codigo == 404:
        return "Esse arquivo não está mais disponível no servidor (a versão pode ter sido retirada). Verifique de novo."
    if codigo in (401, 403):
        return "O servidor recusou o pedido (acesso negado)."
    if codigo == 413:
        return "O arquivo enviado é grande demais para o servidor."
    if codigo >= 500:
        return (f"O servidor de atualizações está fora do ar ou reiniciando (erro {codigo}). "
                "Tente de novo daqui a alguns minutos.")
    return f"O servidor respondeu com um erro inesperado (HTTP {codigo})."


def descrever_erro(e: BaseException) -> str:
    """Mensagem em português, sem jargão, para qualquer falha de rede/disco/pacote."""
    import errno
    import socket
    import zipfile as _zf
    if isinstance(e, ErroServidor):
        return str(e)
    motivo = getattr(e, "reason", e)
    if isinstance(e, (socket.timeout, TimeoutError)) or isinstance(motivo, (socket.timeout, TimeoutError)):
        return "O servidor demorou demais para responder. Tente de novo; se a internet estiver lenta, aguarde um pouco."
    if isinstance(motivo, socket.gaierror):
        return "Sem conexão com a internet (não consegui encontrar o endereço do servidor). Confira a rede e tente de novo."
    if isinstance(motivo, ConnectionRefusedError) or isinstance(e, ConnectionRefusedError):
        return "O servidor de atualizações está fora do ar (recusou a conexão). Tente mais tarde."
    if isinstance(motivo, (ConnectionResetError, ConnectionAbortedError)) or isinstance(e, (ConnectionResetError, ConnectionAbortedError)):
        return "A conexão com o servidor caiu no meio do caminho. Tente de novo."
    if isinstance(e, _zf.BadZipFile):
        return "O pacote baixado está inválido (arquivo zip corrompido). Nada foi instalado; tente baixar de novo."
    if isinstance(e, PermissionError):
        return ("Sem permissão para gravar na pasta do programa. Feche outros programas que estejam usando "
                "os arquivos ou mova o Autoclick para uma pasta sua (ex.: Documentos).")
    if isinstance(e, OSError) and e.errno == errno.ENOSPC:
        return "Sem espaço em disco para baixar ou instalar a atualização. Libere espaço e tente de novo."
    if isinstance(e, urllib.error.URLError) or isinstance(e, OSError):
        return f"Não consegui falar com o servidor ({motivo}). Confira a internet e tente de novo."
    return f"Algo inesperado aconteceu ({type(e).__name__}: {e}). Se repetir, use “Enviar relatório”."


def conferir_espaco(pasta: str, tamanho: int, fator: float = 3.0) -> None:
    """Falha com mensagem clara se o disco não comporta baixar + instalar + backup."""
    try:
        livre = shutil.disk_usage(pasta if os.path.isdir(pasta) else os.path.dirname(os.path.abspath(pasta)) or ".").free
    except OSError:
        return
    precisa = int(tamanho * fator)
    if livre < precisa:
        raise ErroServidor(f"Sem espaço em disco: preciso de uns {precisa / 1048576:.0f} MB livres e só há "
                           f"{livre / 1048576:.0f} MB. Libere espaço e tente de novo.")


def consultar(srv: Servidor, versao_atual: str, artefato: Optional[str] = None,
              chave_publica_hex: Optional[str] = None) -> dict[str, Any]:
    """Pergunta ao servidor se há versão nova.

    Devolve {"nova": bool, "obrigatoria": bool, "versao", "notas", "tamanho", "sha256", "minima",
    "canal", "nome", "mensagem"}. A assinatura é conferida AQUI; se não bater, ErroServidor.
    """
    artefato = artefato or ("exe" if esta_congelado() else "fonte")
    chave = chave_publica_hex if chave_publica_hex is not None else chave_publica_embutida()
    with _pedir(srv, "/manifesto", {"atual": versao_atual, "artefato": artefato, "canal": srv.canal,
                                    "so": sys.platform}) as r:
        try:
            d = json.loads(r.read(1_000_000).decode("utf-8"))
        except ValueError:
            raise ErroServidor("resposta inválida do servidor")
    if not isinstance(d, dict):
        raise ErroServidor("resposta inválida do servidor")
    saida: dict[str, Any] = {"nova": False, "obrigatoria": False,
                             "mensagem": str(d.get("mensagem", "")), "versao_atual": versao_atual}
    a = d.get("atualizacao")
    if not a:
        return saida
    try:
        versao, art = str(a["versao"]), str(a["artefato"])
        canal, minima = str(a.get("canal", "estavel")), str(a.get("minima", "0"))
        sha, tam = str(a["sha256"]), int(a["tamanho"])
        assinatura = str(a["assinatura"])
    except (KeyError, TypeError, ValueError):
        raise ErroServidor("manifesto incompleto")
    if not mais_nova(versao, versao_atual):
        return saida
    if not chave:
        raise ErroServidor("este programa não tem a chave de confiança do administrador; "
                           "peça o pacote completo mais recente e aplique-o em Configurações")
    msg = mensagem_do_pacote(versao, art, sha, tam)
    if not ed25519.verificar_hex(chave, msg, assinatura):
        raise ErroServidor("ASSINATURA INVÁLIDA: a atualização não foi feita pelo administrador. "
                           "Nada foi instalado.")
    if art != artefato:
        raise ErroServidor("o servidor ofereceu um tipo de pacote inesperado")
    saida.update({"nova": True, "versao": versao, "canal": canal, "artefato": art, "sha256": sha,
                  "tamanho": tam, "minima": minima, "notas": str(a.get("notas", "")),
                  "assinatura": assinatura, "obrigatoria": mais_nova(minima, versao_atual)})
    return saida


def baixar_pacote(srv: Servidor, info: dict[str, Any], pasta: str,
                  progresso: Optional[Callable[[int, int], None]] = None,
                  cancelar: Optional[Callable[[], bool]] = None) -> str:
    """Baixa (retomando se houver um download parcial), confere tamanho e SHA-256."""
    os.makedirs(pasta, exist_ok=True)
    conferir_espaco(pasta, int(info["tamanho"]))
    nome = f"autoclick_{info['versao']}_{info['artefato']}.zip"
    final = os.path.join(pasta, nome)
    parcial = final + ".part"
    total = int(info["tamanho"])
    ja = os.path.getsize(parcial) if os.path.exists(parcial) else 0
    if ja > total:
        os.remove(parcial)
        ja = 0
    cab = {"Range": f"bytes={ja}-"} if ja else {}
    if ja != total:
        with _pedir(srv, f"/pacote/{urllib.parse.quote(str(info['versao']))}/{info['artefato']}",
                    params={"canal": srv.canal}, cabecalhos=cab, timeout=30.0) as r:
            if ja and r.status != 206:  # o servidor ignorou o Range: recomeça do zero
                ja = 0
            with open(parcial, "ab" if ja else "wb") as f:
                feito = ja
                while True:
                    if cancelar is not None and cancelar():
                        raise ErroServidor("Download cancelado.")
                    bloco = r.read(65536)
                    if not bloco:
                        break
                    f.write(bloco)
                    feito += len(bloco)
                    if progresso:
                        progresso(feito, total)
    if os.path.getsize(parcial) != total:
        raise ErroServidor("O download ficou incompleto. Tente de novo (o que já foi baixado será aproveitado).")
    h = hashlib.sha256()
    with open(parcial, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    if h.hexdigest() != str(info["sha256"]).lower():
        os.remove(parcial)
        raise ErroServidor("O arquivo baixado está corrompido ou foi alterado (SHA-256 diferente). "
                           "Nada foi instalado; tente baixar de novo.")
    os.replace(parcial, final)
    return final


def autoteste(raiz: str, versao_esperada: str, comando: Optional[list[str]] = None,
              timeout: float = 90.0) -> tuple[bool, str]:
    """Depois de instalar, abre a versão nova num processo à parte e confere a versão."""
    codigo = ("import sys; sys.path.insert(0, sys.argv[1]); import autoclick, autoclick.cli, "
              "autoclick.interface.dados, autoclick.interface.comandos; print(autoclick.__version__)")
    cmd = comando or [sys.executable, "-c", codigo, raiz]
    try:
        r = subprocess.run(cmd, cwd=raiz, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"{type(e).__name__}: {e}"
    saida = (r.stdout or "").strip().splitlines()
    if r.returncode != 0:
        return False, (r.stderr or r.stdout or "falhou").strip()[-400:]
    if not saida or saida[-1].strip() != versao_esperada:
        return False, f"versão instalada ({saida[-1] if saida else '?'}) difere da esperada ({versao_esperada})"
    return True, "ok"


def instalar_zip_baixado(zip_path: str, info: dict[str, Any], raiz: str,
                         comando_autoteste: Optional[list[str]] = None) -> dict[str, Any]:
    """Instala um pacote JÁ baixado e conferido: backup, autoteste e reversão se não abrir."""
    res = aplicar_zip(zip_path, raiz)
    ok, msg = autoteste(raiz, str(info["versao"]), comando_autoteste)
    if not ok:
        n = restaurar_backup(res["backup"], raiz) if res.get("backup") else 0
        raise ErroServidor(f"A versão {info['versao']} não passou no teste ({msg}); "
                           f"a versão anterior foi restaurada ({n} arquivo(s)).")
    res["versao"] = info["versao"]
    from . import novidades
    novidades.guardar(raiz, str(info["versao"]), str(info.get("notas", "")))
    return res


def pasta_baixados(raiz: str) -> str:
    """Onde o download em segundo plano guarda o pacote até a hora de instalar (retoma se cair)."""
    return os.path.join(raiz, "_atualizacao", "baixados")


def limpar_baixados(raiz: str) -> None:
    shutil.rmtree(pasta_baixados(raiz), ignore_errors=True)


def instalar_do_servidor(srv: Servidor, info: dict[str, Any], raiz: str,
                         progresso: Optional[Callable[[int, int], None]] = None,
                         cancelar: Optional[Callable[[], bool]] = None,
                         comando_autoteste: Optional[list[str]] = None) -> dict[str, Any]:
    """Baixa, confere, instala com backup, testa a versão nova e REVERTE sozinho se ela não abrir."""
    if esta_congelado():
        raise ErroServidor("no .exe use preparar_troca_exe()")
    tmp = tempfile.mkdtemp(prefix="autoclick_up_")
    try:
        zip_path = baixar_pacote(srv, info, tmp, progresso, cancelar)
        return instalar_zip_baixado(zip_path, info, raiz, comando_autoteste)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---- .exe: o Windows trava o executável em uso, então a troca é feita por um script ---- #
EXCLUIR_DIRS = ("botoes", "perfis", "jogos", "historico", "erros", "logs", "backup", "_atualizacao")
EXCLUIR_ARQS = ("botoes.json", "autoclick_gui.json", "autoclick_instalacao.txt")


def script_troca_exe(pid: int, origem: str, destino: str, exe: str = "Autoclick.exe",
                     reabrir: bool = True) -> str:
    """Texto do .cmd que espera o programa fechar, guarda backup, copia os arquivos novos e reabre."""
    xd = " ".join(f'"{d}"' for d in EXCLUIR_DIRS)
    xf = " ".join(f'"{a}"' for a in EXCLUIR_ARQS)
    bkp = os.path.join(destino, "backup", datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_exe")
    return "\r\n".join([
        "@echo off",
        "setlocal",
        f'set "PID={pid}"',
        ":espera",
        'tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul',
        "if not errorlevel 1 (",
        "  timeout /t 1 /nobreak >nul",
        "  goto espera",
        ")",
        f'robocopy "{destino}" "{bkp}" /E /XD {xd} /XF {xf} /NFL /NDL /NJH /NJS /NP >nul',
        f'robocopy "{origem}" "{destino}" /E /XD {xd} /XF {xf} /NFL /NDL /NJH /NJS /NP >nul',
        "if errorlevel 8 (",
        f'  robocopy "{bkp}" "{destino}" /E /XD {xd} /XF {xf} /NFL /NDL /NJH /NJS /NP >nul',
        f'  echo A troca falhou e a versao anterior foi restaurada. > "{destino}\\logs\\atualizacao_falhou.txt"',
        ")",
        *([f'start "" "{os.path.join(destino, exe)}"'] if reabrir else []),
        f'rmdir /s /q "{origem}"',
        'del "%~f0"',
        "",
    ])


def preparar_troca_exe(zip_path: str, destino: str, pid: Optional[int] = None, reabrir: bool = True) -> str:
    """Extrai o pacote do .exe numa pasta de preparo e cria o script de troca. Devolve o .cmd.

    O chamador inicia o script (processo separado) e fecha o programa."""
    preparo = Path(destino) / "_atualizacao" / "novo"
    if preparo.exists():
        shutil.rmtree(preparo)
    preparo.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as z:
        entradas = _entradas_uteis(z)
        if not any(rel.lower().endswith(".exe") and "/" not in rel for _, rel in entradas):
            raise ValueError("o pacote não contém o .exe na raiz")
        for info, rel in entradas:
            alvo = _caminho_seguro(preparo, rel)
            if alvo is None:
                continue
            alvo.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as o, open(alvo, "wb") as d:
                shutil.copyfileobj(o, d)
    cmd = Path(destino) / "_atualizacao" / "trocar.cmd"
    cmd.write_text(script_troca_exe(pid or os.getpid(), str(preparo), destino, reabrir=reabrir), encoding="utf-8")
    return str(cmd)
