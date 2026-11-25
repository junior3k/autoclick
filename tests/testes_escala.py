import sys, types, time as _time
import numpy as np, cv2
try:
    import mss  # noqa
except Exception:
    sys.modules["mss"] = types.SimpleNamespace()
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from fachada import A
from pathlib import Path
import tempfile

def check(nome, cond, extra=""):
    print(("  OK   " if cond else "  FALHOU ") + nome + (f"  {extra}" if extra and not cond else ""))
    if not cond: sys.exit(1)

rng = np.random.default_rng(7)

def botao(w, h, cor, texto):
    b = np.zeros((h, w, 3), np.uint8)
    for i in range(h):
        b[i, :] = np.clip(np.array(cor) * (0.6 + 0.4 * i / h), 0, 255)
    cv2.rectangle(b, (2, 2), (w - 3, h - 3), (255, 255, 255), 3)
    cv2.putText(b, texto, (w // 8, int(h * 0.65)), cv2.FONT_HERSHEY_SIMPLEX, h / 45, (255, 255, 255), 3)
    cv2.circle(b, (w - 18, 16), 8, (0, 255, 255), -1)
    return b

BTNS = {"maximo": botao(220, 80, (60, 160, 40), "MAX"), "proxima": botao(260, 90, (200, 90, 30), "NEXT"),
        "torre": botao(180, 120, (40, 40, 200), "TOWER")}
pasta = Path(tempfile.mkdtemp())
for n, b in BTNS.items(): cv2.imwrite(str(pasta / f"{n}.png"), b)

def cena(escala, posicoes, W=1920, H=1080):
    fundo = (rng.integers(20, 90, (H, W, 3))).astype(np.uint8)
    fundo = cv2.GaussianBlur(fundo, (0, 0), 3)
    img = fundo.copy()
    for n, (x, y) in posicoes.items():
        b = BTNS[n]
        if abs(escala - 1) > 1e-6:
            b = cv2.resize(b, (round(b.shape[1] * escala), round(b.shape[0] * escala)), interpolation=cv2.INTER_AREA)
        img[y:y + b.shape[0], x:x + b.shape[1]] = b
    return img

POS = {"maximo": (300, 200), "proxima": (900, 640), "torre": (1400, 300)}
def centros_esperados(esc):
    return {n: (x + round(BTNS[n].shape[1] * esc) // 2, y + round(BTNS[n].shape[0] * esc) // 2) for n, (x, y) in POS.items()}

def confere(hits, esc, tol_esc=0.06, tol_px=4):
    exp = centros_esperados(esc)
    por = {h.rotulo: h for h in hits}
    if set(por) != set(exp): return False, f"rótulos {sorted(por)}"
    for n, (cx, cy) in exp.items():
        h = por[n]
        if abs(h.centro[0] - cx) > tol_px or abs(h.centro[1] - cy) > tol_px: return False, f"{n}: {h.centro} != {(cx, cy)}"
        if abs(h.escala - esc) > tol_esc: return False, f"{n}: escala {h.escala:.3f} != {esc}"
    return True, ""

print("1) Escala 1.0 (sem regressão)")
A.configurar_escala(busca_a_cada=0)
hits = A.detectar_imagens(cena(1.0, POS), str(pasta), 0.85)
ok, why = confere(hits, 1.0); check("acha os 3 botões no tamanho original", ok, why)
check("escala aprendida = 1.0", abs(A.escala_atual() - 1.0) < 0.01)

for esc in (0.7, 0.55, 0.4):
    print(f"2) Janela menor: PNGs no tamanho máximo, tela com botões a {esc:.0%}")
    A.configurar_escala(busca_a_cada=0)
    t = _time.time(); hits = A.detectar_imagens(cena(esc, POS), str(pasta), 0.85); dt = _time.time() - t
    ok, why = confere(hits, esc); check(f"busca completa achou os 3 botões na escala {esc}", ok, why)
    print(f"       busca completa: {dt:.2f}s (1920x1080, 3 recortes); escala aprendida {A.escala_atual():.3f}")
    t = _time.time(); hits = A.detectar_imagens(cena(esc, POS), str(pasta), 0.85); dt2 = _time.time() - t
    ok, why = confere(hits, esc); check("varredura seguinte (escala já aprendida) acha de novo", ok, why)
    print(f"       varredura rápida: {dt2:.3f}s")

print("3) Redimensionou a janela depois de aprendida")
A.configurar_escala(busca_a_cada=0)
A.detectar_imagens(cena(0.7, POS), str(pasta), 0.85)
hits = A.detectar_imagens(cena(0.5, POS), str(pasta), 0.85)
ok, why = confere(hits, 0.5); check("reaprende sozinho 0.7 -> 0.5", ok, why)
A.escala_mudou_janela(0.5 / 0.5)  # sem mudança: não quebra
A.configurar_escala(busca_a_cada=0); A.detectar_imagens(cena(0.7, POS), str(pasta), 0.85)
A.escala_mudou_janela(0.5 / 0.7)
check("escala prevista pelo tamanho da janela (0.7 * 0.714 = 0.5)", abs(A.escala_atual() - 0.5) < 0.01, str(A.escala_atual()))
hits = A.detectar_imagens(cena(0.5, POS), str(pasta), 0.85)
ok, why = confere(hits, 0.5); check("com a previsão acerta de primeira", ok, why)

print("4) Tela vazia / limites")
A.configurar_escala(busca_a_cada=0)
vazio = cena(1.0, {})
check("tela sem botões => []", A.detectar_imagens(vazio, str(pasta), 0.85) == [])
A.configurar_escala(busca_a_cada=60)
A.detectar_imagens(vazio, str(pasta), 0.85)
t = _time.time(); A.detectar_imagens(vazio, str(pasta), 0.85); dt = _time.time() - t
check("tela vazia: a busca completa é limitada (2ª chamada é rápida)", dt < 0.25, f"{dt:.2f}s")
A.configurar_escala(busca_a_cada=0, minima=0.6)
check("--escala-min respeitado (botões a 0.4 não são procurados)", A.detectar_imagens(cena(0.4, POS), str(pasta), 0.85) == [])
A.configurar_escala(fixa=0.55)
hits = A.detectar_imagens(cena(0.55, POS), str(pasta), 0.85)
ok, why = confere(hits, 0.55); check("--escala 0.55 fixa", ok, why)
A.configurar_escala(ativa=False)
check("multi-escala desligada: só o tamanho original", A.detectar_imagens(cena(0.55, POS), str(pasta), 0.85) == [])
A.configurar_escala()
small = cena(1.0, {"maximo": (50, 40)}, W=400, H=300)
check("imagem pequena (região) funciona", [h.rotulo for h in A.detectar_imagens(small, str(pasta), 0.85)] == ["maximo"])
check("recorte maior que a imagem não quebra", A.detectar_imagens(np.zeros((30, 30, 3), np.uint8), str(pasta), 0.85) == [])
print("\nEscala OK.")

print("5) Robustez: interpolação diferente, ruído, escala fora da grade, escalas pequenas")
for esc in (0.63, 0.77, 0.34):
    A.configurar_escala(busca_a_cada=0)
    img = cena(esc, POS)
    ruido = rng.normal(0, 4, img.shape)
    img = np.clip(img.astype(np.float32) + ruido, 0, 255).astype(np.uint8)
    hits = A.detectar_imagens(img, str(pasta), 0.8)
    ok, why = confere(hits, esc, tol_esc=0.07, tol_px=5)
    check(f"escala {esc} com ruído (confiança 0.8)", ok, why)
print("6) Falso positivo: botão de OUTRA cor/forma não é aceito")
A.configurar_escala(busca_a_cada=0)
outra = cena(1.0, {}); outra[200:280, 300:520] = botao(220, 80, (200, 40, 160), "XYZ")[:, :]
res = A.detectar_imagens(outra, str(pasta), 0.85)
check("nenhum recorte confundido com o botão roxo", res == [], str([(h.rotulo, round(h.score, 2)) for h in res]))
print("\nEscala (robustez) OK.")
