"""
공개 사이트 빌더
종가베팅 대시보드(github.io)에서 외부 공개 가능한 시장 데이터만 추려
정적 멀티페이지 사이트를 생성한다. 하루 1회 실행.

공개: 시장 요약 / 주도 섹터 / 거래대금·상승률·상한가·교집합 Top
제외: 핵심후보 점수·진입가 / 수급 / 패턴분류 / 탈락사유 / 누적승률
"""

import requests
import json
import os
import sys
import glob
import re
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(ROOT, "reports", "data")
DASH_URL = "https://sunflowerofmine-afk.github.io/-/reports/{date}_{slot}.html"
SITE_URL = "https://stock-report-site.pages.dev"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; stock-report-site/1.0)"}

NAV = [
    ("index.html", "홈"),
    ("reports/index.html", "리포트"),
    ("sectors.html", "섹터란?"),
    ("glossary.html", "용어사전"),
    ("about.html", "소개"),
]


# ────────────────────────── fetch & parse ──────────────────────────
def fetch_dashboard(date: str):
    for slot in ("1750", "1450"):
        url = DASH_URL.format(date=date, slot=slot)
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200 and "종가베팅" in r.text:
                print(f"  fetched: {url}")
                return r.text
        except Exception as e:
            print(f"  fetch error {url}: {e}")
    return None


def _txt(el):
    return el.get_text(" ", strip=True) if el else ""


def section_after(soup, keyword: str):
    """section-title 텍스트에 keyword가 포함된 다음 형제 요소 반환"""
    for st in soup.select("div.section-title"):
        if keyword in st.get_text():
            return st.find_next_sibling()
    return None


def parse_table(wrap):
    """tbl-wrap 안의 table을 헤더 기반 dict 리스트로"""
    if not wrap:
        return []
    table = wrap.find("table")
    if not table:
        return []
    heads = [_txt(th) for th in table.select("thead th")]
    rows = []
    for tr in table.select("tbody tr"):
        cells = tr.find_all("td")
        row = {}
        for i, td in enumerate(cells):
            key = heads[i] if i < len(heads) else f"col{i}"
            cls = td.get("class") or []
            val = _txt(td)
            row[key] = val
            if "td-pos" in cls:
                row[f"_{key}_dir"] = "pos"
            elif "td-neg" in cls:
                row[f"_{key}_dir"] = "neg"
        rows.append(row)
    return rows


def parse_sectors(soup):
    grid = section_after(soup, "주도 섹터")
    if not grid:
        return []
    out = []
    for card in grid.select(".sector-card"):
        name = _txt(card.select_one(".s-name"))
        chg = _txt(card.select_one(".s-chg"))
        chg_dir = "pos" if (card.select_one(".s-chg") and "pos" in (card.select_one(".s-chg").get("class") or [])) else "neg"
        share = _txt(card.select_one(".s-tv"))
        stocks = []
        for tr in card.select("table.sector-stocks tr"):
            tds = tr.find_all("td")
            if len(tds) >= 3:
                stocks.append({
                    "name": _txt(tds[0]),
                    "chg": _txt(tds[1]),
                    "chg_dir": "pos" if "td-pos" in (tds[1].get("class") or []) else "neg",
                    "tv": _txt(tds[2]),
                })
        out.append({"name": name, "chg": chg, "chg_dir": chg_dir, "share": share, "stocks": stocks})
    return out


def parse_calendar(soup):
    cal = soup.find("table", class_="cal-table")
    if not cal:
        return []
    weeks = []
    for tr in cal.select("tbody tr"):
        week = []
        for td in tr.find_all("td"):
            day = _txt(td.select_one(".cal-day"))
            sectors = [_txt(s) for s in td.select(".cal-sector")]
            week.append({
                "day": day,
                "sectors": sectors,
                "today": "cal-today" in (td.get("class") or []),
            })
        weeks.append(week)
    return weeks


