import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from loguru import logger

from config.settings import settings
from src.models import SessionLocal, get_session
# from src.services.sms_sender import SMSSender
from src.services.kakao_sender import KakaoSender
from src.services.booking_manager import BookingManager

# 크롤링 간격 (분)
SCRAPE_MIN_INTERVAL = 8
SCRAPE_MAX_INTERVAL = 13


class BookingScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=ZoneInfo("Asia/Seoul"))
        self.scraper = None
        # self.sms_sender: Optional[SMSSender] = None
        self.kakao_sender: Optional[KakaoSender] = None
        self.test_mode = settings.use_test_mode
        logger.info(f"Scheduler init ({self.test_mode})")

    async def initialize(self):
        try:
            if self.test_mode:
                from src.services.html_file_scraper import HtmlFileScraper
                html_file = settings.test_html_file
                self.scraper = HtmlFileScraper(html_file)
                await self.scraper.initialize()
                logger.info(f"Test mode: using {html_file}")
            else:
                # SmartplaceCrawler 사용 (봇 탐지 우회 로그인)
                from src.services.smartplace_crawler import SmartplaceCrawler
                self.scraper = SmartplaceCrawler(headless=True)
                logger.info("Using SmartplaceCrawler")

            # self.sms_sender = SMSSender()
            self.kakao_sender = KakaoSender()

            logger.success("Scheduler resources initialized (Kakao)")

        except Exception as e:
            logger.error(f"[Error] Scheduler init failed {e}")
            raise

    def _get_random_scrape_interval(self) -> int:
        """8-13분 사이 랜덤 간격 반환"""
        return random.randint(SCRAPE_MIN_INTERVAL, SCRAPE_MAX_INTERVAL)

    def _schedule_next_scrape(self, first_run: bool = False):
        """다음 크롤링 작업을 랜덤 간격으로 스케줄링"""
        interval = self._get_random_scrape_interval()
        next_time = datetime.now() if first_run else datetime.now() + timedelta(minutes=interval)

        # 기존 job 제거 후 새로 등록
        try:
            self.scheduler.remove_job("scrape_bookings")
        except Exception:
            pass

        self.scheduler.add_job(
            self.scrape_and_process_bookings,
            trigger=DateTrigger(run_date=next_time),
            id="scrape_bookings",
            name="Scrape bookings",
            replace_existing=True,
            max_instances=1,
        )

        if not first_run:
            logger.info(f"Next scrape scheduled in {interval} min")

    def start(self):
        try:
            # 첫 실행은 즉시, 이후 랜덤 간격
            self._schedule_next_scrape(first_run=True)
            logger.info(
                f"Job registered: scrape bookings (random {SCRAPE_MIN_INTERVAL}-{SCRAPE_MAX_INTERVAL} min)"
            )

            self.scheduler.add_job(
                self.send_pending_sms,
                trigger=IntervalTrigger(minutes=1),
                id="send_sms",
                name="Send SMS",
                replace_existing=True,
                max_instances=1,
            )
            logger.info("Job registered: send SMS (every 1min)")

            self.scheduler.add_job(
                self.daily_health_check,
                trigger=CronTrigger(hour=9, minute=0),
                id="health_check",
                name="Daily health check",
                replace_existing=True,
            )
            logger.info("Job registered: daily check (09:00)")

            self.scheduler.start()
            logger.success("Scheduler started")

        except Exception as e:
            logger.error(f"[Error] Scheduler start failed {e}")
            raise

    async def shutdown(self):
        try:
            logger.info("Shutting down scheduler...")

            if self.scheduler and self.scheduler.running:
                self.scheduler.shutdown(wait=True)

            if self.scraper and hasattr(self.scraper, 'cleanup'):
                await self.scraper.cleanup()

            logger.success("Scheduler stopped")

        except Exception as e:
            logger.error(f"[Error] Scheduler shutdown failed {e}")

    async def scrape_and_process_bookings(self):
        try:
            logger.info("=" * 60)
            logger.info("Scrape job started")
            logger.info("=" * 60)

            bookings_data = await self.scraper.get_new_bookings()

            if not bookings_data:
                logger.info("No new bookings")
                return

            logger.info(f"Found {len(bookings_data)} bookings")

            with get_session() as db:
                booking_manager = BookingManager(db)

                new_bookings_count = 0
                for booking_data in bookings_data:
                    booking = booking_manager.create_or_update_booking(booking_data)

                    if booking:
                        sms_logs = booking_manager.create_sms_logs_for_booking(booking)

                        if sms_logs:
                            new_bookings_count += 1
                            logger.info(
                                f"Booking processed: {booking.guest_name} - "
                                f"{len(sms_logs)} SMS created"
                            )

                if new_bookings_count > 0:
                    from src.models.booking import Booking

                    alert_msg = f"New bookings: {new_bookings_count}"

                    recent_bookings = (
                        db.query(Booking)
                        .order_by(Booking.id.desc())
                        .limit(new_bookings_count)
                        .all()
                    )

                    bookings_with_requests = [
                        b for b in recent_bookings if b.special_request
                    ]

                    if bookings_with_requests:
                        alert_msg += "\n\nSpecial requests:"
                        for b in bookings_with_requests:
                            alert_msg += f"\n- {b.guest_name}: {b.special_request}"

                    # await self.sms_sender.send_admin_alert(alert_msg)
                    await self.kakao_sender.send_admin_alert(alert_msg)

                logger.success(
                    f"Scrape job done - {new_bookings_count} new bookings processed"
                )

            # 크롤링 시간 저장
            from src.web.dashboard import save_crawl_time
            save_crawl_time()

        except Exception as e:
            logger.error(f"[Error] Scrape job failed {e}", exc_info=True)
        finally:
            # 다음 크롤링 랜덤 간격으로 스케줄링
            self._schedule_next_scrape()

    async def send_pending_sms(self):
        from src.utils.constants import SMS_BATCH_SIZE, SMS_BATCH_DELAY_SECONDS

        try:
            with get_session() as db:
                booking_manager = BookingManager(db)

                pending_logs = booking_manager.get_pending_sms_logs()

                if not pending_logs:
                    logger.debug("No pending SMS")
                    return

                logger.info(f"Pending SMS: {len(pending_logs)}")

                results = []
                permanent_failures = []

                async def send_single_sms(sms_log):
                    try:
                        # 기존 SMS 발송 (보관용)
                        # result = await self.sms_sender.send(
                        #     recipient=sms_log.recipient_phone,
                        #     message=sms_log.message_content,
                        # )

                        # 카카오 알림톡 발송 (template_key가 있으면)
                        if sms_log.template_key:
                            import json
                            template_vars = json.loads(sms_log.template_vars) if sms_log.template_vars else {}
                            result = await self.kakao_sender.send_template(
                                recipient=sms_log.recipient_phone,
                                template_key=sms_log.template_key,
                                variables=template_vars
                            )
                        else:
                            # 친구톡으로 fallback (template_key 없는 경우)
                            result = await self.kakao_sender.send_friendtalk(
                                recipient=sms_log.recipient_phone,
                                message=sms_log.message_content,
                            )

                        if result.get("success"):
                            booking_manager.mark_sms_as_sent(sms_log, result)
                            return ("sent", sms_log)
                        else:
                            error_msg = result.get("error", "Unknown error")
                            booking_manager.mark_sms_as_failed(sms_log, error_msg)

                            if sms_log.can_retry:
                                logger.info(
                                    f"SMS {sms_log.id} will retry "
                                    f"({sms_log.retry_count}/{sms_log.max_retries})"
                                )
                            else:
                                logger.error(
                                    f"SMS {sms_log.id} permanent fail "
                                    f"({sms_log.retry_count} attempts)"
                                )
                                permanent_failures.append(sms_log)

                            return ("failed", sms_log)

                    except Exception as e:
                        logger.error(f"[Error] SMS {sms_log.id} {e}")
                        booking_manager.mark_sms_as_failed(sms_log, str(e))
                        return ("failed", sms_log)

                for i in range(0, len(pending_logs), SMS_BATCH_SIZE):
                    batch = pending_logs[i:i + SMS_BATCH_SIZE]
                    tasks = [send_single_sms(sms_log) for sms_log in batch]
                    batch_results = await asyncio.gather(*tasks)
                    results.extend(batch_results)

                    if i + SMS_BATCH_SIZE < len(pending_logs):
                        await asyncio.sleep(SMS_BATCH_DELAY_SECONDS)

                sent_count = sum(1 for r in results if r[0] == "sent")
                failed_count = sum(1 for r in results if r[0] == "failed")

                for sms_log in permanent_failures:
                    # await self.sms_sender.send_admin_alert(
                    await self.kakao_sender.send_admin_alert(
                        f"SMS failed: {sms_log.recipient_phone} "
                        f"({sms_log.sms_type.value})"
                    )

                logger.success(
                    f"SMS job done - sent: {sent_count}, failed: {failed_count}"
                )

        except Exception as e:
            logger.error(f"[Error] SMS job failed {e}", exc_info=True)

    async def daily_health_check(self):
        try:
            logger.info("=" * 60)
            logger.info("Daily health check started")
            logger.info("=" * 60)

            with get_session() as db:
                from src.models.booking import Booking, SMSLog, SMSStatus
                from datetime import timedelta
                from src.utils.datetime_utils import now_kst

                now = now_kst()
                yesterday = now - timedelta(days=1)

                total_bookings = db.query(Booking).count()
                yesterday_bookings = (
                    db.query(Booking)
                    .filter(Booking.created_at >= yesterday)
                    .count()
                )

                sent_sms = (
                    db.query(SMSLog)
                    .filter(SMSLog.status == SMSStatus.SENT)
                    .count()
                )
                failed_sms = (
                    db.query(SMSLog)
                    .filter(SMSLog.status == SMSStatus.FAILED)
                    .count()
                )
                pending_sms = (
                    db.query(SMSLog)
                    .filter(SMSLog.status == SMSStatus.SCHEDULED)
                    .count()
                )

                report = (
                    f"Daily Report\n\n"
                    f"[Bookings]\n"
                    f"- Total: {total_bookings}\n"
                    f"- Yesterday: {yesterday_bookings}\n\n"
                    f"[SMS]\n"
                    f"- Sent: {sent_sms}\n"
                    f"- Failed: {failed_sms}\n"
                    f"- Pending: {pending_sms}\n\n"
                    f"System OK"
                )

                logger.info(report)

                # await self.sms_sender.send_admin_alert(
                await self.kakao_sender.send_admin_alert(
                    f"Daily: {total_bookings} bookings, "
                    f"{sent_sms} SMS sent, {failed_sms} failed"
                )

                logger.success("Daily health check done")

        except Exception as e:
            logger.error(f"[Error] Daily check failed {e}", exc_info=True)
            # await self.sms_sender.send_admin_alert(f"Health check error: {str(e)[:50]}")
            await self.kakao_sender.send_admin_alert(f"Health check error: {str(e)[:50]}")
