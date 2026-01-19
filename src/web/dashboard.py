import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

from src.models import Booking, SMSLog, get_session
from src.models.booking import SMSStatus, BookingStatus, KakaoTemplate
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
        booking_manager = BookingManager(db)
        today = now_kst().date()

        if filter == "check_in":
            # 오늘 입실
            bookings = booking_manager.get_check_ins_for_date(today)
        elif filter == "check_out":
            # 오늘 퇴실
            bookings = booking_manager.get_check_outs_for_date(today)
        elif filter == "long_stay":
            # 연박 (2박 이상 = 퇴실일 - 입실일 > 1)
            from sqlalchemy import func
            query = db.query(Booking).filter(
                func.julianday(Booking.check_out_date) - func.julianday(Booking.check_in_date) > 1,
                Booking.status != BookingStatus.CANCELLED
            )
            bookings = query.order_by(Booking.check_in_date.desc()).all()
        else:
            # 전체 조회
            bookings = db.query(Booking).order_by(Booking.check_in_date.desc()).all()

        # 입실/퇴실 필터의 경우 정렬 유지
        if filter in ["check_in", "check_out"]:
            bookings = sorted(bookings, key=lambda b: b.check_in_date, reverse=True)

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


# ============================================================================
# 카카오 템플릿 관리
# ============================================================================

@app.get("/kakao-templates", response_class=HTMLResponse)
async def kakao_templates_page(request: Request):
    """카카오 템플릿 관리 페이지"""
    with get_session() as db:
        template_list = db.query(KakaoTemplate).order_by(KakaoTemplate.id).all()

        return templates.TemplateResponse("kakao_templates.html", {
            "request": request,
            "templates": template_list,
        })


@app.get("/api/kakao-templates")
async def get_kakao_templates():
    """카카오 템플릿 목록 조회 API"""
    with get_session() as db:
        templates = db.query(KakaoTemplate).order_by(KakaoTemplate.id).all()
        return {"success": True, "templates": [t.to_dict() for t in templates]}


@app.post("/api/kakao-templates")
async def create_kakao_template(request: Request):
    """카카오 템플릿 추가 API"""
    import json

    data = await request.json()

    # 필수 필드 검증
    required_fields = ["template_key", "template_code", "name"]
    for field in required_fields:
        if field not in data:
            return {"success": False, "error": f"Missing required field: {field}"}

    with get_session() as db:
        # 중복 확인
        existing = db.query(KakaoTemplate).filter_by(template_key=data["template_key"]).first()
        if existing:
            return {"success": False, "error": "Template key already exists"}

        # 새 템플릿 생성
        template = KakaoTemplate(
            template_key=data["template_key"],
            template_code=data["template_code"],
            name=data["name"],
            description=data.get("description", ""),
            variables=json.dumps(data.get("variables", [])),
            buttons=json.dumps(data.get("buttons", [])),
            is_active=data.get("is_active", True)
        )

        db.add(template)
        db.commit()
        db.refresh(template)

        return {"success": True, "template": template.to_dict()}


@app.post("/api/kakao-templates/{template_id}")
async def update_kakao_template(template_id: int, request: Request):
    """카카오 템플릿 수정 API"""
    from fastapi import Body

    data = await request.json()

    with get_session() as db:
        template = db.query(KakaoTemplate).filter_by(id=template_id).first()
        if not template:
            return {"success": False, "error": "Template not found"}

        # 수정 가능한 필드만 업데이트
        if "template_code" in data:
            template.template_code = data["template_code"]
        if "name" in data:
            template.name = data["name"]
        if "description" in data:
            template.description = data["description"]
        if "is_active" in data:
            template.is_active = data["is_active"]

        db.commit()

        return {"success": True, "template": template.to_dict()}
