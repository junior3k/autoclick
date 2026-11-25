"""Processo falso que usa o mesmo protocolo de controle do programa (pausa/parar/status)."""
import sys, time
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from autoclick import operacao as OP, windows as W
OP.nova_telemetria()
ctl = OP.controle_do_ambiente("imagem")
print("fake iniciou", flush=True)
n = 0
while not W.PARADA.is_set():
    if OP.pausa.pausado:
        time.sleep(0.05); continue
    n += 1
    OP.tel().clique("botao_x")
    if n % 5 == 0:
        print(f"acao {n}", flush=True)
    time.sleep(0.05)
print("fake parou limpo", flush=True)
ctl.parar()
