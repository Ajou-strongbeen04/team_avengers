# -*- coding: utf-8 -*-
"""특허 도면 SVG 생성기 — 도01~도11. 흑백 선도."""
import os, math, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "./도면"
os.makedirs(OUT, exist_ok=True)

FONT = "Noto Sans CJK KR, Malgun Gothic, sans-serif"
SW = 1.6          # 기본 선 굵기
THIN = 0.9        # 인출선·보조선
FS = 13           # 기본 글자
FSS = 11          # 작은 글자
FSN = 12          # 부호


def head(w, h, title):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" font-family="{FONT}">\n'
        f'<defs>\n'
        f'  <marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0,0 L10,5 L0,10 z" fill="#000"/></marker>\n'
        f'  <marker id="ao" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0,0 L10,5 L0,10 z" fill="none" stroke="#000" stroke-width="1.4"/></marker>\n'
        f'  <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" '
        f'patternTransform="rotate(45)">'
        f'<line x1="0" y1="0" x2="0" y2="6" stroke="#000" stroke-width="0.7"/></pattern>\n'
        f'  <pattern id="hatch2" width="10" height="10" patternUnits="userSpaceOnUse" '
        f'patternTransform="rotate(-45)">'
        f'<line x1="0" y1="0" x2="0" y2="10" stroke="#000" stroke-width="0.7"/></pattern>\n'
        f'  <pattern id="dots" width="7" height="7" patternUnits="userSpaceOnUse">'
        f'<circle cx="2" cy="2" r="1" fill="#000"/></pattern>\n'
        f'</defs>\n'
        f'<rect width="{w}" height="{h}" fill="#fff"/>\n'
        f'<text x="18" y="30" font-size="17" font-weight="bold">{title}</text>\n'
    )


def foot():
    return "</svg>\n"


# Noto Sans CJK KR 에 없는 위/아래 첨자 글리프를 ASCII 로 치환 (도면 규격상 흑백 선도 + 판독성 우선)
_SUB = {
    "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4", "₅": "5",
    "⁰": "0", "¹": "1", "²": "2", "³": "3",
    "⁻": "-", "⁺": "+", "ₐ": "a", "ₑ": "e", "ₒ": "o", "ₓ": "x",
    "C̄": "C_avg",
}


def esc(t):
    t = str(t)
    for k, v in _SUB.items():
        t = t.replace(k, v)
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def box(x, y, w, h, lines, fs=FS, rx=3, dash=None, fill="none", weight="normal"):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    s = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
         f'stroke="#000" stroke-width="{SW}"{d}/>\n')
    if isinstance(lines, str):
        lines = [lines]
    n = len(lines)
    for i, t in enumerate(lines):
        ty = y + h / 2 + (i - (n - 1) / 2) * (fs + 3) + fs * 0.35
        s += (f'<text x="{x + w/2}" y="{ty:.1f}" font-size="{fs}" text-anchor="middle" '
              f'font-weight="{weight}">{esc(t)}</text>\n')
    return s


def txt(x, y, t, fs=FS, anchor="start", weight="normal", style=""):
    st = f' font-style="{style}"' if style else ""
    return (f'<text x="{x}" y="{y}" font-size="{fs}" text-anchor="{anchor}" '
            f'font-weight="{weight}"{st}>{esc(t)}</text>\n')


def num(x, y, t):
    """부호 표기"""
    return txt(x, y, t, fs=FSN, weight="bold")


def line(x1, y1, x2, y2, w=SW, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#000" stroke-width="{w}"{d}/>\n'


def arr(x1, y1, x2, y2, w=SW, dash=None, open_head=False):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    m = "ao" if open_head else "a"
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#000" '
            f'stroke-width="{w}"{d} marker-end="url(#{m})"/>\n')


def poly(pts, w=SW, dash=None, marker=True, fill="none"):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    m = ' marker-end="url(#a)"' if marker else ""
    p = " ".join(f"{x},{y}" for x, y in pts)
    return (f'<polyline points="{p}" fill="{fill}" stroke="#000" stroke-width="{w}"{d}{m}/>\n')


def leader(x1, y1, x2, y2, label):
    """인출선 + 부호"""
    s = line(x1, y1, x2, y2, w=THIN)
    s += f'<circle cx="{x1}" cy="{y1}" r="2" fill="#000"/>\n'
    dx = 6 if x2 >= x1 else -6
    anchor = "start" if x2 >= x1 else "end"
    s += txt(x2 + dx, y2 + 4, label, fs=FSN, anchor=anchor, weight="bold")
    return s


def save(name, body):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(body)
    print("wrote", name)


