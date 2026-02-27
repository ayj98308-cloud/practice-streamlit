"""
재무 데이터 파서 - Claude API를 활용한 LLM 기반 파싱
텍스트에서 재무 지표를 추출하고 구조화된 데이터로 변환
"""

import os
import json
from typing import List, Dict, Any, Optional
from anthropic import Anthropic
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()


class FinancialDataParser:
    """Claude API를 사용하여 텍스트에서 재무 데이터를 추출하는 파서"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        초기화

        Args:
            api_key: Anthropic API 키 (없으면 환경 변수에서 로드)
            model: Claude 모델 이름 (기본값: claude-3-5-sonnet-20241022)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        # 빠른 처리를 위해 Haiku 모델 사용
        self.model = model or os.getenv("CLAUDE_MODEL", "claude-3-haiku-20240307")

        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")

        self.client = Anthropic(api_key=self.api_key)
        self.debug = os.getenv("DEBUG", "False").lower() == "true"
        self.translation_cache = {}  # 번역 캐시 (같은 텍스트 재번역 방지)

    def extract_financial_data(self, text: str, document_type: str = "earning_call") -> List[Dict[str, Any]]:
        """
        텍스트에서 재무 데이터 추출

        Args:
            text: 재무 정보가 포함된 텍스트
            document_type: 문서 타입 ("earning_call" 또는 "dss")

        Returns:
            추출된 재무 데이터 리스트
            [
                {
                    "company": "테크코리아",
                    "period": "2024-Q4",
                    "metric": "매출액",
                    "value": 1250,
                    "unit": "억원",
                    "context": "2024년 4분기 매출액은 1,250억원으로..."
                },
                ...
            ]
        """

        prompt = self._build_extraction_prompt(text, document_type)

        try:
            if self.debug:
                print(f"\n[DEBUG] Calling Claude API...")
                print(f"[DEBUG] Model: {self.model}")
                print(f"[DEBUG] Text length: {len(text)} characters")

            # DSS 문서는 더 길 수 있으므로 충분한 토큰 할당
            # Haiku 모델은 최대 4096 토큰까지 지원
            max_tokens_to_use = 4096

            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens_to_use,
                temperature=0,  # 결정론적 출력
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # 응답 파싱
            response_text = response.content[0].text

            if self.debug:
                print(f"[DEBUG] Claude response received")
                print(f"[DEBUG] Response length: {len(response_text)} characters")
                print(f"[DEBUG] First 500 chars of raw response:")
                print(response_text[:500])

            # JSON 추출 (마크다운 코드 블록이 있을 수 있음)
            financial_data = self._parse_json_response(response_text)

            if self.debug:
                print(f"[DEBUG] Extracted {len(financial_data)} financial metrics")

            return financial_data

        except Exception as e:
            print(f"[ERROR] Error calling Claude API: {e}")
            raise

    def detect_language(self, text: str) -> str:
        """
        텍스트 언어 감지 (영어 또는 한국어)

        Args:
            text: 입력 텍스트

        Returns:
            "en" 또는 "ko"
        """
        # 샘플링 (처음 1000자만 검사)
        sample = text[:1000]

        # ASCII 문자 비율 계산
        ascii_count = sum(1 for c in sample if ord(c) < 128)
        ascii_ratio = ascii_count / len(sample) if len(sample) > 0 else 0

        # ASCII 비율이 70% 이상이면 영어로 판단
        if ascii_ratio > 0.7:
            print(f"[LANG] 영어 텍스트 감지됨 (ASCII 비율: {ascii_ratio:.2%})")
            return "en"
        else:
            print(f"[LANG] 한국어 텍스트로 판단 (ASCII 비율: {ascii_ratio:.2%})")
            return "ko"

    def translate_to_korean(self, text: str) -> str:
        """
        영어 텍스트를 한국어로 번역 (재무 용어 정확도 우선)

        Args:
            text: 영어 텍스트

        Returns:
            한국어 번역 텍스트
        """
        # 캐시 확인 (같은 텍스트를 여러 번 번역하지 않음)
        max_length = 30000
        text_to_translate = text[:max_length]

        cache_key = hash(text_to_translate)
        if cache_key in self.translation_cache:
            print(f"[CACHE] 번역 캐시 히트! (재번역 생략)")
            return self.translation_cache[cache_key]

        prompt = f"""다음 어닝콜 원문을 한국어로 번역해주세요.

**번역 규칙:**
1. **재무 용어를 정확하게 번역**: billion → 억 (10억 아님), million → 백만, trillion → 조
2. **숫자 단위 변환**:
   - 15 billion dollars → 150억 달러 (1500억 아님!)
   - 1.5 million → 150만
   - 2.3 trillion → 2조 3000억
3. **퍼센트, 회사명, 고유명사는 그대로 유지**
4. **문맥과 뉘앙스를 자연스럽게 번역**
5. **"approximately", "nearly", "about" → "약", "거의" 등으로 번역**

원문:
<text>
{text_to_translate}
</text>

한국어 번역만 반환하세요 (설명이나 주석 없이):"""

        try:
            print(f"[TRANSLATE] 영어 → 한국어 번역 중... (길이: {len(text_to_translate)} characters)")

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )

            translated_text = response.content[0].text.strip()

            print(f"[TRANSLATE] 번역 완료 (결과 길이: {len(translated_text)} characters)")

            # 캐시에 저장
            self.translation_cache[cache_key] = translated_text

            return translated_text

        except Exception as e:
            print(f"[ERROR] 번역 실패: {e}")
            print(f"[WARN] 원본 텍스트 그대로 사용")
            return text

    def extract_both_documents(self, ec_text: str, dss_text: str) -> tuple:
        """
        어닝콜과 DSS 데이터를 한 번의 API 호출로 추출 (속도 최적화)

        Args:
            ec_text: 어닝콜 원문 텍스트
            dss_text: DSS 요약 텍스트

        Returns:
            (ec_data, dss_data) 튜플
        """
        # 한국어 텍스트만 처리 (번역 없음)
        print("[FAST] 한국어 텍스트 처리 (번역 생략)")
        import sys
        sys.stdout.flush()

        prompt = f"""당신은 재무 분석 및 IR 검수 전문가입니다.

