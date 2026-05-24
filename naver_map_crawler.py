import asyncio
import re
import json
import pandas as pd
from playwright.async_api import async_playwright

SEARCH_QUERY = "부산대학교 음식점"
MAX_STORES = 10

TXT_FILE = "naver_final.txt"
XLSX_FILE = "naver_final.xlsx"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        menu_data = []

        # 🔥 네트워크 응답 가로채기
        async def handle_response(response):
            url = response.url

            if "menu" in url and "list" in url:
                try:
                    data = await response.json()

                    for item in data.get("list", []):
                        name = item.get("name")
                        price = item.get("price")

                        if name and price:
                            price_num = int(re.sub(r"[^\d]", "", str(price)))

                            menu_data.append({
                                "메뉴명": name,
                                "가격": price_num
                            })

                except:
                    pass

        page.on("response", handle_response)

        # 검색
        await page.goto(f"https://map.naver.com/v5/search/{SEARCH_QUERY}")
        await page.wait_for_timeout(5000)

        # 검색 결과 frame 찾기
        search_frame = None
        for f in page.frames:
            if "search" in f.url:
                search_frame = f

        if not search_frame:
            print("❌ search frame 없음")
            return

        items = await search_frame.query_selector_all("a[href*='/place/']")

        for i in range(min(len(items), MAX_STORES)):
            try:
                href = await items[i].get_attribute("href")
                match = re.search(r"/place/(\d+)", href)

                if not match:
                    continue

                place_id = match.group(1)

                print(f"[{i+1}] {place_id}")

                # place 페이지 이동
                await page.goto(f"https://pcmap.place.naver.com/restaurant/{place_id}")
                await page.wait_for_timeout(3000)

                # 메뉴 탭 클릭
                try:
                    await page.click("text=메뉴")
                    await page.wait_for_timeout(3000)
                except:
                    pass

            except Exception as e:
                print("에러:", e)

        await browser.close()

    if not menu_data:
        print("❌ 데이터 없음 (네트워크 감지 실패)")
        return

    df = pd.DataFrame(menu_data).drop_duplicates()

    df.to_excel(XLSX_FILE, index=False)

    with open(TXT_FILE, "w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            f.write(f"{row['메뉴명']} | {row['가격']}원\n")

    print("✅ 완료")
    print(f"{len(df)}개 수집됨")


if __name__ == "__main__":
    asyncio.run(main())