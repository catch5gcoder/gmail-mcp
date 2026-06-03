Dim dir
dir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
Set UAC = CreateObject("Shell.Application")
UAC.ShellExecute "cmd.exe", "/c """ & dir & "\install_autostart.bat""", "", "runas", 1