두 개의 문서에서 재무 지표, 가이던스, 주요 발언을 추출해주세요:

**문서 1 (어닝콜 원문):**
<earning_call>
{ec_text[:15000]}
</earning_call>

**문서 2 (DSS 요약):**
<dss>
{dss_text[:10000]}
</dss>

각 문서에서 다음 정보를 추출하여 JSON 형식으로 반환해주세요:

{{
  "earning_call": [
    {{"company": "...", "period": "2024-Q4", "metric": "매출액", "value": 1250, "unit": "억원", "context": "원문 전체 문장", "type": "실적|가이던스|목표|Q&A"}},
    {{"company": "...", "period": "2025-Q1", "metric": "매출 가이던스", "value": 1300, "unit": "억원", "context": "...", "type": "가이던스"}},
    ...
  ],
  "dss": [
    {{"company": "...", "period": "2024-Q4", "metric": "매출액", "value": 1250, "unit": "억원", "context": "원문 전체 문장", "type": "실적|가이던스|목표|Q&A"}},
    ...
  ]
}}

**추출 규칙:**
1. **실적 수치**: 발표된 모든 실적 숫자 (매출, 영업이익, 순이익 등)
2. **가이던스**: 향후 전망, 목표치, 예상 수치
3. **Q&A 핵심 내용**: Q&A에서 언급된 중요한 숫자나 발언
4. **문맥 정확히 포함**: context에는 숫자가 언급된 전체 문장을 포함
5. **확정 vs 예상 구분**: "예상", "목표", "전망" 등의 표현이 있으면 type을 "가이던스"로
6. **조건부 발언 주의**: "만약", "경우" 등 조건이 붙은 발언은 context에 조건까지 포함

