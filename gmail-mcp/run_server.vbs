Dim dir, shell
dir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = dir

' Resolve the actual python.exe path via 'where' so App Execution Aliases
' (which fail silently in Task Scheduler) are bypassed.
Dim pyPath
pyPath = ""

On Error Resume Next
Dim exec, line
Set exec = shell.Exec("cmd /c where python 2>nul")
Do While Not exec.StdOut.AtEndOfStream
    line = Trim(exec.StdOut.ReadLine())
    ' Skip Microsoft Store stub aliases — they are in WindowsApps and unreliable
    If InStr(LCase(line), "windowsapps") = 0 And line <> "" Then
        pyPath = line
        Exit Do
    End If
Loop
On Error GoTo 0

' Fall back to py launcher if no clean python found
If pyPath = "" Then
    Set exec = shell.Exec("cmd /c where py 2>nul")
    On Error Resume Next
    If Not exec.StdOut.AtEndOfStream Then
        pyPath = Trim(exec.StdOut.ReadLine())
    End If
    On Error GoTo 0
End If

' Last resort: well-known install locations
If pyPath = "" Then
    Dim fso, candidates, c
    Set fso = CreateObject("Scripting.FileSystemObject")
    candidates = Array( _
        shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python312\python.exe"), _
        shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python311\python.exe"), _
        shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python310\python.exe"), _
        shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python39\python.exe"), _
        "C:\Python312\python.exe", _
        "C:\Python311\python.exe", _
        "C:\Python310\python.exe" _
    )
    For Each c In candidates
        If fso.FileExists(c) Then
            pyPath = c
            Exit For
        End If
    Next
End If

If pyPath = "" Then
    MsgBox "Python not found. Please install Python from python.org and re-run install_autostart.vbs.", 16, "Gmail Dashboard"
Else
    shell.Run """" & pyPath & """ dashboard.py", 0, False
End If
