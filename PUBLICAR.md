# Como publicar o Autoclick (GitHub, sem servidor no seu PC)

A página de download (`https://ac.cabro.me/`) é servida pelo **GitHub Pages** e os arquivos vêm das
**Releases** do repositório. Nada depende do seu PC ligado.

## Configurar uma vez só

1. **Git só nesta pasta** (nada global):
   ```powershell
   git config --local user.name  "SEU NOME"
   git config --local user.email "ID+USUARIO@users.noreply.github.com"
   git remote add origin git@github.com:USUARIO/REPO.git
   ```
   Acesso por SSH com uma chave só deste repositório:
   ```powershell
   ssh-keygen -t ed25519 -f $HOME\.ssh\id_autoclick -C "autoclick"
   git config --local core.sshCommand "ssh -i $HOME/.ssh/id_autoclick -o IdentitiesOnly=yes"
   ```
   Cole `id_autoclick.pub` em GitHub > Settings > SSH keys (ou em Deploy keys do repositório, com escrita).
2. **Chaves de assinatura** (as atualizações só são aceitas se assinadas por você):
   ```powershell
   uv run python tools/gerar_chave.py --escrever --url https://ac.cabro.me
   ```
   - Faça commit de `autoclick/chave_publica.py` e `autoclick/servidor_padrao.py` (a chave pública não é segredo).
   - Cole a **chave privada** mostrada em GitHub > repositório > Settings > Secrets and variables > Actions >
     New repository secret, com o nome **`AC_CHAVE_PRIVADA`**.
   - Guarde uma cópia da chave privada FORA do PC (gerenciador de senhas). Sem ela não dá para publicar
     versões que quem já tem o programa aceite.
3. **Pages**: Settings > Pages > Source = **GitHub Actions**; em *Custom domain* coloque `ac.cabro.me` e
   marque *Enforce HTTPS* quando liberar.
4. **DNS** (onde está o cabro.me): registro `CNAME`  `ac` → `USUARIO.github.io`
   (na Cloudflare, "somente DNS"/nuvem cinza). Remova antes qualquer rota antiga de `ac.cabro.me` do
   cloudflared/túnel. Os outros subdomínios e o `cabro.me` não são afetados.
5. `git push -u origin master`.

## Publicar uma versão

1. Ajuste o código, o `CHANGELOG.md` (a seção `## 0.13.0` vira as notas da Release) e a versão em
   `autoclick/__init__.py` e `pyproject.toml`.
2. ```powershell
   git commit -am "Versão 0.13.0"
   git push
   git tag v0.13.0
   git push --tags
   ```
   A tag precisa ser **igual** à versão do código (`v0.13.0` ↔ `0.13.0`).
3. Em uns 5 a 10 minutos (aba Actions > publicar): testes, `.exe`, assinatura, Release e site no ar.
4. Mande aos amigos o link `https://ac.cabro.me/`. Quem já tem o programa recebe a atualização
   (ao abrir, ou em Configurações > Atualizações).

## Dia a dia

- **Aviso para todos / versão mínima obrigatória:** edite `site/config.json`
  (`{"mensagem": "texto", "minima": "0.13.0"}`), faça commit e push, e rode Actions > publicar > *Run workflow*
  informando a tag atual.
- **Versão ruim:** apague a Release no GitHub (e a tag) e rode *Run workflow* com a tag da versão boa
  anterior: o site volta a oferecer aquela. O site nunca regride sozinho para uma versão mais velha.
- **Testar a montagem sem publicar** (precisa de uma pasta `dist/Autoclick` já construída):
  `uv run python tools/montar_release.py --tag v0.13.0 --repo USUARIO/REPO --dist dist/Autoclick --saida _release`
  com a variável `AC_CHAVE_PRIVADA` definida.

## Limites desta forma de publicar

- Sem painel, canal beta, percentual de liberação, contagem de instalações nem envio de relatórios
  (o programa salva o relatório num .zip e o amigo manda para você).
- O `.exe` não tem assinatura de código paga: na primeira abertura o Windows pode mostrar "protegeu seu
  computador" (Mais informações > Executar assim mesmo). A assinatura Ed25519 protege as atualizações,
  não evita esse aviso.
