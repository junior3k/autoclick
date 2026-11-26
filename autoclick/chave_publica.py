"""Chave pública de quem assina as atualizações (Ed25519, 64 caracteres hexadecimais).

É preenchida automaticamente ao instalar o servidor e ao publicar uma versão, de modo que
todo pacote que você entrega já leva a chave. Enquanto estiver vazia, o programa recusa
atualizações vindas de servidor (só aceita um pacote .zip aplicado manualmente).
Esta chave NÃO é secreta; a chave privada fica só no PC do servidor.
"""
CHAVE_PUBLICA_HEX = "e52785d6652c0d7602500b3340d639a63cde56853fa3976fe2328385e577a3f9"
