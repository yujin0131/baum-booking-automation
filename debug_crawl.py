import asyncio
from src.services.smartplace_crawler import SmartplaceCrawler

async def debug():
    crawler = SmartplaceCrawler(headless=True)
    html, _ = await crawler.crawl_booking_list()

    if not html:
        print("❌ 크롤링 실패")
        return

    with open('/app/debug_crawled.html', 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✅ HTML 저장됨: {len(html)} bytes")

    if 'BookingListView__contents-user' in html:
        print("✅ CSS 클래스 발견!")
    else:
        print("❌ CSS 클래스 없음 - 구조가 바뀌었을 수 있음")

    await crawler.cleanup()

asyncio.run(debug())
