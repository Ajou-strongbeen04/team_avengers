#!/bin/bash
# ============================================================================
#  漁벤져스 · Mac 워치독 상주 등록 (launchd)   2026-07-20
#
#  screen 과의 차이:
#    screen  — Mac 이 켜져 있는 동안만. 재부팅/로그아웃하면 사라짐.
#    launchd — 재부팅해도 로그인 시 자동 기동, 죽으면 자동 재시작. (권장)
#
#  실행:  bash install_launchd.sh
#  해제:  launchctl bootout gui/$(id -u)/com.eobengers.spotwatchdog
# ============================================================================
set -uo pipefail

LABEL="com.eobengers.spotwatchdog"
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/spot_watchdog.sh"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"

TARGET="${TARGET:-380}"
INTERVAL="${INTERVAL:-120}"
PROJECT="${PROJECT:-cfd-pilot}"
BUCKET="${BUCKET:-cfd-pilot-cfdbatch}"
NW="${NW:-6}"

[ -f "$SCRIPT" ] || { echo "!! $SCRIPT 없음"; exit 1; }
chmod +x "$SCRIPT"
mkdir -p "$HOME/Library/LaunchAgents"

# 기존 등록 해제(설정 변경 반영)
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${SCRIPT}</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PROJECT</key><string>${PROJECT}</string>
    <key>BUCKET</key><string>${BUCKET}</string>
    <key>NW</key><string>${NW}</string>
    <key>TARGET</key><string>${TARGET}</string>
    <key>INTERVAL</key><string>${INTERVAL}</string>
    <key>HOME</key><string>${HOME}</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key><false/>
  </dict>
  <key>StandardOutPath</key><string>${HOME}/spot_watchdog.out</string>
  <key>StandardErrorPath</key><string>${HOME}/spot_watchdog.err</string>
</dict>
</plist>
PLIST_EOF

launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/${LABEL}"

echo "== 등록 완료 =="
echo "  목표 ${TARGET}건 · 주기 ${INTERVAL}s"
echo ""
echo "  상태:  launchctl print gui/$(id -u)/${LABEL} | head -20"
echo "  로그:  tail -f ~/spot_watchdog.log"
echo "  해제:  launchctl bootout gui/$(id -u)/${LABEL}"
echo ""
echo "※ KeepAlive/SuccessfulExit=false → 비정상 종료 시 자동 재시작,"
echo "   목표 달성 후 정상 종료(exit 0)하면 재시작하지 않고 스스로 등록 해제합니다."
