# Staytuned 예약 자동화 시스템

```bash
python3 -m venv staytuned_venv && source staytuned_venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# .env 파일 수정 (네이버 계정, SMS API 등)

python main.py

open http://localhost:8000
```

## 핵심 기능

| 기능 | 설명 |
|------|------|
| 자동 예약 수집 | 시작 시 즉시 + N분마다 네이버 플레이스 크롤링 |
| 예약 확정 문자 | 예약 접수 즉시 WELCOME 문자 발송 |
| 입실 안내 문자 | 체크인 10분 전 CHECK_IN_GUIDE + FACILITY_INFO 발송 |
| 당일 예약 처리 | 체크인 시간 이후 예약 시 3개 문자 모두 즉시 발송 |
| 자동 재시도 | 발송 실패 시 최대 3회 재시도 |
| 웹 대시보드 | http://localhost:8000 에서 예약/SMS 관리 |

## SMS 발송 로직

```
┌─────────────────────────────────────────────────────────────┐
│ [사전 예약] 현재 시간 < 체크인 시간 (15:00)                 │
│                                                             │
│   WELCOME (예약확정)      → 즉시 발송                       │
│   CHECK_IN_GUIDE (입실안내) → 체크인 10분 전 (14:50)        │
│   FACILITY_INFO (시설안내)  → 체크인 9분 전 (14:51)         │
├─────────────────────────────────────────────────────────────┤
│ [당일 예약] 현재 시간 >= 체크인 시간 (15:00)                │
│                                                             │
│   WELCOME (예약확정)      → 즉시 발송                       │
│   CHECK_IN_GUIDE (입실안내) → 즉시 발송                     │
│   FACILITY_INFO (시설안내)  → 1분 후 발송                   │
└─────────────────────────────────────────────────────────────┘
```

## 프로젝트 구조

```
├── main.py                      # 앱 진입점
├── config/
│   ├── settings.py              # 환경변수 설정
│   ├── accommodation.yaml       # 숙소 정보, 호실 비밀번호
│   ├── sms_templates.yaml       # SMS 템플릿
│   └── crawling.yaml            # 크롤링 셀렉터
└── src/
    ├── models/                  # DB 모델
    ├── services/                # 스케줄러, 크롤러, SMS
    ├── utils/                   # 유틸리티
    └── web/                     # 대시보드
```

## 환경 변수 (.env)

```env
# 네이버 플레이스
NAVER_EMAIL=
NAVER_PASSWORD=
NAVER_PLACE_URL=

# SMS API (솔라피)
SMS_API_KEY=         # 솔라피 콘솔에서 발급받은 API Key
SMS_API_SECRET=      # 솔라피 콘솔에서 발급받은 API Secret
SMS_SENDER=          # 발신번호 (사전 등록 필요)

# 관리자
ADMIN_PHONE=

# 스케줄러
SCRAPE_INTERVAL_MINUTES=5
CHECK_IN_TIME=15:00

# 테스트 모드
USE_TEST_MODE=false
```

### 솔라피 설정 방법

1. [솔라피 콘솔](https://console.solapi.com) 회원가입 및 로그인
2. **API Key 발급**: 설정 > API Key > 새로운 API Key 생성
3. **발신번호 등록**: 설정 > 발신번호 > 발신번호 등록 (본인 인증 필요)
4. **충전**: 설정 > 충전 (SMS: 약 9원/건, LMS: 약 30원/건)
5. `.env` 파일에 API Key, API Secret, 발신번호 입력

## 테스트 모드

`.env`에서 `USE_TEST_MODE=true` 설정 시
- HTML 파일(`sample_booking_page.html`)로 오프라인 테스트
- SMS는 실제 발송 없이 로그만 출력 (API 호출 없음)

## 대시보드

- `/` - 메인 대시보드
- `/bookings` - 예약 목록
- `/sms` - SMS 로그

## 문제 해결

| 증상 | 확인 |
|------|------|
| 예약 미수집 | 네이버 로그인, URL 확인 |
| SMS 미발송 | API 키, 잔액, 발신번호 등록 확인 |

```bash
tail -f logs/app.log
```
