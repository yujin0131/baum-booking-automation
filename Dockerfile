# Playwright 공식 이미지 사용 (Python 3.11 + Firefox 포함)
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

# 작업 디렉토리 설정
WORKDIR /app

# 환경변수 설정 (tzdata interactive prompt 방지)
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Seoul
ENV PYTHONUNBUFFERED=1

# Firefox 메모리 최적화: 멀티프로세스 비활성화
ENV MOZ_FORCE_DISABLE_E10S=1
ENV MOZ_DISABLE_CONTENT_SANDBOX=1

# Xvfb 및 타임존 데이터 설치 (가상 디스플레이로 non-headless 브라우저 실행)
RUN apt-get update && apt-get install -y \
    xvfb \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 파일 복사
COPY requirements.txt .

# Python 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 로그 디렉토리 생성
RUN mkdir -p /app/logs

# 포트 노출 (대시보드)
EXPOSE 8000

# 애플리케이션 실행 (Xvfb 가상 디스플레이 사용)
# Xvfb를 백그라운드로 시작하고 Python 실행
CMD ["/bin/bash", "-c", "Xvfb :99 -screen 0 1920x1080x24 & sleep 2 && export DISPLAY=:99 && python main.py"]