def parse(html: str, date: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    # 시장 요약
    regime = ""
    h1span = soup.select_one(".page-header h1 span[class^='regime']")
    if h1span:
        regime = _txt(h1span)

    kospi = kosdaq = ""
    for sp in soup.select(".page-header .meta span"):
        t = _txt(sp)
        if t.startswith("코스피"):
            kospi = t
        elif t.startswith("코스닥"):
            kosdaq = t

    market_type = hlimit = ""
    for row in soup.select(".env-row"):
        lbl = _txt(row.select_one(".env-label"))
        val = _txt(row.select_one(".env-val"))
        if lbl == "장세 유형":
            market_type = val
        elif lbl == "상한가":
            hlimit = val

    return {
        "date": date,
        "regime": regime,
        "kospi": kospi,
        "kosdaq": kosdaq,
        "market_type": market_type,
        "halt_count": hlimit,
        "sectors": parse_sectors(soup),
        "halt": parse_table(section_after(soup, "상한가")),
        "value": parse_table(section_after(soup, "거래대금 Top20")),
        "rise": parse_table(section_after(soup, "상승률 Top20")),
        "inter": parse_table(section_after(soup, "교집합")),
        "calendar": parse_calendar(soup),
    }


# ────────────────────────── HTML 렌더 ──────────────────────────
def page(title, desc, path, body, base=""):
    canonical = f"{SITE_URL}/{path}"
    nav = ""
    for href, label in NAV:
        active = ' class="active"' if href == path else ""
        nav += f'<a href="{base}{href}"{active}>{label}</a>'
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
<link rel="stylesheet" href="{base}assets/style.css">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6804053572487864" crossorigin="anonymous"></script>
</head>
<body>
<header class="site-header"><div class="inner">
  <div class="brand"><a href="{base}index.html">한국주식 데이터 리포트</a><span>공개 시장 데이터 정리</span></div>
  <nav class="site-nav">{nav}</nav>
</div></header>
<main>
{body}
</main>
<footer>
  <div class="links">
    <a href="{base}about.html">소개</a>
    <a href="{base}disclaimer.html">면책조항</a>
    <a href="{base}privacy.html">개인정보처리방침</a>
  </div>
  <p>본 사이트는 공개된 시장 데이터를 정리해 제공하는 정보 사이트이며, 특정 종목의 매매를 권유하지 않습니다.</p>
  <p>© 한국주식 데이터 리포트</p>
</footer>
</body>
</html>"""


def chg_span(val, direction):
    cls = "pos" if direction == "pos" else "neg"
    return f'<span class="{cls}">{val}</span>'


def render_top_table(rows, kind):
    """kind: value | rise"""
    if not rows:
        return "<p class='muted'>데이터 없음</p>"
    head = "<tr><th>#</th><th>종목명</th><th>섹터</th><th>시장</th>"
    head += "<th class='num'>거래대금</th><th class='num'>등락률</th></tr>" if kind == "value" \
        else "<th class='num'>등락률</th><th class='num'>거래대금</th></tr>"
    body = ""
    for i, r in enumerate(rows, 1):
        chg = chg_span(r.get("등락률", ""), r.get("_등락률_dir", "pos"))
        tv = r.get("거래대금", "")
        c1 = f"<td class='num'>{tv}</td><td class='num'>{chg}</td>" if kind == "value" \
            else f"<td class='num'>{chg}</td><td class='num'>{tv}</td>"
        body += (f"<tr><td>{i}</td><td class='name'>{r.get('종목명','')}</td>"
                 f"<td class='sector-tag'>{r.get('섹터','')}</td>"
                 f"<td class='muted small'>{r.get('시장','')}</td>{c1}</tr>")
    return f"<div class='tbl-wrap'><table><thead>{head}</thead><tbody>{body}</tbody></table></div>"


def render_halt_table(rows):
    if not rows:
        return "<p class='muted'>당일 상한가 종목 없음</p>"
    body = ""
    for r in rows:
        chg = chg_span(r.get("등락률", ""), r.get("_등락률_dir", "pos"))
        body += (f"<tr><td class='name'>{r.get('종목명','')}</td>"
                 f"<td class='code'>{r.get('코드','')}</td>"
                 f"<td class='muted small'>{r.get('시장','')}</td>"
                 f"<td class='sector-tag'>{r.get('섹터','')}</td>"
                 f"<td class='num'>{chg}</td><td class='num'>{r.get('거래대금','')}</td></tr>")
    return ("<div class='tbl-wrap'><table><thead><tr><th>종목명</th><th>코드</th>"
            "<th>시장</th><th>섹터</th><th class='num'>등락률</th><th class='num'>거래대금</th>"
            f"</tr></thead><tbody>{body}</tbody></table></div>")


def render_inter_table(rows):
    if not rows:
        return "<p class='muted'>당일 교집합 종목 없음</p>"
    body = ""
    for i, r in enumerate(rows, 1):
        chg = chg_span(r.get("등락률", ""), r.get("_등락률_dir", "pos"))
        body += (f"<tr><td>{i}</td><td class='name'>{r.get('종목명','')}</td>"
                 f"<td class='code'>{r.get('코드','')}</td>"
                 f"<td class='num'>{chg}</td><td class='num'>{r.get('거래대금','')}</td></tr>")
    return ("<div class='tbl-wrap'><table><thead><tr><th>#</th><th>종목명</th><th>코드</th>"
            "<th class='num'>등락률</th><th class='num'>거래대금</th>"
            f"</tr></thead><tbody>{body}</tbody></table></div>")


def render_sectors(sectors):
    if not sectors:
        return "<p class='muted'>데이터 없음</p>"
    cards = ""
    for s in sectors:
        rows = ""
        for st in s["stocks"]:
            rows += (f"<tr><td class='name'>{st['name']}</td>"
                     f"<td class='num'>{chg_span(st['chg'], st['chg_dir'])}</td>"
                     f"<td class='num muted'>{st['tv']}</td></tr>")
        cards += (f"<div class='sector'><div class='head'>"
                  f"<span class='nm'>{s['name']}</span>"
                  f"<span class='ch {s['chg_dir']}'>{s['chg']}</span>"
                  f"<span class='sh'>{s['share']}</span></div>"
                  f"<table><tbody>{rows}</tbody></table></div>")
    return f"<div class='sectors'>{cards}</div>"


def render_calendar(weeks):
    if not weeks:
        return "<p class='muted'>데이터 없음</p>"
    head = "".join(f"<th>{d}</th>" for d in ("월", "화", "수", "목", "금"))
    body = ""
    for week in weeks:
        cells = ""
        for c in week:
            if not c["day"]:
                cells += "<td class='cal-cell empty'></td>"
                continue
            tags = "".join(f"<span class='cal-sector'>{s}</span>" for s in c["sectors"])
            today = " today" if c["today"] else ""
            cells += (f"<td class='cal-cell{today}'><div class='cal-day'>{c['day']}</div>{tags}</td>")
        body += f"<tr>{cells}</tr>"
    return ("<div class='tbl-wrap'><table class='cal-table'><thead><tr>"
            f"{head}</tr></thead><tbody>{body}</tbody></table></div>")


SOURCE_NOTE = ('데이터 출처: 한국거래소(KRX) 및 증권 포털 등에서 공개되는 시장 데이터를 '
               '장 마감 기준으로 자동 집계했습니다.')

def disclaimer_box(base):
    return f"""<div class="disclaimer">
<strong>면책조항</strong><br>
본 페이지는 한국거래소·증권 포털 등에서 공개된 시장 데이터(거래대금·등락률·섹터 등)를 자동으로 정리한 정보 제공 자료입니다.
특정 종목의 매수·매도를 권유하거나 수익을 보장하지 않으며, 투자 판단과 그 결과에 대한 책임은 전적으로 투자자 본인에게 있습니다.
데이터는 수집 시점 기준이며 정확성·완전성을 보증하지 않습니다. 자세한 내용은 <a href="{base}disclaimer.html">면책조항</a> 페이지를 참고하세요.
</div>"""


def metrics_block(d):
    return f"""<div class="metrics">
    <div class="metric"><div class="k">코스피</div><div class="v">{d['kospi'].replace('코스피','').strip() or '-'}</div></div>
    <div class="metric"><div class="k">코스닥</div><div class="v">{d['kosdaq'].replace('코스닥','').strip() or '-'}</div></div>
    <div class="metric"><div class="k">시장 상태</div><div class="v" style="font-size:.95rem">{d['regime'] or '-'}</div></div>
    <div class="metric"><div class="k">상한가</div><div class="v">{d['halt_count'] or '-'}</div></div>
  </div>"""


def market_sections(d, base):
    """주도섹터·거래대금·상승률·상한가·교집합·4주달력 카드 (홈/리포트 공용)"""
    return f"""<div class="card">
  <h2>주도 섹터</h2>
  <p class="small muted">당일 자금과 상승이 집중된 테마·업종과 대표 종목입니다.</p>
  {render_sectors(d['sectors'])}
</div>

<div class="card">
  <h2>거래대금 상위 20</h2>
  <p class="small muted">하루 동안 가장 많은 금액이 거래된 종목입니다. 시장의 관심도를 보여줍니다.</p>
  {render_top_table(d['value'], 'value')}
</div>

<div class="card">
  <h2>상승률 상위 20</h2>
  <p class="small muted">당일 가장 많이 오른 종목입니다. 거래대금이 적은 종목은 변동성이 클 수 있습니다.</p>
  {render_top_table(d['rise'], 'rise')}
</div>

<div class="card">
  <h2>상한가 종목</h2>
  <p class="small muted">가격제한폭(+30%)까지 오른 종목입니다.</p>
  {render_halt_table(d['halt'])}
</div>

<div class="card">
  <h2>상승률·거래대금 동시 상위 (교집합)</h2>
  <p class="small muted">상승률 Top20과 거래대금 Top20에 동시에 든 종목으로, 관심과 수급이 함께 쏠린 종목입니다.</p>
  {render_inter_table(d['inter'])}
</div>

<div class="card">
  <h2>최근 4주간 주도 섹터</h2>
  <p class="small muted">거래일별로 자금과 상승이 집중됐던 상위 섹터입니다. 시장의 관심이 어떻게 옮겨갔는지 흐름을 볼 수 있습니다.</p>
  {render_calendar(d.get('calendar', []))}
  {disclaimer_box(base)}
</div>"""


def build_report_page(d):
    date = d["date"]
    body = f"""<div class="card">
  <span class="pill">일일 시장 리포트</span>
  <h1>{date} 한국 증시 데이터 요약</h1>
  <p class="lead">장 마감 기준 KOSPI·KOSDAQ 시장 상황과 거래대금·상승률 상위, 주도 섹터를 한눈에 정리했습니다.</p>
  {metrics_block(d)}
  <div class="edu">📌 <strong>장세 유형</strong> {d['market_type'] or '정보 없음'}<br>
  자금이 일부 섹터에 몰리는지, 시장 전반이 강한지를 나타냅니다. 용어가 생소하면 <a href="../glossary.html">용어사전</a>을 참고하세요.</div>
  <p class="small muted" style="margin-top:10px">{SOURCE_NOTE}</p>
</div>

{market_sections(d, "../")}"""
    title = f"{date} 한국 증시 데이터 요약 | 한국주식 데이터 리포트"
    desc = f"{date} KOSPI·KOSDAQ 거래대금·상승률 상위, 주도 섹터, 상한가 종목 정리"
    return page(title, desc, f"reports/{date}.html", body, base="../")


ADL_SECTION = """<div class="card">
  <h2>시장 상태와 ADL이란?</h2>
  <p>리포트 상단의 <strong>시장 상태</strong> 칸에는 '강세 / 약세'와 함께 <strong>ADL</strong>이라는 수치가 표시됩니다.
  이 값은 그날 시장이 <em>얼마나 넓게</em> 오르고 내렸는지를 보여주는 지표입니다.</p>

  <h3>ADL (등락주선, Advance-Decline Line)</h3>
  <p>ADL은 <strong>오른 종목 수와 내린 종목 수의 관계</strong>를 나타냅니다. 본 사이트에서는 전체 종목 중
  상승한 종목의 비율(%)을 함께 표기합니다. 예를 들어 <strong>ADL 27.8%</strong>라면, 그날 거래된 종목 중
  약 27.8%만 올랐고 나머지 약 72%는 내렸거나 보합이었다는 뜻입니다.</p>

  <h3>왜 중요한가</h3>
  <ul>
    <li><strong>지수만으로는 알 수 없는 시장의 체감을 보여줍니다.</strong> 코스피가 올라도 ADL이 낮으면,
    소수의 대형주만 끌어올린 '겉으로만 강한 장'일 수 있습니다.</li>
    <li><strong>50%가 기준선입니다.</strong> 50%를 크게 웃돌면 시장 전반이 강세, 크게 밑돌면 약세로 봅니다.</li>
    <li><strong>지수와 ADL의 방향이 엇갈릴 때</strong> 시장의 힘이 약해지고 있다는 신호로 해석되기도 합니다.</li>
  </ul>

  <h3>'자금집중형'이란</h3>
  <p>ADL이 낮은데도 지수나 특정 종목이 강하게 오르는 날은, 돈이 시장 전체가 아니라 일부 섹터·종목에만
  몰린 경우입니다. 이런 장세를 본 사이트에서는 <strong>자금집중형</strong>으로 표시합니다.
  이때는 주도 섹터의 영향력이 특히 큽니다.</p>
  <p class="small muted">ADL은 시장 상황을 이해하기 위한 참고 지표이며, 그 자체로 매매 신호가 아닙니다.</p>
</div>"""


def build_home(all_data):
    latest = all_data[0] if all_data else None
    intro = f"""<div class="card">
  <h1>한국주식 데이터 리포트</h1>
  <p class="lead">매 거래일 마감 후, 한국 증시의 공개 데이터를 누구나 보기 쉽게 정리합니다.</p>
  <p>이 사이트는 KOSPI·KOSDAQ 시장의 <strong>거래대금 상위 종목, 당일 상승률 상위 종목, 자금이 몰린 주도 섹터, 상한가 종목</strong>을
  매일 자동으로 정리해 보여줍니다. 모든 수치는 한국거래소와 증권 포털에서 공개되는 시장 데이터에 기반합니다.</p>
  <p>특정 종목을 추천하거나 매매를 권유하지 않습니다. 오늘 시장에서 <em>무슨 일이 있었는지</em>를
  데이터로 빠르게 파악하도록 돕는 것이 목적입니다.</p>
</div>

<div class="card">
  <h2>데이터를 읽는 법</h2>
  <ul>
    <li><strong>거래대금</strong> — 그날 가장 많은 돈이 오간 종목. 시장의 관심이 어디 쏠렸는지 보여줍니다.</li>
    <li><strong>상승률</strong> — 가장 많이 오른 종목. 단, 거래대금이 적으면 변동성이 큽니다.</li>
    <li><strong>주도 섹터</strong> — 자금과 상승이 집중된 업종·테마.</li>
    <li><strong>교집합</strong> — 상승률과 거래대금이 함께 상위인 종목.</li>
  </ul>
  <p class="small muted">각 용어의 자세한 설명은 <a href="glossary.html">용어사전</a>에서 확인할 수 있습니다.</p>
</div>

{ADL_SECTION}"""

    if latest:
        report = f"""<div class="card">
  <span class="pill">최신 리포트 · {latest['date']}</span>
  <h2 style="margin-top:8px">오늘의 한국 증시 데이터 요약</h2>
  <p class="lead">장 마감 기준 KOSPI·KOSDAQ 시장 상황과 거래대금·상승률 상위, 주도 섹터입니다.
  지난 리포트는 <a href="reports/index.html">아카이브</a>에서 볼 수 있습니다.</p>
  {metrics_block(latest)}
  <div class="edu">📌 <strong>장세 유형</strong> {latest['market_type'] or '정보 없음'}<br>
  자금이 일부 섹터에 몰리는지, 시장 전반이 강한지를 나타냅니다.</div>
  <p class="small muted" style="margin-top:10px">{SOURCE_NOTE}</p>
</div>

{market_sections(latest, "")}"""
    else:
        report = """<div class="card"><p class="muted">아직 발행된 리포트가 없습니다.</p></div>"""

    body = intro + "\n\n" + report
    return page("한국 주식시장 일일 데이터 리포트 | KOSPI·KOSDAQ 거래대금·섹터 분석",
                "매 거래일 자동 정리되는 KOSPI·KOSDAQ 거래대금·상승률·주도 섹터·상한가 데이터와 ADL·장세 해설",
                "index.html", body, base="")


def build_archive(all_data):
    rows = ""
    for d in all_data:
        rows += (f"<tr><td class='dt'>{d['date']}</td>"
                 f"<td><a href='{d['date']}.html'>리포트 보기 →</a></td>"
                 f"<td class='muted small'>{d['regime']}</td></tr>")
    if not rows:
        rows = "<tr><td colspan='3' class='muted'>아직 리포트가 없습니다.</td></tr>"
    body = f"""<div class="card">
  <h1>리포트 아카이브</h1>
  <p class="lead">날짜별 한국 증시 데이터 요약 리포트 목록입니다.</p>
  <div class="tbl-wrap"><table class="archive"><tbody>{rows}</tbody></table></div>
</div>"""
    return page("리포트 아카이브 | 한국주식 데이터 리포트",
                "날짜별 KOSPI·KOSDAQ 시장 데이터 요약 리포트 아카이브",
                "reports/index.html", body, base="../")


# ────────────────────────── 정적 페이지 ──────────────────────────
def build_static_pages():
    pages = {}

    pages["glossary.html"] = page(
        "주식 용어사전 | 한국주식 데이터 리포트",
        "거래대금, 등락률, 상한가, 주도 섹터, 장세 등 주식 시장 기본 용어 해설",
        "glossary.html",
        """<div class="card">
  <h1>주식 용어사전</h1>
  <p class="lead">리포트에 나오는 기본 용어를 쉽게 설명합니다.</p>

  <h3>거래대금</h3>
  <p>하루 동안 그 종목이 사고팔린 금액의 총합입니다. '거래량(주식 수)'과 달리 실제 오간 <strong>돈의 규모</strong>를 나타내므로,
  시장의 관심이 어디에 쏠렸는지 가늠하는 지표로 자주 쓰입니다. 단위는 보통 '억 원'입니다.</p>

  <h3>등락률</h3>
  <p>전 거래일 종가 대비 오늘 가격이 몇 % 오르거나 내렸는지입니다. 한국 증시는 하루 변동폭이
  ±30%로 제한되어 있습니다.</p>

  <h3>상한가 / 하한가</h3>
  <p>가격제한폭의 위쪽 끝(+30%)까지 오른 것을 <strong>상한가</strong>, 아래쪽 끝(-30%)까지 내린 것을 <strong>하한가</strong>라고 합니다.
  상한가 종목이 많은 날은 단기 테마가 강하게 형성된 경우가 많습니다.</p>

  <h3>주도 섹터</h3>
  <p>특정 업종이나 테마(예: 반도체, 2차전지)에 자금과 상승이 집중되는 경우, 그 무리를 '주도 섹터'라고 부릅니다.
  시장이 어떤 이야기에 반응하는지 보여줍니다.</p>

  <h3>교집합</h3>
  <p>'상승률 상위 20'과 '거래대금 상위 20'에 <strong>동시에</strong> 포함된 종목입니다. 많이 오른 데다 거래도 활발했다는 뜻으로,
  그날 시장의 관심이 가장 집중된 종목으로 볼 수 있습니다.</p>

  <h3>KOSPI / KOSDAQ</h3>
  <p>KOSPI는 대형 우량주 중심의 유가증권시장, KOSDAQ은 기술·성장 기업 중심의 시장입니다.
  두 지수의 등락은 전체 시장 분위기를 보여줍니다.</p>

  <h3>장세 (시장 상태)</h3>
  <p>시장 전반이 오르는 분위기인지(강세), 내리는 분위기인지(약세)를 나타냅니다.
  '자금집중형'은 소수 종목·섹터에만 돈이 몰리는 상태, 'ADL'은 오른 종목과 내린 종목의 비율로 시장의 폭을 보는 지표입니다.</p>
</div>""",
        base="")

    pages["sectors.html"] = page(
        "주도 섹터란 무엇인가 | 한국주식 데이터 리포트",
        "주식 시장의 주도 섹터(테마) 개념과 이를 살펴보는 이유 설명",
        "sectors.html",
        """<div class="card">
  <h1>주도 섹터란 무엇인가</h1>
  <p class="lead">시장을 종목 하나하나가 아니라 '무리'로 보는 관점입니다.</p>

  <p>주식 시장에서 돈은 보통 한 종목에만 흐르지 않습니다. 비슷한 사업을 하는 기업들, 같은 이슈에 영향을 받는 기업들이
  <strong>함께 움직이는</strong> 경우가 많습니다. 이렇게 같이 묶이는 무리를 <strong>섹터</strong> 또는 <strong>테마</strong>라고 합니다.</p>

  <h3>왜 섹터를 보는가</h3>
  <p>개별 종목의 등락만 보면 우연인지 흐름인지 알기 어렵습니다. 하지만 같은 섹터의 여러 종목이 동시에 오른다면,
  그 배경에 공통된 이유(정책, 실적, 글로벌 이슈 등)가 있을 가능성이 큽니다.
  그래서 '오늘 어떤 섹터에 자금이 몰렸는가'를 보면 시장이 어떤 이야기에 반응하는지 파악할 수 있습니다.</p>

  <h3>주도 섹터의 특징</h3>
  <ul>
    <li>섹터 내 여러 종목이 함께 상승</li>
    <li>해당 섹터의 거래대금 비중이 평소보다 큼</li>
    <li>대표 종목이 시장 전체 상승을 이끄는 경우가 많음</li>
  </ul>

  <h3>주의할 점</h3>
  <p>주도 섹터는 그날의 결과를 정리한 것일 뿐, 내일도 같은 흐름이 이어진다는 보장은 없습니다.
  테마는 빠르게 바뀌며, 뒤늦게 따라가면 손실을 볼 수 있습니다.
  이 사이트의 섹터 정보는 <strong>시장을 이해하기 위한 참고 자료</strong>이며 매매 신호가 아닙니다.</p>
  <div class="disclaimer">본 페이지는 교육·정보 제공 목적이며 특정 종목·섹터의 투자를 권유하지 않습니다.</div>
</div>""",
        base="")

    pages["about.html"] = page(
        "사이트 소개 | 한국주식 데이터 리포트",
        "한국주식 데이터 리포트 사이트의 목적, 데이터 출처, 운영 방식 안내",
        "about.html",
        """<div class="card">
  <h1>사이트 소개</h1>
  <p class="lead">공개 시장 데이터를, 매일, 읽기 쉽게.</p>

  <h3>무엇을 하는 사이트인가요</h3>
  <p>한국주식 데이터 리포트는 매 거래일 장 마감 후 한국 증시(KOSPI·KOSDAQ)의 공개 데이터를 자동으로 정리해 보여주는
  정보 사이트입니다. 거래대금 상위 종목, 당일 상승률 상위 종목, 자금이 몰린 주도 섹터, 상한가 종목 등을 한 페이지에 모았습니다.</p>

  <h3>데이터는 어디서 오나요</h3>
  <p>모든 수치는 한국거래소와 증권 포털 등에서 누구나 확인할 수 있는 공개 시장 데이터에 기반합니다.
  내부 분석 자료나 비공개 정보, 종목 추천은 포함하지 않습니다.</p>

  <h3>어떻게 만들어지나요</h3>
  <p>매 거래일 저녁, 자동화된 스크립트가 그날의 시장 데이터를 수집·정리해 페이지로 발행합니다.
  사람이 종목을 고르거나 의견을 더하지 않으며, 기계적으로 집계된 데이터만 제공합니다.</p>

  <h3>무엇을 하지 않나요</h3>
  <p>이 사이트는 특정 종목의 매수·매도를 권유하지 않고, 수익을 보장하지 않으며, 유료 리딩이나 종목 추천을 하지 않습니다.
  제공되는 정보는 투자 판단을 위한 참고 자료일 뿐입니다.</p>

  <h3>문의</h3>
  <p>사이트 관련 문의는 이메일로 받습니다: <a href="mailto:sunflowerofmine@gmail.com">sunflowerofmine@gmail.com</a></p>
</div>""",
        base="")

    pages["disclaimer.html"] = page(
        "면책조항 | 한국주식 데이터 리포트",
        "투자 정보 제공 및 책임 한계에 관한 면책조항",
        "disclaimer.html",
        """<div class="card">
  <h1>면책조항</h1>
  <p class="lead">투자 판단과 책임은 전적으로 이용자 본인에게 있습니다.</p>

  <h3>정보 제공 목적</h3>
  <p>본 사이트가 제공하는 모든 콘텐츠는 공개된 시장 데이터를 정리한 <strong>정보 제공 목적</strong>의 자료입니다.
  특정 종목이나 금융상품의 매수·매도를 권유하거나 추천하는 것이 아닙니다.</p>

  <h3>수익 보장 없음</h3>
  <p>본 사이트의 정보를 이용한 투자로 발생하는 손익에 대해 사이트 운영자는 어떠한 책임도 지지 않습니다.
  과거의 시장 데이터나 흐름이 미래의 수익을 보장하지 않습니다.</p>

  <h3>데이터 정확성</h3>
  <p>데이터는 수집 시점을 기준으로 자동 정리되며, 수집·가공 과정에서 오류나 지연, 누락이 있을 수 있습니다.
  운영자는 정보의 정확성·완전성·적시성을 보증하지 않습니다. 실제 투자 전에는 반드시 공식 출처(한국거래소, 증권사 등)에서
  원본 데이터를 확인하시기 바랍니다.</p>

  <h3>투자 책임</h3>
  <p>모든 투자 결정은 이용자 본인의 판단과 책임하에 이루어져야 합니다. 투자에는 원금 손실의 위험이 따릅니다.</p>
</div>""",
        base="")

    pages["privacy.html"] = page(
        "개인정보처리방침 | 한국주식 데이터 리포트",
        "개인정보 수집·이용 및 쿠키, 광고에 관한 처리방침",
        "privacy.html",
        """<div class="card">
  <h1>개인정보처리방침</h1>
  <p class="lead">본 사이트는 회원가입 없이 이용할 수 있으며, 직접적인 개인정보를 수집하지 않습니다.</p>

  <h3>1. 수집하는 정보</h3>
  <p>본 사이트는 이름, 이메일, 전화번호 등 개인을 식별할 수 있는 정보를 직접 수집하지 않습니다.
  로그인이나 회원가입 절차가 없습니다.</p>

  <h3>2. 쿠키 및 접속 정보</h3>
  <p>방문 통계 분석과 광고 제공을 위해 쿠키(cookie)가 사용될 수 있습니다. 쿠키는 브라우저 설정에서 거부하거나 삭제할 수 있습니다.</p>

  <h3>3. 광고 (Google AdSense)</h3>
  <p>본 사이트는 제3자 광고 제공업체인 Google의 AdSense를 사용할 수 있습니다. Google을 포함한 제3자 광고 사업자는
  쿠키를 사용하여 이용자의 방문 기록에 기반한 광고를 게재할 수 있습니다. 이용자는
  <a href="https://policies.google.com/technologies/ads" rel="nofollow noopener" target="_blank">Google 광고 설정</a>에서
  맞춤 광고를 거부할 수 있습니다.</p>

  <h3>4. 제3자 제공</h3>
  <p>본 사이트는 이용자의 개인정보를 제3자에게 판매하거나 제공하지 않습니다.</p>

  <h3>5. 문의</h3>
  <p>개인정보 관련 문의: <a href="mailto:sunflowerofmine@gmail.com">sunflowerofmine@gmail.com</a></p>

  <p class="small muted">본 방침은 사이트 운영 정책에 따라 변경될 수 있으며, 변경 시 본 페이지에 반영됩니다.</p>
</div>""",
        base="")

    return pages


# ────────────────────────── main ──────────────────────────
def write(path, content):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  wrote: {path}")


def load_all_data():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")), reverse=True)
    out = []
    for f in files:
        with open(f, encoding="utf-8") as fp:
            out.append(json.load(fp))
    return out


def main():
    kst = timezone(timedelta(hours=9))
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now(kst).strftime("%Y-%m-%d")
    print(f"[build] target date: {date}")

    html = fetch_dashboard(date)
    if html:
        data = parse(html, date)
        if data["value"] or data["sectors"]:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(os.path.join(DATA_DIR, f"{date}.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            write(f"reports/{date}.html", build_report_page(data))
            print(f"  parsed: 거래대금 {len(data['value'])} / 섹터 {len(data['sectors'])} / 상한가 {len(data['halt'])}")
        else:
            print("  파싱 결과 없음 — 리포트 생략")
    else:
        print(f"  {date} 대시보드 없음 (휴장일 가능) — 데이터 페이지 생략")

    all_data = load_all_data()
    write("index.html", build_home(all_data))
    write("reports/index.html", build_archive(all_data))
    for name, content in build_static_pages().items():
        write(name, content)
    print("[build] done")


if __name__ == "__main__":
    main()
