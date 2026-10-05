# 안드로이드 APK 빌드 가이드

`app_demo.html` 을 Capacitor 로 감싸 안드로이드 앱으로 만드는 절차입니다.
화면 코드는 그대로 재사용하고, BLE 만 네이티브 플러그인이 처리합니다.

---

## 0. 미리 설치할 것

| 항목 | 비고 |
|---|---|
| **Node.js 18 이상** | `node -v` 로 확인 |
| **Android Studio** | SDK Platform 34 이상 + Android SDK Platform-Tools 포함 설치 |
| **JDK 17** | 최근 Android Studio 에 번들되어 있음. 따로 없어도 대개 통과 |

Android Studio 를 처음 설치하면 SDK 다운로드에 시간이 꽤 걸립니다. 미리 받아두세요.

---

## 1. 의존성 설치

프로젝트 폴더(이 파일이 있는 곳)에서:

```bash
npm install @capacitor/core @capacitor/cli @capacitor/android
npm install @capacitor-community/bluetooth-le
```

> 버전을 고정하지 않은 이유: Capacitor 메이저 버전과 BLE 플러그인 버전이 서로 맞아야 하는데,
> `@latest` 로 받으면 npm 이 알아서 호환되는 조합을 잡아줍니다.
> 만약 `peer dependency` 경고가 뜨면 두 패키지의 메이저 버전이 같은지 확인하세요.

---

## 2. 안드로이드 플랫폼 추가

```bash
npm run build          # app_demo.html → www/index.html
npx cap add android    # android/ 폴더 생성 (최초 1회)
npm run sync           # www 반영 + BLE 권한 자동 주입
```

`npm run sync` 는 세 가지를 한 번에 합니다.

1. `app_demo.html` → `www/index.html` 복사
2. `npx cap sync android` — 웹 자산과 플러그인을 네이티브 프로젝트에 반영
3. `scripts/patch-manifest.js` — **AndroidManifest.xml 에 BLE 권한 주입**

3번이 핵심입니다. 이 권한이 없으면 BLE 스캔이 **에러 없이 빈 목록**을 돌려주는데,
원인을 찾기가 아주 어렵습니다. `android/` 폴더를 지우고 다시 만들어도 자동으로 다시 들어갑니다.

---

## 3. 빌드 & 설치

```bash
npm run open           # Android Studio 실행
```

Android Studio 가 열리면:

1. 폰을 USB 로 연결 (폰에서 **개발자 옵션 → USB 디버깅** 켜야 함)
2. 상단 기기 목록에서 폰 선택
3. ▶ Run 버튼

APK 파일만 필요하면 Android Studio 메뉴에서
**Build → Build Bundle(s) / APK(s) → Build APK(s)** 를 누르세요.
결과물은 `android/app/build/outputs/apk/debug/app-debug.apk` 에 생깁니다.

---

## 4. 코드 수정 후 재빌드

`app_demo.html` 만 고치면 됩니다.

```bash
npm run sync
```

그다음 Android Studio 에서 ▶ Run. `www/` 와 `android/` 는 자동 생성물이라
직접 수정하지 마세요 — 다음 sync 때 덮어써집니다.

---

## 실기기 테스트 체크리스트

BLE 가 안 될 때 열에 아홉은 아래 중 하나입니다.

- [ ] **폰 블루투스가 켜져 있는가**
- [ ] **ESP32 전원이 들어와 있고 광고 중인가** — 시리얼에 `[BLE] 광고 시작` 이 떠야 함
- [ ] **권한 팝업에서 '허용' 을 눌렀는가** — 실수로 거부했다면 앱 정보 → 권한에서 다시 허용
- [ ] **안드로이드 11 이하라면 위치 서비스(GPS)가 켜져 있는가** — 꺼져 있으면 스캔 결과가 조용히 빈 채로 나옴
- [ ] **다른 앱(nRF Connect 등)이 이미 ESP32 에 연결되어 있지 않은가** — BLE 는 동시 연결이 제한됨

앱을 의심하기 전에 **nRF Connect 앱으로 먼저 연결해 보세요.** 거기서도 안 보이면 하드웨어/펌웨어 문제입니다.

---

## 배포 전 반드시 처리할 것

### API 키 노출

`app_demo.html` 안에 Gemini API 키가 평문으로 들어 있습니다.
**APK 는 누구나 압축을 풀어 내용을 볼 수 있습니다.** 남이 이 키로 API 를 쓰면 요금이 청구됩니다.

- 발표·시연까지는 그대로 둬도 되지만, 최소한 Google Cloud 콘솔에서
  **Android 앱 제한**(패키지명 `com.eobengers.aquasense` + 서명 SHA-1)을 걸어두세요.
- 실제 배포한다면 Gemini 호출을 서버(또는 Firebase Functions)로 옮기고,
  앱은 그 서버만 호출하게 바꿔야 합니다.
- 이 파일이 이미 공개 저장소에 올라가 있다면 **키를 폐기하고 재발급**하세요.

### 릴리스 서명

Play 스토어에 올리려면 릴리스 키스토어로 서명해야 합니다. 교내 발표·시연 목적이면
디버그 APK 를 그대로 설치해도 됩니다(설치 시 "출처를 알 수 없는 앱" 허용 필요).

---

## 폴더 구조

```
ai_integrated_capston_design/
├─ app_demo.html            ← 앱 화면 원본. 여기만 수정하면 됨
├─ capacitor.config.json    ← 앱 ID / 이름 / webDir 설정
├─ package.json             ← 빌드 스크립트
├─ BUILD.md                 ← 이 문서
├─ scripts/
│  ├─ build.js              ← app_demo.html → www/index.html
│  └─ patch-manifest.js     ← BLE 권한 자동 주입
├─ firmware/
│  └─ aqua_sense_esp32/     ← ESP32 아두이노 스케치
│     ├─ aqua_sense_esp32.ino
│     └─ aqua_sense_types.h
├─ www/                     ← 자동 생성 (수정 금지)
└─ android/                 ← 자동 생성 (수정 금지)
```
