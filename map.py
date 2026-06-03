"""
부산대학교 주변 음식점 지도 시각화
실행: streamlit run map_app.py
"""

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from pathlib import Path

# --------------------------------------------------
# 상수
# --------------------------------------------------
SCRIPT_DIR    = Path(__file__).parent
EXCEL_FILENAME = "부산대_주변_음식점_목록_최종_수정본.xlsx"
EXCEL_PATH    = SCRIPT_DIR / EXCEL_FILENAME

PNU_CENTER   = [35.2318, 129.0844]  # 부산대학교 정문
DEFAULT_ZOOM = 17                   # 17 이상에서 건물 윤곽 표시

# 음식점 마커 색상
MARKER_COLOR  = "#FF4E4E"
MARKER_BORDER = "#C0392B"

# 주요 랜드마크: 이름 / 위도 / 경도 / 표시 라벨
LANDMARKS = [
    {"name": "부산대학교 정문",       "lat": 35.231902,  "lng": 129.085193,  "label": "부산대 정문"},
    {"name": "NC백화점 부산대점",     "lat": 35.2322978, "lng": 129.0842446, "label": "NC백화점"},
    {"name": "부산장전동우체국",      "lat": 35.2296877, "lng": 129.0844727, "label": "우체국"},
    {"name": "부산대학교역 (1호선)",  "lat": 35.229771,  "lng": 129.089356,  "label": "부산대역"},
    {"name": "장전역 (1호선)",        "lat": 35.238099,  "lng": 129.0880602, "label": "장전역"},
]


# --------------------------------------------------
# 데이터 로드
# --------------------------------------------------
@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    """엑셀 파일을 불러와 유효한 좌표 행만 반환"""
    df = pd.read_excel(path)
    df = df.dropna(subset=["위도", "경도"])
    df["위도"] = pd.to_numeric(df["위도"], errors="coerce")
    df["경도"] = pd.to_numeric(df["경도"], errors="coerce")
    df = df.dropna(subset=["위도", "경도"])
    return df.reset_index(drop=True)


@st.cache_data
def load_data_from_bytes(data: bytes) -> pd.DataFrame:
    """업로드된 파일 바이트를 받아 데이터프레임으로 반환"""
    import io
    df = pd.read_excel(io.BytesIO(data))
    df = df.dropna(subset=["위도", "경도"])
    df["위도"] = pd.to_numeric(df["위도"], errors="coerce")
    df["경도"] = pd.to_numeric(df["경도"], errors="coerce")
    df = df.dropna(subset=["위도", "경도"])
    return df.reset_index(drop=True)


