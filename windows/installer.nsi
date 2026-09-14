Unicode True
!include "MUI2.nsh"
!include "LogicLib.nsh"
!define APPNAME "Jinx"
!define VERSION "0.3.0-preview"
Name "Jinx ${VERSION}"
OutFile "..\dist\Jinx-${VERSION}-windows-x64-setup.exe"
InstallDir "$LOCALAPPDATA\Programs\Jinx"
RequestExecutionLevel user
SetCompressor /SOLID lzma
Icon "jinx.ico"
UninstallIcon "jinx.ico"
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE"
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\Jinx.exe"
!define MUI_FINISHPAGE_RUN_NOTCHECKED
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
Function .onInit
  FindWindow $0 "" "Jinx"
  ${If} $0 != 0
    MessageBox MB_OK "Please close Jinx before installing an update."
    Abort
  ${EndIf}
FunctionEnd
Section "Jinx"
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  ClearErrors
  File /r "..\dist\Jinx\*"
  ${If} ${Errors}
    MessageBox MB_OK "Some files could not be installed. Close Jinx and run the installer again."
    Abort
  ${EndIf}
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\Jinx"
  CreateShortcut "$SMPROGRAMS\Jinx\Jinx.lnk" "$INSTDIR\Jinx.exe"
  CreateShortcut "$SMPROGRAMS\Jinx\Uninstall Jinx.lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Jinx" "DisplayName" "Jinx"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Jinx" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Jinx" "Publisher" "DexterouZs"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Jinx" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Jinx" "DisplayIcon" "$INSTDIR\Jinx.exe"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Jinx" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Jinx" "NoRepair" 1
SectionEnd
Section "Uninstall"
  nsExec::ExecToLog 'schtasks /Delete /TN "Jinx personal reminders" /F'
  SetShellVarContext current
  Delete "$SMPROGRAMS\Jinx\Jinx.lnk"
  Delete "$SMPROGRAMS\Jinx\Uninstall Jinx.lnk"
  RMDir "$SMPROGRAMS\Jinx"
  Delete "$INSTDIR\Jinx.exe"
  RMDir /r "$INSTDIR\_internal"
  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\hermes"
  RMDir /r "$INSTDIR\voice"
  RMDir /r "$INSTDIR\windows"
  Delete "$INSTDIR\assets.json"
  Delete "$INSTDIR\starter-avatar.json"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Jinx"
  ; User notes, avatars, models and Ollama remain intact in separate directories.
SectionEnd
