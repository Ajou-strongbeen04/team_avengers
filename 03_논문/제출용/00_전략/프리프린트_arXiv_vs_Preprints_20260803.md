# 프리프린트 서버 비교 — Preprints.org vs arXiv (2026-08-03)

> 팀 漁벤져스 · 상위: `venue_재검토_20260803.md` · 기존 판단: `venue_비교표.md` §3 "arXiv = endorsement 리스크로 임계경로 제외"
> **[확인]** = 2026-08-03 공식 페이지에서 직접 읽음 / **[미확인]** = 근거 확보 못함
> 출처: preprints.org/instructions-for-authors · preprints.org/help-center · info.arxiv.org/help/endorsement.html · info.arxiv.org/help/moderation/index.html

---

## 0. 결론 3줄

1. **비용은 둘 다 0원이라 비용 축으로는 갈리지 않는다.** 갈리는 건 **진입 가능성(arXiv endorsement)** 과 **이름값**이다.
2. **arXiv가 이름값에서 압도적이지만, 2026-01-21 정책 개정으로 우리 팀은 자동 endorsement 대상이 아니다.** 기관 이메일만으로는 안 되고 "공저자 논문 소유권 주장 + 기관 이메일"이 **둘 다** 필요하다 [확인]. 우리는 arXiv 논문 이력이 0이므로 **지도교수급 개인 endorsement가 필수**다.
3. **양쪽 다 우리 원고를 "coursework / course project"로 읽으면 거절한다** [확인, 양쪽 모두 명문화]. 캡스톤이라는 사실보다 **원고가 연구논문 형식인지**가 판정선이다. 이건 서버 선택보다 먼저 해결할 문제다.

---

## 1. 항목별 비교

| 항목 | **Preprints.org** | **arXiv** |
|---|---|---|
| 비용 | **0원** [확인] "free preprint server supported by MDPI" | **0원** [확인] |
| 진입 장벽 | **스크리닝만.** 통상 **24시간**, 근무일 기준 [확인] | **endorsement 필수** (첫 투고 또는 새 카테고리) [확인] |
| 자동 통과 조건 | 없음 (모든 원고 스크리닝) | 공저자 논문 **소유권 주장 + 기관 이메일**을 **둘 다** 충족 시 [확인] → **우리는 미해당** |
| 대안 경로 | — | **개인 endorsement** — 해당 분야 활동 저자에게 6자리 코드 전달 [확인] |
| 언어 | **영어만.** 스크리닝 항목에 "The content is written in English" [확인] | 영어 원칙 (비영어 별도 정책) [미확인 — 세부 페이지 미조회] |
| 심사 성격 | 피어리뷰 아님 [확인] | 피어리뷰 아님. "moderation process is not a peer-review process" [확인] |
| 거절 사유 (우리에게 걸릴 것) | "we typically do not permit editorials, discussion papers, or **coursework**" [확인] | "including **course projects**, research proposals ... may be declined" / "Submissions in need of significant review and revision may also be declined" [확인] |
| **음성 결과** | **"We welcome manuscripts reporting negative or non-significant results"** [확인] | 명문 규정 없음. "lacks originality, novelty, significance" 는 거절 사유 [확인] |
| 카테고리 재분류 | — | 모더레이터가 **재분류 가능**, 공개 후에도 가능 [확인] |
| 거절 시 이의신청 | — | 가능하나 **결정은 최종, 피드백 없음.** 일부는 정식 저널 게재 후에야 재심 [확인] |
| 식별자 | **DOI 등록** [확인] | arXiv ID `arXiv:YYMM.NNNNN` [확인] / DOI 부여 여부 **[미확인]** |
| 버전 관리 | 가능. 권장 주기 **2주~1개월에 1회** [확인] | 가능 (v1, v2 …) [확인] |
| 라이선스 | **CC BY 4.0 고정** [확인] | 제출 시 선택 [확인, 세부 미조회] |
| 철회 | **완전 삭제 불가.** DOI 등록 후 영구 [확인] | 공개 후 "part of the permanent scholarly record", 삭제는 법적 권리 문제일 때만 [확인] |
| 장기 보존 | Portico 아카이브 [확인] | — |
| 저널 투고와의 관계 | "after submission to a peer-reviewed venue ... **before formal acceptance**" 허용 [확인] | 저널 투고와 병행 관행적 |
| 이름값 (심사위원 인지도) | 낮음 | **압도적으로 높음** |
| 계열 | **MDPI 운영** | 독립 비영리 [확인, 사이트 배너] |

---

## 2. 우리 상황에 실제로 걸리는 것 4가지

### 2-1. arXiv endorsement — 8/4 미팅에서 바로 확인할 것

정책 원문 [확인]:

> "Your account may receive endorsement if: you have **claimed ownership of a paper submitted by a co-author** ***and*** your email address meets the institutional email criteria"

`@ajou.ac.kr` 기관 메일은 있지만 arXiv 논문 이력이 0이므로 **자동 endorsement 불가**. 남은 길은 개인 endorsement 하나다.

