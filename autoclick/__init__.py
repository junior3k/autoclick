"""
Autoclick inteligente: olha a tela, encontra botões e clica neles (Windows).

Uso mais simples (interface gráfica):
    uv run autoclick            # abre a janela; "Gravar & Reproduzir" é a página inicial
    (ou dê dois cliques em iniciar.bat)
    Tudo que existe no terminal está na janela. Sem argumentos = janela.
    No terminal, se você não informar o modo, o padrão é "reproduzir".

Instalação (uv) - o essencial já vem no pyproject (mss, numpy, opencv):
    uv sync
    # OPCIONAL, só para os modos "texto" e "auto" (OCR). Sem isto o programa roda
    # normalmente; esses dois modos apenas ficam desativados, com um aviso de como instalar:
    uv sync --extra ocr     # (ou: uv add pytesseract)
    # + Tesseract OCR instalado no sistema:
    #   https://github.com/UB-Mannheim/tesseract/wiki  (marque o idioma Portuguese)

Modos:
    texto      (OCR, opcional) lê a tela e clica em palavras como "Aceitar", "Continuar"...
    imagem     procura imagens de botões (PNGs recortados por você) na tela
    auto       (OCR, opcional) detecta retângulos com formato de botão, lê o rótulo e clica
    gui        abre a interface gráfica (padrão sem argumentos)
    gravar     grava SEUS cliques, arrastos e teclas (coordenadas e tempo)
    reproduzir refaz uma gravação (opcionalmente em loop) - MODO PADRÃO
    validar    confere o botoes.json (typos, PNG sem regra, destinos, condições)
    diagnostico  checa o ambiente e gera diagnostico.txt (use antes do 1º teste real)
    recortar NOME     seleciona um botão na tela e salva botoes/NOME.png (avisa se ruim)
    calibrar NOME     mede botão normal/cinza/hover e grava queda_saturacao
    visualizar        desenha botões, ações e destinos em mapa_regras.png
    definir-destino NOME   clique no ponto de soltura e ele grava o "destino" no json
    relatorio ARQ.csv resume um --log

Controle durante a execução:
    F8 pausa/continua (SÓ pela tecla: mexer o mouse NÃO pausa). F9 ou canto superior
    esquerdo para. --gui abre janelinha; --painel mostra status periódico;
    --relatorio resumo.md salva o resumo; --variacao 0.15 espalha os tempos (±15%).
    --perfil NOME usa perfis/NOME.json (as mesmas opções do terminal; o terminal vence).

Regras extras no botoes.json:
    "requer": ["a"], "ignorar_se": ["b"], "etapa": "nome"   só age se a condição valer
    "acao": "marcador"   só é "visto" (para condições/etapas), nunca clicado
    "acao": "erro", "ao_ver": "avisar|parar"   tela de erro/desconexão
    "_fluxo": [{"etapa": "lobby", "quando": ["jogar"], "timeout": 300,
                "ao_estourar": "avisar|parar|reiniciar"}]   etapas do jogo

Exemplos:
    python autoclick_inteligente.py imagem --pasta botoes --janela Roblox --preview
    python autoclick_inteligente.py imagem --pasta botoes --janela Roblox --log acoes.csv
    python autoclick_inteligente.py texto --palavras "aceitar" "continuar" --preview
    python autoclick_inteligente.py gravar --janela Roblox --ancora mapa_ref --gerar-regras
    python autoclick_inteligente.py reproduzir --arquivo gravacao.json --loop
    python autoclick_inteligente.py reproduzir --arquivo gravacao.json --loop --pasta botoes         --janela Roblox     # com "auto_detect": true no json, clica em maximo/novamente

Tamanho da janela (modo imagem):
    Tire os PNGs com a janela no MAIOR tamanho possível. Se depois você a deixar menor,
    o programa descobre sozinho a escala (todos os botões encolhem juntos) e a reaprende
    se a janela for redimensionada. Com --janela ele também acompanha a janela quando ela
    é movida. Pode ser forçada com --escala 0.6, ou desligada com --escala 1.
    Obs.: com recortes reduzidos o score cai um pouco; se faltar reconhecimento, use
    --confianca 0.8.

Regras por botão (botoes.json, ao lado do script; a chave é o nome do PNG sem extensão):
    {
      "_janela":        "Roblox",
      "maximo":         { "acao": "clicar" },
      "proxima":        { "acao": "clicar", "intervalo": 2 },
      "torre":          { "acao": "arrastar", "vezes": 1,
                          "destino": { "ancora": "mapa_ref", "offset": [320, -140] } },
      "mapa_ref":       { "acao": "ancora" },
      "inicio_partida": { "acao": "inicio" }
    }
    - clicar    clica sempre que vê o botão (padrão para PNGs sem regra).
    - arrastar  aperta no botão, leva até "destino", solta, e confirma que o botão ficou
                cinza. "vezes" = quantas vezes POR PARTIDA (padrão 1). Se não ficar cinza,
                tenta de novo ("tentativas", padrão 3).
    - inicio    PNG de algo que só aparece no começo da partida: ao aparecer, zera os
                contadores de "vezes" (libera os botões de "uma vez por partida").
    - ancora    PNG de uma referência do mapa (nunca é clicado); serve de base ao destino.
    Formas do "destino" (da mais frágil para a mais robusta):
        [980, 540]                                   coordenada FIXA de tela (quebra se a
                                                     janela mexer ou a câmera andar)
        {"janela": [0.62, 0.55]}                     fração da janela do jogo (acompanha
                                                     mover/redimensionar; exige --janela)
        {"ancora": "mapa_ref", "offset": [dx, dy]}   relativo a uma imagem do mapa (acompanha
                                                     também a câmera; dx/dy em pixels do PNG
                                                     de referência, a partir do centro dele)
    A âncora só funciona se a câmera apenas deslizar: girar ou dar zoom no mapa muda
    as distâncias e exige regravar o ponto.
    "auto_detect": true  = o botão é clicado assim que for detectado, em qualquer modo, inclusive
                durante a REPRODUÇÃO de uma gravação: se ele aparecer, a reprodução pausa,
                clica nele enquanto estiver à vista e só então continua (só para "clicar").
                false = nunca é clicado sozinho. Sem a chave: os modos de varredura clicam
                (como sempre) e a reprodução ignora o botão.
    "escolha": "primeiro" | "ultimo" | "aleatorio"  = vários botões parecidos aparecem juntos
                (ex.: 3 cartas de "escolha uma") e basta clicar em UM, uma vez por aparição.
                Com um único PNG que case em todos (uma parte igual entre eles, como a ponta
                do botão amarelo), ele clica em um só. "grupo": "nome" junta PNGs diferentes
                na mesma escolha. O grupo só destrava depois que as cartas somem da tela.
    "reiniciar_loop": true  = clicar neste botão (ex.: Jogar Novamente) reinicia o ciclo: zera
                a partida e, na reprodução com --loop, a gravação volta ao início SEM clicar de
                novo neste botão (o clique gravado nele é pulado uma vez).
    Opcionais: "offset": [dx, dy], "intervalo": segundos, "confirmar_cinza": true/false,
               "queda_saturacao": 0.5, "tentativas": 3, "espera_confirmacao": 0.7.

Gravação e reprodução:
    python autoclick_inteligente.py gravar --arquivo gravacao.json --janela Roblox --gerar-regras
        Grava seus cliques, arrastos e teclas até apertar F9. Cada ponto é salvo também como
        fração da janela. Com --gerar-regras, o ponto onde você soltou vira o "destino" no
        botoes.json (por âncora se usar --ancora NOME, senão por fração da janela).
        ATENÇÃO: tudo o que você digitar durante a gravação é salvo (não digite senhas);
        --sem-teclado desliga a gravação de teclas.
    python autoclick_inteligente.py reproduzir --arquivo gravacao.json --velocidade 1 --loop
        Refaz a gravação. --loop repete até F9 (--loop 5 = 5 vezes). Antes de cada ação
        confere se a janela do jogo está ativa: tenta trazê-la para frente e, se não der,
        pausa até ela voltar. F9 ou mouse no canto superior esquerdo para parar.
    Em qualquer modo de varredura, --log acoes.csv registra cada ação automática e também
    as teclas que você apertar.

Segurança:
    - Jogue o mouse para o canto superior esquerdo da tela para ABORTAR (failsafe).
    - Ctrl+C no terminal também para.
    - Use --preview primeiro: só salva preview.png com o que foi detectado, sem clicar.
    - Use apenas em apps/sites onde automação é permitida (veja os termos de uso).
"""

__version__ = "0.12.0"