# --------------------------------------------------
# 팝업 HTML 생성
# --------------------------------------------------
def build_popup_html(row: pd.Series) -> str:
    """
    각 음식점 마커 클릭 시 표시할 팝업 HTML을 생성한다.
    메뉴/가격 컬럼(메뉴1~9, 가격1~9)을 동적으로 파싱한다.
    """
    name      = row.get("장소명", "")
    phone     = row.get("전화번호", "")
    address   = row.get("주소", "")
    url       = row.get("카카오지도_URL", "")
    avg_price = row.get("가격 평균", None)

    menu_rows = []
    for i in range(1, 10):
        menu  = row.get(f"메뉴{i}", None)
        price = row.get(f"가격{i}", None)
        if pd.notna(menu) and str(menu).strip():
            price_str = f"{int(price):,}원" if pd.notna(price) else "-"
            menu_rows.append(f"""
                <tr>
                  <td style="padding:3px 8px;color:#444;">{menu}</td>
                  <td style="padding:3px 8px;text-align:right;color:#E74C3C;font-weight:600;">{price_str}</td>
                </tr>""")

    menu_table = ""
    if menu_rows:
        menu_table = f"""
        <div style="margin-top:8px;">
          <div style="font-size:12px;font-weight:700;color:#333;margin-bottom:4px;">메뉴</div>
          <table style="width:100%;border-collapse:collapse;font-size:12px;">
            {''.join(menu_rows)}
          </table>
        </div>"""

    avg_str = ""
    if pd.notna(avg_price):
        avg_str = f"""
        <div style="margin-top:6px;font-size:11px;color:#888;text-align:right;">
          평균 가격: <strong style="color:#E74C3C;">{int(avg_price):,}원</strong>
        </div>"""

    kakao_btn = ""
    if pd.notna(url) and str(url).startswith("http"):
        kakao_btn = f"""
        <div style="margin-top:8px;">
          <a href="{url}" target="_blank"
             style="display:inline-block;padding:4px 10px;background:#FAE100;
                    color:#3A1D1D;border-radius:4px;font-size:11px;
                    font-weight:700;text-decoration:none;">카카오맵 보기</a>
        </div>"""

    phone_str = f'<div style="font-size:12px;color:#555;margin-top:2px;">{phone}</div>' if pd.notna(phone) and str(phone).strip() else ""
    addr_str  = f'<div style="font-size:11px;color:#888;margin-top:2px;">{address}</div>' if pd.notna(address) and str(address).strip() else ""

    return f"""
    <div style="font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;
                width:230px;padding:2px;">
      <div style="font-size:15px;font-weight:700;color:#222;
                  border-bottom:2px solid #FAE100;padding-bottom:4px;margin-bottom:4px;">
        {name}
      </div>
      {phone_str}
      {addr_str}
      {menu_table}
      {avg_str}
      {kakao_btn}
    </div>"""


