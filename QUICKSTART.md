# 빠른 시작 가이드

## 🚀 5분 안에 시작하기

### 1단계: API 키 설정 (2분)

```bash
# .env 파일 생성
cp .env.example .env
```

`.env` 파일을 편집하고 Anthropic API 키를 입력하세요:

```bash
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxx
```

API 키가 없다면:
1. [Anthropic Console](https://console.anthropic.com/) 방문
2. 계정 생성 및 로그인
3. API Keys 메뉴에서 키 생성
4. 키 복사하여 `.env` 파일에 붙여넣기

### 2단계: 의존성 설치 (1분)

```bash
pip install -r requirements.txt
```

### 3단계: 샘플 데이터로 테스트 (2분)

```bash
python main.py \
  --earning-call data/sample_earning_call_2024Q4.txt \
  --dss data/sample_dss_data_2024Q4.txt
```

### 예상 결과

```
================================================================================
                      어닝콜 vs DSS 데이터 검수 결과
================================================================================

[ 요약 통계 ]
  총 어닝콜 항목: 28개
  총 DSS 항목: 28개
  ✅ 일치: 26개
  ⚠️  불일치: 2개
  매칭률: 92.9%

================================================================================
                    ⚠️  불일치 항목 상세 (2건)
================================================================================

[1] 영업이익 (2024-Q4)
  📄 어닝콜 원본: 185.00 억원
  📊 DSS 데이터: 178.00 억원
  ⚖️  차이: -7.00 억원 (-3.78%)

[2] 광고선전비 (2024-Q4)
  📄 어닝콜 원본: 45.00 억원
  📊 DSS 데이터: 52.00 억원
  ⚖️  차이: +7.00 억원 (+15.56%)
```

### 4단계: 실제 데이터로 사용

```bash
python main.py \
  -e path/to/your/earning_call.txt \
  -d path/to/your/dss_data.txt \
  -o output/report.md \
  --format markdown
```

## 💡 유용한 명령어

### 디버그 모드로 실행

```bash
python main.py \
  -e data/sample_earning_call_2024Q4.txt \
  -d data/sample_dss_data_2024Q4.txt \
  --debug \
  --save-parsed
```

파싱된 JSON 데이터를 확인하려면:
- `output/parsed_earning_call.json` - 어닝콜 추출 데이터
- `output/parsed_dss.json` - DSS 추출 데이터

### 영문 문서 처리

```bash
python main.py \
  -e data/sample_earning_call_2024Q4_EN.txt \
  -d data/sample_dss_data_2024Q4.txt
```

### 마크다운 보고서 생성

```bash
python main.py \
  -e data/sample_earning_call_2024Q4.txt \
  -d data/sample_dss_data_2024Q4.txt \
  -o output/report.md \
  --format markdown
```

## 🔧 문제 해결

### "ANTHROPIC_API_KEY가 설정되지 않았습니다" 오류

→ `.env` 파일에 API 키가 제대로 설정되었는지 확인하세요.

```bash
# .env 파일 확인
cat .env

# 출력 예시:
# ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxx
```

### "모듈을 찾을 수 없습니다" 오류

→ 의존성을 설치하세요:

```bash
pip install -r requirements.txt
```

### Claude API 호출 오류

→ API 키가 유효한지, 크레딧이 충분한지 확인하세요:
- [Anthropic Console](https://console.anthropic.com/) → Usage 메뉴 확인

### 파싱 결과가 예상과 다름

→ 디버그 모드로 실행하여 Claude의 응답을 확인하세요:

```bash
python main.py \
  -e your_file.txt \
  -d your_dss.txt \
  --debug \
  --save-parsed
```

## 📚 더 알아보기

- [README.md](README.md) - 전체 문서
- [SAMPLE_DATA_README.md](SAMPLE_DATA_README.md) - 샘플 데이터 설명
- [PRD/TRD](어닝콜+요약+검수_안예진.txt) - 프로젝트 요구사항

## 🎯 다음 단계

프로토타입 검증 후:
1. 실제 어닝콜 문서와 DSS 데이터로 테스트
2. 불일치 감지 정확도 평가
3. Claude Skills 통합 (P1)
4. 웹 UI 개발 (P1)

## 💬 피드백

이슈나 개선 제안이 있으시면 알려주세요!

---
**프로토타입 버전**: 0.1.0
