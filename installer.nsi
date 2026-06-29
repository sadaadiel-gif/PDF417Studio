Name "PDF417 Studio"
OutFile "PDF417Studio_Setup.exe"
InstallDir "$PROGRAMFILES\PDF417Studio"
InstallDirRegKey HKLM "Software\PDF417Studio" "Install_Dir"
RequestExecutionLevel admin

Page components
Page directory
Page instfiles

UninstPage uninstConfirm
UninstPage instfiles

Section "PDF417 Studio (required)"
  SectionIn RO
  SetOutPath $INSTDIR
  File "PDF417Studio.exe"
  File "version.txt"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\PDF417Studio" "Install_Dir" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PDF417Studio" "DisplayName" "PDF417 Studio"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PDF417Studio" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PDF417Studio" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PDF417Studio" "NoRepair" 1
  CreateDirectory "$SMPROGRAMS\PDF417Studio"
  CreateShortCut "$SMPROGRAMS\PDF417Studio\PDF417 Studio.lnk" "$INSTDIR\PDF417Studio.exe"
  CreateShortCut "$DESKTOP\PDF417 Studio.lnk" "$INSTDIR\PDF417Studio.exe"
SectionEnd

Section "Uninstall"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PDF417Studio"
  DeleteRegKey HKLM "Software\PDF417Studio"
  Delete "$INSTDIR\PDF417Studio.exe"
  Delete "$INSTDIR\version.txt"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  Delete "$SMPROGRAMS\PDF417Studio\PDF417 Studio.lnk"
  RMDir "$SMPROGRAMS\PDF417Studio"
  Delete "$DESKTOP\PDF417 Studio.lnk"
SectionEnd