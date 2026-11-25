"""Modo reproduzir: refaz gravações, com vigia de botões (auto_detect)."""
from __future__ import annotations

import json
import sys
import threading
import time
from functools import partial
from pathlib import Path
from typing import Any, Optional, cast

from .tipos import Regiao
from .windows import FailSafe, LEFTDOWN, LEFTUP, RIGHTDOWN, RIGHTUP
from .regras import Escolhedor, Registro, Regra
from . import windows as m_windows
from .operacao import pausa, tel
from . import captura as m_captura
from . import deteccao as m_deteccao
from . import regras as m_regras
from . import acao as m_acao
from . import robustez as m_robustez
from .som import som as m_som


# --------------------------------------------------------------------------- #
# Modo reproduzir: refaz uma gravação (coordenadas, teclas e tempos)
# --------------------------------------------------------------------------- #
def _ponto_do_evento(ev: dict[str, Any], suf: str, rect: Optional[Regiao]) -> tuple[int, int]:
    """Ponto do evento: pela fração da janela atual (se conhecida), senão absoluto."""
    fx, fy = ev.get("fx" + suf), ev.get("fy" + suf)
    if rect is not None and fx is not None and fy is not None:
        return round(rect[0] + float(fx) * rect[2]), round(rect[1] + float(fy) * rect[3])
    return int(ev["x" + suf]), int(ev["y" + suf])

def _garantir_janela(titulo: str, espera_max: float) -> Optional[float]:
    """Espera a janela ficar ativa (tentando trazê-la para frente).

    Devolve os segundos esperados, ou None se foi abortado / estourou o tempo.
    """
    if m_windows.janela_ativa(titulo):
        return 0.0
    inicio = time.time()
    avisou = False
    while True:
        hwnd = m_windows.achar_janela(titulo)
        if hwnd is not None:
            try:
                m_windows.focar_hwnd(hwnd)
            except Exception:
                pass
            if m_windows.janela_ativa(titulo):
                if avisou:
                    print("  Janela ativa de novo; continuando.")
                return time.time() - inicio
        if not avisou:
            print(f"  A janela '{titulo}' não está ativa; aguardando "
                  f"({m_windows.NOME_PARAR} ou mouse no canto para parar)...")
            avisou = True
        if m_windows.abortar():
            return None
        if espera_max and time.time() - inicio > espera_max:
            print(f"  A janela '{titulo}' não ficou ativa em {espera_max:g}s; parando.")
            return None
        time.sleep(0.3)

def _aguardar_marcador(ev: dict[str, Any], pasta: str, confianca: float, monitor: int,
                       titulo: Optional[str], vigia: Optional["VigiaBotoes"]) -> tuple[Optional[bool], float]:
    """Marcador de verificação: espera um botão aparecer (ou sumir, com "ate": "sumir").

    Devolve (resultado, segundos esperados): True = condição atendida, False = estourou o
    tempo, None = abortado (F9 etc.). O tempo gasto não conta no ritmo da gravação.
    """
    nome = str(ev.get("botao", ""))
    timeout = float(ev.get("timeout", 30.0))
    quer_ver = str(ev.get("ate", "aparecer")).lower() != "sumir"
    ini = time.time()
    while True:
        if m_windows.abortar():
            return None, time.time() - ini
        if pausa.pausado:
            esp = pausa.esperar()
            if esp is None:
                return None, time.time() - ini
            ini += esp
        try:
            rect = m_captura.rect_seguro(titulo) if titulo else None
            regiao = m_captura.regiao_da_janela(rect, monitor) if rect else None
            if titulo is None or regiao is not None:
                img = m_captura.capturar(monitor, regiao)[0]
                visto = any(h.rotulo == nome for h in
                            m_deteccao.detectar_imagens(img, pasta, confianca))
                if visto == quer_ver:
                    return True, time.time() - ini
        except Exception as e:  # falha pontual de captura: tenta de novo
            print(f"  (marcador: erro ao olhar a tela: {type(e).__name__}: {e})")
        if timeout and time.time() - ini >= timeout:
            return False, time.time() - ini
        time.sleep(0.3)


