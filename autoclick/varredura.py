"""Laço principal dos modos texto / imagem / auto: olha a tela e age conforme as regras."""
from __future__ import annotations

import random
import sys
import threading
import time
from dataclasses import dataclass
from functools import partial
from typing import Callable, Optional

from .tipos import Hit, Img, Regiao
from .windows import FailSafe
from .regras import NAO_CLICAVEIS, Ancora, Escolhedor, Estado, Registro, Regra
from .condicoes import Visibilidade, carregar_fluxo, permite
from .operacao import Saude, Telemetria, Vigilante, pausa, v
from . import windows as m_windows
from . import robustez as m_robustez
from . import captura as m_captura
from . import deteccao as m_deteccao
from . import regras as m_regras
from . import acao as m_acao


@dataclass
class Opcoes:
    modo: str
    config: str
    pasta: str
    confianca: float
    lang: str
    palavras: list[str]
    monitor: int
    regiao: Optional[Regiao]
    titulo_janela: Optional[str]
    intervalo: float
    cooldown: float
    max_cliques: int
    duracao: float
    preview: bool
    debug: bool
    espera_hover: float
    hold: float
    off_dx: int
    off_dy: int
    jitter: float
    foco: bool
    recheck: bool
    estacionar: bool
    destino: Optional[tuple[int, int]]
    sem_teclado: bool
    painel: float = 0.0
    janela_max: float = 120.0
    inatividade: float = 0.0
    ao_travar: str = "avisar"


@dataclass
class Cena:
    """O que foi capturado neste ciclo."""
    img: Img
    ex: float
    ey: float
    ox: int
    oy: int
    regiao: Optional[Regiao]
    rect_jogo: Optional[Regiao]
    hits: list[Hit]


