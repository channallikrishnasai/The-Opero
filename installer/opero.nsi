; Per-user Windows installer. Requires NSIS 3.x (makensis).
Unicode true
Name "OPERO"
OutFile "..\dist\OPERO-Setup.exe"
InstallDir "$LOCALAPPDATA\OPERO"
RequestExecutionLevel user
SetCompressor /SOLID zlib

!include "MUI2.nsh"

!define StartMenuFolder "$SMPROGRAMS\OPERO"
!define MUI_ICON "..\config\jarvis.ico"
!define MUI_UNICON "..\config\jarvis.ico"

!define MUI_FINISHPAGE_RUN "$INSTDIR\OPERO.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch OPERO"
!define MUI_FINISHPAGE_RUN_CHECKED

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "..\dist\OPERO\*.*"
  CreateDirectory "${StartMenuFolder}"
  CreateShortcut "${StartMenuFolder}\OPERO.lnk" "$INSTDIR\OPERO.exe"
  CreateShortcut "$DESKTOP\OPERO.lnk" "$INSTDIR\OPERO.exe"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\OPERO" "DisplayName" "OPERO"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\OPERO" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\OPERO" "DisplayIcon" "$INSTDIR\OPERO.exe"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\OPERO" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\OPERO" "NoRepair" 1
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\OPERO.lnk"
  Delete "${StartMenuFolder}\OPERO.lnk"
  RMDir "${StartMenuFolder}"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\OPERO"
  ; Keep config/ and other user-created state so reinstalling preserves setup.
  Delete "$INSTDIR\OPERO.exe"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR\_internal"
  RMDir /r "$INSTDIR\actions"
  RMDir /r "$INSTDIR\assets"
  RMDir /r "$INSTDIR\core"
  RMDir /r "$INSTDIR\ms-playwright"
  RMDir /r "$INSTDIR\plugins"
  RMDir /r "$INSTDIR\site"
  RMDir /r "$INSTDIR\ui"
SectionEnd
