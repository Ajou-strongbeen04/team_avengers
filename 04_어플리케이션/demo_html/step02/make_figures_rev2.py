# -*- coding: utf-8 -*-
"""발표용 그림 rev.2 — 기계팀 검토(2026-08-01) 지적사항 반영

정정 내용
  2.1/2.3 : K_La 3.618 /h, chi = 1/(V·K_La) 로 절대값 전면 재계산
  2.2     : 결핍량과 절대 DO 임계를 같은 축에 놓던 오류 → 패널 분리
  2.4     : skill 프로토콜 명기
  2.5     : 소비 시간척도 24.2h(7 mg/h 기준) → 9.5h(18 mg/h 기준), 배율 6800→2673
"""
import json, re, math, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker
from matplotlib import font_manager

for cand in ['Malgun Gothic', 'Gulim', 'Batang']:
    if any(cand.lower() in f.name.lower() for f in font_manager.fontManager.ttflist):
        matplotlib.rcParams['font.family'] = cand
        break
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['figure.dpi'] = 110

OUT = os.path.dirname(os.path.abspath(__file__))
M = json.loads(re.search(r'const ROM_MODEL = (\{.*\});\s*$',
                         open(os.path.join(OUT, 'rom_model.js'), encoding='utf8').read(), re.S).group(1))

V, KLA = 20.7, 3.618
VK = V * KLA
FISH = 18.0          # 금붕어 3마리 [mg/h]
CRIT = 6.0           # C_crit (C7)


def csat(T):
    Ta = T + 273.15
    return math.exp(-139.34411 + 1.575701e5 / Ta - 6.642308e7 / Ta ** 2
                    + 1.243800e10 / Ta ** 3 - 8.621949e11 / Ta ** 4)


CS = csat(25)
DO_NOW = CS - FISH / VK
HEADROOM = DO_NOW - CRIT

ym = np.array(M['u_fish']['y_mean'])
CHI_SPAN = ym.max() - ym.min()
SPATIAL = CHI_SPAN * FISH
CASE_SPAN = 0.00025 * 0.082308 * FISH          # 케이스간 chi 차이 (rev2 배율)
ROM_GAIN = (4.875e-05 - 2.914e-05) * 0.082308 * FISH


def logticks(ax, axis, ticks, labels):
    if axis == 'x':
        ax.set_xticks(ticks); ax.set_xticklabels(labels)
        ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    else:
        ax.set_yticks(ticks); ax.set_yticklabels(labels)
        ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())


# ============ 그림 1: 절대 DO(좌) / 편차 규모(우) — 축 분리 ============
fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))

a = axes[0]
names = ['포화 C*(25°C)', '현재 DO\n(금붕어 3마리)', '위험 임계\nC_crit']
vals = [CS, DO_NOW, CRIT]
cols = ['#93c5fd', '#2563eb', '#dc2626']
bars = a.bar(names, vals, color=cols, width=0.55)
for b, v in zip(bars, vals):
    a.text(b.get_x() + b.get_width() / 2, v + 0.15, '%.2f' % v, ha='center', fontsize=11, fontweight='bold')
a.annotate('', xy=(1, DO_NOW), xytext=(1, CRIT),
           arrowprops=dict(arrowstyle='<->', color='#065A82', lw=1.6))
a.text(1.13, (DO_NOW + CRIT) / 2, '여유\n%.2f mg/L' % HEADROOM, fontsize=10,
       color='#065A82', fontweight='bold', va='center')
a.set_ylabel('용존산소 [mg/L]')
a.set_ylim(0, 9.6)
a.set_title('① 절대 농도 — 위험까지 %.2f mg/L 여유' % HEADROOM, fontsize=11)
a.grid(axis='y', alpha=0.3)

b_ = axes[1]
items = [('위험까지의 여유', HEADROOM, '#dc2626'),
         ('어항 내 위치별 차이', SPATIAL, '#f59e0b'),
         ('장애물 배치에 따른 차이', CASE_SPAN, '#10b981'),
         ('ROM이 개선한 양', ROM_GAIN, '#8b5cf6')]
ypos = list(range(len(items)))[::-1]
bars = b_.barh(ypos, [i[1] for i in items], color=[i[2] for i in items], height=0.58)
b_.set_xscale('log')
b_.set_yticks(ypos); b_.set_yticklabels([i[0] for i in items], fontsize=9.5)
for v, bb in zip([i[1] for i in items], bars):
    b_.text(v * 1.3, bb.get_y() + bb.get_height() / 2, '%.4g' % v, va='center', fontsize=9.5)
b_.set_xlabel('DO 차이 [mg/L] — 로그 스케일')
b_.set_xlim(1e-5, 30)
logticks(b_, 'x', [1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1, 10],
         ['0.00001', '0.0001', '0.001', '0.01', '0.1', '1', '10'])