# --------------------------------------------------
# 랜드마크 DivIcon — 텍스트 라벨 + 파란 배경
# --------------------------------------------------
def make_landmark_icon(label: str) -> folium.DivIcon:
    """
    주요 건물을 나타내는 라벨형 마커.
    텍스트가 중앙 정렬되며 icon_anchor를 마커 하단 중심으로 설정한다.
    """
    w = max(52, len(label) * 11)  # 라벨 길이에 맞게 너비 조정
    html = f"""
    <div style="position:relative;display:inline-block;">
      <div style="background:#1A73E8;color:white;border:2px solid white;
                  border-radius:4px;padding:2px 6px;font-size:11px;font-weight:700;
                  white-space:nowrap;box-shadow:0 2px 4px rgba(0,0,0,0.35);
                  font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;">
        {label}
      </div>
      <div style="width:0;height:0;border-left:5px solid transparent;
                  border-right:5px solid transparent;border-top:6px solid #1A73E8;
                  margin:0 auto;"></div>
    </div>
    """
    h = 36
    return folium.DivIcon(
        html=html,
        icon_size=(w, h),
        icon_anchor=(w // 2, h),   # 삼각형 꼭짓점이 좌표에 맞춰짐
        popup_anchor=(0, -h),
    )


# --------------------------------------------------
# 지도 생성
# --------------------------------------------------
def build_map(df: pd.DataFrame) -> folium.Map:
    """
    음식점 데이터와 주요 랜드마크를 OpenStreetMap 위에 표시한다.
    - 음식점: CircleMarker (중심 앵커, 건물 위에 정확히 표시)
    - 랜드마크: 텍스트 라벨 DivIcon
    """
    m = folium.Map(
        location=PNU_CENTER,
        zoom_start=DEFAULT_ZOOM,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    # 주요 랜드마크 마커
    for lm in LANDMARKS:
        folium.Marker(
            location=[lm["lat"], lm["lng"]],
            tooltip=folium.Tooltip(lm["name"], sticky=False),
            icon=make_landmark_icon(lm["label"]),
        ).add_to(m)

    # 음식점 마커 — CircleMarker: 좌표 중심에 원이 정확히 위치
    for _, row in df.iterrows():
        popup = folium.Popup(
            folium.Html(build_popup_html(row), script=True),
            max_width=260,
        )
        folium.CircleMarker(
            location=[row["위도"], row["경도"]],
            radius=5,                    # 픽셀 반지름 (줌에 무관하게 고정)
            color=MARKER_BORDER,         # 테두리 색
            weight=1.5,
            fill=True,
            fill_color=MARKER_COLOR,
            fill_opacity=0.9,
            popup=popup,
            tooltip=folium.Tooltip(row.get("장소명", ""), sticky=False),
        ).add_to(m)

    return m


# --------------------------------------------------
# 사이드바: 검색 / 가격 필터
# --------------------------------------------------
def render_sidebar(df: pd.DataFrame) -> pd.DataFrame:
    """
    사이드바에 검색창과 가격 슬라이더를 렌더링하고
    필터링된 데이터프레임을 반환한다.
    """
    st.sidebar.markdown(
        """
        <div style="font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;
                    font-size:20px;font-weight:700;color:#3A1D1D;margin-bottom:4px;">
            부산대 주변 음식점 지도
        </div>
        <div style="font-size:12px;color:#888;margin-bottom:16px;">
            Powered by 인디사 프로젝트팀
        </div>
        """,
        unsafe_allow_html=True,
    )

    query    = st.sidebar.text_input("음식점 이름 검색", placeholder="예: 국밥, 삼겹살 …")
    filtered = df[df["장소명"].str.contains(query, na=False)] if query else df

    avg_vals = df["가격 평균"].dropna()
    if len(avg_vals) > 0:
        min_p, max_p = int(avg_vals.min()), int(avg_vals.max())
        price_range  = st.sidebar.slider(
            "평균 가격 범위 (원)",
            min_value=min_p, max_value=max_p,
            value=(min_p, max_p), step=500, format="%d원",
        )
        filtered = filtered[
            filtered["가격 평균"].isna() |
            filtered["가격 평균"].between(price_range[0], price_range[1])
        ]

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"<div style='font-size:13px;color:#444;'>"
        f"<b>검색 결과:</b> {len(filtered)}개 &nbsp;|&nbsp; <b>전체:</b> {len(df)}개</div>",
        unsafe_allow_html=True,
    )

    if query and len(filtered) > 0:
        st.sidebar.markdown("**검색된 음식점**")
        for _, row in filtered.iterrows():
            avg = f"평균 {int(row['가격 평균']):,}원" if pd.notna(row["가격 평균"]) else ""
            st.sidebar.markdown(
                f"- **{row['장소명']}** <span style='font-size:11px;color:#888;'>{avg}</span>",
                unsafe_allow_html=True,
            )

    return filtered


# --------------------------------------------------
# 메인
# --------------------------------------------------
def main():
    st.set_page_config(
        page_title="부산대 주변 음식점 지도",
        page_icon="🍽️",
        layout="wide",
    )

    # Windows: 맑은 고딕 / macOS·iOS: Apple SD Gothic Neo
    st.markdown(
        """
        <style>
        html, body, [class*="css"] {
            font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
        }
        .block-container { padding-top: 1rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 데이터 로드 — 스크립트 옆 엑셀 우선, 없으면 업로드 위젯 표시
    if EXCEL_PATH.exists():
        df = load_data(EXCEL_PATH)
    else:
        st.warning(
            f"엑셀 파일을 찾을 수 없습니다.  \n"
            f"스크립트와 같은 폴더에 **{EXCEL_FILENAME}** 을 놓거나, 아래에서 업로드하세요."
        )
        uploaded = st.file_uploader("엑셀 파일 업로드", type=["xlsx"])
        if uploaded is None:
            st.stop()
        df = load_data_from_bytes(uploaded.read())

    filtered_df = render_sidebar(df)

    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
          <span style="font-size:22px;font-weight:700;color:#3A1D1D;">
            부산대학교 주변 음식점 지도
          </span>
          <span style="font-size:14px;color:#888;">— {len(filtered_df)}개 음식점 표시 중</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    fmap = build_map(filtered_df)
    st_folium(fmap, use_container_width=True, height=700, returned_objects=[])


if __name__ == "__main__":
    main()