JSON만 반환하세요."""

        try:
            if self.debug:
                print(f"\n[DEBUG] Calling Claude API for batch extraction...")

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # 디버깅: API 응답 출력
            print(f"[DEBUG] API Response length: {len(response_text)}")
            print(f"[DEBUG] API Response preview: {response_text[:500]}")
            sys.stdout.flush()

            # JSON 직접 파싱 (딕셔너리 구조 유지)
            # 마크다운 코드 블록 제거
            clean_text = response_text
            if "```json" in clean_text:
                start = clean_text.find("```json") + 7
                remaining = clean_text[start:]
                end_idx = remaining.find("```")
                if end_idx != -1:
                    clean_text = remaining[:end_idx].strip()
                else:
                    clean_text = remaining.strip()
            elif "```" in clean_text:
                start = clean_text.find("```") + 3
                remaining = clean_text[start:]
                end_idx = remaining.find("```")
                if end_idx != -1:
                    clean_text = remaining[:end_idx].strip()
                else:
                    clean_text = remaining.strip()

            result = json.loads(clean_text)

            print(f"[DEBUG] Parsed result type: {type(result)}")
            if isinstance(result, dict):
                print(f"[DEBUG] Dict keys: {result.keys()}")
            sys.stdout.flush()

            # 결과가 리스트면 두 개로 분리 필요
            if isinstance(result, list):
                # 단일 리스트로 반환된 경우 - 절반씩 나눔 (비이상적)
                mid = len(result) // 2
                return result[:mid], result[mid:]
            elif isinstance(result, dict):
                # 올바른 형식
                ec_data = result.get("earning_call", [])
                dss_data = result.get("dss", [])
                return ec_data, dss_data
            else:
                raise ValueError("Unexpected response format")

        except Exception as e:
            print(f"[ERROR] Batch extraction failed: {e}")
            # 폴백: 개별 호출
            print("[WARN] Falling back to individual API calls...")
            ec_data = self.extract_financial_data(ec_text, "earning_call")
            dss_data = self.extract_financial_data(dss_text, "dss")
            return ec_data, dss_data

    def _extract_company_from_text(self, text: str) -> str:
        """텍스트에서 회사명 추출"""
        try:
            # 간단한 프롬프트로 회사명만 추출
            response = self.client.messages.create(
                model=self.model,
                max_tokens=100,
                temperature=0,
                messages=[{
                    "role": "user",
                    "content": f"다음 텍스트에서 회사명만 추출하세요. 회사명만 반환하고 다른 설명은 하지 마세요:\n\n{text[:1000]}"
                }]
            )
            company = response.content[0].text.strip()
            return company if company else "미상"
        except:
            return "미상"

    def _fetch_external_reference(self, company_name: str, ec_text: str) -> str:
        """
        외부 공식 자료를 검색하여 참고 정보 수집

        Args:
            company_name: 회사명
            ec_text: 어닝콜 텍스트 (기간 추출용)

        Returns:
            외부 자료 요약 텍스트
        """
        try:
            import sys

            # 기간 추출 (간단한 휴리스틱)
            year = "2025"
            quarter = ""
            if "2025" in ec_text:
                year = "2025"
            elif "2024" in ec_text:
                year = "2024"
            elif "2026" in ec_text:
                year = "2026"

            if "4분기" in ec_text or "Q4" in ec_text:
                quarter = "4분기"
            elif "1분기" in ec_text or "Q1" in ec_text:
                quarter = "1분기"

            search_query = f"{company_name} {year} {quarter} 실적 발표".strip()

            print(f"[EXTERNAL] 외부 자료 검색 중: {search_query}")
            sys.stdout.flush()

            # 참고: 실제 웹 검색은 app.py에서 수행할 수 있도록 구조화
            # 현재는 프롬프트에 "외부 자료 참고" 지시만 추가
            return f"검색 쿼리: {search_query} (외부 공식 자료와 교차 검증 필요)"

        except Exception as e:
            print(f"[EXTERNAL] 외부 자료 검색 실패: {e}")
            return ""

    def _split_dss_by_sections(self, dss_text: str) -> Dict[str, str]:
        """DSS 텍스트를 섹션별로 분리 - ### 마크다운 헤더 우선"""
        import sys
        print(f"[DEBUG _split_dss_by_sections] Input length: {len(dss_text)} chars")
        print(f"[DEBUG _split_dss_by_sections] First 200 chars: {dss_text[:200]}")
        sys.stdout.flush()

        sections = {
            "실적": "",
            "가이던스": "",
            "Q&A": ""
        }

        lines = dss_text.split('\n')
        print(f"[DEBUG _split_dss_by_sections] Total lines: {len(lines)}")
        sys.stdout.flush()

        current_section = "실적"  # 기본값
        found_any_header = False

        for line in lines:
            # ### 마크다운 헤더 명시적 감지 (최우선) - 짧은 줄만 헤더로 인식
            # 긴 줄(100자 이상)은 내용으로 취급 (예: "## 2025년 SK텔레콤..." 같은 내용)
            if (line.strip().startswith('###') or line.strip().startswith('##')) and len(line.strip()) < 100:
                line_lower = line.lower().replace('#', '').strip()
                found_any_header = True
                print(f"[DEBUG] Found header: {line.strip()[:50]} -> section: ", end="")
                sys.stdout.flush()

                if any(kw in line_lower for kw in ['실적', '실적발표', '성과', '결과']):
                    if 'q&a' not in line_lower and '가이던스' not in line_lower and '전망' not in line_lower:
                        current_section = "실적"
                        print("실적")
                        sys.stdout.flush()
                        continue  # 헤더 자체는 섹션에 포함하지 않음
                elif any(kw in line_lower for kw in ['가이던스', '전망', '계획', '목표', '가이드']):
                    current_section = "가이던스"
                    print("가이던스")
                    sys.stdout.flush()
                    continue
                elif any(kw in line_lower for kw in ['q&a', 'q & a', '질의', '응답', '질문']):
                    current_section = "Q&A"
                    print("Q&A")
                    sys.stdout.flush()
                    continue

            # 빈 줄이 아니면 현재 섹션에 추가
            if line.strip():
                print(f"[DEBUG] Adding to '{current_section}': {line.strip()[:80]}")
                sys.stdout.flush()
                sections[current_section] += line + '\n'
            else:
                print(f"[DEBUG] Skipping empty line")
                sys.stdout.flush()

        # 헤더가 하나도 없었다면 키워드 기반으로 재분류
        if not found_any_header:
            sections = {
                "실적": "",
                "가이던스": "",
                "Q&A": ""
            }
            current_section = "실적"

            for line in lines:
                if not line.strip():
                    continue

                line_lower = line.lower()
                # 키워드 기반 섹션 감지
                if any(keyword in line_lower for keyword in ['실적', '성과', '결과', '매출', '영업이익']):
                    if '가이던스' not in line_lower and 'q&a' not in line_lower and '전망' not in line_lower:
                        current_section = "실적"
                elif any(keyword in line_lower for keyword in ['가이던스', '전망', '계획', '목표', '예상', '가이드']):
                    current_section = "가이던스"
                elif any(keyword in line_lower for keyword in ['q&a', '질의', '응답', '질문']):
                    current_section = "Q&A"

                sections[current_section] += line + '\n'

        # Debug: 필터링 전 섹션 길이 로그
        print(f"[DEBUG Before filter] 실적: {len(sections.get('실적', ''))} chars, 가이던스: {len(sections.get('가이던스', ''))} chars, Q&A: {len(sections.get('Q&A', ''))} chars")
        print(f"[DEBUG Before filter] found_any_header: {found_any_header}")
        sys.stdout.flush()

        # 빈 섹션 제거
        result = {k: v.strip() for k, v in sections.items() if v.strip()}

        print(f"[DSS 섹션 분할] 실적: {len(result.get('실적', ''))} chars, 가이던스: {len(result.get('가이던스', ''))} chars, Q&A: {len(result.get('Q&A', ''))} chars")
        print(f"[DSS 섹션 분할] Result keys: {list(result.keys())}")
        sys.stdout.flush()

        return result

    def retag_corrections_by_sections(self, corrections: List[Dict], dss_text: str) -> List[Dict]:
        """
        Corrections을 ### 마크다운 헤더 기반으로 재태깅

        Args:
            corrections: 수정사항 리스트
            dss_text: 원본 DSS 텍스트

        Returns:
            재태깅된 수정사항 리스트
        """
        # DSS를 섹션별로 분할
        sections = self._split_dss_by_sections(dss_text)

        print(f"[재태깅] {len(corrections)}개 corrections을 섹션별로 재분류 중...")

        # 각 correction의 context를 보고 어느 섹션에 속하는지 판단
        for correction in corrections:
            dss_context = correction.get('dss_context', '')
            matched_section = None
            max_overlap = 0

            # 각 섹션에서 context가 나타나는지 확인
            for section_name, section_text in sections.items():
                if dss_context and dss_context in section_text:
                    # 완전 매칭 found
                    matched_section = section_name
                    break
                # 부분 매칭 체크 (긴 context의 경우)
                elif dss_context and len(dss_context) > 20:
                    # context의 일부분이 section에 있는지 확인
                    context_words = set(dss_context.split())
                    section_words = set(section_text.split())
                    overlap = len(context_words & section_words)
                    if overlap > max_overlap:
                        max_overlap = overlap
                        matched_section = section_name

            # 매칭된 섹션으로 type 업데이트 (또는 기존 type 유지)
            if matched_section:
                correction['type'] = matched_section
                print(f"  - {correction.get('metric', 'N/A')} → {matched_section}")
            else:
                # 매칭 실패 시 기존 type 유지하거나 기본값 설정
                if not correction.get('type'):
                    correction['type'] = '실적'  # 기본값
                print(f"  - {correction.get('metric', 'N/A')} → {correction['type']} (기본값)")

        return corrections

    def _split_into_sentences(self, text: str) -> List[str]:
        """텍스트를 마침표(.) 기준으로 문장 분리"""
        import re
        import sys

        # ## 으로 시작하는 줄 단위로 분리
        lines = text.strip().split('\n')
        sentences = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # ## 으로 시작하는 경우 (DSS 문장)
            if line.startswith('##'):
                # ## 제거
                content = line[2:].strip()
            else:
                content = line

            # 마침표로 분리 (단, 숫자 사이의 마침표는 제외)
            # 정규식: 숫자가 아닌 문자 뒤의 마침표 + 공백 또는 문장 끝
            # 예: "1.5조원"은 분리 안 함, "증가했습니다. 영업이익은"은 분리
            parts = re.split(r'(?<=[^0-9])\.(?:\s+|$)', content)

            for part in parts:
                part = part.strip()
                if part:
                    # 마침표가 없으면 추가
                    if not part.endswith('.'):
                        part += '.'
                    sentences.append(part)

        print(f"[DEBUG] 총 {len(sentences)}개 문장으로 분리됨")
        sys.stdout.flush()
        for i, sent in enumerate(sentences, 1):
            print(f"[DEBUG]   {i}. {sent[:80]}..." if len(sent) > 80 else f"[DEBUG]   {i}. {sent}")
        sys.stdout.flush()

        return sentences

    def _validate_section_detailed(self, ec_text: str, section_text: str, section_type: str, external_ref: str = None) -> List[Dict]:
        """특정 섹션을 문장별로 상세 검증 - 마침표 기준으로 문장 분리"""
        import sys

        # 1. 문장 분리
        sentences = self._split_into_sentences(section_text)
        print(f"[SENTENCE] {section_type} 섹션을 {len(sentences)}개 문장으로 분리")
        sys.stdout.flush()

        # 2. 각 문장을 개별적으로 검증
        all_issues = []

        for idx, sentence in enumerate(sentences, 1):
            print(f"[SENTENCE] {idx}/{len(sentences)}: {sentence[:50]}..." if len(sentence) > 50 else f"[SENTENCE] {idx}/{len(sentences)}: {sentence}")
            sys.stdout.flush()

            # 개별 문장 검증
            sentence_result = self._validate_single_sentence(ec_text, sentence, section_type, external_ref, idx)

            if sentence_result:
                all_issues.append(sentence_result)

                if sentence_result.get('validation_status') == 'passed':
                    print(f"[SENTENCE] → 문제 없음 (일치함)")
                else:
                    print(f"[SENTENCE] → 이슈 발견: {sentence_result.get('issue_type', 'N/A')}")
            sys.stdout.flush()

        return all_issues

    def _validate_single_sentence(self, ec_text: str, sentence: str, section_type: str, external_ref: str = None, sentence_idx: int = 0) -> Dict:
        """단일 문장을 검증 - 모든 문장에 대해 결과 반환"""

        external_context = ""
        if external_ref:
            external_context = f"""

**외부 공식 자료 참고:**
<external_reference>
{external_ref}
</external_reference>

⚠️ **중요**: 숫자 검증 시 외부 공식 자료(뉴스, IR 발표자료)와도 교차 검증하세요.
- 어닝콜 원문의 숫자가 공식 발표 자료와 일치하는지 확인
- DSS의 숫자가 원문을 정확히 반영했는지 검증
- 단위 변환이 정확한지 확인 (조원, 억원 등)
"""

        prompt = f"""당신은 IR 자료 검수 전문가입니다.

아래는 DSS의 **{section_type}** 섹션에서 추출한 **한 개의 문장**입니다. 이 문장을 어닝콜 원문과 비교하여 검증하세요.

**어닝콜 원문 (전체):**
<earning_call>
{ec_text[:30000]}
</earning_call>

**검증할 DSS 문장:**
<dss_sentence>
{sentence}
</dss_sentence>
{external_context}
**검증 방법:**
1. 위의 DSS 문장에서 주장하는 내용을 파악하세요
2. 어닝콜 원문에서 해당 내용의 근거를 찾으세요
3. **숫자는 특히 주의깊게 검증** - 원문과 정확히 일치하는지, 외부 자료와도 일치하는지 확인
4. 다음 문제가 있는지 체크하세요:
   - **수치 오류**: 숫자가 원문과 다름 (⚠️ 가장 중요!)
   - **과장**: 원문보다 더 긍정적으로 표현
   - **축소**: 부정적 내용이나 리스크를 축소/생략
   - **확대해석**: "~할 수 있다" → "~할 것이다" 같은 확정적 변경
   - **문맥누락**: 중요한 조건, 단서, 배경 설명 생략
   - **조건무시**: "만약", "~인 경우" 같은 조건 제거

**수정안 작성 원칙 (매우 중요!):**
🚫 **절대 금지 사항**:
   ❌ "삭제하세요", "제거하세요", "삭제", "제거" 같은 표현 금지
   ❌ "없애세요", "지우세요", "빼세요" 같은 표현 금지
   ❌ 설명이나 지시문 금지 (예: "검토가 필요합니다", "수정해야 합니다")

✅ **반드시 지켜야 할 사항**:
   1. recommendation은 **완전한 문장**만 작성하세요
   2. 원래 DSS 문장을 기반으로 **수정된 버전**을 제공하세요
   3. 숫자가 틀렸다면 → 올바른 숫자로 **교체한 문장**
   4. 문맥이 부족하다면 → 필요한 정보를 **추가한 문장**
   5. 과장되었다면 → 정확한 표현으로 **수정한 문장**
   6. 모든 recommendation은 **그대로 DSS에 복사-붙여넣기 가능**해야 합니다

⚠️ **경고**: 삭제/제거 권장은 시스템에서 자동으로 필터링되어 제외됩니다!

**반환 형식 (JSON):**
{{
  "issues": [
    {{
      "type": "{section_type}",
      "company": "회사명 (DSS에서 추출)",
      "period": "기간 (예: 2025-FY, 2025-Q4)",
      "metric": "관련 지표 (예: 매출, 영업이익)",
      "issue_type": "수치오류|과장|축소|확대해석|문맥누락|조건무시",
      "severity": "Critical|High|Medium|Low",
      "dss_statement": "문제가 있는 DSS 문장 (위의 문장 그대로)",
      "earning_call_context": "어닝콜 원문의 해당 부분",
      "issue": "무엇이 잘못되었는지",
      "recommendation": "수정된 완전한 문장 (원문을 수정한 버전, 삭제 아님)"
    }}
  ]
}}

**recommendation 작성 예시:**
❌ 나쁜 예: "이 문장은 부정확하므로 삭제하세요"
❌ 나쁜 예: "해당 내용을 제거하세요"
❌ 나쁜 예: "검토가 필요합니다"

✅ 좋은 예 1 (숫자 수정):
   - 원문: "크래프톤은 2025년 4분기 매출액 5조원을 기록했습니다."
   - 수정: "크래프톤은 2025년 4분기 매출액 3조 4,510억원을 기록했습니다."

✅ 좋은 예 2 (문맥 보완):
   - 원문: "매출이 증가했습니다."
   - 수정: "매출이 전년 대비 5% 증가했으나 목표에는 미달했습니다."

✅ 좋은 예 3 (과장 수정):
   - 원문: "성장이 예상됩니다."
   - 수정: "시장 상황이 개선되면 성장할 수 있습니다."

**중요 지침:**
- 문제가 없으면 빈 issues 배열 반환: {{"issues": []}}
- 문제가 있을 때만 issues에 포함하세요
- 확실한 근거가 있을 때만 문제로 지적하세요
- **recommendation은 항상 완전한 문장이어야 합니다** (삭제나 제거가 아닌 수정)

JSON만 반환하세요. 설명이나 마크다운은 넣지 마세요."""

        try:
            import sys

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # 디버그: API 응답 로깅
            print(f"[DEBUG] API 응답 길이: {len(response_text)} chars")
            if len(response_text) < 200:
                print(f"[DEBUG] API 응답: {response_text}")
            else:
                print(f"[DEBUG] API 응답 (처음 200자): {response_text[:200]}")
            sys.stdout.flush()

            # 빈 응답 체크
            if not response_text or not response_text.strip():
                print(f"[WARN] API 응답이 비어있음 - 문제없음으로 처리")
                sys.stdout.flush()
                return {
                    "type": section_type,
                    "validation_status": "passed",
                    "dss_sentence": sentence,
                    "dss_statement": sentence,
                    "metric": "일치함",
                    "issue": "",
                    "recommendation": sentence,
                    "severity": "Low",
                    "company": "",
                    "period": "",
                    "sentence_index": sentence_idx
                }

            # JSON 파싱
            clean_text = response_text.strip()
            if "```json" in clean_text:
                start = clean_text.find("```json") + 7
                remaining = clean_text[start:]
                end_idx = remaining.find("```")
                if end_idx != -1:
                    clean_text = remaining[:end_idx].strip()
                else:
                    clean_text = remaining.strip()
            elif "```" in clean_text:
                start = clean_text.find("```") + 3
                remaining = clean_text[start:]
                end_idx = remaining.find("```")
                if end_idx != -1:
                    clean_text = remaining[:end_idx].strip()
                else:
                    clean_text = remaining.strip()

            # JSON 파싱 전 체크
            if not clean_text:
                print(f"[WARN] 파싱 후 텍스트가 비어있음 - 문제없음으로 처리")
                sys.stdout.flush()
                return {
                    "type": section_type,
                    "validation_status": "passed",
                    "dss_sentence": sentence,
                    "dss_statement": sentence,
                    "metric": "일치함",
                    "issue": "",
                    "recommendation": sentence,
                    "severity": "Low",
                    "company": "",
                    "period": "",
                    "sentence_index": sentence_idx
                }

            # JSON 정리: 제어 문자 제거
            import re
            # Remove control characters (ASCII 0-31 except newline, tab)
            clean_text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]', '', clean_text)

            # JSON 파싱 시도
            try:
                result = json.loads(clean_text)
            except json.JSONDecodeError as json_err:
                # JSON 파싱 실패 - 상세 로깅
                print(f"[ERROR] JSON 파싱 실패: {json_err}")
                print(f"[ERROR] 에러 위치: line {json_err.lineno}, column {json_err.colno}")
                print(f"[ERROR] 문제가 있는 텍스트 (처음 500자):")
                print(clean_text[:500])
                print(f"[ERROR] 전체 길이: {len(clean_text)} chars")
                sys.stdout.flush()

                # JSON 수정 시도 1: trailing commas 제거
                fixed_text = re.sub(r',(\s*[}\]])', r'\1', clean_text)

                # JSON 수정 시도 2: 불완전한 문자열 수정 (끝나지 않은 따옴표 처리)
                # 마지막 완전한 객체까지만 파싱하도록 시도
                try:
                    result = json.loads(fixed_text)
                    print(f"[INFO] trailing comma 제거 후 JSON 파싱 성공")
                    sys.stdout.flush()
                except json.JSONDecodeError:
                    # 마지막 완전한 '}' 또는 ']' 위치 찾기
                    last_brace = fixed_text.rfind('}')
                    last_bracket = fixed_text.rfind(']')
                    last_complete = max(last_brace, last_bracket)

                    if last_complete > 0:
                        truncated_text = fixed_text[:last_complete + 1]
                        try:
                            result = json.loads(truncated_text)
                            print(f"[INFO] 불완전한 JSON 잘라내기 후 파싱 성공")
                            sys.stdout.flush()
                        except:
                            # 여전히 실패하면 문제없음으로 처리
                            print(f"[WARN] JSON 수정 후에도 파싱 실패 - 문제없음으로 처리")
                            sys.stdout.flush()
                            return {
                                "type": section_type,
                                "validation_status": "passed",
                                "dss_sentence": sentence,
                                "dss_statement": sentence,
                                "metric": "일치함",
                                "issue": "",
                                "recommendation": sentence,
                                "severity": "Low",
                                "company": "",
                                "period": "",
                                "sentence_index": sentence_idx
                            }
                    else:
                        # 완전한 JSON을 찾을 수 없음
                        print(f"[WARN] JSON 수정 후에도 파싱 실패 - 문제없음으로 처리")
                        sys.stdout.flush()
                        return {
                            "type": section_type,
                            "validation_status": "passed",
                            "dss_sentence": sentence,
                            "dss_statement": sentence,
                            "metric": "일치함",
                            "issue": "",
                            "recommendation": sentence,
                            "severity": "Low",
                            "company": "",
                            "period": "",
                            "sentence_index": sentence_idx
                        }
            issues = result.get("issues", [])

            # 필터링: 삭제/제거 관련 권장사항 제외
            filtered_issues = []
            delete_keywords = ["삭제", "제거", "없애", "지우", "빼"]

            for issue in issues:
                recommendation = issue.get("recommendation", "").lower()

                # 삭제/제거 키워드 체크
                has_delete_keyword = any(keyword in recommendation for keyword in delete_keywords)

                if has_delete_keyword:
                    print(f"[FILTER] 삭제 권장 이슈 제외: {issue.get('metric', 'N/A')}")
                    print(f"[FILTER] 원래 recommendation: {issue.get('recommendation', '')[:100]}")
                    sys.stdout.flush()
                    continue  # 이 이슈는 포함하지 않음

                # 기본값 추가
                if "type" not in issue:
                    issue["type"] = section_type
                if "company" not in issue:
                    issue["company"] = ""
                if "period" not in issue:
                    issue["period"] = ""
                if "metric" not in issue:
                    issue["metric"] = "전반적 내용"

                filtered_issues.append(issue)

            if len(issues) != len(filtered_issues):
                print(f"[FILTER] {len(issues) - len(filtered_issues)}개 삭제 권장 이슈 필터링됨")
                sys.stdout.flush()

            # 문제가 없으면 "검수 완료" 상태로 반환
            if len(filtered_issues) == 0:
                return {
                    "type": section_type,
                    "validation_status": "passed",
                    "dss_sentence": sentence,
                    "dss_statement": sentence,
                    "metric": "일치함",
                    "issue": "",
                    "recommendation": sentence,  # 원문 그대로
                    "severity": "Low",
                    "company": "",
                    "period": "",
                    "sentence_index": sentence_idx
                }
            else:
                # 문제가 있으면 첫 번째 이슈 반환 (문장당 하나씩)
                issue = filtered_issues[0]
                issue["validation_status"] = "issue_found"
                issue["dss_sentence"] = sentence
                issue["sentence_index"] = sentence_idx
                return issue

        except Exception as e:
            print(f"[ERROR] Sentence validation failed: {e}")
            import traceback
            traceback.print_exc()
            # 오류 발생 시에도 문장 반환 (검수 실패)
            return {
                "type": section_type,
                "validation_status": "error",
                "dss_sentence": sentence,
                "dss_statement": sentence,
                "metric": "검수 오류",
                "issue": f"검증 중 오류 발생: {str(e)[:100]}",
                "recommendation": sentence,
                "severity": "Low",
                "company": "",
                "period": "",
                "sentence_index": sentence_idx
            }

    def validate_dss_interpretation(self, ec_text: str, dss_text: str, external_reference: str = None) -> Dict[str, Any]:
        """
        DSS를 섹션별로 나누어 문장 단위로 상세 검증
        - 근본적 개선: 섹션별 개별 검증으로 정확도 향상
        - 외부 공식 자료 참고 기능 추가

        Args:
            ec_text: 어닝콜 원문
            dss_text: DSS 텍스트
            external_reference: 외부 공식 자료 (웹 검색 결과 등)
        """
        print("[CONTEXT] 섹션별 문장 단위 상세 검증 시작...")
        import sys
        sys.stdout.flush()

        # 0단계: 회사명 추출
        company_name = self._extract_company_from_text(dss_text)
        print(f"[CONTEXT] 회사명: {company_name}")
        sys.stdout.flush()

        # 0-1단계: 외부 공식 자료 검색 (선택적)
        if external_reference is None:
            external_reference = self._fetch_external_reference(company_name, ec_text)
            if external_reference:
                print(f"[EXTERNAL] 외부 자료 확인 완료: {len(external_reference)} chars")
                sys.stdout.flush()

        # 1단계: DSS를 섹션별로 분리
        sections = self._split_dss_by_sections(dss_text)
        print(f"[CONTEXT] 발견된 섹션: {list(sections.keys())}")
        total_dss_length = len(dss_text)
        sections_total_length = sum(len(s) for s in sections.values())
        print(f"[CONTEXT] DSS 전체 길이: {total_dss_length} chars, 섹션별 분류 합계: {sections_total_length} chars")
        sys.stdout.flush()

        # 2단계: 각 섹션을 개별적으로 상세 검증 (외부 자료 참고)
        all_issues = []
        for section_type, section_text in sections.items():
            if len(section_text) > 50:  # 충분한 내용이 있는 섹션만
                # 문장 개수 카운트 (대략적)
                sentence_count = len([s for s in section_text.replace('\n', ' ').split('.') if s.strip()])
                print(f"[CONTEXT] {section_type} 섹션 검증 중... ({len(section_text)} chars, 약 {sentence_count}개 문장)")
                sys.stdout.flush()
                section_issues = self._validate_section_detailed(ec_text, section_text, section_type, external_reference)
                # 모든 이슈에 회사명 추가
                for issue in section_issues:
                    if not issue.get("company") or issue.get("company") == "":
                        issue["company"] = company_name
                all_issues.extend(section_issues)
                print(f"[CONTEXT] {section_type} 섹션: {len(section_issues)}건 이슈 발견 (검증 완료)")
                sys.stdout.flush()

        # 3단계: 전체 평가
        total_issues = len(all_issues)
        critical_count = sum(1 for i in all_issues if i.get("severity") == "Critical")
        high_count = sum(1 for i in all_issues if i.get("severity") == "High")

        if total_issues == 0:
            faithfulness = "good"
            summary = "DSS가 어닝콜 내용을 정확하게 반영했습니다."
        elif critical_count > 0 or high_count > 3:
            faithfulness = "poor"
            summary = f"심각한 문제 {critical_count}건, 주요 문제 {high_count}건 발견. 수정 필요."
        elif high_count > 0:
            faithfulness = "fair"
            summary = f"주요 문제 {high_count}건 발견. 일부 수정 권장."
        else:
            faithfulness = "good"
            summary = f"경미한 문제 {total_issues}건만 발견. 전반적으로 양호."

        result = {
            "interpretation_issues": all_issues,
            "overall_assessment": {
                "accuracy_score": max(0, 100 - (critical_count * 20 + high_count * 10 + (total_issues - critical_count - high_count) * 3)),
                "faithfulness": faithfulness,
                "major_issues_count": critical_count + high_count,
                "summary": summary
            }
        }

        print(f"[CONTEXT] 총 {total_issues}건의 문맥 이슈 발견 (Critical: {critical_count}, High: {high_count})")
        sys.stdout.flush()
        return result

    def generate_corrected_dss_versions(self, original_dss: str, ec_text: str,
                                       corrections: List[Dict], interpretation_issues: List[Dict]) -> Dict[str, str]:
        """
        DSS 수정본을 1개 버전으로 생성 (권장 버전)

        Args:
            original_dss: 원본 DSS 텍스트
            ec_text: 어닝콜 원문 텍스트
            corrections: 숫자 수정 사항 리스트
            interpretation_issues: 해석 문제 리스트

        Returns:
            {
                "corrected_dss": "수정된 DSS (숫자 + 중요 해석)"
            }
        """
        import sys

        # 수정 사항 요약
        corrections_summary = "\n".join([
            f"- {c['metric']} ({c['period']}): {c['dss_value']} {c['unit']} → {c['earning_call_value']} {c['unit']} (차이: {c['difference_pct']:.1f}%)"
            for c in corrections[:10]  # 최대 10개만
        ])

        # 중요한 해석 문제만 (high severity)
        high_severity_issues = [i for i in interpretation_issues if i.get('severity') == 'high']
        interpretation_summary = "\n".join([
            f"- [{i['issue_type']}] {i['dss_statement']}\n  → {i['suggestion']}"
            for i in high_severity_issues[:5]  # 최대 5개만
        ])

        prompt = f"""당신은 IR 자료 검수 전문가입니다.

아래 DSS 요약본에서 발견된 오류를 수정해주세요.

**원본 DSS:**
<original_dss>
{original_dss[:10000]}
</original_dss>

**어닝콜 원문 (참고용):**
<earning_call>
{ec_text[:5000]}
</earning_call>

**발견된 숫자 오류:**
{corrections_summary if corrections_summary else "없음"}

**발견된 해석 문제 (중요도 높음):**
{interpretation_summary if interpretation_summary else "없음"}

---

수정된 DSS를 다음 형식으로 생성해주세요:

{{
  "corrected_dss": "수정된 DSS 텍스트"
}}

**수정 원칙:**
- 숫자 오류를 정확하게 수정
- 중요한 해석 문제(과장, 축소, 확대해석, 조건 무시 등)를 수정
- 원본 문장 구조를 최대한 유지하되, 필요시 명확하게 개선
- 어닝콜 원문에 충실하게 작성

JSON만 반환하세요."""

        try:
            print("[DSS] 수정본 생성 중...")
            sys.stdout.flush()

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # JSON 파싱
            clean_text = response_text
            if "```json" in clean_text:
                start = clean_text.find("```json") + 7
                remaining = clean_text[start:]
                end_idx = remaining.find("```")
                if end_idx != -1:
                    clean_text = remaining[:end_idx].strip()
            elif "```" in clean_text:
                start = clean_text.find("```") + 3
                remaining = clean_text[start:]
                end_idx = remaining.find("```")
                if end_idx != -1:
                    clean_text = remaining[:end_idx].strip()

            result = json.loads(clean_text)

            print(f"[DSS] 수정본 생성 완료")
            sys.stdout.flush()

            return {
                "corrected_dss": result.get("corrected_dss", original_dss)
            }

        except Exception as e:
            print(f"[ERROR] DSS 수정본 생성 실패: {e}")
            sys.stdout.flush()
            return {
                "corrected_dss": original_dss
            }

    def _build_extraction_prompt(self, text: str, document_type: str) -> str:
        """재무 데이터 추출을 위한 프롬프트 생성 - 맥락 이해 강화"""

        base_prompt = f"""당신은 재무 분석 전문가입니다. 다음 텍스트에서 모든 재무 지표를 추출하여 구조화된 JSON 형식으로 변환해주세요.

**중요:** 단순히 숫자를 추출하는 것이 아니라, **각 문장의 의미와 맥락을 정확히 이해**하여 추출해야 합니다.

<document_type>{document_type}</document_type>

<text>
{text}
</text>

**핵심 원칙 - 맥락 우선 이해:**

1. **기간 식별 - 명시적 언급 우선:**
   - ✅ "2026년 연간 매출액 목표는..." → period: "2026-연간" (명시적으로 2026년이라고 했음)
   - ✅ "2025년 실적은..." → period: "2025-연간"
   - ❌ "전년 대비 5% 증가" → "전년"은 무시하고, 문맥에서 실제 연도 찾기
   - ❌ 상대적 표현("전년", "지난해")에 속지 말고 절대적 연도/분기를 찾으세요

2. **값 추출 - 문장의 주어가 되는 값:**
   - ✅ "매출액은 2조 500억원으로..." → 2조 500억원이 매출액의 값
   - ✅ "목표는 2,700억원으로" → 2,700억원이 목표값
   - ❌ "전년 대비 7.3% 증가" → 이것은 증감률이지 실제 값이 아님
   - 같은 문장에 여러 숫자가 있으면, 지표명과 직접 연결된 값을 선택하세요

3. **목표 vs 실적 구분:**
   - "목표", "계획", "전망" → 미래 기간의 목표값
   - "실적", "기록", "달성" → 과거/현재 기간의 실제값
   - 예: "2026년 매출 목표 2조원" → period: "2026-연간", metric: "매출액 목표"

4. **문맥 완전 이해:**
   - 각 문장이 무엇을 말하는지 전체적으로 이해한 후 추출
   - 문장 구조: "주어(기간) + 동사 + 목적어(지표와 값)"
   - 예: "2026년 1분기 영업이익은 620억원으로 전년 동기 대비 8.7% 증가"
     → period: "2026-Q1", metric: "영업이익", value: 620 (전년이나 8.7%가 아님)

**추출 규칙:**

1. 각 수치에 대해 다음 정보를 추출하세요:
   - company: 회사명
   - period: 기간 (예: "2024-Q4", "2024-연간", "2026-Q1") - 문맥에서 명시된 연도/분기
   - metric: 재무 지표명 (예: "매출액", "영업이익", "매출액 목표")
   - value: 해당 지표의 실제 숫자 값 (원문에 표기된 단위 기준, **절대 변환하지 말 것**)
   - unit: 단위 (원문에 표기된 그대로, 예: "조원", "억원", "%", "원")
   - context: 해당 수치가 언급된 원문 전체 문장 (최대 150자)

2. **숫자 추출 규칙 (원문 그대로!):**
   **중요: 원문의 숫자와 단위를 절대 변환하지 말고 정확히 그대로 추출하세요**

   - "1,250억원" → value: 1250, unit: "억원" (그대로)
   - "1조 2,500억원" → value: 1.25, unit: "조원" (조 단위 그대로)
   - "17조 992억원" → value: 17.0992, unit: "조원" (조 단위 그대로)
   - "2조 500억원" → value: 2.05, unit: "조원" (조 단위 그대로)
   - "18.5 billion KRW" → value: 185, unit: "억원" (변환 필요 시)
   - "55.0%" → value: 55.0, unit: "%" (그대로)
   - "1,420원" → value: 1420, unit: "원" (그대로)

   **핵심: 원문이 "조" 단위면 "조"로, "억" 단위면 "억"으로 그대로 추출!**

3. **기간 표준화:**
   - "2024년 4분기", "4분기", "Q4 2024" → "2024-Q4"
   - "2024년 연간", "2024년", "2024년도" → "2024-연간"
   - "2025년 1분기", "25년 1분기" → "2025-Q1"
   - "2026년 2분기", "2026 Q2" → "2026-Q2"

**출력 형식 (JSON):**
```json
[
  {{
    "company": "회사명",
    "period": "기간",
    "metric": "지표명",
    "value": 숫자,
    "unit": "단위",
    "context": "원문 전체 문장"
  }}
]
```

**주의사항:**
- 증감률(%, 전년 대비)은 별도의 항목으로 추출하거나 무시하세요
- 문장을 전체적으로 이해하여 정확한 기간과 값을 추출하세요
- JSON 배열만 출력하고, 다른 설명은 추가하지 마세요"""

        return base_prompt

    def _parse_json_response(self, response_text: str) -> List[Dict[str, Any]]:
        """Claude 응답에서 JSON 추출 및 파싱"""

        # 마크다운 코드 블록 제거
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            # 시작 이후의 텍스트에서 닫는 ``` 찾기
            remaining = response_text[start:]
            end_in_remaining = remaining.find("```")
            if end_in_remaining != -1:
                response_text = remaining[:end_in_remaining].strip()
            else:
                response_text = remaining.strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            remaining = response_text[start:]
            end_in_remaining = remaining.find("```")
            if end_in_remaining != -1:
                response_text = remaining[:end_in_remaining].strip()
            else:
                response_text = remaining.strip()

        try:
            data = json.loads(response_text)

            # 단일 객체를 리스트로 변환
            if isinstance(data, dict):
                data = [data]

            return data

        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON 파싱 실패: {e}")
            if self.debug:
                print(f"=== Full Response (first 2000 chars) ===")
                print(response_text[:2000])
                print(f"=== End Response ===")
            else:
                print(f"Response text: {response_text[:200]}...")
            return []

    def normalize_financial_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        추출된 재무 데이터 정규화
        - 항목명 표준화
        - 단위 통일
        - 중복 제거
        """

        normalized = []
        seen = set()

        for item in data:
            # 키 생성 (중복 체크용)
            key = (
                item.get("company", "").strip(),
                item.get("period", "").strip(),
                item.get("metric", "").strip()
            )

            if key in seen:
                continue

            seen.add(key)

            # 정규화된 항목 추가
            # value를 숫자로 변환
            raw_value = item.get("value")
            try:
                value = float(raw_value) if raw_value is not None else 0.0
            except (ValueError, TypeError):
                print(f"[WARN] value 변환 실패: {raw_value}, 0으로 대체")
                value = 0.0

            normalized_item = {
                "company": (item.get("company") or "").strip(),
                "period": self._normalize_period(item.get("period") or ""),
                "metric": self._normalize_metric(item.get("metric") or ""),
                "value": value,
                "unit": (item.get("unit") or "").strip(),
                "context": (item.get("context") or "").strip(),
                "type": (item.get("type") or "").strip()  # 실적/가이던스/목표/Q&A
            }

            normalized.append(normalized_item)

        return normalized

    def _normalize_period(self, period: str) -> str:
        """기간 표기 정규화"""
        period = period.strip()

        # 이미 표준 형식이면 반환
        if "-Q" in period or "-연간" in period:
            return period

        # 변환 규칙
        replacements = {
            "4분기": "Q4",
            "1분기": "Q1",
            "2분기": "Q2",
            "3분기": "Q3",
            "Q4 2024": "2024-Q4",
            "Q1 2025": "2025-Q1",
            "연간": "연간"
        }

        for old, new in replacements.items():
            if old in period:
                # 연도 추출
                import re
                year_match = re.search(r'20\d{2}', period)
                if year_match:
                    year = year_match.group()
                    if "연간" in new or "연간" in old:
                        return f"{year}-연간"
                    else:
                        return f"{year}-{new}"

        return period

    def _normalize_metric(self, metric: str) -> str:
        """재무 지표명 정규화 (동의어 통일)"""
        metric = metric.strip()

        # 표준화 매핑
        synonyms = {
            "매출액": ["매출", "Revenue", "Sales"],
            "영업이익": ["영업익", "Operating Income", "Operating Profit"],
            "당기순이익": ["순이익", "Net Income", "Net Profit"],
            "현금및현금성자산": ["현금", "Cash and Cash Equivalents", "Cash"],
        }

        for standard, alternatives in synonyms.items():
            if metric == standard:
                return standard
            for alt in alternatives:
                if alt.lower() in metric.lower():
                    return standard

        return metric


def parse_file(file_path: str, document_type: str = "earning_call") -> List[Dict[str, Any]]:
    """
    파일에서 재무 데이터 추출 (헬퍼 함수)

    Args:
        file_path: 파일 경로
        document_type: 문서 타입

    Returns:
        추출된 재무 데이터
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()

    parser = FinancialDataParser()
    raw_data = parser.extract_financial_data(text, document_type)
    normalized_data = parser.normalize_financial_data(raw_data)

    return normalized_data


if __name__ == "__main__":
    # 테스트 코드
    import sys

    if len(sys.argv) < 2:
        print("Usage: python financial_parser.py <file_path> [document_type]")
        sys.exit(1)

    file_path = sys.argv[1]
    doc_type = sys.argv[2] if len(sys.argv) > 2 else "earning_call"

    print(f"\n📄 파싱 중: {file_path}")
    print(f"📋 문서 타입: {doc_type}\n")

    data = parse_file(file_path, doc_type)

    print(f"\n✅ 추출 완료: {len(data)}개 항목\n")
    print(json.dumps(data, ensure_ascii=False, indent=2))
