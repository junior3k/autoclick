"""Janelinha opcional (Tk) com pausar/continuar, parar e contadores (opção --gui)."""
from __future__ import annotations

import threading
from typing import Optional

from . import windows as m_windows
from .operacao import Telemetria, pausa


def abrir(tel: Telemetria, titulo: str = "Autoclick inteligente") -> Optional[threading.Thread]:
    """Abre a janela em segundo plano. Devolve a thread (ou None se o Tk não existe)."""
    try:
        import tkinter as tk
    except Exception:
        print("Aviso: Tk indisponível; seguindo sem janela (use --painel).")
        return None

    def rodar() -> None:
        raiz = tk.Tk()
        raiz.title(titulo)
        raiz.attributes("-topmost", True)
        raiz.resizable(False, False)
        status = tk.StringVar()
        detalhe = tk.StringVar()
        tk.Label(raiz, textvariable=status, font=("Segoe UI", 12, "bold"), width=34).pack(padx=10, pady=(10, 2))
        tk.Label(raiz, textvariable=detalhe, justify="left", anchor="w", width=44,
                 font=("Consolas", 9)).pack(padx=10, pady=4)
        barra = tk.Frame(raiz)
        barra.pack(pady=8)
        btn_pausa = tk.Button(barra, text="Pausar (F8)", width=14, command=pausa.alternar)
        btn_pausa.pack(side="left", padx=4)

        def parar() -> None:
            m_windows.PARADA.set()

        tk.Button(barra, text="Parar (F9)", width=14, command=parar).pack(side="left", padx=4)

        def atualizar() -> None:
            d = int(tel.duracao())
            status.set(("⏸ PAUSADO" if pausa.pausado else "▶ rodando") + f"  {d // 60:02d}:{d % 60:02d}")
            btn_pausa.config(text="Continuar (F8)" if pausa.pausado else "Pausar (F8)")
            linhas: list[str] = [f"partida #{tel.partidas} | ações: {tel.total_cliques}",
                                 f"último: {tel.ultimo}"]
            for nome, n in sorted({**tel.cliques, **tel.arrastos}.items()):
                linhas.append(f"  {nome}: {n}")
            for a in tel.avisos[-2:]:
                linhas.append(f"⚠ {a}")
            detalhe.set("\n".join(linhas))
            if m_windows.PARADA.is_set():
                raiz.destroy()
                return
            raiz.after(500, atualizar)

        atualizar()
        raiz.protocol("WM_DELETE_WINDOW", parar)
        raiz.mainloop()

    t = threading.Thread(target=rodar, daemon=True)
    t.start()
    return t


__all__ = ["abrir"]