- endorser 조건: 해당 **endorsement 도메인**에서 **최근 3개월~5년 사이** 투고 이력이 있는 활동 저자 [확인]
- **도메인 선택이 난이도를 바꾼다** [확인]:
  - `physics.flu-dyn` → **physics는 개별 subject class가 각각 endorsement 도메인**이라 범위가 좁다. flu-dyn 활동 저자를 직접 찾아야 함
  - `cs.*` / `eess.*` → 상위 아카이브 단위 도메인이라 **endorser 풀이 넓다**
- 절차: 제출 시작 → endorsement 요청 메일 수신 → 6자리 코드를 endorser에게 전달 [확인]
- **다수에게 동시 발송 금지** [확인]

→ **액션:** 8/4 교수 2차 미팅에서 "arXiv에 최근 5년 내 투고하신 적 있으십니까, 어느 카테고리입니까"를 묻는다. 있으면 arXiv, 없으면 Preprints.org. 이 질문 하나로 결정된다.

### 2-2. coursework 거절 — 서버 선택보다 먼저 해결할 것

양쪽 다 명문 규정이다 [확인]. 방어는 원고 쪽에서 한다.

- 본문·초록·감사의 글에서 **"캡스톤", "과제", "수업"** 표현 제거
- IMRaD 구조 유지 — Preprints.org는 "introduction, methods, results, and discussion" 구조와 **포괄적 참고문헌**을 명시 요구 [확인]
- `References/00_References.md` R1–R48이 이미 있으므로 이 요건은 충족 가능

### 2-3. 음성 결과 — 이게 Preprints.org 쪽으로 기우는 이유

`논문_최종.md`의 주 결과는 음성이다("공간항이 등급을 뒤집을 경로가 구조적으로 없다").

- Preprints.org: **"We welcome manuscripts reporting negative or non-significant results"** [확인] — 명시적 환영
- arXiv: 그런 문구 없고, 오히려 "lacks originality, novelty, significance"가 거절 사유로 열거돼 있다 [확인]

arXiv 모더레이터가 우리 음성 결과를 "significance 부족"으로 읽을 위험은 실재한다. **다만 이건 원고가 음성 결과를 어떻게 프레이밍하느냐에 달렸다** — "실패"가 아니라 "설계 공간의 경계를 확정했다"로 쓰면 다른 이야기가 된다.

### 2-4. 특허 — Preprints.org가 직접 경고하고 있다

> "**If you intend to register a patent based on the work, do not post a preprint, as it will compromise your application.**" [확인]

우리 게이트(`제출전략.md` 게이트 0, **P < X**)가 정확히 이 문제를 막고 있다. **출원번호 수령 전에는 어느 서버에도 올리지 않는다** — 변경 없음.

---

## 3. 판정

| 조건 | 선택 |
|---|---|
| **지도교수가 arXiv 활동 저자** (최근 5년, cs/eess/physics.flu-dyn 중 하나) | **arXiv.** 이름값 차이가 크고, 대회 심사위원에게 "arXiv에 올렸습니다"는 즉시 전달된다 |
| **endorser 확보 실패 또는 8월 말까지 미확정** | **Preprints.org.** 24시간 스크리닝이라 9/15 게시 일정이 확실히 지켜진다 |
| 어느 쪽이든 | **둘 다 올리지 않는다.** Preprints.org가 다중 서버 게시를 명시적으로 권장하지 않는다 [확인] |

> 기존 `venue_비교표.md` §3의 "arXiv = endorsement 리스크 → 임계경로 제외" 판단은 **유효하다.** 다만 그때는 리스크의 정체가 불명확했고, 지금은 **"지도교수가 arXiv 저자인가"라는 예/아니오 질문 하나**로 좁혀졌다. 8/4에 답이 나온다.

### 부수 논점 — MDPI 일관성

우리는 MDPI *Sensors* 를 APC 사유로 기각했는데 Preprints.org는 MDPI가 운영한다. **비용 판단에는 영향이 없다**(프리프린트는 0원). 다만 심사위원이 물을 수 있으니, 물으면 "게재료 문제로 저널은 접었고 프리프린트 서버는 무료라 별개"라고 답하면 된다. 숨길 사안이 아니다.

---

## 4. 타임라인 반영

| 날짜 | 액션 | 담당 |
|---|---|---|
| **8/4** | 교수 2차 미팅 — **"arXiv 최근 5년 투고 이력 / 카테고리"** 질문 | 전원 |
| 8/12 (하드 8/19) | 특허 출원 (P) — **모든 게시의 선행조건, 불변** | 송두산 |
| 8월 중 | arXiv 경로 확정 시 → 계정 생성 + endorsement 요청 **미리** 착수 (원고 완성 전에 시작 가능) | 김강빈 |
| 8월 중 | 원고에서 "캡스톤/과제" 표현 제거, IMRaD 정리 | 김강빈 |
| ~9/08 | 영문 원고 v1 완성 (양쪽 다 영어 필수) | 전원 |
| **~9/15** | 게시 (X) | 한규태 |
| 10/8 전 | 발표자료에 식별자 반영 — **"프리프린트(피어리뷰 전)"로 명기** | 신동하 |

> **언어 주의:** 기존 계획의 "국문 1건"으로는 어느 서버에도 올릴 수 없다. Preprints.org는 스크리닝 항목에 영어를 명시한다 [확인]. 국내 학회지(국문)와 프리프린트(영문)는 **원고를 따로 준비해야 한다.**
