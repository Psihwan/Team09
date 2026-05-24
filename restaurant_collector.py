"""
부산대학교 주변 음식점 목록 수집기
카카오 로컬 API (카테고리 검색) 사용

[사전 준비]
1. https://developers.kakao.com 에서 앱 생성
2. '카카오 로컬' API 사용 설정
3. REST API 키 복사 후 아래 API_KEY에 입력

[설치]
pip install requests
"""

import requests
import csv
import time
import os
from datetime import datetime

# =============================================
# 설정값
# =============================================
API_KEY = "카카오 API_KEY"   # 카카오 REST API 키

# 부산대학교 정문 좌표
PNU_LAT = 35.2324      # 위도
PNU_LNG = 129.0836     # 경도

RADIUS = 600           # 반경 (미터), 최대 20000
CATEGORY_CODE = "FD6"  # FD6 = 음식점

OUTPUT_FILE = f"부산대_주변_음식점_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"


# =============================================
# 카카오 로컬 API - 카테고리 검색
# =============================================
def fetch_restaurants(page: int = 1) -> dict:
    """카카오 카테고리 검색 API 호출"""
    url = "https://dapi.kakao.com/v2/local/search/category.json"
    headers = {"Authorization": f"KakaoAK {API_KEY}"}
    params = {
        "category_group_code": CATEGORY_CODE,
        "x": PNU_LNG,
        "y": PNU_LAT,
        "radius": RADIUS,
        "page": page,
        "size": 15,          # 페이지당 최대 15개
        "sort": "distance",  # 거리순 정렬
    }

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


def collect_all_restaurants() -> list[dict]:
    """전체 페이지 순회하며 음식점 모두 수집 (카카오 API 최대 45개 제한)"""
    all_restaurants = []
    page = 1

    print(f"📍 부산대학교 정문 기준 {RADIUS}m 이내 음식점 수집 시작\n")

    while True:
        print(f"  → 페이지 {page} 요청 중...", end=" ")
        data = fetch_restaurants(page)

        documents = data.get("documents", [])
        meta = data.get("meta", {})

        print(f"{len(documents)}개 수집")

        for place in documents:
            all_restaurants.append({
                "장소명": place.get("place_name", ""),
                "카테고리": place.get("category_name", ""),
                "전화번호": place.get("phone", ""),
                "주소": place.get("road_address_name") or place.get("address_name", ""),
                "거리(m)": place.get("distance", ""),
                "카카오지도_URL": place.get("place_url", ""),
                "위도": place.get("y", ""),
                "경도": place.get("x", ""),
                # 수작업 입력 컬럼 (나중에 채울 항목)
                "대표메뉴1": "",
                "가격1": "",
                "대표메뉴2": "",
                "가격2": "",
                "대표메뉴3": "",
                "가격3": "",
                "비고": "",
            })

        # 마지막 페이지 확인 (카카오 API는 최대 3페이지 = 45개)
        is_end = meta.get("is_end", True)
        if is_end or page >= 3:
            total = meta.get("total_count", len(all_restaurants))
            print(f"\n✅ 수집 완료: {len(all_restaurants)}개 (API 검색 결과 총 {total}개)")
            if total > 45:
                print(f"⚠️  카카오 API 제한으로 최대 45개까지만 수집됩니다.")
                print(f"   → 더 많은 데이터가 필요하면 아래 '범위 분할 수집' 함수를 사용하세요.")
            break

        page += 1
        time.sleep(0.3)  # API 호출 간격 (서버 부하 방지)

    return all_restaurants


# =============================================
# 범위 분할 수집 (45개 초과 시 사용)
# =============================================
def collect_with_keyword_split() -> list[dict]:
    """
    카카오 API 45개 제한 우회: 음식 카테고리 키워드로 분할 검색
    카테고리 검색 대신 키워드 검색을 여러 번 호출
    """
    keywords = [
        "부산대 한식", "부산대 중식", "부산대 일식", "부산대 양식",
        "부산대 분식", "부산대 카페", "부산대 치킨", "부산대 피자",
        "부산대 고기", "부산대 국밥", "부산대 술집", "부산대 패스트푸드",
        "장전동 밥집", "장전동 식당",
    ]

    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {API_KEY}"}

    seen_ids = set()
    all_restaurants = []

    print(f"📍 키워드 분할 수집 모드\n")

    for keyword in keywords:
        for page in range(1, 4):  # 최대 3페이지
            params = {
                "query": keyword,
                "category_group_code": CATEGORY_CODE,
                "x": PNU_LNG,
                "y": PNU_LAT,
                "radius": RADIUS,
                "page": page,
                "size": 15,
            }

            print(f"  [{keyword}] 페이지 {page}...", end=" ")
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            documents = data.get("documents", [])
            print(f"{len(documents)}개")

            for place in documents:
                pid = place.get("id")
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)

                all_restaurants.append({
                    "장소명": place.get("place_name", ""),
                    "카테고리": place.get("category_name", ""),
                    "전화번호": place.get("phone", ""),
                    "주소": place.get("road_address_name") or place.get("address_name", ""),
                    "거리(m)": place.get("distance", ""),
                    "카카오지도_URL": place.get("place_url", ""),
                    "위도": place.get("y", ""),
                    "경도": place.get("x", ""),
                    "대표메뉴1": "", "가격1": "",
                    "대표메뉴2": "", "가격2": "",
                    "대표메뉴3": "", "가격3": "",
                    "비고": "",
                })

            if data.get("meta", {}).get("is_end", True):
                break

            time.sleep(0.3)

    print(f"\n✅ 중복 제거 후 총 {len(all_restaurants)}개 수집")
    return all_restaurants


# =============================================
# CSV 저장
# =============================================
def save_to_csv(restaurants: list[dict], filename: str = OUTPUT_FILE):
    if not restaurants:
        print("❌ 저장할 데이터가 없습니다.")
        return

    fieldnames = list(restaurants[0].keys())

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(restaurants)

    print(f"\n💾 저장 완료: {os.path.abspath(filename)}")
    print(f"   총 {len(restaurants)}개 음식점 → 엑셀에서 열어 메뉴/가격을 수작업 입력하세요!")


# =============================================
# 실행
# =============================================
if __name__ == "__main__":
    # 방법 1: 기본 카테고리 수집 (45개 이하일 때 사용)
    restaurants = collect_all_restaurants()

    # 방법 2: 결과가 45개라면 키워드 분할 수집으로 전환
    if len(restaurants) >= 45:
        print("\n🔄 45개 한계 도달 → 키워드 분할 수집으로 전환합니다...\n")
        restaurants = collect_with_keyword_split()

    save_to_csv(restaurants)
