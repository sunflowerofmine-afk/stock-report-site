# CLAUDE.md — stock-report-site

## 프로젝트 개요

한국 개인투자자 대상 공개 데이터 리포트 사이트.
`korea-close-betting-bot` (종가베팅 봇)이 매일 자동 생성하는 시장 데이터를 외부 공개용으로 배포.

**핵심 목적:** 수익화 검증 (1차: 트래픽·반응 확인 → 장기: 애드센스)
**타겟:** 한국 개인 주식 투자자
**포지션:** 종목 추천 ❌ / 데이터 기반 시장 정보 제공 ✓

## 봇과의 연결 구조

```
korea-close-betting-bot (별도 레포)
  └── scripts/public_report.py  ← 공개 HTML 생성
          └── pipeline.py에서 호출
                  └── public_site/reports/YYYY-MM-DD.html 생성
                          └── 이 레포(stock-report-site)로 자동 push
                                  └── Cloudflare Pages 자동 배포
                                          └── stock-report-site.pages.dev
```

배포 재활성화 방법: `korea-close-betting-bot/.github/workflows/run_bot.yml`에서 `if: false` 한 줄 삭제 (현재 프론트엔드 작업 중이라 일시 중단)

## 파일 구조

```
stock-report-site/
  index.html          ← 리포트 목록 (봇이 자동 생성)
  reports/
    YYYY-MM-DD.html   ← 일별 리포트 (봇이 자동 생성)
```

HTML은 봇이 자동 생성하므로 이 레포에서 직접 편집하지 않음.
프론트엔드 변경은 `korea-close-betting-bot/scripts/public_report.py`에서 수행.

## 공개 페이지에 포함하는 것 / 하지 않는 것

| 포함 | 제외 |
|---|---|
| 시장 요약 (KOSPI/KOSDAQ/장세) | 핵심·관심 후보 종목 진입가·점수 |
| 주도 섹터 + 구성 종목명 | 수급 데이터 (기관/외국인) |
| 거래대금 상위 20 종목 | 체크리스트·패턴 분류 |
| 교육 레이어 (짧은 맥락 설명) | 백테스트 복기 |
| 면책조항 | |

종목명은 공개 가능 (네이버 금융 등 공개 데이터 기반). 단 투자 권유로 보이지 않게 면책조항 필수.

## 사용자 선호도

- 답변은 간결하게. 요약 블록, 긴 설명 불필요
- 이모지 사용 금지
- 코드 변경은 외과적으로 — 요청한 것만, 인접 코드 건드리지 않음
- 과설계 금지 (로그인, DB, React, 실시간 API 불필요)
- 작업 전 가정을 명시하고 불확실하면 질문

## 개발 원칙

- 정적 HTML/CSS 우선 — JS는 꼭 필요할 때만
- SEO 최적화 (한국어 키워드, meta 태그, canonical)
- 모바일 반응형 필수
- 외부 CDN 의존성 최소화 (빠른 로딩)
- 면책조항 항상 유지

## 배포

- Cloudflare Pages: `stock-report-site.pages.dev`
- main 브랜치 push → 자동 배포
- 빌드 명령 없음 (순수 정적 HTML)
