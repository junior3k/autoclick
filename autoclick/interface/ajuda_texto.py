"""Texto da página Ajuda (curto e prático). Cada item: (título, texto)."""
from __future__ import annotations

TOPICOS: list[tuple[str, str]] = [
    ("Primeiros passos", """\
1. Em Configurações, escolha a janela do jogo (ex.: Roblox) e a pasta dos botões.
2. Em Gravar & Reproduzir, clique em “Iniciar gravação”, vá ao jogo e jogue UMA partida normalmente.
3. Aperte a tecla de parar (F9) para terminar.
4. Clique em “Reproduzir” (de preferência “Em loop até parar”) e deixe o programa repetir.

Pausar/continuar: F8 (ou o botão do topo). Parar: F9 (ou jogar o mouse no canto superior esquerdo da tela). As teclas podem ser trocadas em Configurações: clique em “Mudar” e aperte a tecla ou a combinação (Ctrl, Alt ou Shift + tecla, ex.: Ctrl+F11). Esc cancela.
Mexer o mouse NÃO pausa o programa."""),
    ("Gravar e reproduzir", """\
A gravação guarda cliques, arrastos e teclas com o tempo certo. Ao reproduzir, o programa repete tudo na mesma cadência e confere se a janela do jogo está ativa.

• Velocidade: 1× é igual ao que você fez; valores maiores aceleram (pode errar em jogos sensíveis).
• Repetir / Em loop: faz várias voltas, com uma pausa entre elas.
• “Clicar sozinho nos botões auto_detect”: durante a reprodução, botões marcados assim (ex.: “Pular”, “Continuar”) são clicados assim que aparecem.
• F10 (padrão) inicia/para a gravação de qualquer lugar, sem precisar voltar a esta janela.
• F11 (padrão) reproduz a gravação de qualquer lugar; apertar de novo para a reprodução.
• 🔔 “Som por volta” (barra de mensagens): toca um sininho suave ao concluir cada volta do loop. Dá para ligar e desligar a qualquer momento, até com a reprodução rodando.
• Se a janela ou a resolução mudou desde a gravação, aparece um aviso amarelo; o botão “Usar tamanho atual” passa o tamanho de hoje a ser a referência."""),
    ("Editor de gravação", """\
Abra com “Editar gravação…”. Você vê todos os eventos em ordem e pode:
• Apagar (Delete) ou Duplicar eventos selecionados;
• Inserir espera: soma segundos antes do evento selecionado (valor negativo encurta);
• Ajustar tempo de um evento; Cortar antes / depois do evento selecionado;
• Inserir marcador de verificação (veja abaixo);
• Desfazer (Ctrl+Z) e Refazer (Ctrl+Y). Ao salvar, o original fica em <arquivo>.bak."""),
    ("Marcadores de verificação", """\
Um marcador faz a reprodução ESPERAR até um botão aparecer (ou sumir) antes de continuar. Ex.: esperar o botão “Jogar” aparecer antes de clicar nele.

• Tempo máximo: quanto esperar.
• Se estourar: avisar (alerta e segue), parar (encerra) ou pular (só segue).
• O botão precisa existir como imagem na pasta de botões."""),
    ("Botões e regras", """\
Cada botão é uma imagem PNG recortada do jogo. A regra diz o que fazer ao vê-lo: clicar, esperar, avisar, tratar como tela de erro etc.

• “Recortar novo botão” captura a tela e deixa você desenhar um retângulo.
• “Validar” procura erros no botoes.json antes de jogar.
• “Desfazer / Refazer” revertem salvamentos de regras; trocar de botão com alterações pergunta se quer salvar."""),
    ("Telas de erro e reconexão", """\
Uma regra com ação “erro” representa uma tela como “Desconectado”.
• ao_ver = avisar: só alerta; parar: encerra; reconectar: recomeça a partida.
• “Reconectar com”: o botão (regra de clicar) que fecha a tela de erro ou reconecta.
• Para não ficar tentando para sempre: no máximo 5 reconexões em 10 minutos; depois disso o programa encerra e avisa."""),
    ("Tela travada", """\
Em Configurações > Segurança, “Avisar se a tela não mudar por N segundos” liga um vigia: se nada na tela do jogo mudar por esse tempo, o programa salva uma captura em erros/, avisa e (se escolhido) encerra.
Use um tempo maior que as esperas normais do jogo (ex.: 180 s). 0 desliga."""),
    ("Modo automático", """\
Sem gravação: o programa olha a tela e clica nos botões conforme as regras.
• Imagem: usa as PNGs (recomendado, não precisa de nada extra).
• Texto/Auto (OCR): lê palavras na tela. É OPCIONAL: precisa do Tesseract e do pytesseract; sem eles o resto do programa funciona normalmente.
A “Visão ao vivo” mostra o que o programa está enxergando."""),
    ("Avisos e bandeja", """\
Alertas (tela parada, erro, reconexão falhou) aparecem como balão do Windows e, se configurado, vão para um webhook do Discord ou para o Telegram (formato telegram:TOKEN@CHAT_ID).
A bandeja (perto do relógio) mostra o estado por cor: cinza parado, verde rodando, amarelo pausado, vermelho gravando. Botão direito: Mostrar, pausar/continuar o loop, reproduzir/parar a gravação, gravar, parar tudo, ligar/desligar o som e trocar de jogo."""),
    ("Jogos do Roblox", """\
O Roblox é uma plataforma com milhares de jogos; cada um tem botões e regras diferentes. Na página Jogos você cadastra cada jogo; o “Roblox (geral)” guarda o que vale para todos (desconectado, reconectar, erro de conexão) e cada jogo soma os seus por cima (se o nome for igual, o do jogo vence).
Com um jogo escolhido, as páginas Gravar, Botões e Automático usam os arquivos dele (pasta jogos/NOME: botoes/, botoes.json, gravacao.json) e “Salvar minhas opções neste jogo” guarda intervalo, variação, rigor, loop e som para ele. Troque rápido pelo botão “🎮 jogo ▾” ao lado das mensagens ou pelo menu da bandeja.
Reconhecer o jogo: (1) pelos logs do Roblox, comparando o número do jogo (o que aparece em roblox.com/games/NÚMERO) com os ids cadastrados — experimental; (2) pela tela, com PNGs “assinatura” que só existem naquele jogo; (3) à mão. “Coletar pistas dos logs” salva em pistas_roblox.txt só as linhas úteis, sem o resto do log.
Estatísticas por jogo (voltas por hora, tempo por volta, cliques por botão) ficam na mesma página, com exportação para CSV."""),
    ("Rotinas (vários scripts juntos)", """\
Página Rotinas: cada jogo pode ter vários scripts gravados (coletar, loja, plantar…) e uma rotina que os junta. O mouse é um só, então os scripts se revezam: um só começa quando o anterior termina.
• Sequência: lista em ordem que repete (cada script com suas repetições). Entre os itens use “Esperar tempo” ou “Esperar botão/NPC” (espera um botão aparecer, com tempo máximo; se não vier, a rotina para e avisa — ou segue, se você escolher). O tempo padrão entre scripts e entre voltas é ajustável.
• Intervalos: scripts que entram sozinhos (“loja a cada 300 s”) entre dois scripts da sequência ou durante uma espera, nunca no meio de um.
• Qualquer script pode esperar um botão antes de começar. Se algo falhar, tudo para e o aviso aparece.
• Para gravar um script novo use “Gravar novo script”. A tecla de reproduzir (F11) pode iniciar a rotina em vez da gravação (opção na própria página)."""),
    ("Espera final da gravação", """\
O tempo entre a última ação e o momento em que você encerra a gravação (F9) também é gravado: se você parou aos 10 min com a última ação aos 7, cada volta do loop dura 10 min. Para gravações antigas, use Editar → “Espera final…”.\n\nO cronômetro da página Gravar começa quando a gravação de fato começa (depois da contagem) e lista as teclas e cliques com o tempo de cada um; ao terminar, o console resume quantas vezes cada tecla foi apertada. É só para conferir: não altera o arquivo. A tecla de reproduzir (F11) não é gravada.\n\nNa reprodução, o painel mostra “volta 3 · 04:12 / 10:00” e uma barra de progresso; o total da volta inclui a espera final. Nas Rotinas aparece também o script em andamento, e a dica do ícone da bandeja mostra o mesmo progresso."""),
    ("Som", """\
Cada tipo de som liga e desliga sozinho: fim de volta, início/fim da gravação, início/fim da reprodução (e das rotinas) e um tique na contagem inicial. Os de gravação e reprodução soam diferentes (duas notas graves x três notas), subindo ao iniciar e descendo ao terminar. Use “Ouvir” para testar.
Configurações → Segurança e avisos: escolha o estilo (sino, gota, marimba, discreto ou um .wav seu), o volume e use “Ouvir”. O som toca ao concluir cada volta do loop; liga/desliga na barra de mensagens ou na bandeja, a qualquer momento."""),
    ("Atualizações e relatórios", """\
Não precisa de convite nem de senha. Em Configurações → Atualizações, “Verificar atualização” consulta o site de downloads para saber se há versão nova; “Verificar ao abrir” faz isso sozinho; a versão nova é baixada em segundo plano e só instala quando você mandar, quando o programa estiver parado (ele pergunta) ou ao fechar. Depois de atualizar, uma janela mostra “O que mudou” uma única vez.
Toda atualização vem ASSINADA pelo autor e é recusada se a assinatura não bater. Seus botões, regras, perfis e gravações nunca são sobrescritos, e se a versão nova não abrir a anterior volta sozinha. Uma versão marcada como obrigatória aparece com esse aviso.
“Salvar relatório…” cria um .zip com só o log recente, o histórico, até 3 capturas de erro e dados do sistema (você vê a lista e confirma antes) e NÃO envia nada: você escolhe a quem mandar o arquivo. Nunca vão webhook, botões nem gravações."""),
    ("Arquivos criados", """\
• botoes/ e botoes.json — imagens e regras
• gravacao.json (+ .bak ao editar) — suas gravações
• perfis/ — conjuntos de opções salvas (os antigos foram movidos para jogos/)
• jogos/NOME/ — botões, regras, gravação e opções de cada jogo
• pistas_roblox.txt — só as linhas úteis dos logs do Roblox (quando você pede)
• historico/sessoes.jsonl — histórico de execuções
• erros/ — capturas de tela de quando algo deu errado
• logs/autoclick.log — registro do que apareceu no console (rotativo)
• backup/ — cópias feitas ao atualizar
• autoclick_instalacao.txt — número aleatório desta instalação (só para contar instalações ativas)"""),
    ("Problemas comuns", """\
• “Nada acontece ao reproduzir”: confira a janela do jogo em Configurações e deixe-a em primeiro plano.
• Clica no lugar errado: a resolução/janela mudou; use “Usar tamanho atual” ou regrave.
• Não acha o botão: recorte de novo, ou baixe a “confiança” em Configurações.
• OCR indisponível: instale em Configurações > Dependências opcionais (ou ignore: não é necessário).
• Mais detalhes: veja logs/autoclick.log."""),
    ("Uso responsável", """\
Muitos jogos (inclusive o Roblox) restringem automação nos termos de uso. Use por sua conta e risco, de preferência em modos/servidores em que isso seja permitido. O botão “Só detectar” (modo de teste) mostra o que seria clicado sem clicar em nada."""),
]
