# -*- coding: utf-8 -*-
"""
Claude Skills 구현
어닝콜 DSS 검수를 위한 Claude Skills 정의 및 구현
"""

from typing import Dict, List, Any, Optional
from anthropic import Anthropic
import os
import json


class EarningCallSkills:
    """어닝콜 DSS 검수를 위한 Claude Skills"""

    def __init__(self, earning_call_text: str, dss_text: str, api_key: Optional[str] = None):
        """
        초기화

        Args:
            earning_call_text: 어닝콜 원본 문서 텍스트
            dss_text: DSS 데이터 텍스트
            api_key: Anthropic API 키
        """
        self.earning_call_text = earning_call_text
        self.dss_text = dss_text
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = os.getenv("CLAUDE_MODEL", "claude-3-haiku-20240307")
        self.client = Anthropic(api_key=self.api_key)

    def get_skill_definitions(self) -> List[Dict[str, Any]]:
        """
        Claude Skills 정의 반환

        Returns:
            Skills 정의 리스트 (Anthropic Tool Use 형식)
        """
        return [
            {
                "name": "search_original_document_for_keywords",
                "description": "어닝콜 원본 문서에서 특정 키워드나 재무 지표를 검색합니다. 불일치 항목의 원본 문맥을 찾거나 특정 재무 수치를 확인할 때 사용합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "검색할 키워드 또는 재무 지표명 (예: '영업이익', '매출액', '185억')"
                        },
                        "context_lines": {
                            "type": "integer",
                            "description": "결과에 포함할 주변 문맥 라인 수 (기본값: 2)",
                            "default": 2
                        }
                    },
                    "required": ["keyword"]
                }
            },
            {
                "name": "explain_discrepancy",
                "description": "어닝콜 원본과 DSS 데이터 간의 불일치 원인을 분석하고 설명합니다. 두 값의 차이가 왜 발생했는지, 어떤 값이 올바른지 판단하는 데 도움을 줍니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "metric_name": {
                            "type": "string",
                            "description": "불일치가 발생한 재무 지표명 (예: '영업이익', '광고선전비')"
                        },
                        "earning_call_value": {
                            "type": "number",
                            "description": "어닝콜 원본의 값"
                        },
                        "dss_value": {
                            "type": "number",
                            "description": "DSS 데이터의 값"
                        },
                        "period": {
                            "type": "string",
                            "description": "기간 (예: '2024-Q4')"
                        }
                    },
                    "required": ["metric_name", "earning_call_value", "dss_value", "period"]
                }
            },
            {
                "name": "propose_dss_update_for_review",
                "description": "불일치가 발견된 항목에 대해 DSS 데이터 수정안을 제안합니다. 어닝콜 원본을 기준으로 DSS의 어떤 값을 어떻게 수정해야 하는지 구체적인 제안을 생성합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "metric_name": {
                            "type": "string",
                            "description": "수정할 재무 지표명"
                        },
                        "current_dss_value": {
                            "type": "number",
                            "description": "현재 DSS 값"
                        },
                        "correct_value": {
                            "type": "number",
                            "description": "올바른 값 (어닝콜 원본 기준)"
                        },
                        "period": {
                            "type": "string",
                            "description": "기간"
                        },
                        "reason": {
                            "type": "string",
                            "description": "수정 사유"
                        }
                    },
                    "required": ["metric_name", "current_dss_value", "correct_value", "period"]
                }
            }
        ]

    def search_original_document_for_keywords(
        self,
        keyword: str,
        context_lines: int = 2
    ) -> Dict[str, Any]:
        """
        어닝콜 원본 문서에서 키워드 검색

        Args:
            keyword: 검색할 키워드
            context_lines: 주변 문맥 라인 수

        Returns:
            검색 결과
        """
        lines = self.earning_call_text.split('\n')
        results = []

        for i, line in enumerate(lines):
            if keyword.lower() in line.lower():
                # 주변 문맥 추출
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                context = '\n'.join(lines[start:end])

                results.append({
                    "line_number": i + 1,
                    "matched_line": line.strip(),
                    "context": context,
                    "keyword": keyword
                })

        return {
            "keyword": keyword,
            "matches_found": len(results),
            "results": results
        }

    def explain_discrepancy(
        self,
        metric_name: str,
        earning_call_value: float,
        dss_value: float,
        period: str
    ) -> Dict[str, Any]:
        """
        불일치 원인 분석 및 설명 (Claude API 활용)

        Args:
            metric_name: 재무 지표명
            earning_call_value: 어닝콜 값
            dss_value: DSS 값
            period: 기간

        Returns:
            분석 결과
        """
        # 관련 문맥 검색
        ec_context = self.search_original_document_for_keywords(metric_name, context_lines=3)

        # Claude에게 분석 요청
        prompt = f"""당신은 재무 분석 전문가입니다. 다음 불일치를 분석하고 설명해주세요:

**재무 지표**: {metric_name} ({period})
**어닝콜 원본 값**: {earning_call_value}
**DSS 데이터 값**: {dss_value}
**차이**: {dss_value - earning_call_value} ({((dss_value - earning_call_value) / earning_call_value * 100) if earning_call_value != 0 else 0:.2f}%)

**어닝콜 원본 문맥**:
{json.dumps(ec_context, ensure_ascii=False, indent=2)}

**분석 요청사항**:
1. 이 불일치의 가능한 원인은 무엇인가요?
2. 단위 변환 오류, 입력 오류, 반올림 차이 등 구체적인 원인을 추정해주세요
3. 어느 값이 올바른 것으로 보이나요?
4. DSS 데이터를 수정해야 한다면 어떻게 수정해야 하나요?

JSON 형식으로 답변해주세요:
```json
{{
  "likely_cause": "불일치의 가능한 원인",
  "analysis": "상세 분석",
  "correct_value": 올바른_값,
  "confidence": "high/medium/low",
  "recommendation": "권장 조치"
}}
```"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # JSON 추출
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                remaining = response_text[start:]
                end = remaining.find("```")
                if end != -1:
                    response_text = remaining[:end].strip()

            analysis = json.loads(response_text)

            return {
                "metric_name": metric_name,
                "period": period,
                "earning_call_value": earning_call_value,
                "dss_value": dss_value,
                "difference": dss_value - earning_call_value,
                "difference_pct": ((dss_value - earning_call_value) / earning_call_value * 100) if earning_call_value != 0 else 0,
                "analysis": analysis,
                "context": ec_context
            }

        except Exception as e:
            return {
                "error": str(e),
                "metric_name": metric_name,
                "message": "분석 중 오류가 발생했습니다"
            }

    def propose_dss_update_for_review(
        self,
        metric_name: str,
        current_dss_value: float,
        correct_value: float,
        period: str,
        reason: str = ""
    ) -> Dict[str, Any]:
        """
        DSS 데이터 수정 제안

        Args:
            metric_name: 재무 지표명
            current_dss_value: 현재 DSS 값
            correct_value: 올바른 값
            period: 기간
            reason: 수정 사유

        Returns:
            수정 제안
        """
        update_proposal = {
            "metric_name": metric_name,
            "period": period,
            "current_value": current_dss_value,
            "proposed_value": correct_value,
            "change": correct_value - current_dss_value,
            "change_pct": ((correct_value - current_dss_value) / current_dss_value * 100) if current_dss_value != 0 else 0,
            "reason": reason or "어닝콜 원본과 불일치",
            "status": "pending_review",
            "confidence": "high" if abs(correct_value - current_dss_value) / max(abs(current_dss_value), 1) > 0.01 else "medium"
        }

        return update_proposal

    def execute_skill(self, skill_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Skill 실행

        Args:
            skill_name: Skill 이름
            parameters: Skill 파라미터

        Returns:
            실행 결과
        """
        if skill_name == "search_original_document_for_keywords":
            return self.search_original_document_for_keywords(**parameters)
        elif skill_name == "explain_discrepancy":
            return self.explain_discrepancy(**parameters)
        elif skill_name == "propose_dss_update_for_review":
            return self.propose_dss_update_for_review(**parameters)
        else:
            return {"error": f"Unknown skill: {skill_name}"}


if __name__ == "__main__":
    # 테스트 코드
    print("Claude Skills 모듈 로드 완료")
    print("\n사용 가능한 Skills:")

    # 더미 데이터로 테스트
    skills = EarningCallSkills("테스트 어닝콜 문서", "테스트 DSS 데이터")

    for skill in skills.get_skill_definitions():
        print(f"\n- {skill['name']}")
        print(f"  설명: {skill['description']}")