class VigiaBotoes:
    """Durante a reprodução: clica sozinho nos botões com "auto_detect": true.

    Roda em segundo plano, olhando a tela. Enquanto algum desses botões está visível, ele
    clica (respeitando "intervalo", "vezes" e "offset" da regra) e a reprodução fica em
    pausa, para continuar só quando o botão sumir. Mouse e teclado da reprodução e os
    cliques daqui nunca se misturam: ambos usam a mesma trava.
    """

    def __init__(
        self,
        regras: dict[str, Regra],
        pasta: str,
        confianca: float,
        monitor: int,
        regiao: Optional[Regiao],
        titulo: Optional[str],
        checar_janela: bool,
        travar: threading.Lock,
        registro: Optional[Registro] = None,
        cooldown: float = 0.8,
        intervalo: float = 0.4,
        graca: float = 1.0,
        max_continuo: float = 120.0,
        espera_hover: float = 0.25,
    ) -> None:
        self.regras = {n: r for n, r in regras.items() if r.auto_detect is True and r.acao == "clicar"}
        # Telas de erro/desconexão ("acao": "erro"): avisa, e conforme "ao_ver" para ou reconecta.
        self.erros = {n: r for n, r in regras.items() if r.acao == "erro"}
        for r_erro in self.erros.values():
            alvo = r_erro.reconectar_com
            if r_erro.ao_ver == "reconectar" and alvo and alvo in regras and regras[alvo].acao == "clicar":
                self.regras.setdefault(alvo, regras[alvo])  # o botão de reconectar também é clicado
        self.limite_recon = m_robustez.LimiteReconexao()
        self._erro_visto: dict[str, float] = {}
        self.pasta, self.confianca, self.monitor = pasta, confianca, monitor
        self.regiao, self.titulo, self.checar_janela = regiao, titulo, checar_janela
        self.travar = travar
        self.registro = registro
        self.cooldown, self.intervalo, self.graca = cooldown, intervalo, graca
        self.max_continuo, self.espera_hover = max_continuo, espera_hover
        self.cliques = 0
        self._feitos: dict[str, int] = {}
        self._recentes: dict[str, float] = {}
        self._ocupado_ate = 0.0
        self._ocupado_desde: Optional[float] = None
        self._suspenso_ate = 0.0
        self._reinicio: Optional[str] = None
        self.escolhedor = Escolhedor()
        self._parar = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def nomes(self) -> list[str]:
        return sorted(set(self.regras) | set(self.erros))

    def _tratar_erros(self, hits: list[Any], agora: float, regiao: Optional[Regiao]) -> None:
        for h in hits:
            r = self.erros.get(h.rotulo)
            if r is None or agora - self._erro_visto.get(h.rotulo, 0.0) < 30.0:
                continue
            self._erro_visto[h.rotulo] = agora
            m_robustez.alerta("tela de erro", f"'{h.rotulo}' (ao_ver: {r.ao_ver})",
                              monitor=self.monitor, regiao=regiao)
            if r.ao_ver == "parar":
                print("Encerrando por causa da tela de erro.")
                m_windows.PARADA.set()
            elif r.ao_ver == "reconectar":
                if not self.limite_recon.registrar(agora):
                    m_robustez.alerta("reconexão falhou", "tentativas demais; encerrando",
                                      monitor=self.monitor)
                    m_windows.PARADA.set()
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] reconectando: a gravação recomeça "
                          "do início.")
                    self._reinicio = "(reconexão)"

    def ocupado(self) -> bool:
        """True enquanto há botão automático à vista (a reprodução deve esperar)."""
        return time.time() < self._ocupado_ate

    def aguardar_livre(self) -> Optional[float]:
        """Espera o botão sumir. Devolve os segundos esperados, ou None se abortou."""
        ini = time.time()
        while self.ocupado():
            if m_windows.abortar():
                return None
            time.sleep(0.05)
        return time.time() - ini

    def pegar_reinicio(self) -> Optional[str]:
        """Nome do botão 'reiniciar_loop' clicado automaticamente (uma vez; limpa o pedido)."""
        r, self._reinicio = self._reinicio, None
        return r

    def _livre(self) -> None:
        self._ocupado_desde = None
        self._ocupado_ate = 0.0

    def varrer_uma_vez(self) -> None:
        agora = time.time()
        if agora < self._suspenso_ate:
            return
        if pausa.pausado:  # F8: a vigia também fica quieta
            self._livre()
            return
        if self.titulo and self.checar_janela and not m_windows.janela_ativa(self.titulo):
            self._livre()  # o jogo não está à frente: não briga com o que você está fazendo
            return
        regiao = self.regiao
        if self.titulo:
            rect = m_captura.rect_seguro(self.titulo)
            regiao = m_captura.regiao_da_janela(rect, self.monitor) if rect else None
            if regiao is None:
                self._livre()
                return
        img, ex, ey, ox, oy = m_captura.capturar(self.monitor, regiao)
        todos = m_deteccao.detectar_imagens(img, self.pasta, self.confianca)
        m_robustez.previa.atualizar(img, todos)
        if self.erros:
            self._tratar_erros(todos, agora, regiao)
        alvos = [h for h in todos if h.rotulo in self.regras]
        alvos = self.escolhedor.filtrar(alvos, self.regras, agora)
        if not alvos:
            self._livre()
            return
        if self._ocupado_desde is None:
            self._ocupado_desde = agora
        elif agora - self._ocupado_desde > self.max_continuo:
            print(f"[{time.strftime('%H:%M:%S')}] auto_detect: botão à vista há mais de "
                  f"{self.max_continuo:g}s; pausando a vigia por 30s para a reprodução seguir")
            self._suspenso_ate = agora + 30.0
            self._livre()
            return
        self._ocupado_ate = agora + self.graca
        for h in alvos:
            r = self.regras[h.rotulo]
            if r.vezes and self._feitos.get(h.rotulo, 0) >= r.vezes:
                continue
            espera = r.intervalo if r.intervalo is not None else self.cooldown
            if r.reiniciar_loop:
                espera = max(espera, 5.0)
            if agora - self._recentes.get(h.rotulo, 0.0) < espera:
                continue
            sx, sy = m_acao.para_tela(h, r.offset[0], r.offset[1], ex, ey, ox, oy)
            confirmar = partial(m_acao.ainda_no_lugar, h, self.monitor, regiao, self.pasta,
                                max(0.6, self.confianca - 0.05))
            with self.travar:
                feito = m_acao.clicar(h, ex, ey, ox, oy, self.espera_hover, 0.08, r.offset[0],
                               r.offset[1], 0.0, True, False, confirmar, True, None)
            if not feito:
                continue
            self._recentes[h.rotulo] = time.time()
            if r.escolha is not None:
                self.escolhedor.travar(h, self.regras, time.time())
            if r.reiniciar_loop:
                self._reinicio = h.rotulo
            self._feitos[h.rotulo] = self._feitos.get(h.rotulo, 0) + 1
            self.cliques += 1
            self._ocupado_ate = time.time() + self.graca
            tel().clique(h.rotulo)
            print(f"[{time.strftime('%H:%M:%S')}] auto_detect: clique em {h.rotulo} ({sx}, {sy})")
            if self.registro is not None:
                self.registro.log("clique_auto", h.rotulo, sx, sy, detalhe="auto_detect (reprodução)")

    def _loop(self) -> None:
        while not self._parar.is_set():
            try:
                self.varrer_uma_vez()
            except FailSafe:
                return
            except Exception as e:  # uma falha de captura não derruba a reprodução
                print(f"auto_detect: erro ao varrer a tela ({type(e).__name__}: {e})")
                self._parar.wait(2.0)
            self._parar.wait(self.intervalo)

    def iniciar(self) -> None:
        self.varrer_uma_vez()  # já olha uma vez antes da reprodução começar
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        if self._thread is not None:
            self._thread.join(timeout=3)

