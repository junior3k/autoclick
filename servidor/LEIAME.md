# Servidor de atualizações e download do Autoclick

Roda no seu PC, atrás do seu túnel cloudflared. **Tudo é público e sem convite**:

| Endereço | O que é |
|---|---|
| `https://ac.cabro.me/download` | página com o botão **Baixar** (qualquer pessoa) |
| `https://ac.cabro.me/download/arquivo` | o zip da última versão estável |
| `https://ac.cabro.me/download/api/v1/...` | API que o próprio programa usa para checar e baixar atualizações |
| `https://ac.cabro.me/ac-xxxxxxxxxxxx/painel` | seu painel (caminho secreto + token) |

## Resumo: como mandar o programa para alguém

**Uma vez só:** `instalar_servidor.bat ac.cabro.me` → colocar a regra no cloudflared → `iniciar_servidor.bat`.

**Toda versão nova:**
1. `publicar.bat --exe` — roda os testes, **constrói o .exe sozinho**, assina e publica (entra em *beta*).
2. Teste você mesmo (Configurações → "Receber também versões beta").
3. `servidor.bat promover 0.7.0` (o número que o passo 1 mostrou). A partir daí:
   - a página `/download` passa a oferecer essa versão;
   - quem já tem o programa recebe a atualização (ao abrir, ou em Configurações → Atualizações).

**Para um amigo novo:** é só mandar o link `https://ac.cabro.me/download`. Ele baixa, extrai e abre `Autoclick.exe`. Sem convite, sem configurar nada.

## Instalação detalhada

```
instalar_servidor.bat ac.cabro.me
```
Gera as chaves de assinatura, o prefixo secreto do painel e o **token do painel** (aparece uma vez só — guarde!),
grava a chave pública e o endereço da API dentro do programa (`autoclick\chave_publica.py`, `autoclick\servidor_padrao.py`)
e registra o início automático no logon. **Faça uma cópia segura de `servidor\dados\chave_privada.txt`**
(sem ela não dá para publicar mais).

### Cloudflared
Adicione ao seu `config.yml` o bloco mostrado na instalação (modelo em `cloudflared.exemplo.yml`), antes da
regra final `http_status:404`, e reinicie o cloudflared. Uma regra cobre `/download` e o painel; o resto do
domínio continua com as suas outras APIs. Teste: `https://ac.cabro.me/download/api/v1/saude` → `{"ok":true}`.

### Iniciar
`iniciar_servidor.bat` (reinicia sozinho se cair; log em `servidor\dados\servidor.log`).
Dependências: `uv sync --extra servidor` (FastAPI + uvicorn). Escuta só em 127.0.0.1:8765.

## Controle de versões
- `servidor.bat versoes` · `promover X` · `retirar X` · `percentual X 20` (libera para 20 % das instalações) ·
  `minima X Y` (versão mínima obrigatória) · `aviso "texto"` (mensagem mostrada no programa).
- Deu problema numa versão? `servidor.bat retirar X` — ela some da página e das atualizações.

## O que o servidor sabe sobre quem usa
Nada pessoal. Cada programa gera um número aleatório local (`autoclick_instalacao.txt`) só para o painel contar
instalações ativas por versão. Não há nomes, contas nem convites.
**Relatórios de problema** só chegam se a pessoa clicar em "Enviar relatório" e confirmar a lista do que vai
(log recente, histórico, capturas de erro, dados do sistema; nunca webhook, botões ou gravações).

## Segurança — resumo
- **Atualizações assinadas (Ed25519):** a chave privada fica só no seu PC; a pública vai embutida no programa.
  Mesmo que alguém invada o servidor ou o domínio, os programas recusam qualquer pacote sem a sua assinatura.
  O servidor também recusa registrar pacote com assinatura ruim. A assinatura é invisível para quem usa.
- **Limites folgados por IP** (uso normal nunca chega perto): 300 pedidos/min na API, 30 downloads do zip/hora,
  5 relatórios/hora. Servem só para robôs não esgotarem o seu upload de casa.
- Relatórios: máx. 5 MB cada e só os 300 mais recentes ficam guardados.
- Painel: token só como hash, CSP, sem upload de pacotes (publicar é só pelo seu PC), bloqueio após tentativas erradas.
- Perdeu o token? `servidor.bat novo-token`. Perdeu a chave privada? É preciso gerar outra e distribuir um programa
  novo manualmente (a pública está embutida).

## Comandos
`instalar` · `rodar` · `status` · `link` · `versoes` · `publicar` · `promover` · `retirar` · `percentual` · `minima` ·
`backup` · `relatorios` · `eventos` · `aviso` · `novo-token` · `exportar-chave` — todos via `servidor.bat <comando>`.

## Backup
Diário e automático (14 mais recentes). Guarde fora do PC: `servidor\dados\` inteira + a chave privada.
