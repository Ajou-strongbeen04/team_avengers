/* ---------------------------------------------------------------------------
 *  Tailwind CSS 를 로컬로 내려받아 vendor/tailwind.js 에 저장한다.
 *
 *  왜 필요한가:
 *  app_demo.html 은 원래 <script src="https://cdn.tailwindcss.com"> 을 썼다.
 *  이건 APK 안에 스타일이 들어 있는 게 아니라, 앱을 켤 때마다 인터넷에서 받아오는 구조다.
 *  발표장 와이파이가 안 되거나 느리면 화면 전체가 스타일 없이 흰 배경에 검은 글씨로 뜬다.
 *  기능 하나가 죽는 게 아니라 UI 가 통째로 날아가는 실패라, 미리 받아서 APK 에 넣는다.
 *
 *  실행:  npm run vendor      (npm run sync 에 이미 포함되어 있음)
 *  이미 받아둔 파일이 있으면 다시 받지 않는다. 강제로 다시 받으려면 vendor/ 를 지우면 된다.
 * ------------------------------------------------------------------------ */
const fs    = require('fs');
const path  = require('path');
const https = require('https');

/* 버전을 고정하는 이유:
 * 버전 없는 주소는 항상 '최신'을 준다. 어느 날 메이저 버전이 올라가면 클래스 동작이
 * 조용히 달라지는데, 발표 전날 그런 일이 나면 원인을 찾기가 아주 어렵다.
 *
 * ★ 3.4.17 은 Play CDN 이 제공하는 마지막 3.x 다.
 *   npm 에는 3.4.19 까지 있지만 Play CDN 에는 올라가 있지 않다. 둘은 목록이 다르다.
 *   없는 버전을 요청하면 404 가 아니라 200 과 함께 console.error(...) 한 줄짜리
 *   자바스크립트가 돌아온다 — 그래서 상태코드만 봐서는 실패를 알 수 없고,
 *   아래 checkLooksLikeTailwind() 로 내용을 직접 검사한다. */
const PINNED_URL   = 'https://cdn.tailwindcss.com/3.4.17';
const FALLBACK_URL = 'https://cdn.tailwindcss.com';

const OUT_DIR  = path.resolve(__dirname, '..', 'vendor');
const OUT_FILE = path.join(OUT_DIR, 'tailwind.js');

const MIN_BYTES = 100 * 1024;   // 정상 파일은 300KB 이상이다. 이보다 작으면 뭔가 잘못 받은 것

if (fs.existsSync(OUT_FILE) && fs.statSync(OUT_FILE).size > MIN_BYTES) {
  console.log('[vendor] vendor/tailwind.js 가 이미 있습니다. 건너뜁니다.');
  process.exit(0);
}

function download(url, redirectsLeft = 5) {
  return new Promise((resolve, reject) => {
    https.get(url, res => {
      // CDN 이 실제 파일 위치로 넘기는 경우가 있어 리다이렉트를 따라간다
      if ([301, 302, 307, 308].includes(res.statusCode) && res.headers.location && redirectsLeft > 0) {
        res.resume();
        return resolve(download(new URL(res.headers.location, url).toString(), redirectsLeft - 1));
      }
      if (res.statusCode !== 200) {
        res.resume();
        return reject(new Error(`HTTP ${res.statusCode}`));
      }
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => resolve(Buffer.concat(chunks)));
    }).on('error', reject);
  });
}

/* 받아온 게 진짜 Tailwind 인지 확인한다. 상태코드 200 만으로는 부족한 경우가 둘 있다.
 *  1) 없는 버전을 요청 → 200 + 에러 메시지 한 줄 (수백 바이트)
 *  2) 학교·카페 와이파이의 로그인 페이지 → 200 + HTML
 * 둘 다 파일은 멀쩡히 생기는데 스타일만 전부 사라지는, 원인 찾기 어려운 실패를 만든다. */
async function fetchValid(url) {
  const buf  = await download(url);
  const head = buf.slice(0, 400).toString('utf8').trim();

  if (buf.length < MIN_BYTES || head.startsWith('<')) {
    const err = new Error(`Tailwind 가 아닌 내용 (${buf.length} 바이트)`);
    err.snippet = head.replace(/\s+/g, ' ').slice(0, 180);
    throw err;
  }
  return buf;
}

function report(prefix, e) {
  console.log(`${prefix} ${e.message}`);
  if (e.snippet) console.log(`[vendor] 서버 응답: ${e.snippet}`);
}

(async () => {
  let buf;

  try {
    buf = await fetchValid(PINNED_URL);
  } catch (e) {
    report('[vendor] 고정 버전 실패 —', e);
    console.log('[vendor] 버전 없는 최신 주소로 다시 시도합니다...');
    try {
      buf = await fetchValid(FALLBACK_URL);
    } catch (e2) {
      report('[vendor] 최신 버전도 실패 —', e2);
      console.error('[vendor] 내려받지 못했습니다.');
      console.error('[vendor] 인터넷 연결(로그인이 필요한 와이파이인지)을 확인하고 다시 실행하세요:  npm run vendor');
      console.error('[vendor] 급하면 이 단계를 건너뛰어도 앱은 CDN 으로 동작합니다 (오프라인만 불가):  npm run build');
      process.exit(1);
    }
  }

  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(OUT_FILE, buf);
  console.log(`[vendor] vendor/tailwind.js 저장 완료 (${Math.round(buf.length / 1024)} KB)`);
})();
