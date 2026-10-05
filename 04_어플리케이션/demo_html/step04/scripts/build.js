/* ---------------------------------------------------------------------------
 *  www/ 빌드 스크립트
 *
 *  app_demo.html 을 www/index.html 로 복사한다.
 *  이렇게 해두는 이유: app_demo.html 하나만 수정하면 되고, 브라우저에서 바로 열어
 *  테스트하던 그 파일이 그대로 APK 에 들어간다. 두 벌로 나뉘어 서로 어긋나는 일이 없다.
 *
 *  실행:  npm run build
 * ------------------------------------------------------------------------ */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SRC  = path.join(ROOT, 'app_demo.html');
const OUT  = path.join(ROOT, 'www');

if (!fs.existsSync(SRC)) {
  console.error(`[build] app_demo.html 을 찾을 수 없습니다: ${SRC}`);
  process.exit(1);
}

fs.mkdirSync(OUT, { recursive: true });
fs.copyFileSync(SRC, path.join(OUT, 'index.html'));

console.log('[build] app_demo.html → www/index.html 복사 완료');

/* vendor/ 안에는 Tailwind 가 들어 있다. 이게 빠지면 APK 안에서 스타일이 통째로
 * 사라지는데, 화면이 하얗게 뜨는 것 말고는 아무 에러도 안 나서 원인을 찾기 어렵다.
 * 그래서 없으면 조용히 넘어가지 않고 눈에 띄게 경고한다. */
const VENDOR_SRC = path.join(ROOT, 'vendor');
const VENDOR_OUT = path.join(OUT, 'vendor');

if (fs.existsSync(VENDOR_SRC)) {
  fs.cpSync(VENDOR_SRC, VENDOR_OUT, { recursive: true });
  console.log('[build] vendor/ → www/vendor/ 복사 완료');
} else {
  console.warn('[build] ⚠ vendor/ 가 없습니다. `npm run vendor` 를 먼저 실행하세요.');
  console.warn('[build] ⚠ 이대로 두면 인터넷이 없을 때 앱 스타일이 전부 사라집니다.');
}

/* assets/ 에는 물고기 그림이 들어 있다.
 * 빠져도 앱은 이모지로 되돌아가 동작하지만, 화면이 초라해지므로 몇 개인지 세어 알려준다. */
const ASSETS_SRC = path.join(ROOT, 'assets');
const ASSETS_OUT = path.join(OUT, 'assets');

if (fs.existsSync(ASSETS_SRC)) {
  fs.cpSync(ASSETS_SRC, ASSETS_OUT, { recursive: true });

  const fishDir = path.join(ASSETS_SRC, 'fish');
  const n = fs.existsSync(fishDir)
    ? fs.readdirSync(fishDir).filter(f => f.toLowerCase().endsWith('.png')).length
    : 0;

  console.log(`[build] assets/ → www/assets/ 복사 완료 (물고기 그림 ${n}개)`);
  if (n < 6) {
    console.warn('[build] ⚠ assets/fish/ 에 PNG 가 6개보다 적습니다. 빠진 종은 이모지로 표시됩니다.');
  }
} else {
  console.warn('[build] ⚠ assets/ 가 없습니다. 물고기 그림이 전부 이모지로 표시됩니다.');
}

/*  물리엔진(SW팀). index.html 이 <script src> 로 참조하므로 www/ 에 함께 있어야 한다.
 *  rom_model.js 가 없으면 do_engine.js 가 근사식으로 자동 폴백하므로 빌드는 계속한다
 *  (단, 그 경우 산소 분포 지도는 나오지 않으므로 경고를 남긴다).  */
const ENGINE_ASSETS = [
  { file: 'do_engine.js', required: true,  note: '용존산소 물리엔진' },
  { file: 'rom_model.js', required: false, note: 'A층 ROM 계수 — 없으면 분포 지도 비활성' }
];

for (const a of ENGINE_ASSETS) {
  const src = path.join(ROOT, a.file);
  const dst = path.join(OUT, a.file);
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, dst);
    const kb = Math.round(fs.statSync(src).size / 1024);
    console.log(`[build] ${a.file} → www/ 복사 완료 (${kb} KB)`);
  } else if (fs.existsSync(dst)) {
    // 루트에 원본이 없어도 www/ 안에 이미 있으면 그대로 둔다 (덮어쓰지 않음)
    console.log(`[build] ${a.file} 은 www/ 에 이미 있습니다 — 유지`);
  } else if (a.required) {
    console.error(`[build] 필수 파일 없음: ${a.file} (${a.note})`);
    process.exit(1);
  } else {
    console.warn(`[build] ⚠ ${a.file} 없음 — ${a.note}`);
  }
}
