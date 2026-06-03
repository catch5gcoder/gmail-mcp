Dim dir, shell, fso
dir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
Set shell = CreateObject("WScript.Shell")
Set fso   = CreateObject("Scripting.FileSystemObject")
shell.CurrentDirectory = dir

' 1. Hosts file — replace gmail.local with emailbox.local
Dim hostsPath, txt
hostsPath = "C:\Windows\System32\drivers\etc\hosts"
Dim ts : Set ts = fso.OpenTextFile(hostsPath, 1)
txt = ts.ReadAll : ts.Close
txt = txt & ""  ' ensure string
Dim lines, i, out
lines = Split(txt, vbLf)
out = ""
For i = 0 To UBound(lines)
    Dim L : L = lines(i)
    If InStr(L, "gmail.local") > 0 Then L = ""   ' remove old entry
    out = out & L
    If i < UBound(lines) Then out = out & vbLf
Next
If InStr(out, "emailbox.local") = 0 Then
    out = out & vbLf & "127.0.0.1 emailbox.local"
End If
Set ts = fso.OpenTextFile(hostsPath, 2) : ts.Write out : ts.Close

' 2. Port proxy 80 -> 5000
shell.Run "cmd /c netsh interface portproxy delete v4tov4 listenport=80 listenaddress=127.0.0.1", 0, True
shell.Run "cmd /c netsh interface portproxy add v4tov4 listenport=80 listenaddress=127.0.0.1 connectport=5000 connectaddress=127.0.0.1", 0, True

' 3. Proxy bypass in registry
shell.Run "cmd /c reg add ""HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings"" /v ProxyOverride /t REG_SZ /d ""emailbox.local;<local>"" /f", 0, True

' 4. Find Python (skip Microsoft Store stubs)
Dim pyPath : pyPath = ""
Dim exec, line
Set exec = shell.Exec("cmd /c where python 2>nul")
Do While Not exec.StdOut.AtEndOfStream
    line = Trim(exec.StdOut.ReadLine())
    If InStr(LCase(line), "windowsapps") = 0 And line <> "" Then
        pyPath = line : Exit Do
    End If
Loop
If pyPath = "" Then
    Set exec = shell.Exec("cmd /c where py 2>nul")
    If Not exec.StdOut.AtEndOfStream Then pyPath = Trim(exec.StdOut.ReadLine())
End If
Dim candidates, c
candidates = Array( _
    shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python312\python.exe"), _
    shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python311\python.exe"), _
    shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python310\python.exe"), _
    shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python39\python.exe"))
If pyPath = "" Then
    For Each c In candidates
        If fso.FileExists(c) Then pyPath = c : Exit For
    Next
End If

' 5. Kill stale server then start fresh
shell.Run "cmd /c taskkill /f /im python.exe >nul 2>&1", 0, True
If pyPath <> "" Then
    shell.Run """" & pyPath & """ dashboard.py", 0, False
End If
