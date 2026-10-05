/* ---------------------------------------------------------------------------
 *  AndroidManifest.xml 에 BLE 권한을 자동 주입한다.
 *
 *  왜 스크립트로 만들었나:
 *  `npx cap add android` 는 매니페스트를 새로 생성하기 때문에, 손으로 넣은 권한이
 *  android 폴더를 지우고 다시 만들 때마다 날아간다. 그런데 이 권한이 없으면
 *  BLE 스캔이 "에러 없이 빈 목록"을 돌려준다 — 원인을 찾기가 매우 어려운 실패 방식이다.
 *  그래서 sync 할 때마다 자동으로 확인·주입되게 해 둔다. (이미 있으면 건너뜀)
 *
 *  실행:  npm run patch      (npm run sync 에 이미 포함되어 있음)
 * ------------------------------------------------------------------------ */
const fs = require('fs');
const path = require('path');

const MANIFEST = path.resolve(
  __dirname, '..', 'android', 'app', 'src', 'main', 'AndroidManifest.xml'
);

if (!fs.existsSync(MANIFEST)) {
  console.log('[patch] android 폴더가 아직 없습니다. `npx cap add android` 를 먼저 실행하세요.');
  process.exit(0);
}

let xml = fs.readFileSync(MANIFEST, 'utf8');

if (xml.includes('android.permission.BLUETOOTH_SCAN')) {
  console.log('[patch] BLE 권한이 이미 들어 있습니다. 건너뜁니다.');
  process.exit(0);
}

/* 안드로이드 12(API 31) 에서 블루투스 권한 체계가 완전히 바뀌었다.
 *  - 12 이상: BLUETOOTH_SCAN / BLUETOOTH_CONNECT (런타임 요청 필요)
 *  - 11 이하: BLUETOOTH / BLUETOOTH_ADMIN + 위치 권한(ACCESS_FINE_LOCATION)
 * 양쪽을 모두 선언하고 maxSdkVersion 으로 구분해야 전 버전에서 동작한다.
 *
 * neverForLocation 은 "위치 추정에 쓰지 않는다"는 선언이다. 이게 없으면
 * 안드로이드 12+ 에서 위치 권한까지 요구받게 된다. */
const PERMISSIONS = `
    <!-- ===== BLE 권한 (scripts/patch-manifest.js 가 자동 주입) ===== -->
    <!-- 안드로이드 12(API 31) 이상 -->
    <uses-permission
        android:name="android.permission.BLUETOOTH_SCAN"
        android:usesPermissionFlags="neverForLocation" />
    <uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />

    <!-- 안드로이드 11(API 30) 이하 호환 -->
    <uses-permission android:name="android.permission.BLUETOOTH" android:maxSdkVersion="30" />
    <uses-permission android:name="android.permission.BLUETOOTH_ADMIN" android:maxSdkVersion="30" />
    <!-- 11 이하에서는 BLE 스캔에 위치 권한이 필수였다. 게다가 기기의 '위치 서비스'가
         꺼져 있으면 스캔 결과가 조용히 비어서 나온다 — 실기기 테스트 시 주의. -->
    <uses-permission
        android:name="android.permission.ACCESS_FINE_LOCATION"
        android:maxSdkVersion="30" />

    <uses-feature android:name="android.hardware.bluetooth_le" android:required="true" />
    <!-- ===== BLE 권한 끝 ===== -->
`;

// <manifest ...> 여는 태그 바로 뒤에 삽입한다
const opening = xml.match(/<manifest\b[^>]*>/);
if (!opening) {
  console.error('[patch] <manifest> 태그를 찾지 못했습니다. 수동으로 권한을 넣어주세요.');
  process.exit(1);
}

const at = opening.index + opening[0].length;
xml = xml.slice(0, at) + '\n' + PERMISSIONS + xml.slice(at);

fs.writeFileSync(MANIFEST, xml, 'utf8');
console.log('[patch] AndroidManifest.xml 에 BLE 권한을 주입했습니다.');
