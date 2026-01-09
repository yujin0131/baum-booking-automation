# 서버 배포 파일 목록

## 📦 필수 파일/폴더

### 1. 애플리케이션 코드
```
src/                          # 전체 소스 코드
├── models/
│   ├── __init__.py
│   ├── database.py
│   └── booking.py           # ✨ KakaoTemplate 모델 추가됨
├── services/
│   ├── booking_manager.py   # ✨ template_key 저장 로직 추가됨
│   ├── scheduler.py          # ✨ 카카오톡 발송으로 변경됨
│   ├── kakao_sender.py      # ✨ 새로 추가됨
│   ├── sms_sender.py        # 보관용 (주석처리)
│   ├── smartplace_crawler.py
│   ├── html_file_scraper.py
│   └── naver_auth.py
├── web/
│   ├── dashboard.py         # ✨ 카카오 템플릿 관리 API 추가됨
│   ├── templates/
│   │   ├── base.html        # ✨ 메뉴 추가됨
│   │   ├── kakao_templates.html  # ✨ 새로 추가됨
│   │   ├── dashboard.html
│   │   ├── bookings.html
│   │   ├── booking_detail.html
│   │   └── sms.html
│   └── static/              # (있으면)
└── utils/
    ├── __init__.py
    ├── config_loader.py
    ├── constants.py
    ├── datetime_utils.py
    ├── logger.py
    └── room_utils.py
```

### 2. 설정 파일
```
config/
├── settings.py              # ✨ kakao 설정 추가됨
├── accommodation.yaml
└── sms_templates.yaml       # SMS용 (보관)
```

**⚠️ 주의: kakao_templates.yaml은 불필요** (DB에서 관리)

### 3. 스크립트
```
scripts/
└── init_templates.py        # ✨ 새로 추가됨 (초기 템플릿 삽입)
```

### 4. 루트 파일
```
main.py                      # 메인 실행 파일
requirements.txt             # Python 패키지
.env                         # ⚠️ 환경변수 (새로 설정 필요)
.env.example
README.md
```

### 5. 가상환경 (선택)
```
baum_venv/                   # 또는 서버에서 새로 생성
```

---

## 🚫 옮기지 않아도 되는 것

```
❌ booking_automation.db      # DB는 서버에서 새로 생성
❌ naver_session.json          # 서버에서 새로 로그인
❌ crawl_status.json           # 자동 생성됨
❌ __pycache__/               # Python 캐시
❌ *.pyc                      # 컴파일된 파일
❌ .git/                      # (선택) Git 사용시만
❌ test_*.py                  # 테스트 파일들
❌ scripts/test_*.py          # 테스트 스크립트
❌ config/kakao_templates.yaml # DB로 이동했으므로 불필요
```

---

## 📋 서버 배포 순서

### 1. 파일 전송
```bash
# 로컬에서 실행
rsync -avz --exclude='*.db' --exclude='__pycache__' --exclude='*.pyc' \
  /Users/uzin/yujin/project/staytuned-automation/ \
  user@server:/path/to/app/
```

### 2. 서버에서 실행
```bash
# SSH로 서버 접속
ssh user@server

# 앱 디렉토리로 이동
cd /path/to/app

# 가상환경 생성
python3 -m venv baum_venv
source baum_venv/bin/activate

# 패키지 설치
pip install -r requirements.txt

# Playwright 설치
playwright install chromium

# .env 파일 설정
nano .env
# USE_TEST_MODE=false
# KAKAO_API_KEY=실제키
# KAKAO_SENDER_KEY=실제키
# KAKAO_CHANNEL_ID=실제ID
# ... (나머지 설정)

# DB 초기화
python -c "from src.models import init_db; init_db()"

# 카카오 템플릿 초기 데이터 삽입
PYTHONPATH=. python scripts/init_templates.py

# 실행
python main.py
```

---

## 🔧 배포 후 설정

### 1. 카카오 템플릿 코드 수정
웹 브라우저에서:
```
http://서버IP:8000/kakao-templates
```
→ 승인받은 템플릿 코드로 수정

### 2. 네이버 로그인
- 첫 실행 시 자동으로 로그인 진행
- `naver_session.json` 자동 생성됨

---

## 📦 간단 압축 명령어

```bash
# 필요한 파일만 압축
cd /Users/uzin/yujin/project/staytuned-automation
tar -czf staytuned-app.tar.gz \
  --exclude='*.db' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='naver_session.json' \
  --exclude='crawl_status.json' \
  --exclude='config/kakao_templates.yaml' \
  src/ config/ scripts/ main.py requirements.txt .env.example README.md

# 서버로 전송
scp staytuned-app.tar.gz user@server:/path/to/

# 서버에서 압축 해제
ssh user@server
cd /path/to/
tar -xzf staytuned-app.tar.gz
```

---

## ✅ 체크리스트

- [ ] `src/` 폴더 전체
- [ ] `config/` 폴더 (kakao_templates.yaml 제외)
- [ ] `scripts/init_templates.py`
- [ ] `main.py`, `requirements.txt`
- [ ] `.env` 파일 새로 작성
- [ ] 서버에서 가상환경 생성
- [ ] 패키지 설치
- [ ] DB 초기화
- [ ] 템플릿 데이터 삽입
- [ ] 웹에서 템플릿 코드 수정
- [ ] 실행 테스트