# ────────────────────────────────────────────────────────────── 도 1
def fig1():
    W, H = 980, 700
    s = head(W, H, "【도 1】")
    # 상단: 입력
    s += box(40, 70, 170, 62, ["촬영부", "(수조 영상)"])
    s += num(46, 62, "10")
    s += box(40, 165, 170, 62, ["수질 계측 센서부", "수온·탁도"])
    s += num(46, 157, "70")
    s += box(40, 260, 170, 62, ["수조", "(진단 대상)"])
    s += num(46, 252, "100")
    s += line(125, 260, 125, 227, w=THIN, dash="4 3")
    # 영상 인식 → BC
    s += box(265, 70, 175, 62, ["영상 인식부", "(시각-언어 모델)"])
    s += num(271, 62, "20")
    s += box(495, 70, 175, 62, ["경계조건", "자동설정부"])
    s += num(501, 62, "30")
    s += arr(210, 101, 265, 101)
    s += txt(237, 94, "11", fs=FSN, anchor="middle", weight="bold")
    s += arr(440, 101, 495, 101)
    s += txt(467, 94, "21", fs=FSN, anchor="middle", weight="bold")
    # 물리 추론부 프레임
    s += ('<rect x="495" y="165" width="330" height="215" rx="5" fill="none" '
          f'stroke="#000" stroke-width="{SW}" stroke-dasharray="7 4"/>\n')
    s += txt(505, 158, "물리 추론부", fs=FS, weight="bold")
    s += num(795, 158, "40")
    s += box(515, 182, 290, 52, ["제1계층(A층) 유동 대리모델"], fs=FSS)
    s += num(521, 176, "41")
    s += box(515, 248, 290, 52, ["제2계층(B층) 복수 스칼라 병렬 풀이"], fs=FSS)
    s += num(521, 242, "42")
    s += box(515, 314, 290, 52, ["국소 산-염기 평형 풀이부 (pH·NH₃)"], fs=FSS)
    s += num(521, 308, "43")
    s += arr(582, 132, 582, 182)
    s += txt(592, 152, "31", fs=FSN, anchor="start", weight="bold")
    s += arr(660, 234, 660, 248)
    s += arr(660, 300, 660, 314)
    # 센서 → 물리 추론부 (계수 확정)
    s += poly([(210, 196), (350, 196), (350, 274), (515, 274)])
    s += txt(216, 178, "수온 → 온도종속 계수 확정", fs=FSS)
    s += txt(216, 160, "탁도 → 소스 진폭 확정", fs=FSS)
    # 캘리브레이션
    s += box(265, 314, 175, 62, ["캘리브레이션부", "재폭기·탈기 시험"])
    s += num(271, 306, "80")
    s += arr(440, 345, 515, 340)
    # 융합 판정 → 표시
    s += box(495, 420, 330, 62, ["융합 판정부 — 항목별 위험구역 결합"])
    s += num(501, 412, "50")
    s += arr(660, 380, 660, 420)
    s += box(495, 512, 155, 58, ["항목별 위험맵"], fs=FSS)
    s += num(501, 505, "51")
    s += box(670, 512, 155, 58, ["처방 생성부"], fs=FSS)
    s += num(676, 505, "52")
    s += arr(572, 482, 572, 512)
    s += arr(748, 482, 748, 512)
    s += box(495, 610, 330, 56, ["표시부 (사용자 단말)"])
    s += num(501, 602, "60")
    s += arr(572, 570, 572, 610)
    s += arr(748, 570, 748, 610)
    # 오프라인 생성기
    s += ('<rect x="855" y="120" width="105" height="260" rx="5" fill="none" '
          f'stroke="#000" stroke-width="{SW}" stroke-dasharray="7 4"/>\n')
    s += txt(907, 112, "서버측 (오프라인)", fs=FSS, anchor="middle")
    s += box(866, 140, 83, 62, ["기하", "파라미터", "표집부"], fs=FSS)
    s += num(872, 134, "91")
    s += box(866, 222, 83, 62, ["과도 CFD", "생성기"], fs=FSS)
    s += num(872, 216, "90")
    s += box(866, 304, 83, 62, ["유동장", "DB"], fs=FSS)
    s += num(872, 298, "92")
    s += arr(907, 202, 907, 222)
    s += arr(907, 284, 907, 304)
    s += arr(866, 335, 805, 250, dash="5 3")
    s += txt(40, 690, "* 실선 = 온라인(사용자 단말) 경로,  파선 = 오프라인·계측 경로", fs=FSS)
    return s + foot()


# ────────────────────────────────────────────────────────────── 도 2 (대표도)
def fig2():
    W, H = 980, 640
    s = head(W, H, "【도 2】")
    s += txt(W / 2, 56, "관측 3종 → 비가시 수질 항목 N종", fs=15, anchor="middle", weight="bold")
    # 좌측 입력
    s += txt(150, 92, "보이는 것 (관측)", fs=13, anchor="middle", weight="bold")
    ins = [("영상 1장", "10 / 11", 120), ("수온", "71", 240), ("탁도", "72", 360)]
    for name, n, y in ins:
        s += box(60, y, 180, 62, [name])
        s += num(66, y - 8, n)
    # 중앙 : 무엇을 닫는가
    s += txt(490, 92, "물리모델에서 닫는 것", fs=13, anchor="middle", weight="bold")
    mids = [
        (["도메인·Ω_air·Γ_filter", "장애물·어류 개체수"], 110),
        (["C*(T), k_L(T), D_mol(T)", "Q₁₀, pK_a(T), K₁(T), K₂(T)"], 230),
        (["부유입자 C_p", "P_TAN·저질산소요구량 진폭"], 350),
    ]
    for lines, y in mids:
        s += box(320, y, 340, 72, lines, fs=FSS)
    for i, (_, _, y) in enumerate(ins):
        s += arr(240, y + 31, 320, mids[i][1] + 36)
    # 우측 : 추정 항목
    s += txt(830, 92, "보이지 않는 것 (추정, 공간분포)", fs=13, anchor="middle", weight="bold")
    outs = [
        ("용존산소 DO", 110), ("용존 이산화탄소 CO₂", 156), ("pH (국소 평형)", 202),
        ("비이온 암모니아 NH₃", 248), ("총암모니아성질소 TAN", 294),
        ("아질산 NO₂⁻ · 질산 NO₃⁻", 340), ("부유입자·퇴적 분포", 386),
    ]
    for name, y in outs:
        s += box(700, y, 250, 38, [name], fs=FSS)
    # 중앙 → 물리 추론부 게이트
    s += ('<rect x="320" y="440" width="340" height="86" rx="5" fill="none" '
          f'stroke="#000" stroke-width="{SW}"/>\n')
    s += txt(490, 470, "물리 추론부 (2계층 축소모델)", fs=13, anchor="middle", weight="bold")
    s += txt(490, 494, "유동장 1회 계산 → 스칼라 N개 병렬 풀이", fs=FSS, anchor="middle")
    s += num(326, 434, "40")
    for _, y in mids:
        s += line(320, y + 36, 296, y + 36, w=THIN)
    s += line(296, 146, 296, 483, w=THIN)
    s += arr(296, 483, 320, 483, w=THIN)
    # 게이트 → 출력
    s += line(660, 483, 680, 483, w=THIN)
    for _, y in outs:
        s += arr(680, 483, 700, y + 19, w=THIN)
    s += txt(60, 560, "요지 : 관측은 3종으로 고정되고, 항목을 늘려도 센서가 늘지 않는다.", fs=13)
    s += txt(60, 586, "난류확산 계수가 항목에 무관하므로 하나의 유동장이 모든 항목의 공간 골격을 결정한다.", fs=FSS)
    s += txt(60, 610, "항목을 가르는 것은 표면 경계조건의 종류와 소스항뿐이다.", fs=FSS)
    return s + foot()


