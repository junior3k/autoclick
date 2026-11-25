"""Linha de comando: modos de varredura, argumentos e laço principal."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional, cast

from .tipos import PALAVRAS_PADRAO, Regiao
from .regras import Registro, Regra
from .condicoes import carregar_fluxo
from .operacao import Telemetria, configurar_variacao, controle_do_ambiente, nova_telemetria, pausa, resumir_csv
from . import robustez as m_robustez
from .opcionais import DICA_OCR, ocr_disponivel
from .perfil import carregar_perfil, localizar_perfil
from .validar import relatorio as relatorio_validacao, validar_config
from . import windows as m_windows
from . import deteccao as m_deteccao
from . import regras as m_regras
from . import gravacao as m_gravacao
from . import reproducao as m_reproducao
from . import ferramentas as m_ferr
from .varredura import Opcoes, Varredura

MODOS = ["texto", "imagem", "auto", "gravar", "reproduzir", "validar", "diagnostico",
         "recortar", "calibrar", "visualizar", "definir-destino", "relatorio", "detectar-jogo",
         "rotina", "gui"]


def main() -> None:
    ap = argparse.ArgumentParser(description="Autoclick inteligente baseado em visão computacional.")
    ap.add_argument("modo", nargs="?", choices=MODOS, default=None,
                    help="o que fazer (padrão: reproduzir; sem nenhum argumento abre a janela). "
                         + ", ".join(MODOS))
    ap.add_argument("nome", nargs="?", default=None,
                    help="recortar/calibrar/definir-destino: nome do botão; relatorio: o CSV")
    ap.add_argument("--palavras", nargs="+", default=PALAVRAS_PADRAO,
                    help="textos dos botões (modos texto/auto)")
    ap.add_argument("--pasta", default="botoes", help="pasta com PNGs dos botões (modo imagem)")
    ap.add_argument("--config", default="botoes.json",
                    help="regras por botão: clicar, arrastar, inicio (padrão: botoes.json)")
    ap.add_argument("--log", default=None, metavar="ARQUIVO.csv",
                    help="grava um CSV com cada ação automática (horário, coordenadas)")
    ap.add_argument("--arquivo", default="gravacao.json",
                    help="arquivo da gravação (modos gravar/reproduzir)")
    ap.add_argument("--gerar-regras", action="store_true",
                    help="modo gravar: cria/atualiza regras no --config a partir da gravação")
    ap.add_argument("--sobrescrever", action="store_true",
                    help="com --gerar-regras, troca regras que já existem")
    ap.add_argument("--velocidade", type=float, default=1.0,
                    help="modo reproduzir: 1 = tempo original, 2 = dobro da velocidade")
    ap.add_argument("--atraso", type=float, default=3.0,
                    help="modos gravar/reproduzir: segundos de contagem antes de começar")
    ap.add_argument("--confianca", type=float, default=0.85, help="0-1, modo imagem")
    ap.add_argument("--lang", default="por+eng", help="idiomas do Tesseract")
    ap.add_argument("--monitor", type=int, default=1, help="índice do monitor (1 = principal)")
    ap.add_argument("--regiao", nargs=4, type=int, metavar=("X", "Y", "L", "A"),
                    help="limita a busca a uma região da tela")
    ap.add_argument("--intervalo", type=float, default=1.5, help="segundos entre varreduras")
    ap.add_argument("--cooldown", type=float, default=10.0,
                    help="segundos antes de clicar de novo na mesma posição")
    ap.add_argument("--max-cliques", type=int, default=0, help="0 = sem limite")
    ap.add_argument("--duracao", type=float, default=0, help="para após N segundos (0 = sem limite)")
    ap.add_argument("--espera-hover", type=float, default=0.25,
                    help="segundos com o mouse parado sobre o botão antes de clicar")
    ap.add_argument("--offset", nargs=2, type=int, default=[0, 0], metavar=("DX", "DY"),
                    help="desloca o ponto de clique em pixels (ex.: --offset -5 3)")
    ap.add_argument("--jitter", type=float, default=0.0,
                    help="variação aleatória do clique como fração do botão (0 = exato)")
    ap.add_argument("--mouse", choices=["input", "pyautogui"], default="input",
                    help=argparse.SUPPRESS)  # obsoleto: agora é sempre SendInput
    ap.add_argument("--janela", default=None, metavar="TÍTULO",
                    help="título (ou parte) da janela do jogo, ex.: --janela Roblox. Limita a "
                         "busca à janela (acompanha mover/redimensionar), habilita destinos "
                         "relativos à janela e, na reprodução, confere se ela está ativa")
    ap.add_argument("--escala", default="auto", metavar="auto|N",
                    help="tamanho dos PNGs em relação à tela. auto (padrão) = descobre sozinho "
                         "(PNGs tirados no maior tamanho da janela); 1 = só tamanho original; "
                         "0.6 = força 60%%")
    ap.add_argument("--escala-min", type=float, default=0.3,
                    help="menor escala testada na busca automática (padrão 0.3)")
    ap.add_argument("--escala-max", type=float, default=1.0,
                    help="maior escala testada (padrão 1.0 = tamanho do PNG)")
    ap.add_argument("--busca-escala", type=float, default=8.0, metavar="SEG",
                    help="intervalo mínimo entre buscas completas de escala quando nada é "
                         "reconhecido (padrão 8)")
    ap.add_argument("--loop", nargs="?", type=int, const=0, default=None, metavar="N",
                    help="modo reproduzir: repete a gravação. Sem número = até apertar F9; "
                         "--loop 5 = 5 vezes")
    ap.add_argument("--pausa-loop", type=float, default=1.0, metavar="SEG",
                    help="modo reproduzir: pausa entre uma volta e outra (padrão 1)")
    ap.add_argument("--sem-checar-janela", action="store_true",
                    help="modo reproduzir: não confere se a janela do jogo está ativa")
    ap.add_argument("--espera-janela", type=float, default=60.0, metavar="SEG",
                    help="modo reproduzir: quanto esperar a janela ficar ativa antes de "
                         "desistir (0 = esperar para sempre; padrão 60)")
    ap.add_argument("--ancora", default=None, metavar="NOME",
                    help="modo gravar: nome de um PNG do mapa (sem .png) usado como referência "
                         "para o ponto de soltura dos arrastos (acompanha a câmera)")
    ap.add_argument("--sem-auto-detect", action="store_true",
                    help="modo reproduzir: ignora os botões com \"auto_detect\": true do json")
    ap.add_argument("--auto-max", type=float, default=120.0, metavar="SEG",
                    help="modo reproduzir: se um botão auto_detect ficar à vista por mais de SEG "
                         "segundos seguidos, a vigia pausa 30s para a reprodução seguir (padrão 120)")
    ap.add_argument("--sem-teclado", action="store_true",
                    help="não grava/reproduz/registra teclas (gravar, reproduzir e --log)")
    ap.add_argument("--estacionar", nargs=2, type=int, default=None, metavar=("X", "Y"),
                    help="onde deixar o mouse após cada clique (padrão: 350 px ao lado do botão)")
    ap.add_argument("--sem-estacionar", action="store_true",
                    help="deixa o mouse parado sobre o botão após o clique")
    ap.add_argument("--sem-recheck", action="store_true",
                    help="não reconfirma a posição do botão logo antes de clicar (modo imagem)")
    ap.add_argument("--sem-foco", action="store_true",
                    help="não tenta trazer a janela do botão para o primeiro plano")
    ap.add_argument("--hold", type=float, default=0.08,
                    help="segundos com o botão do mouse pressionado")
    ap.add_argument("--debug", action="store_true",
                    help="mostra detalhes (palavras lidas pelo OCR, saturação, foco)")
    ap.add_argument("--tesseract", default="",
                    help=r"caminho do tesseract.exe se não estiver no PATH")
    ap.add_argument("--preview", action="store_true",
                    help="não clica; salva preview.png e mostra o que foi detectado")
    ap.add_argument("--perfil", default=None, metavar="NOME",
                    help="carrega opções de perfis/NOME.json (o que você digitar vence o perfil)")
    ap.add_argument("--perfil-arquivo", default=None, metavar="ARQUIVO.json",
                    help="perfil em outro caminho")
    ap.add_argument("--variacao", type=float, default=0.0, metavar="FRAÇÃO",
                    help="espalha esperas/intervalos aleatoriamente (0.15 = ±15%%)")
    ap.add_argument("--painel", nargs="?", type=float, const=30.0, default=0.0, metavar="SEG",
                    help="imprime um resumo de status a cada SEG segundos (padrão 30)")
    ap.add_argument("--gui", action="store_true",
                    help="abre uma janelinha com Pausar/Parar e contadores")
    ap.add_argument("--relatorio", default=None, metavar="ARQUIVO.md|.json",
                    help="ao terminar, salva o resumo da sessão neste arquivo")
    ap.add_argument("--janela-max", type=float, default=120.0, metavar="SEG",
                    help="encerra se a janela do jogo ficar sumida por mais de SEG s (0 = nunca)")
    ap.add_argument("--inatividade", type=float, default=0.0, metavar="SEG",
                    help="avisa/encerra se não houver nenhuma ação por SEG segundos (0 = desligado)")
    ap.add_argument("--ao-travar", choices=["avisar", "parar"], default="avisar",
                    help="o que fazer quando --inatividade ou --tela-parada estouram (padrão avisar)")
    ap.add_argument("--tela-parada", type=float, default=0.0, metavar="SEG",
                    help="avisa/encerra (--ao-travar) se a tela do jogo não mudar por SEG s (0 = desligado)")
    ap.add_argument("--webhook", default=None, metavar="URL",
                    help="avisos (travou, erro...) para um webhook do Discord/URL ou telegram:TOKEN@CHAT_ID")
    ap.add_argument("--sem-captura-erro", action="store_true",
                    help="não salva a tela em erros/ quando algo dá errado")
    ap.add_argument("--tecla-pausa", default=None, metavar="TECLA", help="tecla de pausar (padrão F8)")
    ap.add_argument("--tecla-parar", default=None, metavar="TECLA", help="tecla de parar (padrão F9)")
    ap.add_argument("--retangulo", nargs=4, type=int, default=None, metavar=("X", "Y", "L", "A"),
                    help="recortar: usa este retângulo (da captura) em vez de selecionar na tela")
    ap.add_argument("--ponto", nargs=2, type=int, default=None, metavar=("X", "Y"),
                    help="definir-destino: usa este ponto (da captura) em vez de clicar na tela")
    ap.add_argument("--saida", default=None, metavar="ARQUIVO",
                    help="visualizar/diagnostico: arquivo de saída")
    ap.add_argument("--sem-pausa", action="store_true", help="desliga a tecla F8 de pausa")

    # Perfil: valores do arquivo viram padrões; a linha de comando sempre vence.
    pre, _ = ap.parse_known_args()
    nome_perfil = cast(Optional[str], pre.perfil)
    arq_perfil = cast(Optional[str], pre.perfil_arquivo)
    if nome_perfil or arq_perfil:
        caminho_p = localizar_perfil(nome_perfil or "", arq_perfil)
        validos = [a.dest for a in ap._actions if a.dest not in ("help", "perfil", "perfil_arquivo")]  # pyright: ignore
        ap.set_defaults(**carregar_perfil(caminho_p, validos))
        print(f"Perfil carregado: {caminho_p}")
    args = ap.parse_args()
    if args.modo is None:
        args.modo = "reproduzir"  # padrão do programa: gravar/reproduzir (sem OCR, sem extras)

    modo = str(args.modo)
    if args.webhook:
        os.environ["AUTOCLICK_WEBHOOK"] = str(args.webhook)
    if args.sem_captura_erro:
        os.environ["AUTOCLICK_CAPTURA_ERRO"] = "0"
    m_windows.teclas_do_ambiente()  # a janela define AUTOCLICK_TECLAS
    if args.tecla_pausa or args.tecla_parar:
        m_windows.definir_teclas(str(args.tecla_pausa or m_windows.NOME_PAUSA),
                                 str(args.tecla_parar or m_windows.NOME_PARAR))
    palavras = [str(p) for p in cast(list[Any], args.palavras)]
    pasta = str(args.pasta)
    config = str(args.config)
    log_caminho = cast(Optional[str], args.log)
    arquivo = str(args.arquivo)
    confianca = float(args.confianca)
    lang = str(args.lang)
    monitor = int(args.monitor)
    regiao_raw = cast(Optional[list[int]], args.regiao)
    regiao: Optional[Regiao] = (
        (regiao_raw[0], regiao_raw[1], regiao_raw[2], regiao_raw[3])
        if regiao_raw is not None
        else None
    )
    intervalo = float(args.intervalo)
    cooldown = float(args.cooldown)
    max_cliques = int(args.max_cliques)
    duracao = float(args.duracao)
    preview = bool(args.preview)
    debug = bool(args.debug)
    espera_hover = float(args.espera_hover)
    hold = float(args.hold)
    offset_raw = cast(list[int], args.offset)
    off_dx, off_dy = int(offset_raw[0]), int(offset_raw[1])
    jitter = float(args.jitter)
    foco = not bool(args.sem_foco)
    recheck = not bool(args.sem_recheck)
    estacionar = not bool(args.sem_estacionar)
    park_raw = cast(Optional[list[int]], args.estacionar)
    destino: Optional[tuple[int, int]] = (
        (int(park_raw[0]), int(park_raw[1])) if park_raw is not None else None
    )
    tesseract_cmd = str(args.tesseract)
    if tesseract_cmd:
        os.environ["TESSERACT_CMD"] = tesseract_cmd

    # ---- Modos que não varrem a tela em loop -------------------------------- #
    titulo_janela = cast(Optional[str], args.janela) or m_regras.carregar_janela_config(config)
    sem_teclado = bool(args.sem_teclado)
    if sys.platform == "win32":
        m_windows.api()  # liga o modo "DPI aware" antes de capturar/clicar

    esc_txt = str(args.escala).strip().lower()
    if esc_txt == "auto":
        m_deteccao.configurar_escala(True, None, float(args.escala_min), float(args.escala_max),
                          float(args.busca_escala))
    else:
        try:
            esc_val = float(esc_txt.replace(",", "."))
        except ValueError:
            sys.exit("--escala deve ser 'auto' ou um número (ex.: 1, 0.6).")
        if esc_val <= 0:
            sys.exit("--escala deve ser maior que zero.")
        m_deteccao.configurar_escala(True, esc_val)

    configurar_variacao(float(args.variacao))
    nome_arg = cast(Optional[str], args.nome)
    saida_arg = cast(Optional[str], args.saida)

    if modo == "validar":
        probs = validar_config(config, pasta, titulo_janela)
        print(relatorio_validacao(probs, config))
        sys.exit(1 if any(p.nivel == "erro" for p in probs) else 0)
    if modo == "relatorio":
        print(resumir_csv(nome_arg or log_caminho or "log.csv"))
        return
    if modo == "diagnostico":
        m_ferr.diagnostico(pasta, config, monitor, titulo_janela, confianca,
                           saida_arg or "diagnostico.txt")
        return
    if modo == "detectar-jogo":
        m_ferr.detectar_jogo(monitor, titulo_janela, confianca, saida_arg or "jogo_detectado.txt")
        return
    if modo in ("recortar", "calibrar", "definir-destino") and not nome_arg:
        sys.exit(f"O modo '{modo}' precisa do nome do botão: ... {modo} NOME")
    if modo == "recortar":
        ret_raw = cast(Optional[list[int]], args.retangulo)
        m_ferr.recortar(str(nome_arg), pasta, monitor, titulo_janela,
                        (ret_raw[0], ret_raw[1], ret_raw[2], ret_raw[3]) if ret_raw else None,
                        atraso=float(args.atraso))
        return
    if modo == "calibrar":
        m_ferr.calibrar(str(nome_arg), pasta, config, monitor, titulo_janela, confianca,
                        min(float(args.atraso), 1.0))
        return
    if modo == "visualizar":
        m_ferr.mapa_regras(pasta, config, monitor, titulo_janela, confianca,
                           m_regras.carregar_regras(config), saida_arg or "mapa_regras.png")
        return
    if modo == "definir-destino":
        pt_raw = cast(Optional[list[int]], args.ponto)
        m_ferr.definir_destino(str(nome_arg), pasta, config, monitor, titulo_janela, confianca,
                               cast(Optional[str], args.ancora),
                               (pt_raw[0], pt_raw[1]) if pt_raw else None)
        return

    if modo == "gui":
        from .interface import abrir_app
        abrir_app()
        return
    if modo in ("texto", "auto"):
        ocr_ok, ocr_motivo = ocr_disponivel()
        if not ocr_ok:
            sys.exit(f"O modo '{modo}' não está disponível: {ocr_motivo}.\n{DICA_OCR}")

    tel = nova_telemetria()
    controle = (controle_do_ambiente(modo)
                if modo in ("gravar", "reproduzir", "rotina", "imagem", "texto", "auto") else None)
    if not bool(args.sem_pausa) and modo in ("imagem", "texto", "auto", "reproduzir", "rotina"):
        pausa.iniciar()
        print(f"{m_windows.NOME_PAUSA} pausa/continua (mexer o mouse NÃO pausa). "
              f"{m_windows.NOME_PARAR} ou canto superior esquerdo para parar.")
    if bool(args.gui):
        from . import gui as m_gui
        m_gui.abrir(tel)

    vigia_tela = None
    if modo in ("reproduzir", "rotina", "imagem", "texto", "auto") and not preview and float(args.tela_parada) > 0:
        vigia_tela = m_robustez.vigia_do_ambiente(float(args.tela_parada), str(args.ao_travar),
                                                  monitor, titulo_janela, regiao)

    def finalizar() -> None:
        pausa.parar()
        print(tel.texto())
        if args.relatorio:
            tel.salvar(str(args.relatorio))

    motivo = "concluído"
    try:
        _executar(args, modo, tel, titulo_janela, sem_teclado, esc_txt, palavras, pasta, config,
                  log_caminho, arquivo, confianca, lang, monitor, regiao, intervalo, cooldown,
                  max_cliques, duracao, preview, debug, espera_hover, hold, off_dx, off_dy,
                  jitter, foco, recheck, estacionar, destino)
    except KeyboardInterrupt:
        motivo = "parado"
        raise
    except SystemExit:
        motivo = "encerrado"
        raise
    except Exception as e:
        motivo = f"erro: {type(e).__name__}"
        m_robustez.alerta("erro inesperado", f"{type(e).__name__}: {e}", monitor=monitor, regiao=regiao)
        raise
    finally:
        if vigia_tela is not None:
            vigia_tela.parar()
        if motivo == "concluído" and m_windows.PARADA.is_set():
            motivo = "parado"
        if modo in ("gravar", "reproduzir", "rotina", "imagem", "texto", "auto") and not preview:
            m_robustez.registrar_sessao(modo, motivo)
        if modo in ("imagem", "texto", "auto") and not preview:
            finalizar()
        else:
            pausa.parar()
        if controle is not None:
            controle.parar()


def _executar(args: argparse.Namespace, modo: str, tel: Telemetria, titulo_janela: Optional[str],
              sem_teclado: bool, esc_txt: str, palavras: list[str], pasta: str, config: str,
              log_caminho: Optional[str], arquivo: str, confianca: float, lang: str,
              monitor: int, regiao: Optional[Regiao], intervalo: float, cooldown: float,
              max_cliques: int, duracao: float, preview: bool, debug: bool, espera_hover: float,
              hold: float, off_dx: int, off_dy: int, jitter: float, foco: bool, recheck: bool,
              estacionar: bool, destino: Optional[tuple[int, int]]) -> None:
    if modo == "gravar":
        eventos = m_gravacao.gravar(arquivo, pasta, confianca, monitor, regiao, duracao, float(args.atraso),
                         janela=titulo_janela, ancora=cast(Optional[str], args.ancora),
                         teclado=not sem_teclado)
        if bool(args.gerar_regras):
            info_j = titulo_janela
            if info_j is None:
                try:
                    info_j = cast(Optional[str], json.loads(
                        Path(arquivo).read_text(encoding="utf-8")).get("janela", {}).get("titulo"))
                except (OSError, ValueError, AttributeError):
                    info_j = None
            m_gravacao.gerar_regras(eventos, config, bool(args.sobrescrever), info_j)
        return
    if modo == "rotina":
        from . import rotina_exec as m_rotina_exec
        m_rotina_exec.executar_arquivo(
            arquivo, float(args.velocidade), float(args.atraso), titulo_janela,
            not bool(args.sem_checar_janela), float(args.espera_janela), not sem_teclado, config, pasta,
            confianca, monitor, not bool(args.sem_auto_detect), float(args.auto_max),
            registro=Registro(log_caminho))
        return
    if modo == "reproduzir":
        m_reproducao.reproduzir(arquivo, float(args.velocidade), float(args.atraso),
                   loop=cast(Optional[int], args.loop), pausa_loop=float(args.pausa_loop),
                   janela=titulo_janela, checar_janela=not bool(args.sem_checar_janela),
                   espera_janela=float(args.espera_janela), teclas=not sem_teclado,
                   config=config, pasta=pasta, confianca=confianca, monitor=monitor,
                   auto_detect=not bool(args.sem_auto_detect), auto_max=float(args.auto_max),
                   registro=Registro(log_caminho))
        return

    if modo == "imagem" and not Path(pasta).is_dir():
        sys.exit(f"Pasta '{pasta}' não existe. Crie-a e coloque recortes PNG dos botões nela.")

    regras = m_regras.carregar_regras(config)
    if regras:
        resumo = ", ".join(
            f"{nome}={r.acao}" + (f"({r.vezes}x)" if r.vezes else "") for nome, r in regras.items()
        )
        print(f"Regras de '{config}': {resumo}")
        if modo == "imagem":
            for nome in regras:
                if not any((Path(pasta) / f"{nome}{ext}").exists() for ext in (".png", ".jpg")):
                    print(f"  Aviso: a regra '{nome}' não tem imagem '{nome}.png' em '{pasta}'.")
    elif modo == "imagem":
        print(f"Sem '{config}': todos os botões da pasta serão clicados repetidamente.")

    # Âncoras citadas em destinos nunca devem ser clicadas: viram regra "ancora".
    for r in list(regras.values()):
        if r.destino_ancora is not None and r.destino_ancora[0] not in regras:
            regras[r.destino_ancora[0]] = Regra(acao="ancora")
    if any(r.destino_janela is not None for r in regras.values()) and not titulo_janela:
        sys.exit("Há destinos relativos à janela em '" + config + "'. Informe a janela: "
                 '--janela "Título" (ou "_janela": "Título" no json).')
    if titulo_janela and regiao is not None:
        print("Aviso: --janela tem prioridade sobre --regiao.")
    if modo == "imagem":
        print("Escala dos botões: "
              + ("automática (os PNGs devem estar no tamanho máximo da janela)"
                 if esc_txt == "auto" else f"fixa em {esc_txt}") + ".")

    print(f"Modo: {modo} | Ctrl+C ou mouse no canto superior esquerdo para parar.")
    registro = Registro(log_caminho)
    fluxo = carregar_fluxo(config)
    if fluxo is not None:
        print("Fluxo do jogo: " + " → ".join(fluxo.nomes()))
    if any(r.requer or r.ignorar_se or r.etapa for r in regras.values()):
        print("Condições (requer/ignorar_se/etapa) ativas.")
    op = Opcoes(
        modo=modo, config=config, pasta=pasta, confianca=confianca, lang=lang,
        palavras=palavras, monitor=monitor, regiao=regiao, titulo_janela=titulo_janela,
        intervalo=intervalo, cooldown=cooldown, max_cliques=max_cliques, duracao=duracao,
        preview=preview, debug=debug, espera_hover=espera_hover, hold=hold, off_dx=off_dx,
        off_dy=off_dy, jitter=jitter, foco=foco, recheck=recheck, estacionar=estacionar,
        destino=destino, sem_teclado=sem_teclado, painel=float(args.painel),
        janela_max=float(args.janela_max), inatividade=float(args.inatividade),
        ao_travar=str(args.ao_travar))
    Varredura(op, regras, registro, tel).rodar()