def reproduzir(
    arquivo: str,
    velocidade: float,
    atraso: float,
    loop: Optional[int] = None,
    pausa_loop: float = 1.0,
    janela: Optional[str] = None,
    checar_janela: bool = True,
    espera_janela: float = 60.0,
    teclas: bool = True,
    config: str = "botoes.json",
    pasta: str = "botoes",
    confianca: float = 0.85,
    monitor: int = 1,
    auto_detect: bool = True,
    auto_max: float = 120.0,
    registro: Optional[Registro] = None,
    intervalo_vigia: float = 0.4,
    graca: float = 1.0,
    som: bool = True,
) -> str:
    """Refaz a gravação. Devolve "ok" (terminou), "interrompida" (parada/F9) ou "falhou"
    (marcador com "ao_estourar": "parar" estourou).

    loop: None = uma vez; 0 = repete até F9; N = N vezes.
    auto_detect: botões do botoes.json com "auto_detect": true são clicados assim que
    aparecem; a reprodução espera enquanto algum estiver à vista.
    Antes de cada evento confere se a janela do jogo está ativa; se não estiver, tenta
    trazê-la para frente e, se não conseguir, PAUSA até ela voltar (sem perder o ritmo).
    """
    if sys.platform != "win32":
        sys.exit("O modo 'reproduzir' só funciona no Windows.")
    p = Path(arquivo)
    if not p.is_file():
        sys.exit(f"Gravação '{arquivo}' não encontrada.")
    dados: Any = json.loads(p.read_text(encoding="utf-8"))
    eventos = cast(list[dict[str, Any]], dados.get("eventos", []))
    t_ultimo = max((float(e.get("t", 0)) for e in eventos), default=0.0)  # antes de filtrar teclas
    try:
        cauda = min(max(0.0, float(dados.get("cauda", 0) or 0)), 86400.0)
    except (TypeError, ValueError):
        cauda = 0.0
    if not teclas:
        eventos = [e for e in eventos if e.get("tipo") != "tecla"]
    if not eventos:
        sys.exit("A gravação não tem eventos.")
    if any(e.get("tipo") == "aguardar" for e in eventos) and not Path(pasta).is_dir():
        print(f"Aviso: a gravação tem marcadores de verificação, mas a pasta '{pasta}' não existe.")
    vel = max(0.1, velocidade)
    titulo = janela
    if titulo is None:
        info: Any = dados.get("janela")
        if isinstance(info, dict):
            t_gravado = cast(dict[str, Any], info).get("titulo")
            titulo = str(t_gravado) if t_gravado else None
    if titulo is None:
        if checar_janela:
            print("Aviso: a gravação não tem janela; não dá para conferir se o jogo está ativo "
                  "(use --janela \"Título\").")
    elif checar_janela:
        print(f"Só age com a janela '{titulo}' ativa (--sem-checar-janela desliga).")

    for aviso_r in m_robustez.conferir_resolucao(cast(dict[str, Any], dados), titulo):
        print(f"⚠ Ambiente diferente da gravação: {aviso_r}. Pontos por fração da janela se "
              "ajustam; coordenadas fixas podem errar (regrave se algo ficar torto).")
        tel().aviso(f"ambiente diferente: {aviso_r}")
    repeticoes = 1 if loop is None else max(0, loop)
    for i in range(int(atraso), 0, -1):
        print(f"Reproduzindo em {i}... ({m_windows.NOME_PARAR} ou mouse no canto superior esquerdo para parar)")
        if som:
            m_som.tocar_evento("tique")
        time.sleep(1)
    if som:
        m_som.tocar_evento("repro_inicio")
    print(f"▶ Reproduzindo {len(eventos)} evento(s) a {vel:g}x"
          + (f" em loop ({m_windows.NOME_PARAR} para parar)." if repeticoes == 0
             else f", {repeticoes} vez(es)." if repeticoes > 1 else "."))

    presas: set[int] = set()  # teclas que nós apertamos e ainda não soltamos
    travar = threading.Lock()  # mouse/teclado: ou a reprodução, ou a vigia, nunca os dois
    vigia: Optional[VigiaBotoes] = None
    if auto_detect:
        regras_auto = m_regras.carregar_regras(config)
        candidatos = VigiaBotoes(regras_auto, pasta, confianca, monitor, None, titulo,
                                 checar_janela, travar, registro, intervalo=intervalo_vigia,
                                 graca=graca, max_continuo=auto_max)
        if candidatos.nomes:
            if not Path(pasta).is_dir():
                print(f"Aviso: pasta '{pasta}' não existe; auto_detect desligado.")
            else:
                vigia = candidatos
                print("auto_detect ligado para: " + ", ".join(vigia.nomes)
                      + " (a reprodução espera enquanto eles estiverem à vista).")
    volta = 0
    # Botões "reiniciar_loop" já clicados pela vigia: o clique GRAVADO neles é pulado uma vez.
    pular: set[str] = set()
    reiniciou = False

    def checar_reinicio() -> bool:
        """A vigia clicou num botão 'reiniciar_loop'? Então esta volta termina aqui."""
        nonlocal reiniciou
        if vigia is not None:
            rot = vigia.pegar_reinicio()
            if rot is not None:
                pular.add(rot)
                reiniciou = True
        return reiniciou

    t0 = time.time()

    def _progresso() -> dict[str, object]:
        # decorrido já desconta pausas e esperas (t0 anda junto); a pausa atual congela o relógio
        agora = pausa.desde() if pausa.pausado else time.time()
        total = (t_ultimo + cauda) / vel
        return {"volta": volta, "voltas": repeticoes, "total": round(total, 3),
                "decorrido": round(min(max(0.0, agora - t0), total), 3), "pausado": pausa.pausado}

    try:
        tel().definir_progresso(_progresso)
        if vigia is not None:
            vigia.iniciar()
        while repeticoes == 0 or volta < repeticoes:
            volta += 1
            if volta > 1:
                tel().nova_partida()
            if repeticoes != 1:
                print(f"— Volta {volta}" + (f"/{repeticoes}" if repeticoes else "") + " —")
            reiniciou = False
            if vigia is not None:  # pedido que chegou entre uma volta e outra: já estamos no início
                pendente = vigia.pegar_reinicio()
                if pendente is not None:
                    pular.add(pendente)
            t0 = time.time()
            for n, ev in enumerate(eventos, 1):
                alvo = float(ev["t"]) / vel
                while time.time() - t0 < alvo:
                    if m_windows.abortar():
                        print("Reprodução interrompida.")
                        return "interrompida"
                    if pausa.pausado:  # F8: o tempo parado não conta no ritmo da gravação
                        esp = pausa.esperar()
                        if esp is None:
                            print("Reprodução interrompida.")
                            return "interrompida"
                        t0 += esp
                    if checar_reinicio():
                        break
                    time.sleep(0.005)
                if reiniciou:
                    break
                if m_windows.abortar():
                    print("Reprodução interrompida.")
                    return "interrompida"
                esp2 = pausa.esperar()
                if esp2 is None:
                    print("Reprodução interrompida.")
                    return "interrompida"
                t0 += esp2
                if titulo and checar_janela:
                    esperou = _garantir_janela(titulo, espera_janela)
                    if esperou is None:
                        print("Reprodução interrompida.")
                        return "interrompida"
                    t0 += esperou  # o tempo parado não conta no ritmo da gravação

                if vigia is not None:
                    livre = vigia.aguardar_livre()  # botão automático à vista: espera ele sumir
                    if livre is None:
                        print("Reprodução interrompida.")
                        return "interrompida"
                    t0 += livre
                    if checar_reinicio():
                        break
                if ev["tipo"] == "aguardar":
                    nome_m = str(ev.get("botao", ""))
                    verbo = "sumir" if str(ev.get("ate", "aparecer")).lower() == "sumir" else "aparecer"
                    print(f"  {n}/{len(eventos)} marcador: esperando [{nome_m}] {verbo}"
                          f" (até {float(ev.get('timeout', 30.0)):g}s)")
                    ok_m, esp_m = _aguardar_marcador(ev, pasta, confianca, monitor, titulo, vigia)
                    if ok_m is None:
                        print("Reprodução interrompida.")
                        return "interrompida"
                    t0 += esp_m
                    if not ok_m:
                        acao_m = str(ev.get("ao_estourar", "avisar")).lower()
                        m_robustez.alerta("marcador estourou",
                                          f"[{nome_m}] não ficou {verbo} em "
                                          f"{float(ev.get('timeout', 30.0)):g}s (ao_estourar: {acao_m})",
                                          monitor=monitor)
                        if acao_m == "parar":
                            print("Reprodução interrompida pelo marcador.")
                            return "falhou"
                    continue
                if ev["tipo"] != "tecla" and ev.get("botao") in pular:
                    pular.discard(cast(str, ev["botao"]))
                    print(f"  {n}/{len(eventos)} {ev['tipo']} em [{ev['botao']}] pulado: "
                          "já foi clicado automaticamente")
                    continue
                with travar:
                    if ev["tipo"] == "tecla":
                        vk = int(ev["vk"])
                        baixo = ev.get("estado") == "baixo"
                        m_windows.enviar_tecla(vk, baixo)
                        if baixo:
                            presas.add(vk)
                        else:
                            presas.discard(vk)
                        print(f"  {n}/{len(eventos)} tecla {ev.get('tecla', vk)} "
                              f"{'↓' if baixo else '↑'}")
                        continue

                    rect = m_captura.rect_seguro(titulo)
                    x, y = _ponto_do_evento(ev, "", rect)
                    down, up = ((RIGHTDOWN, RIGHTUP) if ev.get("mouse") == "direito"
                                else (LEFTDOWN, LEFTUP))
                    dur = float(ev.get("duracao", 0.08))

                    m_windows.mover_suave(x, y, duracao=0.2, passos=12)
                    time.sleep(0.05)
                    m_windows.enviar_mouse(0, 0, down)
                    try:
                        if ev["tipo"] == "arrasto":
                            x2, y2 = _ponto_do_evento(ev, "2", rect)
                            time.sleep(0.08)
                            m_windows.mover_suave(x2, y2, duracao=max(0.2, dur / vel),
                                        passos=max(12, int(dur * 40)))
                            time.sleep(0.1)
                        else:
                            time.sleep(min(max(dur, 0.04), 0.3))
                    finally:
                        m_windows.enviar_mouse(0, 0, up)  # nunca deixa o botão do mouse preso
                    rot = f" [{ev['botao']}]" if ev.get("botao") else ""
                    print(f"  {n}/{len(eventos)} {ev['tipo']} em ({x},{y}){rot}")
                    tel().clique(str(ev.get("botao") or "(sem botão)"), ev["tipo"] == "arrasto")
                    tel().ultimo = f"evento {n}/{len(eventos)}"
            if cauda > 0 and not reiniciou:
                # o tempo entre a última ação e o fim da gravação também faz parte da volta
                print(f"  aguardando o fim da gravação (mais {cauda / vel:.0f} s depois da última ação)")
                alvo_fim = (t_ultimo + cauda) / vel
                while time.time() - t0 < alvo_fim:
                    if m_windows.abortar():
                        print("Reprodução interrompida.")
                        return "interrompida"
                    if pausa.pausado:
                        esp = pausa.esperar()
                        if esp is None:
                            print("Reprodução interrompida.")
                            return "interrompida"
                        t0 += esp
                    if checar_reinicio():
                        break
                    time.sleep(0.05)
            if reiniciou:
                with travar:
                    for vk in list(presas):  # recomeço limpo: solta o que estava apertado
                        m_windows.enviar_tecla(vk, False)
                    presas.clear()
                print("  Botão de reinício clicado: recomeçando a gravação do início"
                      + ("" if (repeticoes == 0 or volta < repeticoes) else " (fim das voltas)")
                      + ".")
                if som:
                    m_som.tocar()  # a volta recomeça: também avisa
                continue
            pular.clear()  # nada a pular na próxima volta
            if som:
                m_som.tocar()  # volta concluída: sino suave (se estiver ligado agora)
            if repeticoes == 0 or volta < repeticoes:
                fim = time.time() + max(0.0, pausa_loop)
                while time.time() < fim:
                    if m_windows.abortar():
                        print("Reprodução interrompida.")
                        return "interrompida"
                    time.sleep(0.02)
    finally:
        if som:
            m_som.tocar_evento("repro_fim")  # terminou, parou ou falhou
        tel().definir_progresso(None)
        if vigia is not None:
            vigia.parar()
        for vk in list(presas):  # não deixa tecla "presa" se parar no meio
            try:
                m_windows.enviar_tecla(vk, False)
            except Exception:
                pass
    if vigia is not None:
        print(f"auto_detect: {vigia.cliques} clique(s) automático(s) durante a reprodução.")
    print("Reprodução concluída.")
    return "ok"