class Varredura:
    def __init__(self, op: Opcoes, regras: dict[str, Regra], registro: Registro,
                 tel: Telemetria) -> None:
        self.op, self.regras, self.registro, self.tel = op, regras, registro, tel
        self.padrao = Regra()
        self.estado = Estado()
        self.recentes: dict[str, float] = {}
        self.avisos: dict[str, float] = {}
        self.escolhedor = Escolhedor()
        self.ancoras: dict[str, Ancora] = {}
        self.vis = Visibilidade()
        self.fluxo = carregar_fluxo(op.config)
        self.saude = Saude(avisar=self._aviso_saude)
        self.vig = Vigilante(op.janela_max, 5, op.inatividade)
        self.limite_recon = m_robustez.LimiteReconexao()
        self.acoes = 0
        self.inicio = time.time()
        self.ultimo_painel = time.time()
        self.rect_anterior: Optional[Regiao] = None
        self.escala_anunciada: Optional[float] = None
        self.janela_sumida = False
        self.encerrar = False

    # ---------------- utilitários ---------------- #
    def _aviso_saude(self, msg: str) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] ⚠ {msg}")
        self.tel.aviso(msg)

    def alertar(self, chave: str, motivo: str, texto: str, cada: float = 120.0,
                regiao: Optional[Regiao] = None) -> None:
        """Alerta (captura de tela + aviso externo), no máximo uma vez a cada `cada` segundos."""
        if time.time() - self.avisos.get("alerta:" + chave, 0.0) >= cada:
            self.avisos["alerta:" + chave] = time.time()
            m_robustez.alerta(motivo, texto, monitor=self.op.monitor, regiao=regiao)

    def avisar(self, chave: str, msg: str, cada: float = 10.0) -> None:
        if time.time() - self.avisos.get(chave, 0.0) >= cada:
            self.avisos[chave] = time.time()
            print(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def _regra(self, rotulo: str) -> Regra:
        return self.regras.get(rotulo, self.padrao)

    # ---------------- ciclo ---------------- #
    def rodar(self) -> None:
        op = self.op
        parar_teclas = threading.Event()
        thread_teclas: Optional[threading.Thread] = None
        if (self.registro.ativo and sys.platform == "win32" and not op.sem_teclado
                and not op.preview):
            thread_teclas = threading.Thread(
                target=m_regras.monitorar_teclado_no_log, args=(parar_teclas, self.registro),
                daemon=True)
            thread_teclas.start()
            print("O --log também registra as teclas que você apertar (--sem-teclado desliga).")
        try:
            while not self.encerrar:
                self.ciclo()
        except KeyboardInterrupt:
            print("\nInterrompido pelo usuário.")
        except FailSafe:
            print("\nFailsafe acionado (mouse no canto). Encerrado.")
        except Exception as e:
            if type(e).__name__ == "TesseractNotFoundError":
                sys.exit(
                    "Tesseract OCR não encontrado.\n"
                    "1) Instale: https://github.com/UB-Mannheim/tesseract/wiki "
                    "(marque o idioma Portuguese)\n"
                    "2) Reabra o terminal, ou passe o caminho: "
                    '--tesseract "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"\n'
                    "Alternativa sem OCR: use o modo 'imagem'.")
            raise
        finally:
            parar_teclas.set()
            if thread_teclas is not None:
                thread_teclas.join(timeout=1)
            self.registro.fechar()
        print(f"Fim. Total de ações: {self.acoes}")

    def ciclo(self) -> None:
        if not self._pode_seguir():
            self.encerrar = True
            return
        cena = self._capturar()
        if cena is None:
            return
        agora = time.time()
        if not self._observar(cena, agora):
            self.encerrar = True
            return
        if self.op.preview:
            self._preview(cena, agora)
            self.encerrar = True
            return
        self._marcar_inicio(cena.hits)
        hits = self.escolhedor.filtrar(cena.hits, self.regras, agora)
        for h in hits:
            if not self._agir(h, cena, agora):
                self.encerrar = True
                return
        time.sleep(v(self.op.intervalo))

    def _pode_seguir(self) -> bool:
        op = self.op
        if m_windows.PARADA.is_set():
            print("Parado pelo botão da janela.")
            return False
        esperou = pausa.esperar()
        if esperou is None:
            print("Interrompido durante a pausa.")
            return False
        self.inicio += esperou  # tempo pausado não conta na --duracao
        if op.duracao and time.time() - self.inicio > op.duracao:
            return False
        if op.painel and time.time() - self.ultimo_painel >= op.painel:
            self.ultimo_painel = time.time()
            print(self.tel.linha())
        parado = self.vig.parado()
        if parado:
            self.tel.aviso(parado)
            if op.ao_travar == "parar":
                print(f"[{time.strftime('%H:%M:%S')}] {parado}; encerrando (--ao-travar parar).")
                return False
            self.avisar("inatividade", parado, 60.0)
            self.alertar("inatividade", "possível travamento", parado, 600.0)
        return True

    def _janela(self) -> tuple[bool, Optional[Regiao], Optional[Regiao]]:
        """(ok, região a capturar, retângulo do jogo). ok=False: pular este ciclo."""
        op = self.op
        if not op.titulo_janela:
            return True, op.regiao, None
        rect = m_captura.rect_seguro(op.titulo_janela)
        regiao = m_captura.regiao_da_janela(rect, op.monitor) if rect else None
        if rect is None or regiao is None:
            fim = self.vig.janela(False)
            if fim:
                print(f"[{time.strftime('%H:%M:%S')}] {fim}; encerrando.")
                self.tel.aviso(fim)
                m_robustez.alerta("janela sumiu", fim, monitor=op.monitor)
                self.encerrar = True
                return False, None, None
            if not self.janela_sumida:
                print(f"[{time.strftime('%H:%M:%S')}] janela '{op.titulo_janela}' não "
                      "encontrada (ou minimizada); aguardando...")
            self.janela_sumida = True
            if op.preview:
                sys.exit(f"Janela '{op.titulo_janela}' não encontrada.")
            time.sleep(1.0)
            return False, None, None
        self.vig.janela(True)
        if self.janela_sumida:
            print(f"[{time.strftime('%H:%M:%S')}] janela encontrada de novo.")
            self.janela_sumida = False
        ant = self.rect_anterior
        if ant is not None and ant[2] != rect[2]:
            m_deteccao.escala_mudou_janela(rect[2] / ant[2])
            print(f"[{time.strftime('%H:%M:%S')}] janela redimensionada "
                  f"({ant[2]}x{ant[3]} -> {rect[2]}x{rect[3]}); reajustando a escala")
        self.rect_anterior = rect
        return True, regiao, rect

    def _detectar(self, img: Img) -> list[Hit]:
        op = self.op
        if op.modo == "imagem":
            hits = m_deteccao.detectar_imagens(img, op.pasta, op.confianca)
            esc = m_deteccao.escala_atual()
            if esc is not None and (self.escala_anunciada is None
                                    or abs(esc - self.escala_anunciada) > 0.01):
                self.escala_anunciada = esc
                print(f"[{time.strftime('%H:%M:%S')}] escala dos botões: {esc:.2f}")
            return hits
        if op.modo == "texto":
            return m_deteccao.detectar_texto(img, op.palavras, op.lang, op.debug)
        return m_deteccao.detectar_auto(img, op.palavras, op.lang)

    def _capturar(self) -> Optional[Cena]:
        ok, regiao, rect = self._janela()
        if not ok:
            return None
        try:
            img, ex, ey, ox, oy = m_captura.capturar(self.op.monitor, regiao)
            hits = self._detectar(img)
        except (FailSafe, KeyboardInterrupt):
            raise
        except Exception as e:
            if type(e).__name__ == "TesseractNotFoundError":
                raise
            fim = self.vig.erro(f"{type(e).__name__}: {e}")
            if fim:
                print(f"[{time.strftime('%H:%M:%S')}] {fim}; encerrando.")
                self.tel.aviso(fim)
                self.encerrar = True
                return None
            self.avisar("erro_cap", f"erro ao capturar/detectar ({type(e).__name__}: {e}); "
                        "tentando de novo", 5.0)
            time.sleep(2.0)
            return None
        self.vig.ok()
        m_robustez.previa.atualizar(img, hits)
        return Cena(img, ex, ey, ox, oy, regiao, rect, hits)

    def _observar(self, cena: Cena, agora: float) -> bool:
        """Visibilidade, saúde, fluxo, telas de erro e âncoras. False = encerrar."""
        hits = cena.hits
        esc = m_deteccao.escala_atual() if self.op.modo == "imagem" else None
        self.vis.atualizar([h.rotulo for h in hits], agora)
        self.saude.observar({h.rotulo: h.score for h in hits}, esc, agora)
        self.tel.escala = esc
        if self.fluxo is not None:
            nova = self.fluxo.observar(self.vis.agora_visiveis(agora), agora)
            if nova:
                print(f"[{time.strftime('%H:%M:%S')}] etapa: {nova}")
                self.registro.log("etapa", nova)
            est = self.fluxo.estourou(agora)
            if est is not None:
                et, seg = est
                msg = f"a etapa '{et.nome}' passou de {et.timeout:g}s (ficou {seg:.0f}s)"
                print(f"[{time.strftime('%H:%M:%S')}] ⚠ {msg} (ao_estourar: {et.ao_estourar})")
                self.tel.aviso(msg)
                self.alertar("etapa:" + et.nome, "etapa demorou", msg, 300.0, cena.regiao)
                self.registro.log("timeout_etapa", et.nome, detalhe=msg)
                if et.ao_estourar == "parar":
                    return False
                if et.ao_estourar == "reiniciar":
                    self.estado.zerar()
                    self.tel.nova_partida()
                    self.fluxo.recomecar(agora)
        parar = False
        for h in hits:
            r = self._regra(h.rotulo)
            if r.acao == "erro":
                self.avisar(f"erro:{h.rotulo}", f"tela de erro detectada: '{h.rotulo}' "
                            f"(ao_ver: {r.ao_ver})", 30.0)
                self.tel.aviso(f"tela de erro: {h.rotulo}")
                self.registro.log("erro_tela", h.rotulo, detalhe=r.ao_ver)
                self.alertar("erro:" + h.rotulo, "tela de erro", f"'{h.rotulo}' (ao_ver: {r.ao_ver})",
                             60.0, cena.regiao)
                parar = parar or r.ao_ver == "parar"
                if r.ao_ver == "reconectar" and not self._reconectar(h.rotulo, r.reconectar_com, agora):
                    parar = True
            elif r.acao == "ancora":
                ax, ay = m_acao.para_tela(h, 0, 0, cena.ex, cena.ey, cena.ox, cena.oy)
                self.ancoras[h.rotulo] = (float(ax), float(ay), h.escala * cena.ex,
                                          h.escala * cena.ey, agora)
        if parar:
            print("Encerrando por causa da tela de erro.")
            return False
        return True

    def _reconectar(self, tela_erro: str, botao: Optional[str], agora: float) -> bool:
        """Tela de erro com ao_ver 'reconectar': recomeça a partida (o botão de reconexão, se
        houver, é clicado pelo fluxo normal quando estiver à vista). False = desistir."""
        chave = "reconectar:" + tela_erro
        if agora - self.avisos.get(chave, 0.0) < 30.0:  # a mesma tela já contada há pouco
            return True
        self.avisos[chave] = agora
        if not self.limite_recon.registrar(agora):
            m_robustez.alerta("reconexão falhou", f"mais de {self.limite_recon.maximo} tentativas em "
                              f"{self.limite_recon.janela / 60:g} min; encerrando",
                              monitor=self.op.monitor)
            return False
        print(f"[{time.strftime('%H:%M:%S')}] reconectando: recomeçando a partida"
              + (f" (botão '{botao}')" if botao else "") + ".")
        self.estado.zerar()
        self.tel.nova_partida()
        if self.fluxo is not None:
            self.fluxo.recomecar(agora)
        return True

    def _preview(self, cena: Cena, agora: float) -> None:
        op = self.op
        m_acao.salvar_preview(cena.img, cena.hits, "preview.png", op.off_dx, op.off_dy)
        print(f"{len(cena.hits)} botão(ões) detectado(s). Veja preview.png "
              "(cruz vermelha = ponto do clique)")
        for h in cena.hits:
            r = self._regra(h.rotulo)
            extra = f" [{r.acao}"
            if r.acao == "arrastar":
                alvo, motivo = m_regras.resolver_destino(r, cena.rect_jogo, self.ancoras, agora)
                extra += f" -> {alvo}" if alvo else f" -> ? ({motivo})"
            extra += "]"
            esc_txt = f", escala {h.escala:.2f}" if op.modo == "imagem" else ""
            print(f"  - {h.rotulo} em {h.centro} -> clique em "
                  f"{m_acao.ponto_de_clique(h, op.off_dx, op.off_dy)} (score {h.score:.2f}"
                  f"{esc_txt}){extra}")

    def _marcar_inicio(self, hits: list[Hit]) -> None:
        """Zera os contadores quando o marcador de início APARECE (não enquanto continua)."""
        visivel = any(self._regra(h.rotulo).acao == "inicio" for h in hits)
        if visivel and not self.estado.inicio_visivel:
            self.estado.zerar()
            print(f"[{time.strftime('%H:%M:%S')}] nova partida detectada "
                  f"(#{self.estado.partida}); contadores zerados")
            self.registro.log("inicio_partida", detalhe=f"partida {self.estado.partida}")
            self.tel.nova_partida()
        self.estado.inicio_visivel = visivel

    # ---------------- ação sobre um botão ---------------- #
    def _liberado(self, h: Hit, regra: Regra, agora: float) -> Optional[str]:
        """Devolve a chave de limite de tempo se o botão pode agir agora; None se não."""
        if (regra.acao in NAO_CLICAVEIS or regra.auto_detect is False
                or h.rotulo in self.estado.desistiu):
            return None
        ok, motivo = permite(regra, self.vis, self.fluxo, agora)
        if not ok:
            if self.op.debug:
                self.avisar(f"cond:{h.rotulo}", f"[debug] {h.rotulo} esperando: {motivo}", 5.0)
            return None
        if regra.vezes and self.estado.feitos.get(h.rotulo, 0) >= regra.vezes:
            return None
        cx, cy = h.centro
        chave = h.rotulo if (regra.intervalo is not None or regra.vezes) \
            else f"{h.rotulo}@{cx // 20},{cy // 20}"
        espera = v(regra.intervalo if regra.intervalo is not None else self.op.cooldown)
        if regra.reiniciar_loop:
            espera = max(espera, 5.0)  # um clique por aparição
        if agora - self.recentes.get(chave, 0.0) < espera:
            return None
        return chave

    def _agir(self, h: Hit, cena: Cena, agora: float) -> bool:
        """Executa a regra do botão. False = encerrar o programa (limite atingido)."""
        op = self.op
        regra = self._regra(h.rotulo)
        chave = self._liberado(h, regra, agora)
        if chave is None:
            return True
        dxr, dyr = op.off_dx + regra.offset[0], op.off_dy + regra.offset[1]
        sx, sy = m_acao.para_tela(h, dxr, dyr, cena.ex, cena.ey, cena.ox, cena.oy)
        arrastando = regra.acao == "arrastar"
        alvo: Optional[tuple[int, int]] = None
        if arrastando:
            alvo, motivo = m_regras.resolver_destino(regra, cena.rect_jogo, self.ancoras, agora)
            if alvo is None:
                self.avisar(f"dest:{h.rotulo}", f"{h.rotulo}: destino indisponível ({motivo}); "
                            "aguardando")
                return True
            if not m_regras.dentro_da_tela(alvo):
                self.avisar(f"dest:{h.rotulo}", f"{h.rotulo}: destino {alvo} fora da tela; "
                            "ação adiada")
                return True
        checar_cinza = arrastando and regra.confirmar_cinza
        antes = m_acao.saturacao_media(cena.img, h) if checar_cinza else 0.0
        confirmar: Optional[Callable[[], bool]] = None
        if op.modo == "imagem" and op.recheck:
            confirmar = partial(m_acao.ainda_no_lugar, h, op.monitor, cena.regiao, op.pasta,
                                max(0.6, op.confianca - 0.05))
        executou = m_acao.clicar(
            h, cena.ex, cena.ey, cena.ox, cena.oy, v(op.espera_hover),
            max(op.hold, 0.15) if arrastando else op.hold, dxr, dyr, op.jitter, op.foco,
            op.debug, confirmar, op.estacionar, op.destino, arrastar_para=alvo)
        hora = time.strftime("%H:%M:%S")
        x2, y2 = (alvo[0], alvo[1]) if alvo else (None, None)
        if not executou:
            print(f"[{hora}] {h.rotulo}: botão mudou de lugar; ação cancelada")
            self.registro.log("cancelado", h.rotulo, sx, sy, detalhe="botão mudou de lugar")
            self.tel.falha(h.rotulo)
            return True
        self.recentes[chave] = agora
        self.vig.acao()
        self.tel.clique(h.rotulo, arrastando)
        if regra.escolha is not None:
            self.escolhedor.travar(h, self.regras, agora)
        detalhe = ""
        if checar_cinza:
            ok, detalhe = self._confirmar_cinza(h, regra, antes, cena, hora, sx, sy, x2, y2)
            if not ok:
                return True
        self.estado.feitos[h.rotulo] = self.estado.feitos.get(h.rotulo, 0) + 1
        self.acoes += 1
        tipo = "arrasto" if arrastando else "clique"
        trajeto = f" -> ({x2}, {y2})" if arrastando else ""
        print(f"[{hora}] {tipo} #{self.acoes}: {h.rotulo} em ({sx}, {sy}){trajeto}"
              + (f"  [{detalhe}]" if detalhe else ""))
        self.registro.log(tipo, h.rotulo, sx, sy, x2, y2, detalhe)
        if regra.reiniciar_loop:
            self.estado.zerar()
            print(f"[{hora}] '{h.rotulo}' clicado: ciclo reiniciado "
                  f"(partida #{self.estado.partida}); contadores zerados")
            self.registro.log("inicio_partida", h.rotulo, detalhe="reiniciar_loop")
            self.tel.nova_partida()
        if op.max_cliques and self.acoes >= op.max_cliques:
            print("Limite de ações atingido.")
            return False
        time.sleep(v(random.uniform(0.3, 0.7)))
        return True

    def _confirmar_cinza(self, h: Hit, regra: Regra, antes: float, cena: Cena, hora: str,
                         sx: int, sy: int, x2: Optional[int],
                         y2: Optional[int]) -> tuple[bool, str]:
        """(seguir, detalhe). seguir=False: não ficou cinza, nada foi contado como feito."""
        resultado, depois = m_acao.verificar_cinza(h, antes, regra, self.op.monitor, cena.regiao)
        detalhe = f"saturação {antes:.0f}->{depois:.0f}"
        if self.op.debug:
            print(f"[debug] {h.rotulo}: {detalhe} (queda exigida: <= {regra.queda_saturacao:.0%})")
        if resultado is False:
            self.tel.falha(h.rotulo)
            tent = self.estado.tentativas.get(h.rotulo, 0) + 1
            self.estado.tentativas[h.rotulo] = tent
            if tent >= regra.tentativas:
                self.estado.desistiu.add(h.rotulo)
                msg = f"não ficou cinza; desisti após {tent} tentativa(s)"
            else:
                msg = f"não ficou cinza; nova tentativa ({tent}/{regra.tentativas})"
            print(f"[{hora}] {h.rotulo}: {msg} ({detalhe})")
            self.registro.log("arrasto_nao_confirmado", h.rotulo, sx, sy, x2, y2,
                              f"{detalhe}; {msg}")
            return False, detalhe
        if resultado is None:
            print(f"[{hora}] {h.rotulo}: o botão já era pouco colorido, não dá para confirmar "
                  "por cor; considerando feito")
            return True, detalhe + "; sem como confirmar por cor"
        return True, detalhe + "; confirmado (ficou cinza)"


__all__ = ["Opcoes", "Varredura", "carregar_fluxo"]
