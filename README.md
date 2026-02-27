# 어닝콜 DSS 자동 검수 시스템 (프로토타입)

Claude API를 활용하여 어닝콜 문서와 DSS 재무 데이터를 자동으로 비교하고 불일치를 감지하는 시스템입니다.

## 🎯 주요 기능

- **LLM 기반 텍스트 파싱**: Claude API로 비구조화 텍스트에서 재무 지표 자동 추출
- **지능형 매칭**: 항목명 유사도 기반 자동 매칭
- **불일치 감지**: 수치 비교 및 차이 분석
- **다국어 지원**: 한글/영문 어닝콜 문서 처리
- **유연한 출력**: 텍스트, 마크다운, JSON 형식 지원

## 📁 프로젝트 구조

```
.
├── main.py                           # 메인 실행 스크립트
├── src/
│   ├── financial_parser.py          # Claude API 기반 재무 데이터 파서
│   └── discrepancy_detector.py      # 불일치 감지 엔진
├── data/
│   ├── sample_earning_call_2024Q4.txt       # 샘플 어닝콜 문서 (한글)
│   ├── sample_earning_call_2024Q4_EN.txt    # 샘플 어닝콜 문서 (영문)
│   ├── sample_dss_data_2024Q4.txt           # 샘플 DSS 데이터 (한글)
│   └── SAMPLE_DATA_README.md                # 샘플 데이터 설명
├── output/                           # 결과 출력 디렉토리
├── requirements.txt                  # Python 의존성
├── .env.example                      # 환경 변수 예시
└── README.md                         # 본 문서
```

## 🚀 시작하기

### 1. 필수 요구사항

- Python 3.8 이상
- Anthropic API Key (Claude API 접근)

### 2. 설치

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경 변수 설정
cp .env.example .env

# 3. .env 파일 편집하여 API 키 입력
# ANTHROPIC_API_KEY=your_api_key_here
```

### 3. API 키 발급

1. [Anthropic Console](https://console.anthropic.com/)에 가입
2. API Keys 메뉴에서 새 키 생성
3. `.env` 파일에 키 입력

## 💻 사용법

### 기본 사용

```bash
python main.py --earning-call data/sample_earning_call_2024Q4.txt --dss data/sample_dss_data_2024Q4.txt
```

### 결과를 파일로 저장

```bash
python main.py \
  -e data/sample_earning_call_2024Q4.txt \
  -d data/sample_dss_data_2024Q4.txt \
  -o output/report.md \
  --format markdown
```

### 영문 어닝콜 문서 처리

```bash
python main.py \
  -e data/sample_earning_call_2024Q4_EN.txt \
  -d data/sample_dss_data_2024Q4.txt
```

### 파싱된 데이터 저장 (디버깅용)

```bash
python main.py \
  -e data/sample_earning_call_2024Q4.txt \
  -d data/sample_dss_data_2024Q4.txt \
  --save-parsed \
  --debug
```

이 명령은 `output/parsed_earning_call.json`과 `output/parsed_dss.json` 파일을 생성합니다.

## 📊 출력 예시

### 텍스트 형식 (기본)

```
================================================================================
                      어닝콜 vs DSS 데이터 검수 결과
================================================================================

[ 요약 통계 ]
  총 어닝콜 항목: 28개
  총 DSS 항목: 28개
  ✅ 일치: 26개
  ⚠️  불일치: 2개
  📌 어닝콜에만 존재: 0개
  📌 DSS에만 존재: 0개
  매칭률: 92.9%

================================================================================
                    ⚠️  불일치 항목 상세 (2건)
================================================================================

[1] 영업이익 (2024-Q4)
  📄 어닝콜 원본: 185.00 억원
     문맥: "영업이익은 185억원을 기록하여 전년 동기 대비 22.5% 증가했으며..."
  📊 DSS 데이터: 178.00 억원
     문맥: "영업이익은 1,780억원으로써 전분기 대비 8.2% 증가했으며..."
  ⚖️  차이: -7.00 억원 (-3.78%)
  🎯 항목 유사도: 100.0%

[2] 광고선전비 (2024-Q4)
  📄 어닝콜 원본: 45.00 억원
     문맥: "광고선전비는 45억원, 감가상각비는 67억원이 발생했습니다..."
  📊 DSS 데이터: 52.00 억원
     문맥: "광고선전비는 520억원으로 브랜드 마케팅에 적극 투자했습니다..."
  ⚖️  차이: +7.00 억원 (+15.56%)
  🎯 항목 유사도: 100.0%
