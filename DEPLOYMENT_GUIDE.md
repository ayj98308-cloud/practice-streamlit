# 배포 가이드

이 문서는 DSS 검수 시스템을 GitHub에 업로드하고 Render.com에 배포하는 전체 과정을 안내합니다.

## 📋 사전 준비

### 1. GitHub 계정
- [GitHub](https://github.com)에서 계정 생성
- Git 설치: https://git-scm.com/downloads

### 2. Render.com 계정
- [Render.com](https://render.com) 접속
- GitHub 계정으로 로그인 (권장)

### 3. API 키 확인
- Anthropic API 키 확인: https://console.anthropic.com/

## 🚀 단계별 배포 가이드

### Step 1: Git 저장소 초기화

프로젝트 폴더에서 터미널(cmd 또는 PowerShell) 실행:

```bash
cd "c:\Users\USER\Desktop\AI Work+\바이브코딩 실습"

# Git 저장소 초기화
git init

# 모든 파일 스테이징 (.gitignore에 의해 .env는 자동 제외됨)
git add .

# 커밋 생성
git commit -m "Initial commit: DSS validation system"

# 기본 브랜치를 main으로 설정
git branch -M main
```

**중요**: `.env` 파일은 자동으로 제외됩니다 (.gitignore에 정의됨)

### Step 2: GitHub 저장소 생성

1. **GitHub 웹사이트 접속**
   - https://github.com 로그인
   - 우측 상단 "+" 버튼 클릭
   - "New repository" 선택

2. **저장소 정보 입력**
   - **Repository name**: `dss-validation-system` (원하는 이름)
   - **Description**: DSS 검수 시스템
   - **Public** 또는 **Private** 선택
   - ❌ "Initialize with README" 체크 해제 (이미 README가 있음)
   - "Create repository" 클릭

3. **원격 저장소 연결**

GitHub에서 제공하는 명령어 복사 또는 아래 명령어 사용:

```bash
# your-username을 본인의 GitHub 사용자명으로 변경
git remote add origin https://github.com/your-username/dss-validation-system.git

# 코드 업로드
git push -u origin main
```

**첫 push 시 로그인 요구**:
- GitHub 사용자명 입력
- Password 대신 **Personal Access Token** 입력
  - Token 생성: GitHub → Settings → Developer settings → Personal access tokens → Generate new token
  - 필요한 권한: `repo` 체크

### Step 3: Render.com 배포

1. **Render.com 로그인**
   - https://render.com 접속
   - "Get Started" 또는 "Sign In" 클릭
   - GitHub 계정으로 로그인 (권장)

2. **GitHub 연동**
   - Render가 GitHub 저장소 접근 권한 요청
   - "Authorize Render" 클릭
   - 배포할 저장소 선택

3. **새 Web Service 생성**
   - Dashboard에서 "New +" 버튼 클릭
   - "Web Service" 선택
   - GitHub 저장소 목록에서 `dss-validation-system` 선택
   - "Connect" 클릭

4. **서비스 설정**

아래 정보 입력:

| 항목 | 값 |
|------|-----|
| **Name** | dss-validation-system |
| **Region** | Singapore (또는 가까운 지역) |
| **Branch** | main |
| **Root Directory** | (비워두기) |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app` |
| **Instance Type** | **Free** |

5. **환경 변수 추가**

"Environment Variables" 섹션에서:
- "Add Environment Variable" 클릭
- **Key**: `ANTHROPIC_API_KEY`
- **Value**: 본인의 Anthropic API 키 입력
- "Add" 클릭

추가 환경변수 (선택사항):
```
CLAUDE_MODEL=claude-3-haiku-20240307
MAX_TOKENS=4096
TEMPERATURE=0.0
DEBUG=False
```

6. **배포 시작**
   - "Create Web Service" 버튼 클릭
   - 빌드 로그 확인 (5-10분 소요)
   - "Your service is live" 메시지 확인

7. **배포 URL 확인**
   - 상단에 표시된 URL 복사
   - 예: `https://dss-validation-system.onrender.com`
   - 브라우저에서 접속하여 확인

## ✅ 배포 완료 확인

1. **웹사이트 접속**
   - Render에서 제공한 URL 접속
   - 업로드 화면이 정상적으로 표시되는지 확인

2. **기능 테스트**
   - 테스트 데이터로 검증 실행
   - 결과가 정상적으로 표시되는지 확인

## 🔄 코드 업데이트 (재배포)

코드 수정 후 재배포:

```bash
# 변경사항 확인
git status

# 변경된 파일 스테이징
git add .

# 커밋
git commit -m "Update: 설명"

# GitHub에 푸시
git push origin main
```

**자동 배포**: GitHub에 푸시하면 Render가 자동으로 재배포합니다.

## 🐛 문제 해결

### 빌드 실패

**로그 확인**:
- Render Dashboard → Logs 탭
- 에러 메시지 확인

**일반적인 문제**:
1. **requirements.txt 오류**
   - 패키지 버전 충돌 확인
   - Python 버전 호환성 확인

2. **환경변수 누락**
   - `ANTHROPIC_API_KEY` 설정 확인
   - 환경변수 값 오타 확인

3. **Start Command 오류**
   - `gunicorn app:app` 확인
   - app.py 파일 존재 확인

### 배포 후 500 에러

**로그 확인**:
```bash
# Render Dashboard → Logs에서 에러 확인
```

**일반적인 원인**:
1. API 키 오류
2. 모델 접근 권한 없음
3. 파일 경로 오류

## 💡 팁

### 무료 플랜 제한
- **자동 슬립**: 15분 동안 요청 없으면 슬립 모드
- **첫 요청 느림**: 슬립에서 깨어나는 데 30초-1분 소요
- **월 사용 시간**: 750시간 제한

### 비용 절감
- Claude Haiku 모델 사용 (가장 저렴)
- MAX_TOKENS=4096으로 제한
- TEMPERATURE=0.0으로 일관성 향상

### 프로덕션 권장사항
- **유료 플랜**: $7/month (슬립 없음, 빠른 속도)
- **커스텀 도메인**: 본인 도메인 연결 가능
- **백업**: GitHub에 정기적으로 커밋

## 📞 지원

### Render.com 지원
- 문서: https://render.com/docs
- 커뮤니티: https://community.render.com

### GitHub 도움말
- 문서: https://docs.github.com
- Git 가이드: https://git-scm.com/book/ko/v2

## 🎉 배포 완료!

축하합니다! DSS 검수 시스템이 웹에 배포되었습니다.

배포 URL을 다른 사람들과 공유하여 사용할 수 있습니다.

---

**작성일**: 2026-02-27
**난이도**: 초급-중급
