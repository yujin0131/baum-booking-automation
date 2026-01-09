import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

from src.models import Booking, SMSLog, get_session
from src.models.booking import SMSStatus, BookingStatus
from src.services.booking_manager import BookingManager
from src.services.sms_sender import SMSSender
from src.utils.datetime_utils import now_kst

CRAWL_STATUS_FILE = Path("crawl_status.json")


def get_last_crawl_time() -> Optional[datetime]:
    """마지막 크롤링 시간 조회"""
    if not CRAWL_STATUS_FILE.exists():
        return None
    try:
        data = json.loads(CRAWL_STATUS_FILE.read_text())
        return datetime.fromisoformat(data.get("last_crawl_time"))
    except Exception:
        return None


def save_crawl_time():
    """크롤링 시간 저장"""
    CRAWL_STATUS_FILE.write_text(json.dumps({
        "last_crawl_time": now_kst().isoformat()
    }))

app = FastAPI(title="Booking Automation Dashboard")

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    with get_session() as db:
        total_bookings = db.query(Booking).count()
        total_sms = db.query(SMSLog).count()
        pending_sms = db.query(SMSLog).filter(SMSLog.status == SMSStatus.SCHEDULED).count()
        sent_sms = db.query(SMSLog).filter(SMSLog.status == SMSStatus.SENT).count()
        failed_sms = db.query(SMSLog).filter(SMSLog.status == SMSStatus.FAILED).count()

        recent_bookings = (
            db.query(Booking)
            .order_by(Booking.created_at.desc())
            .limit(10)
            .all()
        )

        last_crawl = get_last_crawl_time()

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "stats": {
                "total_bookings": total_bookings,
                "total_sms": total_sms,
                "pending_sms": pending_sms,
                "sent_sms": sent_sms,
                "failed_sms": failed_sms,
            },
            "recent_bookings": recent_bookings,
            "last_crawl_time": last_crawl,
        })


@app.get("/bookings", response_class=HTMLResponse)
async def bookings_page(request: Request, filter: Optional[str] = None):
    with get_session() as db:
        query = db.query(Booking)
        today = now_kst().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        if filter == "check_in":
            # 오늘 입실
            query = query.filter(
                Booking.check_in_date == today,
                Booking.status != BookingStatus.CANCELLED
            )
        elif filter == "check_out":
            # 오늘 퇴실
            query = query.filter(
                Booking.check_out_date == today,
                Booking.status != BookingStatus.CANCELLED
            )
        elif filter == "long_stay":
            # 연박 (2박 이상 - 어제 이전 입실 + 오늘 이후 퇴실)
            yesterday = today - timedelta(days=1)
            query = query.filter(
                Booking.check_in_date < yesterday,  # 어제 전에 입실 (2박 이상)
                Booking.check_out_date >= today,    # 오늘 이후 퇴실
                Booking.status != BookingStatus.CANCELLED
            )

        bookings = query.order_by(Booking.check_in_date.desc()).all()

        return templates.TemplateResponse("bookings.html", {
            "request": request,
            "bookings": bookings,
            "filter": filter,
        })


@app.get("/booking/{booking_id}", response_class=HTMLResponse)
async def booking_detail(request: Request, booking_id: int):
    from sqlalchemy.orm import joinedload

    with get_session() as db:
        booking = (
            db.query(Booking)
            .options(joinedload(Booking.sms_logs))
            .filter(Booking.id == booking_id)
            .first()
        )
        if not booking:
            return RedirectResponse("/bookings")

        sms_logs = sorted(booking.sms_logs, key=lambda x: x.scheduled_time or x.created_at)

        return templates.TemplateResponse("booking_detail.html", {
            "request": request,
            "booking": booking,
            "sms_logs": sms_logs,
        })


@app.get("/sms", response_class=HTMLResponse)
async def sms_page(request: Request, status: Optional[str] = None):
    with get_session() as db:
        query = db.query(SMSLog).join(Booking)

        if status:
            query = query.filter(SMSLog.status == status)

        sms_logs = query.order_by(SMSLog.created_at.desc()).limit(100).all()

        return templates.TemplateResponse("sms.html", {
            "request": request,
            "sms_logs": sms_logs,
            "filter_status": status,
        })


@app.post("/sms/{sms_id}/resend")
async def resend_sms(sms_id: int):
    with get_session() as db:
        sms_log = db.query(SMSLog).filter(SMSLog.id == sms_id).first()
        if not sms_log:
            return {"success": False, "error": "SMS not found"}

        sms_sender = SMSSender()
        result = await sms_sender.send(
            recipient=sms_log.recipient_phone,
            message=sms_log.message_content,
        )

        booking_manager = BookingManager(db)
        if result.get("success"):
            booking_manager.mark_sms_as_sent(sms_log, result)
        else:
            booking_manager.mark_sms_as_failed(sms_log, result.get("error", "Unknown error"))

        return {"success": result.get("success"), "message": "SMS resent"}


@app.post("/api/crawl")
async def manual_crawl():
    """수동 크롤링 실행"""
    from src.services.smartplace_crawler import SmartplaceCrawler
    from loguru import logger

    try:
        crawler = SmartplaceCrawler(headless=True)
        bookings_data = await crawler.get_new_bookings()
        await crawler.close()

        if not bookings_data:
            return {"success": True, "total": 0, "new_count": 0}

        new_count = 0
        with get_session() as db:
            booking_manager = BookingManager(db)

            for booking_data in bookings_data:
                booking = booking_manager.create_or_update_booking(booking_data)
                if booking:
                    sms_logs = booking_manager.create_sms_logs_for_booking(booking)
                    if sms_logs:
                        new_count += 1

        save_crawl_time()
        logger.info(f"[Manual Crawl] {len(bookings_data)} total, {new_count} new")
        return {"success": True, "total": len(bookings_data), "new_count": new_count}

    except Exception as e:
        logger.error(f"[Manual Crawl Error] {e}")
        return {"success": False, "error": str(e)}
