# DSS 검수 시스템

어닝콜 원문과 DSS(Daily Stock Summary) 요약본을 비교하여 수치 오류, 문맥 이슈를 자동으로 검증하는 AI 기반 웹 검수 시스템입니다.

## 🌟 주요 기능

- **자동 검증**: Claude AI를 사용하여 DSS 문장을 하나씩 검증
- **수치 불일치 탐지**: 어닝콜 원문과 DSS의 숫자, 단위 불일치 자동 탐지
- **문맥 이슈 검출**: 과장, 축소, 누락된 정보 감지
- **실시간 수정**: 승인, 거부, 수동 편집 기능
- **최종 수정안 생성**: DSS 형식으로 최종 수정안 자동 생성
- **직관적인 웹 UI**: Bootstrap 5 기반의 사용하기 쉬운 인터페이스

## 📋 검증 항목

### 수치 이슈 (빨간색 ❌)
- 매출, 이익, 가이던스 등의 숫자 불일치
- 단위 오류 (억원 vs 조원)
- 기간 정보 오류

### 문맥 이슈 (노란색 ⚠️)
- 과장 또는 축소된 표현
- 조건 누락 (단서 조항 생략)
- 불완전한 정보

### 일치함 (초록색 ✅)
- 어닝콜 원문과 일치하는 정확한 문장

## 🚀 설치 및 실행

### 1. 저장소 클론

