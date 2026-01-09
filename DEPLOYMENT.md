# AWS Lightsail 배포 가이드

Staytuned 예약 자동화 시스템을 AWS Lightsail에 배포하는 방법입니다.

## 목차
1. [Lightsail 인스턴스 생성](#1-lightsail-인스턴스-생성)
2. [배포 방법 선택](#2-배포-방법-선택)
   - [방법 A: Docker 사용 (추천)](#방법-a-docker-사용-추천)
   - [방법 B: 직접 설치](#방법-b-직접-설치)
3. [환경 변수 설정](#3-환경-변수-설정)
4. [방화벽 설정](#4-방화벽-설정)
5. [모니터링 및 관리](#5-모니터링-및-관리)

---

## 1. Lightsail 인스턴스 생성

### 1.1 AWS Lightsail 콘솔 접속
1. [AWS Lightsail Console](https://lightsail.aws.amazon.com/) 접속
2. **인스턴스 생성** 클릭

### 1.2 인스턴스 설정
- **플랫폼**: Linux/Unix
- **OS**: Ubuntu 22.04 LTS
- **플랜**: 최소 2GB RAM 이상 권장
  - Playwright(Chromium 브라우저) 사용으로 메모리 필요
  - 권장: $10/월 플랜 (2GB RAM, 1 vCPU, 60GB SSD)

### 1.3 SSH 키 설정
- 기존 키 사용 또는 새 키 다운로드
- 키 파일 권한 설정: `chmod 400 your-key.pem`

### 1.4 인스턴스 생성 완료
- 인스턴스 이름 지정 (예: `staytuned-booking-automation`)
- **인스턴스 생성** 클릭

---

## 2. 배포 방법 선택

### 방법 A: Docker 사용 (추천)

#### 장점
- 환경 독립적
- 배포 간편
- 재시작 자동화

#### 단계

**1. SSH 접속**
```bash
ssh -i your-key.pem ubuntu@YOUR_LIGHTSAIL_IP
```

**2. Docker 설치**
```bash
# Docker 설치
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 현재 사용자를 docker 그룹에 추가
sudo usermod -aG docker ubuntu

# 재접속 또는 다음 명령어 실행
newgrp docker

# Docker Compose 설치
sudo apt-get update
sudo apt-get install -y docker-compose-plugin
```

**3. 프로젝트 업로드**
```bash
# 로컬에서 실행
scp -i your-key.pem -r /path/to/staytuned-booking-automation ubuntu@YOUR_IP:~/
```

또는 Git 사용:
```bash
# 서버에서 실행
cd ~
git clone YOUR_REPO_URL staytuned-booking-automation
cd staytuned-booking-automation
```

**4. 환경 변수 설정**
```bash
cp .env.example .env
nano .env  # 실제 값 입력
```

**5. Docker Compose로 실행**
```bash
docker compose up -d
```

**6. 로그 확인**
```bash
docker compose logs -f
```

**7. 자동 시작 설정 (이미 설정됨)**
Docker Compose의 `restart: unless-stopped` 설정으로 자동 재시작됨

---

### 방법 B: 직접 설치

#### 단계

**1. SSH 접속**
```bash
ssh -i your-key.pem ubuntu@YOUR_LIGHTSAIL_IP
```

**2. 프로젝트 업로드**
```bash
# Git 사용
git clone YOUR_REPO_URL staytuned-booking-automation
cd staytuned-booking-automation
```

또는 SCP 사용:
```bash
# 로컬에서 실행
scp -i your-key.pem -r /path/to/staytuned-booking-automation ubuntu@YOUR_IP:~/
```

**3. 배포 스크립트 실행**
```bash
cd ~/staytuned-booking-automation
chmod +x deploy.sh
./deploy.sh
```

배포 스크립트가 자동으로:
- Python 3.11 설치
- 가상환경 생성
- 패키지 설치
- Playwright 브라우저 설치

**4. 환경 변수 설정**
```bash
cp .env.example .env
nano .env  # 실제 값 입력
```

**5. systemd 서비스 등록**
```bash
sudo cp staytuned-automation.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable staytuned-automation
sudo systemctl start staytuned-automation
```

**6. 서비스 상태 확인**
```bash
sudo systemctl status staytuned-automation
```

---

## 3. 환경 변수 설정

`.env` 파일을 생성하고 다음 값들을 설정하세요:

```bash
# 네이버 계정 (스마트플레이스 접근용)
NAVER_EMAIL=your_email@naver.com
NAVER_PASSWORD=your_password
NAVER_PLACE_URL=https://new-m.pay.naver.com/o/booking/...

# SMS API (Solapi)
SMS_API_KEY=your_api_key
SMS_API_SECRET=your_api_secret
SMS_SENDER=01012345678

# 관리자 연락처
ADMIN_PHONE=01012345678

# 크롤링 설정
SCRAPE_INTERVAL_MINUTES=5
CHECK_IN_TIME=15:00

# 테스트 모드 (배포시 false로 설정)
USE_TEST_MODE=false
```

**보안 주의사항:**
- `.env` 파일은 절대 Git에 커밋하지 마세요
- 권한 설정: `chmod 600 .env`

---

## 4. 방화벽 설정

### 4.1 Lightsail 방화벽
1. Lightsail 콘솔에서 인스턴스 선택
2. **네트워킹** 탭 클릭
3. **방화벽** 섹션에서 규칙 추가:
   - **애플리케이션**: 커스텀
   - **프로토콜**: TCP
   - **포트**: 8000
   - **소스**: 필요에 따라 IP 제한 (보안 강화)

### 4.2 Ubuntu UFW (선택사항)
```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 8000/tcp  # 대시보드
sudo ufw enable
sudo ufw status
```

---

## 5. 모니터링 및 관리

### Docker 방식

**로그 확인**
```bash
docker compose logs -f
docker compose logs -f --tail=100  # 최근 100줄만
```

**컨테이너 상태 확인**
```bash
docker compose ps
```

**재시작**
```bash
docker compose restart
```

**중지**
```bash
docker compose down
```

**업데이트**
```bash
git pull  # 코드 업데이트
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

### systemd 서비스 방식

**서비스 상태 확인**
```bash
sudo systemctl status staytuned-automation
```

**로그 확인**
```bash
# 실시간 로그
sudo journalctl -u staytuned-automation -f

# 최근 100줄
sudo journalctl -u staytuned-automation -n 100

# 애플리케이션 로그
tail -f ~/staytuned-booking-automation/logs/app.log
```

**재시작**
```bash
sudo systemctl restart staytuned-automation
```

**중지**
```bash
sudo systemctl stop staytuned-automation
```

**자동 시작 비활성화**
```bash
sudo systemctl disable staytuned-automation
```

**업데이트**
```bash
cd ~/staytuned-booking-automation
sudo systemctl stop staytuned-automation
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl start staytuned-automation
```

---

## 6. 대시보드 접속

배포 완료 후 웹 브라우저에서:
```
http://YOUR_LIGHTSAIL_IP:8000
```

### 주요 기능
- 예약 목록 조회
- SMS 전송 현황 확인
- 수동 크롤링 실행
- 상태별 예약 관리

---

## 7. 문제 해결

### 메모리 부족
```bash
# 스왑 파일 생성 (2GB)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 영구 적용
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Playwright 브라우저 에러
```bash
# Docker: 컨테이너 재빌드
docker compose down
docker compose build --no-cache
docker compose up -d

# 직접 설치: 브라우저 재설치
source venv/bin/activate
playwright install chromium
playwright install-deps chromium
```

### 포트 접근 불가
1. Lightsail 방화벽 규칙 확인
2. UFW 상태 확인: `sudo ufw status`
3. 애플리케이션 실행 확인: `netstat -tulpn | grep 8000`

### 데이터베이스 권한 에러
```bash
# 데이터베이스 파일 권한 설정
chmod 644 booking_automation.db
```

---

## 8. 백업

### 중요 파일들
- `booking_automation.db` - 예약 데이터베이스
- `.env` - 환경 설정
- `naver_session.json` - 네이버 세션
- `logs/` - 로그 파일

### 자동 백업 스크립트
```bash
#!/bin/bash
# backup.sh
BACKUP_DIR="/home/ubuntu/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
tar -czf $BACKUP_DIR/staytuned-backup-$DATE.tar.gz \
    booking_automation.db \
    .env \
    naver_session.json \
    logs/

# 7일 이상 된 백업 삭제
find $BACKUP_DIR -name "staytuned-backup-*.tar.gz" -mtime +7 -delete
```

**크론탭 등록 (매일 새벽 3시)**
```bash
crontab -e
# 추가:
0 3 * * * cd /home/ubuntu/staytuned-booking-automation && ./backup.sh
```

---

## 9. 보안 권장사항

1. **SSH 포트 변경** (선택사항)
2. **SSH 키 기반 인증만 허용**
3. **방화벽 규칙 최소화**
4. **.env 파일 권한**: `chmod 600 .env`
5. **정기적인 시스템 업데이트**
   ```bash
   sudo apt-get update && sudo apt-get upgrade -y
   ```

---

## 10. 추가 도움말

- 로그 파일: `logs/` 디렉토리
- 대시보드 포트: 8000
- 크롤링 주기: `.env`의 `SCRAPE_INTERVAL_MINUTES`에서 설정

문제가 발생하면 로그를 확인하세요:
```bash
# Docker
docker compose logs -f

# systemd
sudo journalctl -u staytuned-automation -f

# 애플리케이션 로그
tail -f logs/app.log
```
