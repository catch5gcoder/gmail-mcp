Dim dir
dir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
Set UAC = CreateObject("Shell.Application")
UAC.ShellExecute "cmd.exe", "/c """ & dir & "\start_gmail.bat""", "", "runas", 1
