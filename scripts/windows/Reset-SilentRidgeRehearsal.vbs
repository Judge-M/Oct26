Option Explicit

Dim shell, fileSystem, scriptPath, command
Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

scriptPath = fileSystem.BuildPath( _
    fileSystem.GetParentFolderName(WScript.ScriptFullName), _
    "Reset-SilentRidgeRehearsal.ps1")
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ _
    & scriptPath & """"

shell.Run command, 0, False
