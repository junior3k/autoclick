import os, sys, io, wave, struct, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ok = 0
def check(n, c):
    global ok
    print(("  OK   " if c else "  FALHOU ") + n)
    if not c: sys.exit(1)
    ok += 1
from autoclick import som as S, operacao
from autoclick.interface import dados as D

print("1) WAV suave")
w = wave.open(io.BytesIO(S.gerar_wav()))
n = w.getnframes(); amostras = struct.unpack(f"<{n}h", w.readframes(n))
check("mono 16 bits, 0,3–0,8 s", w.getnchannels() == 1 and w.getsampwidth() == 2 and 0.3 < n / w.getframerate() < 0.8)
check("volume baixo (pico < 35% do máximo)", max(abs(a) for a in amostras) < 0.35 * 32767)
check("começa e termina em silêncio (sem clique)", abs(amostras[0]) < 50 and abs(amostras[-1]) < 50)

print("2) Liga/desliga em tempo de execução")
x = S.Som(False); x.saida = lambda b: None
check("desligado não toca", x.tocar() is False and x.tocados == 0)
x.definir(True); check("ligado toca", x.tocar() is True and x.tocados == 1)
x.definir(False); check("desligado de novo: silêncio", x.tocar() is False and x.tocados == 1)
check("forçar (botão Ouvir) toca mesmo desligado", x.tocar(forcar=True) and x.tocados == 2)
x.saida = lambda b: 1 / 0; x.definir(True); check("erro no som nunca propaga", x.tocar() is False)
S.som.definir(False)
c = operacao.Controle(None, None, "reproduzir")
c.executar("som:1"); check("comando som:1", S.som.ativo)
c.executar("som:0"); check("comando som:0", not S.som.ativo)
c.executar("som:alternar"); check("comando som:alternar", S.som.ativo)
S.som.definir(False)
d = tempfile.mkdtemp(); arq = os.path.join(d, "cmd.txt"); open(arq, "w").write("som:1\n")
operacao.Controle(arq, None, "reproduzir")._ler_comandos(); check("chega pelo arquivo de comandos da janela", S.som.ativo)
S.som.definir(False)

print("3) Reprodução toca a cada volta")
import autoclick.reproducao as R
check("reproducao dispara o som", "m_som.tocar()" in open(R.__file__, encoding="utf-8").read())

print("4) Configurações e atalhos")
g = D.Geral()
check("padrões: som desligado, F11", g.som_volta is False and g.tecla_reproduzir == "F11")
g.som_volta = True; check("ambiente repassa o som", D.ambiente(g)["AUTOCLICK_SOM"] == "1")
check("4 teclas válidas", D.teclas_validas("F8", "F9", "F10", "F11") is None)
check("reproduzir repetida", "diferentes" in (D.teclas_validas("F8", "F9", "F10", "F9") or ""))
check("reproduzir inválida", "reproduzir" in (D.teclas_validas("F8", "F9", "F10", "??") or ""))
print("7) Sons por tipo de ação (0.12.0)")
ws = {e: S.gerar_wav(0.2, "sino", e) for e in S.EVENTOS}
check("cada evento tem som próprio (todos diferentes)", len(set(ws.values())) == len(S.EVENTOS))
check("início e fim são diferentes (subindo x descendo)", ws["gravar_inicio"] != ws["gravar_fim"] and ws["repro_inicio"] != ws["repro_fim"])
check("estilos mudam o timbre", S.gerar_wav(0.2, "marimba", "gravar_inicio") != ws["gravar_inicio"])
def _pico(b):
    w = wave.open(io.BytesIO(b)); n = w.getnframes(); a = struct.unpack(f"<{n}h", w.readframes(n)); return a
for e, b in ws.items():
    a = _pico(b)
    check(f"{e}: suave, curto, sem clique", max(abs(v) for v in a) < 0.35 * 32767 and len(a) / S.TAXA < 0.8 and abs(a[0]) < 50 and abs(a[-1]) < 120)
