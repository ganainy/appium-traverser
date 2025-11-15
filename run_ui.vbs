' VBScript to run the Appium Traverser silently (no terminal window)
' This script automatically detects and activates the virtual environment

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the directory where this script is located
scriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptPath

' Determine Python executable (check virtual environment first)
pythonExe = ""
if fso.FolderExists(scriptPath & "\.venv\Scripts") then
    pythonExe = scriptPath & "\.venv\Scripts\python.exe"
elseif fso.FolderExists(scriptPath & "\venv\Scripts") then
    pythonExe = scriptPath & "\venv\Scripts\python.exe"
elseif fso.FolderExists(scriptPath & "\env\Scripts") then
    pythonExe = scriptPath & "\env\Scripts\python.exe"
else
    pythonExe = "python"
end if

' Build command to run the UI
runUiScript = scriptPath & "\run_ui.py"
command = """" & pythonExe & """ """ & runUiScript & """"

' Run the command silently (WindowStyle = 0 means hidden)
WshShell.Run command, 0, False



