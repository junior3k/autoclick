"""Servidor de atualizações do Autoclick (roda no PC do administrador, atrás de um túnel cloudflared).

    python -m servidor instalar     # primeira vez: chaves, configuração, token do painel
    python -m servidor rodar        # liga o servidor (use iniciar_servidor.bat)
    python -m servidor publicar     # testa, empacota, assina e publica uma versão (use publicar.bat)

Veja servidor/LEIAME.md.
"""
