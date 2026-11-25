' Sobe o servidor sem deixar janela de prompt aberta (usado pelo Agendador de Tarefas).
Set sh = CreateObject("WScript.Shell")
pasta = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = pasta
sh.Run Chr(34) & pasta & "\iniciar_servidor.bat" & Chr(34), 0, False
