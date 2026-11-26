"""Chave pública de quem assina as atualizações (Ed25519, 64 caracteres hexadecimais).

É preenchida automaticamente ao instalar o servidor e ao publicar uma versão, de modo que
todo pacote que você entrega já leva a chave. Enquanto estiver vazia, o programa recusa
atualizações vindas de servidor (só aceita um pacote .zip aplicado manualmente).
Esta chave NÃO é secreta; a chave privada fica só no PC do servidor.
"""
CHAVE_PUBLICA_HEX = ""
