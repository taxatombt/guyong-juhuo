; NSIS installer for guyong-juhuo
; Build: E:\NSIS_portable\nsis-3.10\makensis.exe setup.nsi

!include "MUI2.nsh"

!define PRODUCT_NAME "聚活"
!define PRODUCT_VERSION "1.0.0"
!define PRODUCT_PUBLISHER "guyong-juhuo"
!define PRODUCT_WEB_SITE "https://github.com/taxatombt/guyong-juhuo"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_EXE "guyong-juhuo.exe"

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "dist\${PRODUCT_NAME}-${PRODUCT_VERSION}-setup.exe"
InstallDir "$PROGRAMFILES\${PRODUCT_NAME}"
InstallDirRegKey HKLM "${PRODUCT_UNINST_KEY}" "InstallLocation"
RequestExecutionLevel admin

!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\${PRODUCT_EXE}"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "MainSection" SEC01
  SetOutPath "$INSTDIR"
  SetOverwrite on
  File /r "judgment"
  File /r "curiosity"
  File /r "emotion_system"
  File /r "causal_memory"
  File /r "action_system"
  File /r "output_system"
  File /r "self_model"
  File /r "goal_system"
  File /r "perception"
  File /r "chat_system"
  File /r "llm_adapter"
  File /r "feedback_system"
  File /r "openspace"
  File /r "evolver"
  File /r "data"
  File /r "templates"
  File /r "web"
  File /r "gstack_integration"
  File /r "gstack_virtual_team"
  File /r "hermes_integration"
  File /r "hermes_evolution"
  File /r "_legacy"
  File /r "test_snapshots"
  File /r "docs"
  File "dist\guyong-juhuo.exe"
  File "hub.py"
  File "web_console.py"
  File "tui_console.py"
  File "cli.py"
  File "judgment_cli.py"
  File "judgment_web.py"
  File "profile.py"
  File "config.py"
  File "requirements.txt"
  File "README.md"
  File "LICENSE"

  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\${PRODUCT_EXE}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\卸载 ${PRODUCT_NAME}.lnk" "$INSTDIR\uninst.exe"
SectionEnd

Section -Post
  WriteUninstaller "$INSTDIR\uninst.exe"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayName" "$(^Name)"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\${PRODUCT_EXE}"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
SectionEnd

Section -DeskIcons
  CreateShortCut "Desktop\${PRODUCT_NAME}.lnk" "$INSTDIR\${PRODUCT_EXE}"
SectionEnd

Section Uninstall
  Delete "$INSTDIR\uninst.exe"
  Delete "$INSTDIR\${PRODUCT_EXE}"
  RMDir /r "$INSTDIR\judgment"
  RMDir /r "$INSTDIR\curiosity"
  RMDir /r "$INSTDIR\emotion_system"
  RMDir /r "$INSTDIR\causal_memory"
  RMDir /r "$INSTDIR\action_system"
  RMDir /r "$INSTDIR\output_system"
  RMDir /r "$INSTDIR\self_model"
  RMDir /r "$INSTDIR\goal_system"
  RMDir /r "$INSTDIR\perception"
  RMDir /r "$INSTDIR\chat_system"
  RMDir /r "$INSTDIR\llm_adapter"
  RMDir /r "$INSTDIR\feedback_system"
  RMDir /r "$INSTDIR\openspace"
  RMDir /r "$INSTDIR\evolver"
  RMDir /r "$INSTDIR\data"
  RMDir /r "$INSTDIR\templates"
  RMDir /r "$INSTDIR\web"
  RMDir /r "$INSTDIR\gstack_integration"
  RMDir /r "$INSTDIR\gstack_virtual_team"
  RMDir /r "$INSTDIR\hermes_integration"
  RMDir /r "$INSTDIR\hermes_evolution"
  RMDir /r "$INSTDIR\_legacy"
  RMDir /r "$INSTDIR\test_snapshots"
  RMDir /r "$INSTDIR\docs"
  Delete "$INSTDIR\hub.py"
  Delete "$INSTDIR\web_console.py"
  Delete "$INSTDIR\tui_console.py"
  Delete "$INSTDIR\cli.py"
  Delete "$INSTDIR\judgment_cli.py"
  Delete "$INSTDIR\judgment_web.py"
  Delete "$INSTDIR\profile.py"
  Delete "$INSTDIR\config.py"
  Delete "$INSTDIR\requirements.txt"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\LICENSE"
  RMDir "$INSTDIR"
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk"
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\卸载 ${PRODUCT_NAME}.lnk"
  RMDir "$SMPROGRAMS\${PRODUCT_NAME}"
  Delete "Desktop\${PRODUCT_NAME}.lnk"
  DeleteRegKey HKLM "${PRODUCT_UNINST_KEY}"
SectionEnd
