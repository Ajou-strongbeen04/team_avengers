#!/usr/bin/env bash
# 00_운영/현황.md §4 작업 로그에 한 줄 추가하고, 가능하면 Discord #일정관리로 방송한다.
#
#   사용: bash 00_운영/log_status.sh "이름" "구역" "내용"
#   예:   bash 00_운영/log_status.sh "한규태" "04_어플리케이션" "step03 판정 로직 교체, VLM 스키마 초안 추가"
#
# 웹훅 URL은 00_운영/webhooks.md 에서 읽는다(스크립트에 하드코딩하지 않는다).
# 네트워크가 막힌 환경(Claude device_bash 등)에서는 방송만 건너뛰고 현황.md 기록은 정상 수행한다.

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATUS="$DIR/현황.md"
HOOKS="$DIR/webhooks.md"

NAME="${1:?사용: log_status.sh \"이름\" \"구역\" \"내용\"}"
ZONE="${2:?사용: log_status.sh \"이름\" \"구역\" \"내용\"}"
MSG="${3:?사용: log_status.sh \"이름\" \"구역\" \"내용\"}"

[ -f "$STATUS" ] || { echo "현황.md 를 찾을 수 없다: $STATUS" >&2; exit 1; }

TS="$(date '+%Y%m%d %H:%M')"
LINE="- ${TS} · ${NAME} · ${ZONE} — ${MSG}"

# 1) 현황.md §4 바로 아래(인용 블록 뒤)에 삽입
python3 - "$STATUS" "$LINE" <<'PY'
import io, sys
path, line = sys.argv[1], sys.argv[2]
lines = io.open(path, encoding='utf-8').read().split('\n')
for i, l in enumerate(lines):
    if l.startswith('## 4. 작업 로그'):
        j = i + 1
        while j < len(lines) and (lines[j].startswith('>') or lines[j].strip() == ''):
            j += 1
        lines.insert(j, line)
        break
else:
    lines.append(line)
io.open(path, 'w', encoding='utf-8').write('\n'.join(lines))
PY

echo "기록 완료: $LINE"

# 2) Discord #일정관리 방송 (실패해도 스크립트는 성공으로 끝낸다)
if [ -f "$HOOKS" ] && command -v curl >/dev/null 2>&1; then
  HOOK="$(awk '/일정관리/{f=1} f && /^url:/{print $2; exit}' "$HOOKS")"
  if [ -n "${HOOK:-}" ]; then
    if python3 -c 'import json,sys; print(json.dumps({"content": sys.argv[1]}))' "$LINE" \
        | curl -sS --max-time 10 -X POST -H "Content-Type: application/json" -d @- "$HOOK" >/dev/null 2>&1; then
      echo "Discord #일정관리 방송 완료"
    else
      echo "Discord 방송 건너뜀 (네트워크 차단 또는 웹훅 오류) — 현황.md 기록은 정상"
    fi
  fi
fi
