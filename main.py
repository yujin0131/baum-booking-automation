import asyncio
import signal
import sys
import threading
from typing import Optional

import nest_asyncio
from loguru import logger
import uvicorn

# Python 3.9 asyncio 호환성 - 중첩 이벤트 루프 허용
nest_asyncio.apply()

from config.settings import settings
from src.utils.logger import setup_logging
from src.models import init_db
from src.services.scheduler import BookingScheduler
from src.utils.constants import APP_MAIN_LOOP_SLEEP_SECONDS


class Application:
    def __init__(self):
        self.scheduler: Optional[BookingScheduler] = None
        self.is_running = False
        self.dashboard_thread: Optional[threading.Thread] = None

    def start_dashboard(self):
        from src.web.dashboard import app as dashboard_app

        # 스레드에서 새 이벤트 루프 생성
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        config = uvicorn.Config(
            dashboard_app,
            host="0.0.0.0",
            port=8000,
            log_level="warning",
            loop="asyncio",
        )
        server = uvicorn.Server(config)
        loop.run_until_complete(server.serve())

    async def startup(self):
        try:
            logger.info("=" * 50)
            logger.info("Starting staytuned Automation System")
            logger.info("=" * 50)

            logger.info("Initializing database...")
            init_db()

            logger.info("Initializing scheduler...")
            self.scheduler = BookingScheduler()
            await self.scheduler.initialize()

            logger.info("Starting scheduler...")
            self.scheduler.start()

            logger.info("Starting dashboard server...")
            self.dashboard_thread = threading.Thread(target=self.start_dashboard, daemon=True)
            self.dashboard_thread.start()

            self.is_running = True

            logger.info("=" * 50)
            logger.info("http://localhost:8000")
            logger.info("=" * 50)

        except Exception as e:
            logger.error(f"[Fail] {e}", exc_info=True)
            raise

    async def shutdown(self):
        try:
            logger.info("=" * 50)
            logger.info("Shutting down application...")
            logger.info("=" * 50)

            if self.scheduler:
                await self.scheduler.shutdown()

            self.is_running = False

        except Exception as e:
            logger.error(f"[Error] during shutdown {e}")

    async def run(self):
        try:
            await self.startup()

            while self.is_running:
                await asyncio.sleep(APP_MAIN_LOOP_SLEEP_SECONDS)

        except Exception as e:
            logger.error(f"[Error] {e}", exc_info=True)
        finally:
            await self.shutdown()


def main():
    setup_logging()

    app = Application()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(app.shutdown())
        )

    try:
        loop.run_until_complete(app.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
