' Abre o Autoclick sem mostrar o prompt de comando.
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.Run "uv run pythonw -m autoclick", 0, False
