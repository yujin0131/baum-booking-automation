#!/bin/bash

# Staytuned Booking Automation 배포 스크립트
# AWS Lightsail Ubuntu 인스턴스용

set -e

echo "======================================"
echo "Staytuned Booking Automation 배포 시작"
echo "======================================"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. 시스템 업데이트
echo -e "${GREEN}[1/8] 시스템 패키지 업데이트...${NC}"
sudo apt-get update
sudo apt-get upgrade -y

# 2. Python 3.11 설치
echo -e "${GREEN}[2/8] Python 3.11 설치...${NC}"
sudo apt-get install -y python3.11 python3.11-venv python3-pip

# 3. 필수 시스템 패키지 설치 (Playwright용)
echo -e "${GREEN}[3/8] Playwright 의존성 설치...${NC}"
sudo apt-get install -y \
    wget gnupg ca-certificates \
    fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libatspi2.0-0 libcups2 libdbus-1-3 libdrm2 libgbm1 \
    libgtk-3-0 libnspr4 libnss3 libwayland-client0 \
    libxcomposite1 libxdamage1 libxfixes3 libxkbcommon0 \
    libxrandr2 xdg-utils

# 4. 가상환경 생성
echo -e "${GREEN}[4/8] Python 가상환경 생성...${NC}"
if [ ! -d "venv" ]; then
    python3.11 -m venv venv
fi
source venv/bin/activate

# 5. Python 패키지 설치
echo -e "${GREEN}[5/8] Python 패키지 설치...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# 6. Playwright 브라우저 설치
echo -e "${GREEN}[6/8] Playwright Chromium 브라우저 설치...${NC}"
playwright install chromium
playwright install-deps chromium

# 7. .env 파일 확인
echo -e "${GREEN}[7/8] 환경 설정 확인...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}[ERROR] .env 파일이 없습니다!${NC}"
    echo -e "${YELLOW}1. .env.example을 복사하여 .env 파일을 생성하세요${NC}"
    echo -e "${YELLOW}2. .env 파일에 실제 값을 입력하세요${NC}"
    echo ""
    echo "cp .env.example .env"
    echo "nano .env"
    exit 1
fi

# 8. 로그 디렉토리 생성
echo -e "${GREEN}[8/8] 로그 디렉토리 생성...${NC}"
mkdir -p logs

echo ""
echo -e "${GREEN}======================================"
echo "배포 완료!"
echo "======================================${NC}"
echo ""
echo "다음 명령어로 애플리케이션을 실행할 수 있습니다:"
echo ""
echo -e "${YELLOW}1. 직접 실행:${NC}"
echo "   source venv/bin/activate"
echo "   python main.py"
echo ""
echo -e "${YELLOW}2. systemd 서비스로 실행:${NC}"
echo "   sudo cp staytuned-automation.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable staytuned-automation"
echo "   sudo systemctl start staytuned-automation"
echo "   sudo systemctl status staytuned-automation"
echo ""
echo -e "${YELLOW}3. Docker로 실행:${NC}"
echo "   docker-compose up -d"
echo ""
echo "대시보드 접속: http://YOUR_IP:8000"
echo ""
