# pyright: basic
"""Ferramentas: diagnóstico, validação, mapa de regras, recortes, calibração e relatórios."""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog
from typing import Callable

from . import comandos
from .dados import listar_pngs
from .dialogos import escolher_item, pedir_texto
from .pagina import Pagina
from .widgets import Cartao, Rolavel, botao, responsivo


class PaginaFerramentas(Pagina):
    chave = "ferramentas"
    titulo = "Ferramentas"
    subtitulo = "Confira o ambiente, prepare os botões e acompanhe os resultados."

    def construir(self) -> None:
        f = self.frame
        rol = Rolavel(f, self.t)
        rol.pack(fill="both", expand=True)
        g = rol.corpo
        self._botoes: list[object] = []
        itens: list[tuple[str, str, str, Callable[[], None], str]] = [
            ("Diagnóstico", "Confere bibliotecas, DPI, captura da tela, janela do jogo, botões e o "
             "botoes.json. Use antes do primeiro teste real.", "Executar diagnóstico", self.diagnostico, "Accent"),
            ("Validar botoes.json", "Aponta erros e typos (com sugestões), imagens sem regra, âncoras "
             "ou destinos inválidos e condições que não existem.", "Validar agora", self.validar, "Accent"),
            ("Mapa de regras", "Tira uma foto da tela e desenha os botões reconhecidos, a ação de cada "
             "um e o destino dos arrastos.", "Gerar mapa", self.mapa, "Ghost"),
            ("Recortar botão", "Captura a tela e você arrasta um retângulo sobre o botão. Salva o PNG e "
             "avisa se o recorte é ambíguo, liso, pequeno ou grande.", "Recortar…", self.recortar, "Ghost"),
            ("Calibrar “ficou cinza”", "Mede o botão normal, cinza e com o mouse em cima e grava a "
             "queda de saturação ideal na regra.", "Calibrar…", self.calibrar, "Ghost"),
            ("Definir destino do arrasto", "Mostra a tela, você clica onde o botão deve ser solto e o "
             "destino é gravado na regra.", "Definir…", self.destino, "Ghost"),
            ("Resumo de um registro", "Resume um arquivo CSV gerado pelo registro do modo automático: "
             "ações por botão e partidas.", "Escolher CSV…", self.resumo_csv, "Ghost"),
            ("Pastas", "Abre a pasta dos PNGs dos botões ou a pasta do projeto no Explorer.",
             "Abrir pasta dos botões", self.abrir_botoes, "Ghost"),
        ]
        cartoes: list[Cartao] = []
        for i, (titulo, desc, rot, cmd, estilo) in enumerate(itens):
            card = Cartao(g, self.t, titulo, desc)
            cartoes.append(card)
            b = botao(card.corpo, rot, cmd, estilo)
            card.linha_cheia(b, (4, 0))
            self._botoes.append(b)
            if titulo == "Pastas":
                botao(card.corpo, "Abrir pasta do projeto", self.abrir_projeto, "Ghost").grid(
                    row=card._linha, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        responsivo(g, list(cartoes), pady=(0, 14))

    # ------------------------------------------------------------------ #
    def diagnostico(self) -> None:
        self.app.rodar("ferramenta", comandos.diagnostico(self.g))

    def validar(self) -> None:
        self.app.rodar("ferramenta", comandos.validar(self.g))

    def mapa(self) -> None:
        self.app.rodar("ferramenta", comandos.visualizar(self.g), minimizar=True,
                       ao_fim=lambda _c: self.app.mostrar_imagem("mapa_regras.png", "Mapa de regras"))

    def recortar(self) -> None:
        nome = pedir_texto(self.app.raiz, self.t, "Recortar botão", "Nome do botão (ex.: maximo):")
        if nome:
            nome = "".join(ch if (ch.isalnum() or ch in "_-") else "_" for ch in nome)
            self.app.rodar("ferramenta", comandos.recortar(self.g, nome), minimizar=True)

    def calibrar(self) -> None:
        nome = escolher_item(self.app.raiz, self.t, "Calibrar", "Qual botão calibrar?", listar_pngs(self.g.pasta))
        if nome:
            self.app.log_texto("Use o botão “Enviar Enter” (nas mensagens) para avançar cada passo.\n", "aviso")
            self.app.rodar("ferramenta", comandos.calibrar(self.g, nome))

    def destino(self) -> None:
        nome = escolher_item(self.app.raiz, self.t, "Definir destino", "Qual botão será arrastado?",
                             listar_pngs(self.g.pasta))
        if nome:
            self.app.rodar("ferramenta", comandos.definir_destino(self.g, nome), minimizar=True)

    def resumo_csv(self) -> None:
        arq = filedialog.askopenfilename(parent=self.app.raiz, title="Escolher registro CSV",
                                         filetypes=[("CSV", "*.csv"), ("Todos", "*.*")])
        if arq:
            self.app.rodar("ferramenta", comandos.relatorio_csv(arq))

    def _abrir(self, pasta: str) -> None:
        os.makedirs(pasta, exist_ok=True)
        caminho = os.path.abspath(pasta)
        try:
            if sys.platform == "win32":
                os.startfile(caminho)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", caminho])
            else:
                subprocess.Popen(["xdg-open", caminho])
        except OSError as e:
            self.app.log_texto(f"✖ Não consegui abrir {caminho}: {e}\n")

    def abrir_botoes(self) -> None:
        self._abrir(self.g.pasta)

    def abrir_projeto(self) -> None:
        self._abrir(".")

    def ao_estado(self, rodando: bool) -> None:
        for b in self._botoes:
            b.state(["disabled"] if rodando else ["!disabled"])  # type: ignore[attr-defined]
