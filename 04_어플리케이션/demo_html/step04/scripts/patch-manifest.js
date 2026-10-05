/* ---------------------------------------------------------------------------
 *  AndroidManifest.xml 에 BLE + 알림 권한을 자동 주입한다.
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

/* 안드로이드 13(API 33) 부터 알림도 런타임 권한이다.
 * 이게 없으면 LocalNotifications 의 권한 요청창이 아예 뜨지 않고,
 * 알림도 에러 없이 조용히 무시된다 — BLE 권한과 똑같이 찾기 어려운 실패 방식이다. */
const NOTIFY_PERMISSIONS = `
    <!-- ===== 알림 권한 (scripts/patch-manifest.js 가 자동 주입) ===== -->
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <!-- ===== 알림 권한 끝 ===== -->
`;

/* 백그라운드 감시(포그라운드 서비스) 권한.
 * FOREGROUND_SERVICE_CONNECTED_DEVICE 가 빠지면 안드로이드 14 이상에서
 * startForeground() 가 SecurityException 을 던지며 앱이 그 자리에서 죽는다.
 * 빌드는 멀쩡히 되기 때문에 실기기에 올려보기 전까지 모른다. */
const WATCH_PERMISSIONS = `
    <!-- ===== 백그라운드 감시 (scripts/patch-manifest.js 가 자동 주입) ===== -->
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <!-- 안드로이드 14(API 34) 부터는 서비스 타입별 권한이 따로 필요하다. -->
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_CONNECTED_DEVICE" />
    <!-- 제조사 배터리 절약이 프로세스를 정리하는 것을 막기 위한 예외 요청 -->
    <uses-permission android:name="android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS" />
    <!-- ===== 백그라운드 감시 끝 ===== -->
`;

/* 홈 화면 위젯 등록.
 * 권한과 달리 <receiver> 는 <application> 안에 있어야 해서 삽입 위치가 다르다.
 * 이게 빠지면 위젯이 '위젯 추가' 목록에 아예 나타나지 않는데, 빌드는 멀쩡히 성공해서
 * 왜 안 보이는지 알기 어렵다. */
const WIDGET_RECEIVER = `
    <!-- ===== 백그라운드 감시 서비스 (scripts/patch-manifest.js 가 자동 주입) ===== -->
    <service
        android:name=".AquaWatchService"
        android:exported="false"
        android:foregroundServiceType="connectedDevice" />
    <!-- ===== 백그라운드 감시 서비스 끝 ===== -->

    <!-- ===== 홈 화면 위젯 (scripts/patch-manifest.js 가 자동 주입) ===== -->
    <receiver
        android:name=".AquaWidgetProvider"
        android:label="@string/aqua_widget_label"
        android:exported="false">
        <intent-filter>
            <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />
        </intent-filter>
        <meta-data
            android:name="android.appwidget.provider"
            android:resource="@xml/aqua_widget_info" />
    </receiver>
    <!-- ===== 홈 화면 위젯 끝 ===== -->
`;

// <manifest ...> 여는 태그 바로 뒤에 삽입한다
const opening = xml.match(/<manifest\b[^>]*>/);
if (!opening) {
  console.error('[patch] <manifest> 태그를 찾지 못했습니다. 수동으로 권한을 넣어주세요.');
  process.exit(1);
}

/* 권한 묶음마다 따로 검사한다.
 * 예전에는 BLE 권한 하나만 보고 통째로 건너뛰었는데, 그러면 이미 BLE 패치가 끝난
 * 기존 android/ 폴더에는 나중에 추가된 알림 권한이 영영 들어가지 않는다. */
const BLOCKS = [
  { name: 'BLE',  marker: 'android.permission.BLUETOOTH_SCAN',    xml: PERMISSIONS },
  { name: '알림', marker: 'android.permission.POST_NOTIFICATIONS', xml: NOTIFY_PERMISSIONS },
  { name: '백그라운드 감시', marker: 'FOREGROUND_SERVICE_CONNECTED_DEVICE', xml: WATCH_PERMISSIONS }
];

const added = [];
for (const block of BLOCKS) {
  if (xml.includes(block.marker)) continue;
  const at = xml.match(/<manifest\b[^>]*>/);   // 앞선 삽입으로 위치가 밀리므로 매번 다시 찾는다
  const idx = at.index + at[0].length;
  xml = xml.slice(0, idx) + '\n' + block.xml + xml.slice(idx);
  added.push(block.name);
}

/* <service> 와 <receiver> 는 권한과 달리 <application> 안에 있어야 한다.
 * 둘을 한 덩어리로 넣으므로 마커도 하나로 본다. */
if (!xml.includes('.AquaWidgetProvider')) {
  const close = xml.lastIndexOf('</application>');
  if (close < 0) {
    console.warn('[patch] ⚠ <application> 태그를 못 찾아 서비스·위젯을 넣지 못했습니다.');
  } else {
    xml = xml.slice(0, close) + WIDGET_RECEIVER + xml.slice(close);
    added.push('감시 서비스 · 홈 위젯');
  }
}

if (added.length === 0) {
  console.log('[patch] 권한·감시 서비스·홈 위젯이 이미 모두 들어 있습니다. 건너뜁니다.');
  process.exit(0);
}

fs.writeFileSync(MANIFEST, xml, 'utf8');
console.log(`[patch] AndroidManifest.xml 에 ${added.join(' · ')} 을(를) 주입했습니다.`);
