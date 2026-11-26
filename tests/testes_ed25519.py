import sys as _s0
for _f in (_s0.stdout, _s0.stderr):
    try: _f.reconfigure(encoding="utf-8", errors="replace")  # Windows (cp1252) não imprime setas
    except Exception: pass
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from autoclick import ed25519 as E

ok = 0
def check(nome, cond, extra=""):
    global ok
    print(("  OK   " if cond else "  FALHOU ") + nome + (f"  {extra}" if extra and not cond else ""))
    if not cond: sys.exit(1)
    ok += 1

print("1) Vetores do RFC 8032 (seção 7.1)")
vetores = [
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
]
for sk, pk, msg, sig in vetores:
    check(f"chave pública de {sk[:8]}…", E.chave_publica(bytes.fromhex(sk)).hex() == pk)
    s = E.assinar(bytes.fromhex(sk), bytes.fromhex(msg))
    check("assinatura idêntica à do RFC", s.hex() == sig)
    check("verifica", E.verificar(bytes.fromhex(pk), bytes.fromhex(msg), s))

print("2) Rejeita adulteração")
sk = E.gerar_semente(); pk = E.chave_publica(sk)
msg = b"autoclick-v1|0.6.0|estavel|abc|123|0.5.0"
sig = E.assinar(sk, msg)
check("assinatura válida", E.verificar(pk, msg, sig))
check("mensagem alterada", not E.verificar(pk, msg + b"x", sig))
check("assinatura alterada", not E.verificar(pk, msg, bytes([sig[0] ^ 1]) + sig[1:]))
check("s alterado", not E.verificar(pk, msg, sig[:40] + bytes([sig[40] ^ 4]) + sig[41:]))
outra = E.chave_publica(E.gerar_semente())
check("chave de outra pessoa", not E.verificar(outra, msg, sig))
check("tamanhos errados", not E.verificar(pk[:31], msg, sig) and not E.verificar(pk, msg, sig[:63]))
check("lixo de 32 bytes como chave", not E.verificar(b"\xff" * 32, msg, sig))
check("s fora do intervalo (maleabilidade)", not E.verificar(pk, msg, sig[:32] + (2**253).to_bytes(32, "little")))
check("hex", E.verificar_hex(pk.hex(), msg, sig.hex()) and not E.verificar_hex("zz", msg, sig.hex()) and not E.verificar_hex(pk.hex(), msg, "12"))

print("3) Conferência cruzada com a biblioteca 'cryptography'")
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    from cryptography.hazmat.primitives import serialization as S
    from cryptography.exceptions import InvalidSignature
except Exception:
    print("  (cryptography ausente: etapa ignorada)")
else:
    for i in range(12):
        semente = os.urandom(32); m = os.urandom(i * 37)
        ref = Ed25519PrivateKey.from_private_bytes(semente)
        pub_ref = ref.public_key().public_bytes(S.Encoding.Raw, S.PublicFormat.Raw)
        assert E.chave_publica(semente) == pub_ref, "chave pública difere"
        assert E.assinar(semente, m) == ref.sign(m), "assinatura difere"
        Ed25519PublicKey.from_public_bytes(pub_ref).verify(E.assinar(semente, m), m)
        assert E.verificar(pub_ref, m, ref.sign(m))
    check("12 chaves/mensagens: pública e assinatura idênticas; verificação nos dois sentidos", True)

print("4) Desempenho")
t = time.time(); [E.verificar(pk, msg, sig) for _ in range(5)]
dt = (time.time() - t) / 5
check(f"verificar leva {dt * 1000:.0f} ms (aceitável)", dt < 1.0)
print(f"\n{ok} verificações passaram (ed25519).")
