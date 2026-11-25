# pyright: basic
"""Lógica dos jogos na janela (sem desenho): escolher, migrar, salvar opções, detectar.

A janela edita sempre os arquivos do jogo escolhido (g.pasta, g.config, g.gravacao apontam
para jogos/<jogo>/...). O "Roblox (geral)" fica guardado em g.pasta_geral/config_geral e o
motor soma os dois (ver autoclick/jogos.py).
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from .. import jogos
from .dados import salvar_geral

if TYPE_CHECKING:
    from .app import App


class ControleJogos:
    def __init__(self, app: "App") -> None:
        self.app = app
        self.ultimo_id = ""        # id lido dos logs que nenhum jogo cadastrado reconhece
        self._prox = 0.0
        self._avisado_id = ""
        self.ids_atuais: list[str] = []   # place id + universe id do jogo atual nos logs
        self._visto = ""           # último id dos logs já tratado (só reage a mudanças)

    @property
    def g(self) -> Any:
        return self.app.g

    # ---- consulta ---- #
    def atual(self) -> str:
        return self.g.jogo.strip() or jogos.GERAL

    def nome_atual(self) -> str:
        return jogos.nome_de(self.atual())

    def lista(self) -> list[jogos.Jogo]:
        return jogos.listar()

    # ---- migração dos perfis antigos ---- #
    def migrar_se_preciso(self) -> None:
        if self.g.jogos_migrado:
            return
        self.g.jogos_migrado = True
        try:
            movidos = jogos.migrar_perfis()
        except OSError:
            movidos = []
        if movidos:
            self.app.log_texto("✔ Perfis antigos movidos para a página Jogos: " + ", ".join(movidos)
                               + ". O perfil “roblox” virou o Roblox (geral).\n", "ok")
        salvar_geral(self.g)

    # ---- escolher o jogo ---- #
    def escolher(self, slug: str, motivo: str = "") -> bool:
        slug = slug or jogos.GERAL
        if slug == self.atual():
            return True
        if self.app.rodando:
            self.app.log_texto("⚠ Pare a função atual antes de trocar de jogo.\n", "aviso")
            return False
        j = jogos.ler(slug)
        if j is None:
            return False
        g = self.g
        if self.atual() == jogos.GERAL:  # guarda o geral antes de sair dele
            g.pasta_geral, g.config_geral, g.gravacao_geral = g.pasta, g.config, g.gravacao
        if slug == jogos.GERAL:
            g.pasta, g.config, g.gravacao = g.pasta_geral, g.config_geral, g.gravacao_geral
            g.jogo = ""
        else:
            f = jogos.arquivos_do(slug)
            Path(f["pasta"]).mkdir(parents=True, exist_ok=True)
            g.pasta, g.config, g.gravacao = f["pasta"], f["config"], f["gravacao"]
            g.jogo = slug
        self.aplicar_opcoes(j)
        salvar_geral(g)
        self.app.log_texto(f"🎮 Jogo: {j.nome}" + (f" ({motivo})" if motivo else "") + "\n", "ok")
        self.app.jogo_mudou()
        return True

    def aplicar_opcoes(self, j: jogos.Jogo) -> None:
        for k, v in j.opcoes.items():
            if k in jogos.OPCOES_DO_JOGO and hasattr(self.g, k):
                atual = getattr(self.g, k)
                try:
                    if isinstance(atual, bool):
                        novo: Any = bool(v)
                    elif isinstance(atual, int):
                        novo = int(v)
                    elif isinstance(atual, float):
                        novo = float(v)
                    else:
                        novo = str(v)
                except (TypeError, ValueError):
                    continue
                setattr(self.g, k, novo)

    def salvar_opcoes(self) -> bool:
        j = jogos.ler(self.atual())
        if j is None:
            return False
        j.opcoes = {k: getattr(self.g, k) for k in jogos.OPCOES_DO_JOGO if hasattr(self.g, k)}
        jogos.salvar(j)
        return True

    # ---- cadastro ---- #
    def novo(self, nome: str, ids: Optional[list[str]] = None) -> jogos.Jogo:
        j = jogos.criar(nome, ids=ids)
        return j

    def apagar(self, slug: str) -> bool:
        if slug == self.atual():
            self.escolher(jogos.GERAL)
        return jogos.apagar(slug)

    def definir_ids(self, slug: str, ids: list[str], assinatura: list[str]) -> bool:
        j = jogos.ler(slug)
        if j is None:
            return False
        j.ids, j.assinatura = ids, assinatura
        jogos.salvar(j)
        return True

    # ---- detecção ---- #
    def detectar_logs(self) -> tuple[Optional[str], str]:
        lista = jogos.listar()
        slug, i = jogos.detectar_por_logs(lista)
        self.ultimo_id = i if slug is None else ""
        self.ids_atuais = jogos.ids_recentes() if i else []
        if slug:  # aprende: guarda também os outros ids dessa entrada (place + universe)
            j = next((x for x in lista if x.slug == slug), None)
            if j and not j.geral:
                novos = [x for x in self.ids_atuais if x not in j.ids]
                if novos:
                    j.ids += novos
                    jogos.salvar(j)
        return slug, i

    def tick(self) -> None:
        """Chamado pelo laço da janela: de tempos em tempos olha os logs (só parado)."""
        if not self.g.detectar_jogo or self.app.rodando:
            return
        agora = time.time()
        if agora < self._prox:
            return
        self._prox = agora + 10.0
        try:
            slug, i = self.detectar_logs()
        except Exception:
            return
        novo = bool(i) and i != self._visto
        if i:
            self._visto = i
        if slug and novo and slug != self.atual():
            self.escolher(slug, "detectado pelos logs do Roblox")  # respeita a escolha manual depois
        elif slug is None and i and i != self._avisado_id:
            self._avisado_id = i
            self.app.log_texto(f"ℹ Jogo novo nos logs do Roblox (ids {', '.join(self.ids_atuais) or i}). Cadastre em Jogos → "
                               "“Cadastrar o jogo detectado”.\n", "aviso")
            self.app.atualizar_menu_jogos()

    def detectar_tela(self) -> None:
        from . import comandos
        arq = "jogo_detectado.txt"

        def fim(_c: int) -> None:
            try:
                slug = Path(arq).read_text(encoding="utf-8").strip()
            except OSError:
                return
            if slug:
                self.escolher(slug, "reconhecido pela tela")

        self.app.rodar("ferramenta", comandos.detectar_jogo(self.g, arq), ao_fim=fim)

    def coletar_pistas(self) -> str:
        txt = jogos.coletar_pistas()
        try:
            Path("pistas_roblox.txt").write_text(txt + "\n", encoding="utf-8")
        except OSError:
            pass
        return txt
