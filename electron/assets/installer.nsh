; installer.nsh — optional component sections for Vosk and Ollama.
; Both are selected by default. Users can uncheck them on the
; "Choose Components" page for offline or minimal installs.

; LogicLib provides ${If}/${EndIf} — safe to include twice (it has its own guard).
!include "LogicLib.nsh"

; ── Vosk Voice Recognition (~40 MB, requires internet) ────────────────────────
Section "Vosk Voice Recognition" SecVosk
  DetailPrint " "
  DetailPrint "Installing Vosk voice recognition (~40 MB)..."
  CreateDirectory "$INSTDIR\resources\data\vosk-model"

  ; Write a self-contained PS script. $$ → literal $ for PowerShell variables.
  ; $INSTDIR is expanded by NSIS before FileWrite executes.
  FileOpen $R9 "$TEMP\luna-vosk-install.ps1" w
  FileWrite $R9 '$$ProgressPreference = "SilentlyContinue"$\r$\n'
  FileWrite $R9 '$$ErrorActionPreference = "Stop"$\r$\n'
  FileWrite $R9 '$$dest = "$INSTDIR\resources\data\vosk-model"$\r$\n'
  FileWrite $R9 'if ((Test-Path $$dest) -and (Get-ChildItem $$dest -Force -ErrorAction SilentlyContinue)) {$\r$\n'
  FileWrite $R9 '    Write-Output "Vosk model already present, skipping."; exit 0$\r$\n'
  FileWrite $R9 '}$\r$\n'
  FileWrite $R9 'try {$\r$\n'
  FileWrite $R9 '    $$zip = "$$env:TEMP\vosk-model.zip"$\r$\n'
  FileWrite $R9 '    $$tmp = "$$env:TEMP\vosk-extract-luna"$\r$\n'
  FileWrite $R9 '    Write-Output "Downloading vosk-model-small-en-us-0.15.zip..."$\r$\n'
  FileWrite $R9 '    Invoke-WebRequest -Uri "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip" -OutFile $$zip$\r$\n'
  FileWrite $R9 '    Write-Output "Extracting..."$\r$\n'
  FileWrite $R9 '    if (Test-Path $$tmp) { Remove-Item $$tmp -Recurse -Force }$\r$\n'
  FileWrite $R9 '    Expand-Archive -Path $$zip -DestinationPath $$tmp -Force$\r$\n'
  FileWrite $R9 '    $$src = (Get-ChildItem $$tmp -Directory | Select-Object -First 1).FullName$\r$\n'
  FileWrite $R9 '    New-Item -ItemType Directory -Path $$dest -Force | Out-Null$\r$\n'
  FileWrite $R9 '    Copy-Item -Path "$$src\*" -Destination $$dest -Recurse -Force$\r$\n'
  FileWrite $R9 '    Remove-Item $$tmp -Recurse -Force -ErrorAction SilentlyContinue$\r$\n'
  FileWrite $R9 '    Remove-Item $$zip -Force -ErrorAction SilentlyContinue$\r$\n'
  FileWrite $R9 '    Write-Output "Vosk installed."$\r$\n'
  FileWrite $R9 '} catch {$\r$\n'
  FileWrite $R9 '    Write-Output "Vosk error: $$_"; exit 1$\r$\n'
  FileWrite $R9 '}$\r$\n'
  FileClose $R9

  nsExec::ExecToLog 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$TEMP\luna-vosk-install.ps1"'
  Pop $R0
  Delete "$TEMP\luna-vosk-install.ps1"

  ${If} $R0 == "0"
    DetailPrint "Voice recognition ready."
  ${Else}
    DetailPrint "Vosk not installed — add it later: Luna Settings > Controls > Voice."
  ${EndIf}
SectionEnd

; ── Ollama AI Runtime (requires internet) ─────────────────────────────────────
Section "Ollama AI Runtime" SecOllama
  DetailPrint " "
  DetailPrint "Downloading Ollama AI runtime..."

  FileOpen $R9 "$TEMP\luna-ollama-dl.ps1" w
  FileWrite $R9 '$$ProgressPreference = "SilentlyContinue"$\r$\n'
  FileWrite $R9 '$$ErrorActionPreference = "Stop"$\r$\n'
  FileWrite $R9 '$$defaultPath = "$$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"$\r$\n'
  FileWrite $R9 'if ((Test-Path $$defaultPath) -or (Get-Command ollama -ErrorAction SilentlyContinue)) {$\r$\n'
  FileWrite $R9 '    Write-Output "Ollama already installed, skipping."; exit 0$\r$\n'
  FileWrite $R9 '}$\r$\n'
  FileWrite $R9 'try {$\r$\n'
  FileWrite $R9 '    Write-Output "Downloading OllamaSetup.exe..."$\r$\n'
  FileWrite $R9 '    Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile "$$env:TEMP\OllamaSetup.exe"$\r$\n'
  FileWrite $R9 '    Write-Output "Download complete."$\r$\n'
  FileWrite $R9 '} catch {$\r$\n'
  FileWrite $R9 '    Write-Output "Ollama download error: $$_"; exit 1$\r$\n'
  FileWrite $R9 '}$\r$\n'
  FileClose $R9

  nsExec::ExecToLog 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$TEMP\luna-ollama-dl.ps1"'
  Pop $R0
  Delete "$TEMP\luna-ollama-dl.ps1"

  ${If} $R0 == "0"
    DetailPrint "Running Ollama installer..."
    ExecWait '"$TEMP\OllamaSetup.exe" /VERYSILENT /NORESTART /SP-' $R1
    Delete "$TEMP\OllamaSetup.exe"
    ${If} $R1 == "0"
      DetailPrint "Ollama installed."
    ${Else}
      DetailPrint "Ollama installer exited with code $R1 — check ollama.com if needed."
    ${EndIf}
  ${Else}
    DetailPrint "Ollama not installed — get it later from ollama.com."
  ${EndIf}
SectionEnd

; ── Required electron-builder macros ──────────────────────────────────────────
!macro customInstall
  ; Vosk and Ollama are handled by their own sections above.
!macroend

!macro customUnInstall
!macroend