# ──────────────────────────────────────────────────────────── 도 3
def fig3():
    W, H = 1000, 660
    s = head(W, H, "【도 3】")
    x0, y0, w, h = 160, 150, 560, 300
    dx, dy = 82, -58
    # 수조 사시도
    s += f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="none" stroke="#000" stroke-width="{SW}"/>\n'
    s += line(x0, y0, x0 + dx, y0 + dy)
    s += line(x0 + w, y0, x0 + w + dx, y0 + dy)
    s += line(x0 + w, y0 + h, x0 + w + dx, y0 + h + dy)
    s += line(x0 + dx, y0 + dy, x0 + w + dx, y0 + dy)
    s += line(x0 + w + dx, y0 + dy, x0 + w + dx, y0 + h + dy)
    s += leader(x0 + w, y0 + h - 30, x0 + w + 130, y0 + h + 26, "100")
    # 자유수면
    ws = y0 + 46
    s += line(x0, ws, x0 + w, ws)
    s += line(x0, ws, x0 + dx, ws + dy, w=THIN, dash="5 3")
    s += line(x0 + w, ws, x0 + w + dx, ws + dy, w=THIN, dash="5 3")
    s += line(x0 + dx, ws + dy, x0 + w + dx, ws + dy, w=THIN, dash="5 3")
    s += leader(x0 + 470, ws, x0 + w + 96, y0 - 6, "102")
    s += leader(x0 + 30, y0 + h, x0 - 40, y0 + h + 34, "103")
    # 폭기 토출구
    px = x0 + 120
    s += f'<rect x="{px-16}" y="{y0+h-18}" width="32" height="18" fill="none" stroke="#000" stroke-width="{SW}"/>\n'
    s += leader(px, y0 + h - 9, px - 74, y0 + h + 34, "110")
    # 플룸 영역
    s += (f'<rect x="{px-34}" y="{ws}" width="68" height="{y0+h-18-ws}" fill="none" '
          f'stroke="#000" stroke-width="{SW}" stroke-dasharray="6 4"/>\n')
    s += leader(px - 34, ws + 40, px - 108, ws + 10, "111")
    s += txt(px - 116, ws - 8, "Ω_air", fs=FSS, anchor="end")
    for i, yy in enumerate(range(ws + 24, y0 + h - 26, 32)):
        s += f'<circle cx="{px-14+(i%3)*14}" cy="{yy}" r="4.5" fill="none" stroke="#000" stroke-width="1"/>\n'
    s += leader(px - 14, ws + 24, px - 108, ws + 54, "112")
    # 여과부
    fx, fy, fw, fh = px + 42, ws + 12, 46, 92
    s += f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" fill="url(#hatch)" stroke="#000" stroke-width="{SW}"/>\n'
    s += leader(fx + fw, fy + 12, fx + fw + 90, fy - 24, "120")
    s += leader(fx + fw, fy + fh - 12, fx + fw + 90, fy + fh + 24, "121")
    s += txt(fx + fw + 98, fy + fh + 42, "Γ_filter", fs=FSS)
    # 장식물
    s += (f'<path d="M{x0+300},{y0+h} L{x0+330},{y0+h-72} L{x0+372},{y0+h-48} '
          f'L{x0+398},{y0+h} Z" fill="url(#hatch2)" stroke="#000" stroke-width="{SW}"/>\n')
    s += leader(x0 + 350, y0 + h - 56, x0 + 440, y0 + h + 20, "130")
    # 수초
    s += (f'<path d="M{x0+446},{y0+h} C{x0+436},{y0+h-60} {x0+466},{y0+h-70} {x0+456},{y0+h-112}" '
          f'fill="none" stroke="#000" stroke-width="{SW}"/>\n')
    s += (f'<path d="M{x0+476},{y0+h} C{x0+470},{y0+h-50} {x0+496},{y0+h-64} {x0+488},{y0+h-98}" '
          f'fill="none" stroke="#000" stroke-width="{SW}"/>\n')
    s += leader(x0 + 460, y0 + h - 96, x0 + 430, y0 + h - 150, "140")
    # 어류
    ex, ey = x0 + 300, ws + 44
    s += (f'<ellipse cx="{ex}" cy="{ey}" rx="26" ry="12" fill="none" stroke="#000" stroke-width="{SW}"/>\n'
          f'<path d="M{ex+26},{ey} l18,-11 v22 z" fill="none" stroke="#000" stroke-width="{SW}"/>\n')
    s += leader(ex, ey - 12, ex + 30, ey - 52, "150")
    # 정체역
    s += (f'<ellipse cx="{x0+w-80}" cy="{y0+h-58}" rx="64" ry="36" fill="none" '
          f'stroke="#000" stroke-width="{SW}" stroke-dasharray="3 3"/>\n')
    s += leader(x0 + w - 80, y0 + h - 58, x0 + w + 96, y0 + h - 96, "160")
    # 퇴적층 (정체역 하부)
    s += (f'<rect x="{x0+w-158}" y="{y0+h-12}" width="156" height="12" fill="url(#dots)" '
          f'stroke="#000" stroke-width="{THIN}"/>\n')
    s += leader(x0 + w - 80, y0 + h - 6, x0 + w + 96, y0 + h + 2, "170")
    # 수체
    s += leader(x0 + 480, ws + 26, x0 + w + 96, ws + 10, "101")

    # 좌표축
    ax, ay = 120, 612
    s += arr(ax, ay, ax + 96, ay) + txt(ax + 102, ay + 5, "x (길이 L)", fs=FSS)
    s += arr(ax, ay, ax + 58, ay - 42) + txt(ax + 62, ay - 46, "y (폭 B)", fs=FSS)
    s += arr(ax, ay, ax, ay - 74) + txt(ax + 6, ay - 80, "z (수심)", fs=FSS)
    s += txt(ax - 8, ay + 6, "O", fs=FSS, anchor="end")
    s += txt(300, 540, "단일 해석좌표계. 영상 인식부·경계조건 자동설정부·대리모델·센서 배치가 모두 이 좌표계를 공유한다.", fs=FSS)
    s += txt(300, 562, "영상 인식부의 출력은 각 축을 [0,1]로 정규화한 값으로 주어지며, 별도의 좌표 변환 단계를 두지 않는다.", fs=FSS)
    s += txt(300, 584, "102 자유수면은 로빈 조건(재폭기·탈기), 103 바닥은 퇴적 플럭스, 121 여과재 표면은 질산화 면소스이다.", fs=FSS)
    return s + foot()


# ────────────────────────────────────────────────────────────── 도 4
def fig4():
    W, H = 940, 700
    s = head(W, H, "【도 4】")
    # 오프라인 영역
    s += ('<rect x="40" y="60" width="380" height="330" rx="6" fill="none" '
          f'stroke="#000" stroke-width="{SW}" stroke-dasharray="8 4"/>\n')
    s += txt(60, 84, "오프라인 (서버측) — 1회 수행", fs=13, weight="bold")
    s += box(70, 100, 320, 50, ["기하 파라미터 공간 표집"], fs=FSS)
    s += num(76, 94, "91")
    s += box(70, 178, 320, 62, ["과도 URANS 해석 (SST k–ω)", "케이스마다 1회"], fs=FSS)
    s += num(76, 172, "90")
    s += box(70, 268, 320, 62, ["시간평균 유동장 Ū 와 와점성 ν_t 저장", "(ν_t 는 생값으로 저장)"], fs=FSS)
    s += num(76, 262, "92")
    s += arr(230, 150, 230, 178)
    s += arr(230, 240, 230, 268)
    s += box(70, 350, 320, 34, ["→ 연속 사상(대리모델) 학습"], fs=FSS)
    s += arr(230, 330, 230, 350)
    # 온라인 영역
    s += ('<rect x="470" y="60" width="430" height="580" rx="6" fill="none" '
          f'stroke="#000" stroke-width="{SW}"/>\n')
    s += txt(490, 84, "온라인 (사용자 단말) — 매 진단마다", fs=13, weight="bold")
    s += box(500, 100, 370, 46, ["경계조건 객체 (기하 성분)"], fs=FSS)
    s += num(872, 94, "31")
    s += box(500, 174, 370, 56, ["제1계층 (A층) : 기하 → 시간평균 유동장", "조회가 아니라 예측(보간)"], fs=FSS)
    s += num(506, 168, "41")
    s += arr(685, 146, 685, 174)
    s += arr(420, 367, 500, 202, dash="6 3")
    s += txt(496, 246, "학습된 대리모델 이식", fs=FSS, anchor="end")
    # 제2계층 : 병렬 스칼라
    s += box(500, 258, 370, 46, ["제2계층 (B층) : 유동장 고정 → 선형 스칼라 수송"], fs=FSS)
    s += num(506, 252, "42")
    s += arr(685, 230, 685, 258)
    cols = ["DO", "CO₂", "TAN", "NO₂⁻", "NO₃⁻", "DIC", "Alk", "C_p"]
    bw = 42
    for i, c in enumerate(cols):
        bx = 505 + i * (bw + 3)
        s += box(bx, 322, bw, 40, [c], fs=FSS)
        s += line(bx + bw / 2, 304, bx + bw / 2, 322, w=THIN)
    s += txt(685, 382, "동일 유동장 · 동일 난류확산 계수 → 항목 추가 비용 = 선형 풀이 1회", fs=FSS, anchor="middle")
    s += box(500, 400, 370, 46, ["국소 산-염기 평형 풀이 → pH, f(NH₃)"], fs=FSS)
    s += num(506, 394, "43")
    s += arr(685, 362, 685, 400)
    s += box(500, 474, 370, 46, ["보정계수 κ · 잔차 전파 (불확실성 채널)"], fs=FSS)
    s += num(506, 468, "80")
    s += arr(685, 446, 685, 474)
    s += box(500, 548, 370, 46, ["항목별 셀 위험 확률 P_risk,i(x)"], fs=FSS)
    s += arr(685, 520, 685, 548)
    s += box(500, 604, 370, 34, ["구역 단위 조대화 → 융합 판정부(50)"], fs=FSS)
    s += arr(685, 594, 685, 604)
    # 좌하단 설명
    s += txt(40, 430, "비싼 층만 오프라인으로 동결하므로", fs=FSS)
    s += txt(40, 452, "온라인 비용은 선형 스칼라층에 갇힌다.", fs=FSS)
    s += txt(40, 486, "제1계층은 어종 임계·생물 소스와", fs=FSS)
    s += txt(40, 508, "독립이므로, 사육조건이 바뀌어도", fs=FSS)
    s += txt(40, 530, "재생성할 필요가 없다.", fs=FSS)
    return s + foot()


# ────────────────────────────────────────────────────────────── 도 5
def fig5():
    W, H = 960, 660
    s = head(W, H, "【도 5】")
    s += box(60, 80, 200, 50, ["수온 T (센서 71)"], weight="bold")
    s += txt(60, 152, "k_L, C*, D_mol, Q₁₀, pK_a, K₁, K₂ 를 전부 닫음", fs=FSS)
    s += box(380, 80, 240, 50, ["폭기 F_air (Ω_air, 111)"])
    s += box(380, 170, 240, 56, ["유동장 Ū, ν_t", "(모든 항목이 공유 · 1회 계산)"], fs=FSS, weight="bold")
    s += arr(500, 130, 500, 170)
    s += poly([(160, 130), (160, 198), (380, 198)])
    s += box(700, 80, 200, 50, ["탁도 C_p (센서 72)"], weight="bold")
    s += poly([(800, 130), (800, 198), (620, 198)])
    # 항목 노드
    nodes = [("DO", 90, 300), ("DIC", 260, 300), ("Alk", 420, 300),
             ("TAN", 580, 300), ("NO₂⁻", 720, 300), ("NO₃⁻", 850, 300)]
    for name, x, y in nodes:
        s += box(x, y, 92, 42, [name])
        s += line(x + 46, 226, x + 46, 300, w=THIN, dash="4 3")
    # 커플링
    s += poly([(136, 342), (136, 392), (626, 392), (626, 342)], dash="5 3")
    s += txt(300, 386, "질산화가 DO 를 소비 (이중 모노드)", fs=FSS)
    s += arr(672, 321, 720, 321)
    s += arr(812, 321, 850, 321)
    s += txt(676, 314, "r₁", fs=FSS)
    s += txt(816, 314, "r₂", fs=FSS)
    s += box(230, 440, 320, 50, ["국소 산-염기 평형 → pH"], weight="bold")
    s += num(236, 434, "43")
    s += poly([(306, 342), (306, 440)])
    s += poly([(466, 342), (466, 415), (390, 415), (390, 440)])
    s += poly([(626, 342), (626, 415), (700, 415), (700, 466), (550, 466)])
    s += txt(632, 410, "H⁺ 생성 (알칼리도 소비)", fs=FSS)
    s += box(230, 540, 320, 50, ["비이온 암모니아 분율 f(pH, T) × TAN"])
    s += arr(390, 490, 390, 540)
    s += box(620, 540, 300, 50, ["위험 판정 : 항목별 위험구역의 합집합"], fs=FSS, weight="bold")
    s += num(626, 534, "50")
    s += arr(550, 565, 620, 565)
    s += poly([(136, 342), (136, 565), (230, 565)])
    s += txt(40, 626, "요지 : 수온이 모든 계수를 닫고, 유동장 하나가 모든 항목을 나른다. pH 는 이송하지 않고 보존량 두 개(DIC, Alk)로부터 산출한다.", fs=FSS)
    return s + foot()


# ────────────────────────────────────────────────────────────── 도 6
def fig6():
    W, H = 1140, 640
    s = head(W, H, "【도 6】")
    s += txt(250, 62, "(a) 측면도", fs=13, anchor="middle", weight="bold")
    s += txt(790, 62, "(b) 센서 레그 종단면도", fs=13, anchor="middle", weight="bold")
    # (a)
    # 수조 벽
    s += f'<rect x="190" y="120" width="18" height="420" fill="url(#hatch)" stroke="#000" stroke-width="{SW}"/>\n'
    s += leader(199, 520, 150, 560, "100")
    # 수면
    s += line(208, 190, 480, 190, dash="8 4")
    s += leader(430, 190, 470, 150, "102")
    s += txt(478, 130, "수면", fs=FSS)
    # 브릿지
    s += f'<rect x="120" y="120" width="200" height="42" rx="4" fill="none" stroke="#000" stroke-width="{SW}"/>\n'
    s += leader(230, 141, 300, 96, "73")
    s += f'<rect x="140" y="128" width="60" height="26" rx="2" fill="none" stroke="#000" stroke-width="{THIN}"/>\n'
    s += leader(170, 141, 100, 96, "77")
    # 후크
    s += (f'<path d="M186,120 L186,108 L216,108 L216,120" fill="none" stroke="#000" stroke-width="{SW}"/>\n')
    s += leader(201, 108, 250, 78, "76")
    # 배터리 레그 (좌, dry)
    s += f'<rect x="126" y="162" width="46" height="150" rx="4" fill="none" stroke="#000" stroke-width="{SW}"/>\n'
    s += leader(149, 300, 80, 340, "74")
    s += f'<rect x="136" y="186" width="26" height="96" rx="10" fill="none" stroke="#000" stroke-width="{THIN}"/>\n'
    s += leader(149, 234, 74, 250, "78")
    # 센서 레그 (우, wet)
    s += f'<rect x="266" y="162" width="34" height="330" rx="6" fill="none" stroke="#000" stroke-width="{SW}"/>\n'
    s += leader(300, 300, 372, 268, "75")
    # 탁도 광학존
    s += f'<rect x="270" y="330" width="26" height="58" fill="none" stroke="#000" stroke-width="{THIN}"/>\n'
    s += leader(296, 359, 380, 344, "72")
    s += txt(388, 362, "탁도 광학존", fs=FSS)
    # 수온 센서 (최하단)
    s += (f'<path d="M270,452 h26 v26 a13,13 0 0 1 -26,0 z" fill="none" stroke="#000" stroke-width="{THIN}"/>\n')
    s += leader(296, 466, 380, 452, "71")
    s += txt(388, 470, "수온 센서 (최하단)", fs=FSS)
    # 축방향 이격 치수
    s += line(322, 388, 322, 452, w=THIN)
    s += arr(322, 420, 322, 390, w=THIN)
    s += arr(322, 420, 322, 450, w=THIN)
    s += txt(330, 424, "축방향 이격 (광로 차단 방지)", fs=FSS)
    # 폭기 플룸 참조
    s += (f'<rect x="392" y="190" width="56" height="302" fill="none" stroke="#000" '
          f'stroke-width="{THIN}" stroke-dasharray="6 4"/>\n')
    s += leader(420, 520, 470, 552, "111")
    s += line(208, 560, 420, 560, w=THIN)
    s += arr(300, 560, 210, 560, w=THIN)
    s += arr(300, 560, 418, 560, w=THIN)
    s += txt(200, 584, "프로브 축과 폭기 플룸축을 장착벽으로부터 동일 기준거리에 둔다", fs=FSS)
    s += txt(200, 604, "프로브 팁은 Ω_air 외측 · 최원 코너 저층에 근접시킨다", fs=FSS)
    # (b) 단면
    cx, cy = 790, 300
    s += f'<circle cx="{cx}" cy="{cy}" r="86" fill="none" stroke="#000" stroke-width="{SW}"/>\n'
    s += f'<circle cx="{cx}" cy="{cy}" r="70" fill="none" stroke="#000" stroke-width="{SW}"/>\n'
    s += leader(cx, cy - 86, cx + 150, cy - 130, "75")
    s += txt(cx + 158, cy - 112, "외경 약 10 mm 관(밀봉)", fs=FSS)
    s += f'<circle cx="{cx}" cy="{cy}" r="46" fill="url(#dots)" stroke="#000" stroke-width="{THIN}"/>\n'
    s += leader(cx - 30, cy + 34, cx - 160, cy + 110, "포팅")
    s += (f'<rect x="{cx-14}" y="{cy-14}" width="28" height="28" fill="none" stroke="#000" stroke-width="{SW}"/>\n')
    s += leader(cx + 14, cy - 10, cx + 150, cy - 40, "72")
    s += txt(cx + 158, cy - 22, "광학존", fs=FSS)
    s += txt(cx + 158, cy - 4, "(수지 국소 마스킹)", fs=FSS)
    s += arr(cx - 60, cy, cx - 18, cy, w=THIN)
    s += arr(cx + 60, cy, cx + 18, cy, w=THIN)
    s += txt(cx, cy + 130, "광로", fs=FSS, anchor="middle")
    s += line(cx - 40, cy + 40, cx - 20, cy + 116, w=THIN)
    return s + foot()


# ────────────────────────────────────────────────────────────── 도 7
def fig7():
    W, H = 1080, 560
    s = head(W, H, "【도 7】")
    s += txt(W / 2, 60, "조대 위험맵 — 수조 수평면 4 × 9 = 36 구역", fs=14, anchor="middle", weight="bold")
    x0, y0 = 140, 100
    cw, ch = 78, 74
    nx, ny = 9, 4
    for j in range(ny):
        for i in range(nx):
            s += (f'<rect x="{x0+i*cw}" y="{y0+j*ch}" width="{cw}" height="{ch}" '
                  f'fill="none" stroke="#000" stroke-width="{THIN}"/>\n')
    s += (f'<rect x="{x0}" y="{y0}" width="{nx*cw}" height="{ny*ch}" fill="none" '
          f'stroke="#000" stroke-width="{SW}"/>\n')
    # 폭기 위치
    px, py = x0 + 1 * cw + cw / 2, y0 + 1 * ch + ch / 2
    s += f'<circle cx="{px}" cy="{py}" r="16" fill="none" stroke="#000" stroke-width="{SW}"/>\n'
    s += line(px - 11, py - 11, px + 11, py + 11) + line(px - 11, py + 11, px + 11, py - 11)
    s += leader(px, py - 16, px - 40, y0 - 30, "110")
    # 최위험 구역 (해칭)
    ri, rj = 8, 3
    s += (f'<rect x="{x0+ri*cw}" y="{y0+rj*ch}" width="{cw}" height="{ch}" '
          f'fill="url(#hatch)" stroke="#000" stroke-width="2.6"/>\n')
    s += leader(x0 + ri * cw + cw / 2, y0 + rj * ch + ch / 2, x0 + nx * cw + 60, y0 + ny * ch + 20, "161")
    s += txt(x0 + nx * cw + 68, y0 + ny * ch + 40, "최위험 구역 (예측)", fs=FSS)
    # 하위 25% 구역 (점선)
    for (i, j) in [(7, 3), (8, 2), (7, 2), (6, 3), (8, 1), (0, 3), (0, 0)]:
        s += (f'<rect x="{x0+i*cw+4}" y="{y0+j*ch+4}" width="{cw-8}" height="{ch-8}" '
              f'fill="none" stroke="#000" stroke-width="{THIN}" stroke-dasharray="4 3"/>\n')
    s += (f'<rect x="{790}" y="{460}" width="22" height="18" fill="none" stroke="#000" '
          f'stroke-width="{THIN}" stroke-dasharray="4 3"/>\n')
    s += txt(820, 474, "실제 하위 25 % 구역", fs=FSS)
    s += (f'<rect x="{790}" y="{490}" width="22" height="18" fill="url(#hatch)" stroke="#000" stroke-width="2.6"/>\n')
    s += txt(820, 504, "예측 최위험 구역", fs=FSS)
    # 치수
    s += line(x0, y0 + ny * ch + 26, x0 + nx * cw, y0 + ny * ch + 26, w=THIN)
    s += txt(x0 + nx * cw / 2, y0 + ny * ch + 46, "L = 47 cm (9 분할)", fs=FSS, anchor="middle")
    s += line(x0 - 26, y0, x0 - 26, y0 + ny * ch, w=THIN)
    s += txt(x0 - 34, y0 + ny * ch / 2 - 8, "B = 21 cm", fs=FSS, anchor="end")
    s += txt(x0 - 34, y0 + ny * ch / 2 + 10, "(4 분할)", fs=FSS, anchor="end")
    s += txt(140, 470, "실시예 : 253 케이스 5-겹 교차검증 — 최위험 구역 정확 적중 0.67,", fs=FSS)
    s += txt(140, 492, "예측 구역이 실제 하위 25 % 안에 들 확률 1.00.", fs=FSS)
    s += txt(140, 514, "약 5 cm 급 블록이 유효 작동점 (더 조대화하면 과제가 퇴화한다).", fs=FSS)
    return s + foot()


# ────────────────────────────────────────────────────────────── 도 8
def fig8():
    W, H = 940, 600
    s = head(W, H, "【도 8】")
    s += txt(W / 2, 60, "저산소 위험구역과 비이온 암모니아 독성 위험구역의 어긋남", fs=14,
             anchor="middle", weight="bold")

    def tank(ox, oy, label):
        t = f'<rect x="{ox}" y="{oy}" width="360" height="180" fill="none" stroke="#000" stroke-width="{SW}"/>\n'
        t += line(ox, oy + 18, ox + 360, oy + 18, w=THIN, dash="6 3")
        # 폭기 플룸
        t += (f'<rect x="{ox+56}" y="{oy+18}" width="46" height="162" fill="none" '
              f'stroke="#000" stroke-width="{THIN}" stroke-dasharray="5 3"/>\n')
        t += txt(ox + 79, oy + 196, "Ω_air", fs=FSS, anchor="middle")
        t += txt(ox, oy - 10, label, fs=13, weight="bold")
        return t

    s += tank(70, 110, "(a) 용존산소 DO 분포")
    s += tank(510, 110, "(b) 비이온 암모니아 NH₃ 독성 분포")
    # (a) 저산소역 = 우측 하단
    s += (f'<ellipse cx="{70+286}" cy="{110+140}" rx="58" ry="34" fill="url(#hatch)" '
          f'stroke="#000" stroke-width="2.4"/>\n')
    s += leader(70 + 286, 110 + 140, 70 + 286, 110 + 212, "161")
    s += txt(70 + 294, 110 + 230, "저산소 위험구역", fs=FSS)
    s += txt(70 + 62, 110 + 60, "DO 高", fs=FSS)
    s += txt(70 + 250, 110 + 60, "DO 低", fs=FSS)
    # (b) 독성역 = 폭기 플룸 근처
    s += (f'<ellipse cx="{510+79}" cy="{110+90}" rx="44" ry="62" fill="url(#hatch2)" '
          f'stroke="#000" stroke-width="2.4"/>\n')
    s += leader(510 + 79, 110 + 90, 510 + 200, 110 + 210, "162")
    s += txt(510 + 208, 110 + 228, "암모니아 독성 위험구역", fs=FSS)
    s += txt(510 + 150, 110 + 60, "pH 低 → 독성 低", fs=FSS)
    s += txt(510 + 30, 110 + 172, "pH 高", fs=FSS)
    # 설명 박스
    s += box(70, 380, 800, 66, [
        "폭기 플룸에서는 CO₂ 가 탈기되어 국소 pH 가 상승한다 → f(NH₃) 가 pH 1 상승당 약 10 배로 증가 →",
        "TAN 농도가 같아도 독성은 자릿수 단위로 달라진다. 반대로 정체역은 DO 는 낮으나 pH 도 낮아 독성은 상대적으로 낮다."], fs=FSS)
    s += box(70, 466, 800, 44, [
        "→ 융합 판정부(50)는 두 위험구역의 합집합에 대해 안전측 판정을 내리고, 그 어긋남을 별도로 표시한다."], fs=FSS, weight="bold")
    s += txt(70, 552, "단일 항목 지도 또는 단일 지점 계측으로는 이 어긋남을 원리적으로 판정할 수 없다.", fs=FSS)
    return s + foot()


# ────────────────────────────────────────────────────────────── 도 9
def fig9():
    W, H = 900, 880
    s = head(W, H, "【도 9】")
    ys = 80
    steps = [
        (["S1. 기준 수조에 탈산소 시약 투입 → 벌크 DO ≈ 0", "(CO₂ 항목은 CO₂ 주입으로 과포화 : 거울상 시험)"], 74),
        (["S2. 폭기 개시, 벌크 농도 시간이력 기록"], 46),
        (["S3. 지수 회귀 C_b(t) = C* − (C* − C_b0) exp(−K_L a_eff · t)", "→ K_L a_eff, meas 및 C*_meas 추정"], 74),
        (["S4. 동일 초기조건으로 물리모델 가상 시험 수행", "→ K_L a_eff, CFD"], 74),
        (["S5. κ = K_L a_eff,meas / K_L a_eff,CFD ,  ΔC* = C*_meas − C*_CFD"], 46),
        (["S6. 회귀 잔차를 모델 불확실도로 정량화"], 46),
        (["S7. 캘리브레이션에 쓰지 않은 조건에 재피팅 없이 적용", "→ 전이 잔차 확인 (순환논리 차단)"], 74),
        (["S8. κ 와 잔차를 제2계층(42)의 불확실성 채널로 전파", "→ 출력을 셀별 위험 확률로 제공"], 74),
    ]
    y = ys
    for i, (lines, h) in enumerate(steps):
        s += box(150, y, 560, h, lines, fs=FSS)
        if i < len(steps) - 1:
            s += arr(430, y + h, 430, y + h + 26)
        y += h + 26
    # 우측 주석
    s += txt(724, 128, "0차원 축약 :", fs=FSS)
    s += txt(724, 148, "dC_b/dt = K_L a_eff (C* − C_b)", fs=FSS)
    s += txt(724, 300, "κ 는 집약 계수이므로", fs=FSS)
    s += txt(724, 320, "개별 오차원(난류 폐쇄,", fs=FSS)
    s += txt(724, 340, "계면전달, 난류확산,", fs=FSS)
    s += txt(724, 360, "기포 플룸 근사)을", fs=FSS)
    s += txt(724, 380, "분리하지 못한다.", fs=FSS)
    s += txt(724, 412, "조건의존적 유효", fs=FSS)
    s += txt(724, 432, "보정계수로 취급한다.", fs=FSS)
    s += num(120, 108, "81")
    s += num(120, 706, "82")
    s += txt(40, 846, "* CO₂ 탈기 시험으로 k_L,i = k_L,O₂ (D_mol,i / D_mol,O₂)^n 의 지수 n 을 실측 결정한다. 이 한 번의 시험으로 휘발성 기체 항목군 전체가 닫힌다.", fs=FSS)
    return s + foot()


# ────────────────────────────────────────────────────────────── 도 10
def fig10():
    W, H = 880, 620
    s = head(W, H, "【도 10】")
    s += box(250, 80, 380, 46, ["폭기 유량 Q_air 실측, 플룸 단면적 A_p 결정"], fs=FSS)
    s += arr(440, 126, 440, 156)
    s += box(250, 156, 380, 46, ["표면 겉보기 기체속도 U_gs = Q_air / A_p"], fs=FSS)
    s += arr(440, 202, 440, 232)
    s += box(250, 232, 380, 46, ["α_g 초기값 가정"], fs=FSS)
    s += arr(440, 278, 440, 308)
    s += box(250, 308, 380, 56, ["URANS 해석 수행", "→ 플룸 상승 액상속도 W 획득"], fs=FSS)
    s += arr(440, 364, 440, 394)
    s += box(250, 394, 380, 46, ["α_g ← U_gs / (W + U_slip)"], fs=FSS)
    # 판정 마름모
    s += (f'<path d="M440,460 L620,510 L440,560 L260,510 Z" fill="none" stroke="#000" stroke-width="{SW}"/>\n')
    s += txt(440, 506, "수렴?", fs=FSS, anchor="middle")
    s += txt(440, 524, "|Δα_g| < tol", fs=FSS, anchor="middle")
    s += arr(440, 440, 440, 460)
    # 되먹임
    s += poly([(260, 510), (150, 510), (150, 336), (250, 336)])
    s += txt(60, 500, "아니오", fs=FSS)
    s += arr(620, 510, 700, 510)
    s += txt(636, 502, "예", fs=FSS)
    s += box(700, 470, 160, 80, ["α_g 확정", "(부력측 고정)", "→ 전달측만 캘리브"], fs=FSS, weight="bold")
    # 주석
    s += txt(660, 120, "실시예 수렴값", fs=FSS, weight="bold")
    s += txt(660, 142, "α_g = 0.1785", fs=FSS)
    s += txt(660, 162, "Su = 1.751", fs=FSS)
    s += txt(660, 182, "W = 0.3009 m/s", fs=FSS)
    s += txt(660, 202, "a = 2142 /m", fs=FSS)
    s += txt(660, 222, "K_L a = 2.785 /h", fs=FSS)
    s += txt(660, 258, "멱법칙 W ∝ Su^n,", fs=FSS)
    s += txt(660, 278, "n = 0.511 (잔차 0.28 %)", fs=FSS)
    s += txt(40, 596, "α_g 는 부력(운동량)과 계면적(전달)을 동시에 구동한다. 부력측을 고정하지 않으면 캘리브레이션에서 식별이 무너진다.", fs=FSS)
    return s + foot()


# ────────────────────────────────────────────────────────────── 도 11
def fig11():
    W, H = 900, 900
    s = head(W, H, "【도 11】")
    steps = [
        ("S10", ["수조 촬영 — 영상 1장 취득"], 42),
        ("S20", ["영상에서 기하·위상 인식", "(해석좌표계 정규화 좌표)"], 60),
        ("S30", ["물리모델 경계조건 데이터 생성", "(정량 계수는 배제)"], 60),
        ("S40", ["수온·탁도 계측 및 항목별 판정"], 42),
        ("S50", ["수온 → 온도종속 계수 확정", "탁도 → 유기물 부하 소스 진폭 확정"], 60),
        ("S60", ["제1계층 대리모델 → 시간평균 유동장 Ū, ν_t"], 42),
        ("S70", ["제2계층 : DO·CO₂·TAN·NO₂⁻·NO₃⁻·DIC·Alk·C_p", "복수 스칼라 병렬 선형 풀이"], 60),
        ("S80", ["셀별 산-염기 평형 → pH", "pH·T → 비이온 암모니아 독성분율"], 60),
        ("S90", ["보정계수 κ·잔차 적용·전파", "→ 항목별 위험 확률맵"], 60),
        ("S100", ["항목별 위험구역 결합·어긋남 표시", "통합 위험 판정 및 배치 처방 출력"], 60),
    ]
    y = 80
    ytop = {}
    for tag, lines, h in steps:
        ytop[tag] = y
        s += box(150, y, 470, h, lines, fs=FSS)
        s += txt(140, y + h / 2 + 4, tag, fs=FSN, anchor="end", weight="bold")
        y += h
        if tag != "S100":
            s += arr(385, y, 385, y + 28)
            y += 28
    # 되먹임 (처방 후보 재평가) : S100 → S60 재호출
    y100 = ytop["S100"] + 30
    y60 = ytop["S60"] + 21
    s += poly([(620, y100), (700, y100), (700, y60), (620, y60)], dash="5 3")
    s += txt(706, y60 + 60, "처방 후보마다", fs=FSS)
    s += txt(706, y60 + 78, "제1계층 재호출", fs=FSS)
    s += txt(706, y60 + 96, "→ 예상 개선량", fs=FSS)
    s += txt(706, y60 + 114, "비교 (S110)", fs=FSS)
    return s + foot()


save("도01.svg", fig1())
save("도02.svg", fig2())
save("도03.svg", fig3())
save("도04.svg", fig4())
save("도05.svg", fig5())
save("도06.svg", fig6())
save("도07.svg", fig7())
save("도08.svg", fig8())
save("도09.svg", fig9())
save("도10.svg", fig10())
save("도11.svg", fig11())
print("done")
