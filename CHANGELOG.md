# Histórico de versões

(O texto de cada seção `## x.y.z` vira as "notas" mostradas ao amigo quando você publica essa versão.)

## 0.7.0
- Atalho global F11 para reproduzir a gravação (e para parar), configurável em Configurações → Atalhos.
- Som suave ao concluir cada volta do loop; liga/desliga na barra de mensagens a qualquer momento, mesmo durante a execução.
- Novo ícone do aplicativo (janela, barra de tarefas e executável).
- Acentos corretos no terminal do Windows.

## 0.13.1
- Correção: a janela voltou a não carregar numpy/OpenCV (a leitura de atalhos foi movida para um módulo leve, `autoclick/atalhos.py`); o teste automático da janela falhava no Linux.

## 0.13.0
- Download e atualizações agora ficam 100% no GitHub, sem servidor ligado no PC: a página de download é servida pelo GitHub Pages e os arquivos vêm das Releases do repositório (24 horas por dia).
- Publicar uma versão é criar uma tag (`git tag v0.13.0 && git push --tags`): o GitHub testa, constrói o .exe, assina, cria a Release e atualiza o site sozinho. A assinatura Ed25519 das atualizações continua sendo conferida pelo programa.
- Removidos, por dependerem de um servidor ligado: painel, canal beta, percentual de liberação, contagem de instalações e envio de relatórios. “Enviar relatório” virou “Salvar relatório…” (um .zip que você manda a quem mantém o programa).
- `site/config.json` permite mostrar um aviso a todos e exigir uma versão mínima.
- Novas ferramentas: `tools/gerar_chave.py` (chaves, uma vez) e `tools/montar_release.py`.

## 0.12.0
- Sons por tipo de ação, cada um com o seu liga/desliga em Configurações → Segurança e avisos e um botão "Ouvir": início e fim da gravação (duas notas graves, subindo e descendo), início e fim da reprodução e das rotinas (três notas, subindo e descendo), fim de volta (o sino de sempre) e um tique opcional a cada segundo da contagem inicial.
- Todos seguem o estilo e o volume escolhidos (sino, gota, marimba, discreto ou seu .wav; o tique é sempre gerado pelo programa).
- Liga/desliga vale na hora, mesmo com algo rodando. O toque de início da gravação sai um instante antes do cronômetro começar.

## 0.11.0
- Atalhos: agora é só clicar em “Mudar” e apertar a tecla (ou a combinação) em vez de digitar o nome. Esc cancela e há o botão “Padrão”.
- Combinações com Ctrl, Alt e Shift (ex.: Ctrl+F11) e teclas extras: Insert, Delete, Home, End, PageUp, PageDown, setas e teclado numérico.
- Se o atalho já é usado por outra função, o programa oferece trocar os dois; letras e números sozinhos geram um aviso (costumam ser teclas do jogo).
- Os modificadores apertados para parar a gravação (ex.: Ctrl+F9) não entram no fim do arquivo gravado.
- Mouse como atalho: não incluído.

## 0.10.2
- Reprodução: agora mostra "volta 3 · 04:12 / 10:00" e uma barra de progresso. O total da volta inclui a espera final e já considera a velocidade; pausas e esperas por botão não contam no tempo decorrido.
- Rotinas: a mesma barra mostra a volta da rotina e o script em andamento ("volta 2 · coletar").
- Bandeja: a dica do ícone mostra o progresso da volta.

## 0.10.1
- Gravar: novo cronômetro na tela, que começa quando a gravação de fato começa (depois da contagem), com a lista ao vivo de teclas e cliques e o tempo de cada um.
- Ao terminar a gravação, o console mostra uma conferência: quantas vezes cada tecla foi apertada e em que tempos. É só para conferir; o arquivo gravado não muda.
- Corrigido: a tecla de reproduzir (F11) era gravada como se fosse uma ação do jogo.

## 0.10.0
- Rotinas: junte vários scripts gravados do jogo (coletar, loja, plantar…). Lista em sequência (com repetições por script) que repete, mais scripts em intervalos ("loja a cada 5 min") que entram entre os scripts, nunca no meio de um. Quantos você quiser.
- Esperas: tempo entre scripts customizável, esperas fixas na lista e "esperar botão/NPC aparecer" (como item e antes de qualquer script, com tempo máximo). Se algo falhar, a rotina para e avisa.
- Cada jogo tem várias gravações (jogos/NOME/gravacoes/) e a sua rotina; F11 pode iniciar a rotina.
- CORREÇÃO: o tempo entre a última ação e o fim da gravação agora faz parte da volta. Se você parou a gravação aos 10 min com a última ação aos 7, o loop recomeça aos 10. Gravações antigas ganham "Espera final…" no editor.

## 0.9.1
- Cadastrar o jogo detectado guarda o place id e o universe id juntos e sugere o nome (consulta a API pública do Roblox; se falhar, pergunta).
- Um jogo reconhecido por um dos ids aprende sozinho o outro.

## 0.9.0
- Jogos do Roblox: página "Jogos" com "Roblox (geral)" + um perfil por jogo (botões, regras, gravação e opções próprios; o jogo soma ao geral e vence se o nome for igual). Perfis antigos movidos automaticamente.
- Reconhecimento do jogo: pelos logs do Roblox (experimental), por PNGs de assinatura na tela ou à mão; troca rápida pelo menu "🎮 jogo" e pela bandeja; coletor de pistas que traz só as linhas úteis dos logs.
- Estatísticas por jogo (voltas/hora, tempo por volta, cliques por botão) com exportação CSV.
- Menu da bandeja: pausar/continuar o loop, reproduzir/gravar, som e troca de jogo.
- Sons: sino, gota, marimba, discreto ou seu .wav; volume ajustável, vale na hora mesmo durante a execução.
- Atualização baixada em segundo plano; instala quando você quiser, com o programa parado (ele pergunta) ou ao fechar. Janela "O que mudou" depois de atualizar.
- Mensagens de erro claras em português (sem internet, servidor fora do ar, muitas tentativas, pacote inválido, disco cheio).

## 0.8.0
- Atualizar não exige mais convite nem chave: o programa já vem com o endereço do servidor.
- Página pública de download (/download) com o programa pronto para usar.
- Opção "Receber também versões beta" em Configurações → Atualizações.

## 0.6.0
- Servidor de atualizações próprio: o programa verifica, baixa e instala versões novas, assinadas pelo administrador.
- Atualização segura: confere assinatura e SHA-256, faz backup, testa a versão nova e volta sozinha se ela não abrir.
- Convite por amigo (importar em Configurações), canais estável/beta e versão mínima obrigatória.
- Enviar relatório de problema (só com a sua confirmação).
- Aviso no menu quando há versão nova; verificação opcional ao abrir.

## 0.5.0
- Detecção de tela travada, reconexão automática, aviso de resolução/DPI.
- Editor de gravação, marcadores de verificação, atalhos configuráveis, bandeja, histórico, notificações.