b_.grid(axis='x', alpha=0.3)
b_.set_title('② 차이의 규모 — 공간 효과는 여유의 0.07 % 이하', fontsize=11)

fig.suptitle('스케일 비교 (25°C · 금붕어 3마리 18 mg/h · 폭기 보통 K$_L$a 3.618/h)', fontsize=12)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'fig1_scale.png'), bbox_inches='tight')
plt.close()
print('fig1_scale.png   여유 %.3f / 위치별 %.5f / 장애물 %.6f / ROM %.7f' % (HEADROOM, SPATIAL, CASE_SPAN, ROM_GAIN))

# ============ 그림 2: 시간척도 (기준 통일) ============
T_ADV, T_DIFF = 12.8, 3060.0
T_CONS = CS * V / FISH * 3600
fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
ts = [('폭기 순환\n(이류)', T_ADV, '#2563eb'),
      ('난류 확산', T_DIFF, '#f59e0b'),
      ('산소 전량 소비\n(18 mg/h)', T_CONS, '#dc2626')]
tpos = list(range(3))[::-1]
axes[0].barh(tpos, [t[1] for t in ts], color=[t[2] for t in ts], height=0.55)
axes[0].set_xscale('log')
axes[0].set_yticks(tpos); axes[0].set_yticklabels([t[0] for t in ts], fontsize=9)
axes[0].set_xlabel('시간 [초] — 로그 스케일')
axes[0].set_title('섞이는 속도 vs 소비 속도 (이류가 %,d배 빠름)'.replace(',', '') % round(T_CONS / T_ADV), fontsize=10)
for i, t in enumerate(ts):
    lbl = ('%.0f초' % t[1]) if t[1] < 3600 else ('%.1f시간' % (t[1] / 3600))
    axes[0].text(t[1] * 1.3, tpos[i], lbl, va='center', fontsize=9)
axes[0].set_xlim(5, 3e5)
logticks(axes[0], 'x', [10, 100, 1000, 1e4, 1e5], ['10', '100', '1,000', '1만', '10만'])
axes[0].grid(axis='x', alpha=0.3)

bar_vals = [0.00135 * FISH / 18 * s for s in (0.964, 0.979, 1.0)]   # 0/1/2개 상대비 (rev1 실측)
bar_vals = [SPATIAL * r for r in (0.964, 0.979, 1.0)]
axes[1].bar(['장애물\n0개', '장애물\n1개', '장애물\n2개'], bar_vals,
            color=['#94a3b8', '#60a5fa', '#2563eb'], width=0.55)
axes[1].set_ylabel('공간 편차 [mg/L]')
axes[1].set_title('장애물이 늘어도 공간 편차는 거의 그대로', fontsize=10)
for i, v in enumerate(bar_vals):
    axes[1].text(i, v * 1.08, '%.5f' % v, ha='center', fontsize=9)
axes[1].axhline(HEADROOM, color='#dc2626', ls='--', lw=1.2)
axes[1].text(-0.45, HEADROOM * 1.35, '위험까지 여유 %.2f mg/L' % HEADROOM, color='#dc2626', fontsize=8)
axes[1].set_yscale('log')
axes[1].set_ylim(1e-4, 20)
logticks(axes[1], 'y', [1e-4, 1e-3, 1e-2, 1e-1, 1, 10], ['0.0001', '0.001', '0.01', '0.1', '1', '10'])
axes[1].grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'fig2_timescale.png'), bbox_inches='tight')
plt.close()
print('fig2_timescale.png  소비 %.2f h, 배율 %d' % (T_CONS / 3600, round(T_CONS / T_ADV)))

# ============ 그림 3: ROM skill (프로토콜 명기) ============
fig, ax = plt.subplots(figsize=(9, 4.0))
sk = [('u_fish\n(균일소비)', M['skill']['u_fish'], '#2563eb'),
      ('u_sod\n(바닥집중)', M['skill']['u_sod'], '#f59e0b')]
bars = ax.bar([s[0] for s in sk], [s[1] for s in sk], color=[s[2] for s in sk], width=0.42)
for b, s in zip(bars, sk):
    ax.text(b.get_x() + b.get_width() / 2, s[1] + 0.015, '%.3f' % s[1], ha='center', fontsize=12, fontweight='bold')
