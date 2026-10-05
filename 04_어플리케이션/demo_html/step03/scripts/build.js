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

/*  물리엔진(SW팀). index.html 이 <script src> 로 참조하므로 www/ 에 함께 있어야 한다.
 *  rom_model.js 가 없으면 do_engine.js 가 근사식으로 자동 폴백하므로 빌드는 계속한다
 *  (단, 그 경우 산소 분포 지도는 나오지 않으므로 경고를 남긴다).  */
const ASSETS = [
  { file: 'do_engine.js', required: true,  note: '용존산소 물리엔진' },
  { file: 'rom_model.js', required: false, note: 'A층 ROM 계수 — 없으면 분포 지도 비활성' }
];

for (const a of ASSETS) {
  const src = path.join(ROOT, a.file);
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, path.join(OUT, a.file));
    const kb = Math.round(fs.statSync(src).size / 1024);
    console.log(`[build] ${a.file} → www/ 복사 완료 (${kb} KB)`);
  } else if (a.required) {
    console.error(`[build] 필수 파일 없음: ${a.file} (${a.note})`);
    process.exit(1);
  } else {
    console.warn(`[build] 경고: ${a.file} 없음 — ${a.note}`);
  }
}