\`\`\`bash
git clone https://github.com/your-username/dss-validation-system.git
cd dss-validation-system
\`\`\`

### 2. Python 가상환경 생성 (권장)

\`\`\`bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
\`\`\`

### 3. 패키지 설치

\`\`\`bash
pip install -r requirements.txt
\`\`\`

### 4. 환경변수 설정

\`.env.example\` 파일을 복사하여 \`.env\` 파일 생성:

\`\`\`bash
# Windows
copy .env.example .env

# macOS/Linux
cp .env.example .env
\`\`\`

\`.env\` 파일을 열어 API 키 입력:

\`\`\`env
ANTHROPIC_API_KEY=your_actual_api_key_here
CLAUDE_MODEL=claude-3-haiku-20240307
MAX_TOKENS=4096
TEMPERATURE=0.0
DEBUG=False
\`\`\`

**API 키 발급**: [Anthropic Console](https://console.anthropic.com/)

### 5. 서버 실행

\`\`\`bash
python app.py
\`\`\`

브라우저에서 접속: **http://localhost:5000**

## 📁 프로젝트 구조

\`\`\`
dss-validation-system/
├── app.py                      # Flask 메인 애플리케이션
├── src/
│   └── financial_parser.py     # DSS 검증 로직
├── templates/
│   └── index_new.html          # 메인 UI
├── static/
│   └── js/
│       └── index_new.js        # 프론트엔드 로직
├── requirements.txt            # Python 패키지 목록
├── .env.example                # 환경변수 예시
├── .gitignore                  # Git 제외 파일 목록
└── README.md                   # 프로젝트 문서
\`\`\`

## 🌐 웹 배포

### Render.com 무료 배포

1. **requirements.txt에 gunicorn 추가**

\`\`\`bash
echo "gunicorn>=21.0.0" >> requirements.txt
\`\`\`

2. **GitHub에 코드 업로드**

\`\`\`bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/your-username/dss-validation-system.git
git push -u origin main
\`\`\`

3. **Render.com 계정 생성**
   - [Render.com](https://render.com) 접속
   - GitHub 계정으로 로그인

4. **새 Web Service 생성**
   - "New +" 버튼 클릭
   - "Web Service" 선택
   - GitHub 저장소 연결

5. **배포 설정**
   - **Name**: dss-validation-system
   - **Environment**: Python 3
   - **Build Command**: \`pip install -r requirements.txt\`
   - **Start Command**: \`gunicorn app:app\`
   - **Instance Type**: Free

6. **환경 변수 추가**
   - "Environment" 탭 클릭
   - Add Environment Variable:
     - Key: \`ANTHROPIC_API_KEY\`
     - Value: 본인의 API 키

7. **배포 시작**
   - "Create Web Service" 클릭
   - 5-10분 후 자동 배포 완료
   - 제공된 URL로 접속 가능

## 🎯 사용 방법

### 1. 파일 업로드
- **어닝콜 원문**: PDF URL 입력 또는 텍스트 직접 입력
- **DSS 요약본**: 텍스트 직접 입력 (### 섹션, ## 문장 형식)

### 2. 검증 결과 확인
- 섹션별로 이슈 확인 (실적발표, 가이던스, Q&A)
- 각 항목의 문제 유형 및 수정안 확인
- 좌측 사이드바에서 전체 항목 목록 확인

### 3. 수정안 승인/거부
- **승인 ✅**: 수정안 적용
- **거부 ❌**: 원본 유지
- **수동 ✏️**: 직접 편집

### 4. 최종 수정안
- "최종 수정안" 탭에서 결과 확인
- "전체 복사" 버튼으로 클립보드에 복사
- DSS 형식으로 자동 출력

### 5. 새로 시작하기
- 상단 "새로 시작하기" 버튼으로 초기화

## ⚙️ 환경변수

| 변수명 | 설명 | 기본값 | 필수 |
|--------|------|--------|------|
| \`ANTHROPIC_API_KEY\` | Claude API 키 | - | ✅ |
| \`CLAUDE_MODEL\` | 사용할 Claude 모델 | claude-3-haiku-20240307 | ❌ |
| \`MAX_TOKENS\` | 최대 토큰 수 | 4096 | ❌ |
| \`TEMPERATURE\` | AI 응답 다양성 (0.0-1.0) | 0.0 | ❌ |
| \`DEBUG\` | 디버그 모드 | False | ❌ |

## 🛠️ 기술 스택

- **Backend**: Python 3.8+, Flask 2.3+
- **AI**: Claude 3 Haiku (Anthropic API)
- **Frontend**: HTML5, JavaScript (ES6+), Bootstrap 5
- **파일 처리**: PyPDF2, pdfplumber, python-docx
- **배포**: Render.com, Gunicorn

## 🔍 주요 알고리즘

### 문장 분리
- 마침표(.) 기준으로 문장 분리
- 숫자 (예: 1.5조원) 구분 처리

### 수치 검증
- 어닝콜 원문에서 수치 추출
- DSS 문장의 수치와 비교
- 단위 자동 변환 및 비교

### JSON 파싱 에러 처리
- 제어 문자 자동 제거
- Trailing comma 자동 수정
- 불완전한 JSON 복구 시도

## 📊 API 사용량

Claude Haiku 기준:
- **입력**: 약 $0.25 / 1M tokens
- **출력**: 약 $1.25 / 1M tokens
- DSS 문장 1개당 평균 500 tokens 사용
- 50문장 검증 시 약 $0.05 예상

## 🔒 보안

- **API 키 보호**: .gitignore로 .env 파일 제외
- **환경변수**: 서버 환경변수로 안전하게 관리
- **HTTPS**: Render.com 자동 제공

## 📝 라이센스

MIT License

## 🤝 기여

이슈 및 PR 환영합니다!

1. Fork the Project
2. Create your Feature Branch (\`git checkout -b feature/AmazingFeature\`)
3. Commit your Changes (\`git commit -m 'Add some AmazingFeature'\`)
4. Push to the Branch (\`git push origin feature/AmazingFeature\`)
5. Open a Pull Request

## 📧 문의

문제가 발생하면 [Issues](https://github.com/your-username/dss-validation-system/issues)에 등록해주세요.

## 🙏 감사의 말

- Claude API by Anthropic
- Bootstrap 5
- Font Awesome

---

**최종 업데이트**: 2026-02-27
**버전**: 1.0.0
