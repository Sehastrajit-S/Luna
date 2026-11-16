Set shell = CreateObject("WScript.Shell")
repo = CreateObject("Scripting.FileSystemObject").GetParentFolderName(CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName))
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ""Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue; Set-Location '" & repo & "'; npm run dev"""
shell.Run cmd, 0, False
