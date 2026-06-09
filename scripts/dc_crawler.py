"""
DC 한국주식 갤러리 크롤러
검색 기반 수집 - 삼전/하닉 키워드로 검색, 당일 게시글만 수집
하루 1회 실행 (20:00 KST 이후)
"""

import requests
import json
import os
import time
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

SEARCH_URL = "https://gall.dcinside.com/mgallery/board/lists/?id=krstock&s_type=search_subject_memo&s_keyword={}&page={}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://gall.dcinside.com/",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# 종목별 검색 키워드
SEARCH_KEYWORDS = {
    "samsung": ["삼전", "삼성전자"],
    "hynix":   ["하닉", "하이닉스"],
}

# 감성 키워드
POSITIVE = ["롱", "풀롱", "대풀롱", "매수", "떡상", "상승", "오른다", "올라", "호재", "기대",
            "상한가", "반등", "존버", "고고", "불장", "폭등", "가즈아"]
NEGATIVE = ["숏", "종베", "종배", "손절", "하락", "떡락", "내린다", "내려", "악재", "패닉",
            "물렸", "지옥", "망했", "공매도", "써킷", "폭락", "개손", "애개리"]


def is_today(date_str: str, today: str) -> bool:
    """
    DC gall_date title 속성: "2026.06.09 22:38:00" 형태
    표시 텍스트: 당일은 "22:38", 이전 날짜는 "06.08"
    today: "2026-06-09" 형태
    """
    # title 속성으로 비교 (가장 정확)
    if len(date_str) >= 10:
        # "2026.06.09 ..." → "2026-06-09"
        normalized = date_str[:10].replace(".", "-")
        return normalized == today
    # title 없으면 표시 텍스트로 판단: HH:MM이면 오늘
    return "." not in date_str


def fetch_search(keyword: str, today: str) -> list[str]:
    titles = []
    page = 1
    while True:
        url = SEARCH_URL.format(requests.utils.quote(keyword), page)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            print(f"  [{keyword} p{page}] fetch error: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("tr.ub-content")
        if not rows:
            break

        today_count = 0
        for row in rows:
            date_el = row.select_one("td.gall_date")
            title_el = row.select_one("td.gall_tit > a")
            if not date_el or not title_el:
                continue
            date_val = date_el.get("title", date_el.get_text(strip=True))
            if is_today(date_val, today):
                titles.append(title_el.get_text(strip=True).lower())
                today_count += 1

        print(f"  [{keyword} p{page}] 당일 {today_count}건")

        # 당일 게시글이 하나도 없으면 이전 날짜 진입 — 중단
        if today_count == 0:
            break

        page += 1
        time.sleep(2)

    return titles


def classify(title: str) -> str:
    pos = sum(1 for k in POSITIVE if k in title)
    neg = sum(1 for k in NEGATIVE if k in title)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def analyze(titles: list[str]) -> dict:
    counts = {"positive": 0, "negative": 0, "neutral": 0}
    for t in titles:
        counts[classify(t)] += 1
    total = len(titles)
    return {
        "total": total,
        "positive": counts["positive"],
        "negative": counts["negative"],
        "neutral": counts["neutral"],
        "positive_pct": round(counts["positive"] / total * 100) if total else 0,
        "negative_pct": round(counts["negative"] / total * 100) if total else 0,
        "neutral_pct":  round(counts["neutral"]  / total * 100) if total else 0,
    }


def main():
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).strftime("%Y-%m-%d")
    collected_at = datetime.now(kst).strftime("%Y-%m-%d %H:%M KST")

    print(f"[{collected_at}] 크롤링 시작")

    all_titles = {"samsung": [], "hynix": []}

    for stock, keywords in SEARCH_KEYWORDS.items():
        for keyword in keywords:
            titles = fetch_search(keyword, today)
            all_titles[stock].extend(titles)
            print(f"  {stock} / {keyword}: {len(titles)}건")
            time.sleep(2)

        # 중복 제거
        all_titles[stock] = list(set(all_titles[stock]))

    data = {
        "date": today,
        "collected_at": collected_at,
        "samsung": analyze(all_titles["samsung"]),
        "hynix":   analyze(all_titles["hynix"]),
        "total_posts": len(all_titles["samsung"]) + len(all_titles["hynix"]),
    }

    out_path = os.path.join(os.path.dirname(__file__), "..", "sentiment", "data", f"{today}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n저장 완료: {out_path}")
    print(f"  삼전: {data['samsung']['total']}건 | 긍정 {data['samsung']['positive_pct']}% / 부정 {data['samsung']['negative_pct']}%")
    print(f"  하닉: {data['hynix']['total']}건 | 긍정 {data['hynix']['positive_pct']}% / 부정 {data['hynix']['negative_pct']}%")


if __name__ == "__main__":
    main()