```

## 🔧 명령줄 옵션

```
usage: main.py [-h] -e EARNING_CALL -d DSS [-o OUTPUT] [-f {text,markdown,json}]
               [-t THRESHOLD] [--save-parsed] [--debug]

옵션:
  -h, --help            도움말 표시
  -e, --earning-call    어닝콜 문서 파일 경로 (필수)
  -d, --dss             DSS 데이터 파일 경로 (필수)
  -o, --output          결과 출력 파일 경로
  -f, --format          출력 형식 (text/markdown/json)
  -t, --threshold       불일치 판단 임계값 (기본값: 0.01 = 1%)
  --save-parsed         파싱된 데이터를 JSON으로 저장
  --debug               디버그 모드 활성화
```

## 🧪 테스트

샘플 데이터로 시스템을 테스트해보세요:

```bash
# 한글 문서 테스트
python main.py -e data/sample_earning_call_2024Q4.txt -d data/sample_dss_data_2024Q4.txt

# 영문 문서 테스트
python main.py -e data/sample_earning_call_2024Q4_EN.txt -d data/sample_dss_data_2024Q4.txt

# 마크다운 보고서 생성
python main.py -e data/sample_earning_call_2024Q4.txt -d data/sample_dss_data_2024Q4.txt \
  -o output/report.md --format markdown

# JSON 결과 생성
python main.py -e data/sample_earning_call_2024Q4.txt -d data/sample_dss_data_2024Q4.txt \
  -o output/result.json --format json
```

## 🛠️ 기술 스택

- **LLM**: Claude 3.5 Sonnet (Anthropic API)
- **언어**: Python 3.8+
- **주요 라이브러리**:
  - `anthropic`: Claude API SDK
  - `python-dotenv`: 환경 변수 관리
  - `pandas`: 데이터 처리 (옵션)

## 📝 작동 원리

### 1. 텍스트 파싱
Claude API에 프롬프트를 전송하여 텍스트에서 재무 지표 추출:
- 항목명 (예: "매출액", "영업이익")
- 금액 (예: 1,250, 185)
- 단위 (예: "억원", "%")
- 기간 (예: "2024-Q4")
- 원문 문맥

### 2. 데이터 정규화
- 단위 통일: "1,780억원" → 178 (억원 기준)
- 항목명 표준화: "영업익" → "영업이익"
- 기간 표준화: "4분기" → "2024-Q4"

### 3. 매칭
- 기간이 같은 항목끼리 비교
- 항목명 유사도 계산 (문자열 유사도)
- 최고 유사도 항목과 매칭

### 4. 불일치 감지
- 값 차이 계산
- 임계값(기본 1%) 초과 시 불일치로 판단
- 차이 금액 및 비율 리포트

## 🎯 알려진 제한사항

- **PDF 지원**: 현재 버전은 텍스트 파일만 지원, PDF는 추후 추가 예정
- **표/이미지**: 복잡한 표나 이미지 내 텍스트는 처리 불가
- **API 비용**: Claude API 호출 시 비용 발생 (토큰 사용량에 따라)
- **처리 속도**: LLM 호출로 인해 CSV 파싱 대비 느림

## 🚧 개발 로드맵

### MVP (현재)
- [x] LLM 기반 텍스트 파싱
- [x] 기본 매칭 및 불일치 감지
- [x] 텍스트/마크다운 보고서

### P1 (다음 단계)
- [ ] Claude Skills 통합
- [ ] RAG 기반 검색 기능
- [ ] 웹 UI 개발
- [ ] PDF 파일 지원

### P2 (향후)
- [ ] 대시보드 및 이력 관리
- [ ] 실시간 모니터링
- [ ] 다중 문서 배치 처리

## 📄 라이선스

이 프로젝트는 프로토타입이며 교육 및 평가 목적으로 제작되었습니다.

## 🤝 기여

프로토타입 단계이므로 기여는 제한적입니다. 이슈 및 제안은 환영합니다.

## 📧 문의

문의사항이 있으시면 이슈를 등록해주세요.

---

**생성일**: 2026-02-10
**버전**: 0.1.0 (Prototype)
**기반**: PRD/TRD 문서