ax.axhline(0.1, color='gray', ls=':', lw=1)
ax.text(1.55, 0.115, '유의미 기준 0.1', ha='right', color='gray', fontsize=9)
ax.set_ylabel('skill  (1 = 완벽, 0 = 평균장과 동일)')
ax.set_ylim(0, 0.78)
ax.set_title('ROM은 장애물 배치를 실제로 학습했다', fontsize=12)
ax.grid(axis='y', alpha=0.3)
ax.text(0.5, -0.30,
        '프로토콜: 5-fold CV (shuffle, seed=0) · 입력 obs_mask 8×8×12 점유율 768D · 출력 PCA 6성분 + RidgeCV\n'
        '타깃: DO 응답장 χ (단위소비당 결핍).  ※ 05_ROM_Stage2A 의 "RF 채택"은 유동장 POD 계수 타깃으로 별개 실험',
        transform=ax.transAxes, ha='center', fontsize=8.5, color='#5B6B76')
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'fig3_rom.png'), bbox_inches='tight')
plt.close()
print('fig3_rom.png  skill %.3f / %.3f' % (M['skill']['u_fish'], M['skill']['u_sod']))

# ============ 그림 4: 배포 ROM이 예측한 DO 분포 (물리단위) ============
g = M['grid']
nz, ny, nx = g['nz'], g['ny'], g['nx']
T = M['tank']


def predict(key, occ):
    m = M[key]
    z = np.array(m['intercept'], float) + np.array(m['coef'], float) @ occ
    return np.array(m['y_mean'], float) + z @ np.array(m['components'], float)


# 대표 배치: 바위(L) 1개 + 수초(M) 1개
occ = np.zeros(nz * ny * nx)


def stamp(cx, cy, cz, sw, sd, sh, cyl):
    dx, dy, dz = 100 / nx, 100 / ny, 100 / nz
    for k in range(nz):
        zlo, zhi = k * dz, (k + 1) * dz
        fz = max(0, min(cz + sh / 2, zhi) - max(cz - sh / 2, zlo)) / dz
        if fz <= 0: continue
        for j in range(ny):
            for i in range(nx):
                if cyl:
                    hit = sum(1 for a in range(4) for b in range(4)
                              if ((((i + (b + .5) / 4) * dx - cx) / (sw / 2)) ** 2 +
                                  (((j + (a + .5) / 4) * dy - cy) / (sd / 2)) ** 2) <= 1) / 16
                else:
                    fx = max(0, min(cx + sw / 2, (i + 1) * dx) - max(cx - sw / 2, i * dx)) / dx
                    fy = max(0, min(cy + sd / 2, (j + 1) * dy) - max(cy - sd / 2, j * dy)) / dy
                    hit = fx * fy
                if hit > 0:
                    occ[(k * ny + j) * nx + i] = min(1, occ[(k * ny + j) * nx + i] + hit * fz)


stamp(30, 50, 24, 11 / 47 * 100, 11 / 21 * 100, 10 / 21 * 100, False)   # rock L
stamp(65, 30, 38, 10 / 47 * 100, 10 / 21 * 100, 16 / 21 * 100, True)    # plant M

field = (CS - predict('u_fish', occ) * FISH).reshape(nz, ny, nx)
x = (np.arange(nx) + .5) / nx * T['lx'] * 100
y = (np.arange(ny) + .5) / ny * T['ly'] * 100
z = (np.arange(nz) + .5) / nz * T['lz'] * 100

fig, axes = plt.subplots(1, 3, figsize=(15, 3.6))
vmin, vmax = field.min(), field.max()
for ax, (k, ttl) in zip(axes[:2], [(0, '바닥층'), (nz // 2, '중간 높이')]):
    im = ax.pcolormesh(x, y, field[k], cmap='YlOrRd_r', vmin=vmin, vmax=vmax, shading='auto')
    ax.plot(M['plume']['x'] * 100, M['plume']['y'] * 100, 'b*', ms=16, label='폭기')
    ax.set_title('%s (z=%.1fcm)' % (ttl, z[k]), fontsize=10)
    ax.set_xlabel('x [cm]'); ax.set_ylabel('y [cm]'); ax.legend(fontsize=7)
    plt.colorbar(im, ax=ax, label='DO [mg/L]')
jy = int(M['plume']['y'] / T['ly'] * ny)
im = axes[2].pcolormesh(x, z, field[:, jy, :], cmap='YlOrRd_r', vmin=vmin, vmax=vmax, shading='auto')
axes[2].set_title('수직 단면 (y=%.1fcm, 폭기 통과)' % y[jy], fontsize=10)
axes[2].set_xlabel('x [cm]'); axes[2].set_ylabel('z [cm] (위=수면)')
plt.colorbar(im, ax=axes[2], label='DO [mg/L]')
fig.suptitle('배포 ROM 예측 DO 분포 (25°C · 금붕어 3마리) — 전체 %.3f~%.3f mg/L, 임계 6.0 대비 충분'
             % (vmin, vmax), fontsize=11)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'fig4_field.png'), bbox_inches='tight')
plt.close()
print('fig4_field.png  DO %.4f ~ %.4f mg/L' % (vmin, vmax))
print('완료')