tq = _pico(ws["tique"]); check("tique é bem curto", len(tq) / S.TAXA < 0.1)
y = S.Som(False); tocou = []; y.saida = lambda b: tocou.append(b)
check("grupos começam desligados", not any(y.tocar_evento(e) for e in S.EVENTOS) and not tocou)
y.definir_grupo("gravacao", True)
check("liga só a gravação", y.tocar_evento("gravar_inicio") and y.tocar_evento("gravar_fim") and not y.tocar_evento("repro_inicio") and not y.tocar_evento("tique") and not y.tocar())
y.definir_grupo("reproducao", True); y.definir_grupo("contagem", True)
check("reprodução e contagem", y.tocar_evento("repro_fim") and y.tocar_evento("tique") and not y.tocar())
check("sons diferentes foram enviados", len({bytes(b) for b in tocou}) == 4)
y.definir_grupo("gravacao", False); check("desliga um tipo sem afetar os outros", not y.tocar_evento("gravar_inicio") and y.tocar_evento("repro_inicio"))
check("Ouvir (forçar) toca desligado", y.tocar_evento("gravar_fim", forcar=True))
check("contagem por evento", y.tocados_por_evento.get("tique") == 1)
y.definir(True); check("som de volta continua independente", y.tocar() and y.ativo)
y.saida = lambda b: 1 / 0; check("erro no som não propaga", y.tocar_evento("tique") is False)
wavp = os.path.join(tempfile.mkdtemp(), "meu.wav"); open(wavp, "wb").write(S.gerar_wav(0.3, "gota"))
z = S.Som(False); z.saida = lambda b: None; z.definir_grupo("gravacao", True); z.configurar("arquivo", 50, wavp)
check("arquivo do usuário vale para os eventos, o tique continua gerado", z._montar("gravar_inicio")[:4] == b"RIFF" and z._montar("gravar_inicio") == open(wavp, "rb").read() and z._montar("tique") != open(wavp, "rb").read())
S.som.definir_grupo("gravacao", False)
c.executar("somgrupo:gravacao=1"); check("comando somgrupo:gravacao=1", S.som.grupos["gravacao"])
c.executar("somgrupo:gravacao=0"); check("comando somgrupo:gravacao=0", not S.som.grupos["gravacao"])
c.executar("somgrupo:reproducao=1"); c.executar("somgrupo:contagem=1"); check("comandos de reprodução e contagem", S.som.grupos["reproducao"] and S.som.grupos["contagem"] and not S.som.grupos["volta"])
c.executar("somgrupo:lixo=1"); check("grupo desconhecido é ignorado", "lixo" not in S.som.grupos)
S.som.definir_grupo("reproducao", False); S.som.definir_grupo("contagem", False)
g = D.Geral(); e = D.ambiente(g)
check("ambiente leva os grupos (padrão: gravação e reprodução ligadas, tique desligado)", e["AUTOCLICK_SOM_GRAVAR"] == "1" and e["AUTOCLICK_SOM_REPRO"] == "1" and e["AUTOCLICK_SOM_TIQUE"] == "0")
g.som_gravacao = False; g.som_contagem = True; e = D.ambiente(g)
check("ambiente reflete as escolhas", e["AUTOCLICK_SOM_GRAVAR"] == "0" and e["AUTOCLICK_SOM_TIQUE"] == "1")

print(f"\n{ok} verificações passaram (som e atalhos).")

print("Saída do Windows (winsound simulado)")
import types
chamadas = []
fake = types.ModuleType("winsound")
fake.SND_MEMORY, fake.SND_ASYNC, fake.SND_FILENAME, fake.SND_NODEFAULT = 4, 1, 131072, 2
def _play(snd, flags):
    if flags & fake.SND_MEMORY and flags & fake.SND_ASYNC:
        raise RuntimeError("Cannot play asynchronously from memory")  # comportamento real do winsound
    chamadas.append((snd, flags))
fake.PlaySound = _play
sys.modules["winsound"] = fake
from autoclick import som as SOM
s2 = SOM.Som(True); s2.saida = SOM._saida_winsound
check("toca de verdade (sem RuntimeError)", s2.tocar() is True and len(chamadas) == 1)
check("usa arquivo .wav válido, assíncrono", chamadas[0][0].endswith(".wav") and os.path.isfile(chamadas[0][0]) and chamadas[0][1] & fake.SND_ASYNC and not chamadas[0][1] & fake.SND_MEMORY)
import wave
with wave.open(chamadas[0][0]) as w: check("arquivo é um WAV legível", w.getnframes() > 5000)
s2.tocar(); check("reutiliza o mesmo arquivo", len(chamadas) == 2 and chamadas[0][0] == chamadas[1][0])
del sys.modules["winsound"]
