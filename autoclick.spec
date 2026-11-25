# -*- mode: python ; coding: utf-8 -*-
# Gera dist/Autoclick/ com DOIS executáveis lado a lado:
#   Autoclick.exe       -> a janela (sem prompt de comando)
#   autoclick-cli.exe   -> usado pela janela para gravar/reproduzir (e por você, no terminal)
# Uso: construir_exe.bat
from PyInstaller.utils.hooks import collect_submodules

pacotes = collect_submodules("autoclick")  # as páginas da janela são importadas sob demanda
a = Analysis(
    ["autoclick_inteligente.py"],
    pathex=["."],
    hiddenimports=pacotes,
    datas=[("autoclick/interface/recursos", "autoclick/interface/recursos")],
    excludes=["pytest", "pyright"],
)
pyz = PYZ(a.pure)
janela = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Autoclick", console=False,
             icon="autoclick/interface/recursos/icone.ico")
cli = EXE(pyz, a.scripts, [], exclude_binaries=True, name="autoclick-cli", console=True,
          icon="autoclick/interface/recursos/icone.ico")
COLLECT(janela, cli, a.binaries, a.datas, name="Autoclick")
