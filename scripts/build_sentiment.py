"""
수집된 JSON 데이터로 sentiment/index.html 생성
"""

import json
import os
import glob
from datetime import datetime, timezone, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "sentiment", "data")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "sentiment", "index.html")


def load_recent(days: int = 7) -> list[dict]:
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")), reverse=True)[:days]
    records = []
    for f in files:
        with open(f, encoding="utf-8") as fp:
            records.append(json.load(fp))
    return records


def sentiment_label(pos_pct: int, neg_pct: int) -> tuple[str, str]:
    """(텍스트, CSS 클래스) 반환"""
    if pos_pct >= 50:
        return "매우 긍정", "very-pos"
    if pos_pct >= 35:
        return "긍정", "pos"
    if neg_pct >= 50:
        return "매우 부정", "very-neg"
    if neg_pct >= 35:
        return "부정", "neg"
    return "중립", "neutral"


def bar_html(pos: int, neg: int, neu: int) -> str:
    total = pos + neg + neu or 1
    pp = round(pos / total * 100)
    np_ = round(neg / total * 100)
    nup = 100 - pp - np_
    return f"""<div class="bar">
      <div class="bar-pos" style="width:{pp}%" title="긍정 {pp}%"></div>
      <div class="bar-neu" style="width:{nup}%" title="중립 {nup}%"></div>
      <div class="bar-neg" style="width:{np_}%" title="부정 {np_}%"></div>
    </div>"""


def history_rows(records: list[dict]) -> str:
    rows = ""
    for r in records:
        s = r["samsung"]
        h = r["hynix"]
        rows += f"""<tr>
      <td>{r['date']}</td>
      <td>{s['total']}</td>
      <td>{s['positive_pct']}% / {s['negative_pct']}%</td>
      <td>{h['total']}</td>
      <td>{h['positive_pct']}% / {h['negative_pct']}%</td>
    </tr>"""
    return rows


def build_html(records: list[dict]) -> str:
    if not records:
        return "<p>데이터 없음</p>"

    today = records[0]
    s = today["samsung"]
    h = today["hynix"]
    s_label, s_cls = sentiment_label(s["positive_pct"], s["negative_pct"])
    h_label, h_cls = sentiment_label(h["positive_pct"], h["negative_pct"])

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="주식 커뮤니티 삼성전자·SK하이닉스 심리지표 - 개인투자자 반응 분석">
  <title>삼전·하닉 심리지표</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0f1117; color: #e2e8f0; min-height: 100vh; padding: 24px 16px; }}
    .container {{ max-width: 720px; margin: 0 auto; }}
    h1 {{ font-size: 1.4rem; font-weight: 700; margin-bottom: 4px; }}
    .subtitle {{ font-size: 0.85rem; color: #94a3b8; margin-bottom: 24px; }}
    .cards {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 32px; }}
    @media (max-width: 480px) {{ .cards {{ grid-template-columns: 1fr; }} }}
    .card {{ background: #1e2330; border-radius: 12px; padding: 20px; }}
    .card-name {{ font-size: 0.8rem; color: #94a3b8; margin-bottom: 6px; }}
    .card-count {{ font-size: 2rem; font-weight: 700; line-height: 1; margin-bottom: 4px; }}
    .card-unit {{ font-size: 0.8rem; color: #64748b; margin-bottom: 14px; }}
    .badge {{ display: inline-block; padding: 3px 10px; border-radius: 20px;
              font-size: 0.8rem; font-weight: 600; margin-bottom: 12px; }}
    .very-pos {{ background: #14532d; color: #86efac; }}
    .pos      {{ background: #1e3a2a; color: #6ee7b7; }}
    .neutral  {{ background: #1e293b; color: #94a3b8; }}
    .neg      {{ background: #3b1f1f; color: #fca5a5; }}
    .very-neg {{ background: #450a0a; color: #f87171; }}
    .pct-row {{ display: flex; justify-content: space-between; font-size: 0.78rem;
                color: #94a3b8; margin-bottom: 6px; }}
    .bar {{ height: 8px; border-radius: 4px; overflow: hidden; display: flex; }}
    .bar-pos {{ background: #22c55e; }}
    .bar-neu {{ background: #334155; }}
    .bar-neg {{ background: #ef4444; }}
    h2 {{ font-size: 1rem; font-weight: 600; margin-bottom: 12px; color: #cbd5e1; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
    th {{ text-align: left; padding: 8px 10px; color: #64748b;
          border-bottom: 1px solid #1e2330; white-space: nowrap; }}
    td {{ padding: 8px 10px; border-bottom: 1px solid #1a1f2e; }}
    .disclaimer {{ margin-top: 32px; font-size: 0.75rem; color: #475569; line-height: 1.6; }}
    .updated {{ font-size: 0.75rem; color: #475569; margin-bottom: 20px; }}
  </style>
</head>
<body>
<div class="container">
  <h1>삼전 · 하닉 심리지표</h1>
  <p class="subtitle">주식 커뮤니티 게시글 언급 빈도 및 긍/부정 분석</p>
  <p class="updated">기준일: {today['date']} &nbsp;|&nbsp; 수집: {today['collected_at']}</p>

  <div class="cards">
    <div class="card">
      <div class="card-name">삼성전자 (005930)</div>
      <div class="card-count">{s['total']}</div>
      <div class="card-unit">건 언급</div>
      <span class="badge {s_cls}">{s_label}</span>
      <div class="pct-row">
        <span>긍정 {s['positive_pct']}%</span>
        <span>중립 {s['neutral_pct']}%</span>
        <span>부정 {s['negative_pct']}%</span>
      </div>
      {bar_html(s['positive'], s['neutral'], s['negative'])}
    </div>
    <div class="card">
      <div class="card-name">SK하이닉스 (000660)</div>
      <div class="card-count">{h['total']}</div>
      <div class="card-unit">건 언급</div>
      <span class="badge {h_cls}">{h_label}</span>
      <div class="pct-row">
        <span>긍정 {h['positive_pct']}%</span>
        <span>중립 {h['neutral_pct']}%</span>
        <span>부정 {h['negative_pct']}%</span>
      </div>
      {bar_html(h['positive'], h['neutral'], h['negative'])}
    </div>
  </div>

  <h2>최근 7일 추이</h2>
  <table>
    <thead>
      <tr>
        <th>날짜</th>
        <th>삼전 언급</th>
        <th>삼전 긍/부</th>
        <th>하닉 언급</th>
        <th>하닉 긍/부</th>
      </tr>
    </thead>
    <tbody>
      {history_rows(records)}
    </tbody>
  </table>

  <p class="disclaimer">
    본 지표는 특정 주식 커뮤니티 게시글 제목을 기계적으로 집계한 통계입니다.
    투자 권유 또는 종목 추천이 아니며, 투자 판단의 근거로 사용할 수 없습니다.
    모든 투자 결정과 그에 따른 손익은 투자자 본인에게 있습니다.
  </p>
</div>
</body>
</html>"""


def main():
    records = load_recent(7)
    html = build_html(records)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML 생성 완료: {OUT_PATH}")


if __name__ == "__main__":
    main()
