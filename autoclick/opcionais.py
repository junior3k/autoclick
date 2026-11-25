"""Dependências OPCIONAIS (OCR/Tesseract). Só biblioteca padrão: seguro de importar sempre.

O programa inteiro (gravar, reproduzir, modo imagem) funciona sem isto. Só os modos
"texto" e "auto" precisam de pytesseract + Tesseract instalado.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
from pathlib import Path

DICA_OCR = (
    "Os modos 'texto' e 'auto' usam OCR (opcional). Para ativar:\n"
    "  1) uv add pytesseract\n"
    "  2) instale o Tesseract: https://github.com/UB-Mannheim/tesseract/wiki "
    "(marque o idioma Portuguese)\n"
    "Sem isso, use o modo 'imagem' (PNGs dos botões), gravar ou reproduzir: "
    "eles não precisam de OCR."
)


def achar_tesseract() -> str | None:
    """Caminho do executável do Tesseract, ou None."""
    cands = [
        os.environ.get("TESSERACT_CMD", ""),
        shutil.which("tesseract") or "",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        str(Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tesseract.exe"),
    ]
    for c in cands:
        if c and Path(c).is_file():
            return c
    return None


def ocr_disponivel() -> tuple[bool, str]:
    """(ok, motivo). Nunca levanta erro. AUTOCLICK_SEM_OCR=1 simula a ausência (para testes)."""
    if os.environ.get("AUTOCLICK_SEM_OCR"):
        return False, "desativado por AUTOCLICK_SEM_OCR"
    if importlib.util.find_spec("pytesseract") is None:
        return False, "o pacote pytesseract não está instalado"
    if achar_tesseract() is None:
        return False, "o programa Tesseract OCR não foi encontrado"
    return True, "OCR disponível"
