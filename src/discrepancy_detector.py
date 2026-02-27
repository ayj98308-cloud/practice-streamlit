"""
불일치 감지기 - 어닝콜과 DSS 데이터 간의 차이를 감지
"""

from typing import List, Dict, Any, Tuple, Optional
from difflib import SequenceMatcher


class DiscrepancyDetector:
    """어닝콜 데이터와 DSS 데이터 간의 불일치를 감지"""

    def __init__(self, threshold: float = 0.01, similarity_threshold: float = 0.8):
        """
        초기화

        Args:
            threshold: 불일치로 판단할 최소 차이 비율 (기본 1%)
            similarity_threshold: 항목명 매칭을 위한 최소 유사도 (기본 0.8)
        """
        self.threshold = threshold
        self.similarity_threshold = similarity_threshold

    def compare(
            self,
            earning_call_data: List[Dict[str, Any]],
            dss_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        어닝콜 데이터와 DSS 데이터 비교

        Args:
            earning_call_data: 어닝콜에서 추출한 재무 데이터
            dss_data: DSS에서 추출한 재무 데이터

        Returns:
            비교 결과
            {
                "matched": [매칭된 항목들],
                "discrepancies": [불일치 항목들],
                "only_in_earning_call": [어닝콜에만 있는 항목들],
                "only_in_dss": [DSS에만 있는 항목들],
                "summary": {통계 정보}
            }
        """

        matched = []
        discrepancies = []
        only_in_earning_call = []
        only_in_dss = []
        corrections_needed = []  # DSS에서 수정해야 할 항목들

        # DSS 데이터를 빠른 검색을 위해 인덱싱
        dss_index = self._build_index(dss_data)

        # 각 어닝콜 항목에 대해 DSS에서 매칭 찾기
        for ec_item in earning_call_data:
            best_match = self._find_best_match(ec_item, dss_data, dss_index)

            if best_match:
                dss_item, similarity = best_match

                # 값 비교
                if self._is_match(ec_item["value"], dss_item["value"], ec_item.get("unit")):
                    # 일치
                    matched.append({
                        "earning_call": ec_item,
                        "dss": dss_item,
                        "similarity": similarity,
                        "status": "일치"
                    })
                else:
                    # 불일치
                    diff = dss_item["value"] - ec_item["value"]
                    diff_pct = (diff / ec_item["value"] * 100) if ec_item["value"] != 0 else float('inf')

                    discrepancies.append({
                        "earning_call": ec_item,
                        "dss": dss_item,
                        "similarity": similarity,
                        "difference": diff,
                        "difference_pct": diff_pct,
                        "status": "불일치"
                    })

                    # 수정 지침 생성
                    correction = self._generate_correction(ec_item, dss_item, diff, diff_pct)
                    corrections_needed.append(correction)

                # 매칭된 DSS 항목 제거 (중복 매칭 방지)
                dss_data = [d for d in dss_data if d != dss_item]
                dss_index = self._build_index(dss_data)
            else:
                # 매칭되는 DSS 항목 없음
                only_in_earning_call.append(ec_item)

        # DSS에만 있는 항목들
        only_in_dss = dss_data

        # 통계 생성
        summary = {
            "total_earning_call_items": len(earning_call_data),
            "total_dss_items": len(dss_data) + len(matched) + len(discrepancies),
            "matched_count": len(matched),
            "discrepancy_count": len(discrepancies),
            "only_in_earning_call_count": len(only_in_earning_call),
            "only_in_dss_count": len(only_in_dss),
            "match_rate": len(matched) / len(earning_call_data) * 100 if earning_call_data else 0
        }

        return {
            "matched": matched,
            "discrepancies": discrepancies,
            "only_in_earning_call": only_in_earning_call,
            "only_in_dss": only_in_dss,
            "corrections_needed": corrections_needed,  # DSS 수정사항
            "summary": summary
        }

    def _build_index(self, data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """빠른 검색을 위한 인덱스 생성 (기간별로 그룹화)"""
        index = {}
        for item in data:
            period = item.get("period", "")
            if period not in index:
                index[period] = []
            index[period].append(item)
        return index

    def _find_best_match(
            self,
            ec_item: Dict[str, Any],
            dss_data: List[Dict[str, Any]],
            dss_index: Dict[str, List[Dict[str, Any]]]
    ) -> Optional[Tuple[Dict[str, Any], float]]:
        """
        어닝콜 항목에 가장 잘 매칭되는 DSS 항목 찾기

        Returns:
            (dss_item, similarity_score) 또는 None
        """

        ec_period = ec_item.get("period", "")
        ec_metric = ec_item.get("metric", "")
        ec_company = ec_item.get("company", "")

        # 같은 기간의 DSS 항목들만 검색
        candidates = dss_index.get(ec_period, [])

        best_match = None
        best_similarity = 0.0

        for dss_item in candidates:
            # 회사명 확인
            if dss_item.get("company") != ec_company:
                continue

            # 지표명 유사도 계산
            similarity = self._calculate_similarity(ec_metric, dss_item.get("metric", ""))

            if similarity >= self.similarity_threshold and similarity > best_similarity:
                best_similarity = similarity
                best_match = dss_item

        if best_match:
            return (best_match, best_similarity)
        return None

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """두 문자열 간의 유사도 계산 (0.0 ~ 1.0)"""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

    def _is_match(self, value1: float, value2: float, unit: Optional[str] = None) -> bool:
        """
        두 값이 매칭되는지 확인

        Args:
            value1: 어닝콜 값
            value2: DSS 값
            unit: 단위

        Returns:
            매칭 여부
        """

        # 정확히 일치
        if value1 == value2:
            return True

        # 차이 비율 계산
        if value1 == 0:
            return value2 == 0

        diff_ratio = abs(value2 - value1) / abs(value1)

        # 임계값 이하면 일치로 간주
        return diff_ratio <= self.threshold

    def _generate_correction(
            self,
            ec_item: Dict[str, Any],
            dss_item: Dict[str, Any],
            diff: float,
            diff_pct: float
    ) -> Dict[str, Any]:
        """
        DSS 수정 지침 생성

        Args:
            ec_item: 어닝콜 항목 (정답)
            dss_item: DSS 항목 (수정 필요)
            diff: 차이값
            diff_pct: 차이 비율

        Returns:
            수정 지침 딕셔너리
        """
        # 심각도 판단
        abs_diff_pct = abs(diff_pct)
        if abs_diff_pct >= 50:
            severity = "critical"  # 50% 이상 차이
            severity_label = "[긴급] 매우 중요"
        elif abs_diff_pct >= 10:
            severity = "high"  # 10~50% 차이
            severity_label = "[중요] 반드시 수정"
        elif abs_diff_pct >= 1:
            severity = "medium"  # 1~10% 차이
            severity_label = "[보통] 수정 권장"
        else:
            severity = "low"  # 1% 미만 차이
            severity_label = "[경미] 검토 필요"

        # 숫자를 보기 좋게 포맷팅
        def format_value(value: float, unit: str) -> str:
            """값을 한국어 표기법으로 변환 (조, 억 단위 포함, 소수점 자동 조정)"""

            # 조원 단위를 억원으로 변환하여 처리
            if unit == "조원":
                value_in_eok = value * 10000  # 조원을 억원으로 변환
                unit = "억원"
                value = value_in_eok

            if unit == "억원" and value >= 10000:
                jo = int(value // 10000)
                eok = value % 10000
                if eok == 0:
                    return f"{jo}조 원"
                elif eok == int(eok):
                    return f"{jo}조 {int(eok):,}억 원"
                else:
                    # 소수점 2자리까지 표시
                    return f"{jo}조 {eok:,.2f}억 원"
            elif value == int(value):
                return f"{int(value):,}{unit}"
            else:
                # 소수점 자리수 자동 결정
                if abs(value) >= 100:
                    # 큰 숫자는 소수점 1자리
                    return f"{value:,.1f}{unit}"
                elif abs(value) >= 10:
                    # 중간 숫자는 소수점 2자리
                    return f"{value:,.2f}{unit}"
                elif abs(value) >= 1:
                    # 1 이상은 소수점 2자리
                    return f"{value:,.2f}{unit}"
                else:
                    # 1 미만은 소수점 3자리 (퍼센트 등)
                    return f"{value:,.3f}{unit}"

        dss_formatted = format_value(dss_item["value"], dss_item["unit"])
        ec_formatted = format_value(ec_item["value"], ec_item["unit"])

        # 수정 지침 문장 생성
        correction_text = (
            f"DSS에서 '{dss_formatted}'를 '{ec_formatted}'로 수정해야 합니다"
        )

        return {
            "company": ec_item.get("company", ""),  # 회사명 추가
            "type": ec_item.get("type", ""),  # 실적발표/가이던스/Q&A 구분 추가
            "metric": ec_item["metric"],
            "period": ec_item["period"],
            "dss_current_value": dss_formatted,
            "correct_value": ec_formatted,
            "dss_value": dss_item["value"],  # 숫자값 추가
            "earning_call_value": ec_item["value"],  # 숫자값 추가
            "unit": ec_item["unit"],  # 단위 추가
            "dss_context": dss_item["context"],
            "earning_call_context": ec_item["context"],
            "difference": diff,
            "difference_pct": diff_pct,
            "severity": severity,
            "severity_label": severity_label,
            "correction": correction_text
        }

    def format_report(self, comparison_result: Dict[str, Any], output_format: str = "text") -> str:
        """
        비교 결과를 보고서 형식으로 포맷팅

        Args:
            comparison_result: compare() 메서드의 결과
            output_format: "text" 또는 "markdown"

        Returns:
            포맷팅된 보고서 문자열
        """

        if output_format == "markdown":
            return self._format_markdown(comparison_result)
        else:
            return self._format_text(comparison_result)

    def _format_text(self, result: Dict[str, Any]) -> str:
        """텍스트 형식 보고서"""

        summary = result["summary"]
        lines = []

        lines.append("=" * 80)
        lines.append("어닝콜 vs DSS 데이터 검수 결과".center(80))
        lines.append("=" * 80)
        lines.append("")

        # 요약 통계
        lines.append("[ 요약 통계 ]")
        lines.append(f"  총 어닝콜 항목: {summary['total_earning_call_items']}개")
        lines.append(f"  총 DSS 항목: {summary['total_dss_items']}개")
        lines.append(f"  ✅ 일치: {summary['matched_count']}개")
        lines.append(f"  ⚠️  불일치: {summary['discrepancy_count']}개")
        lines.append(f"  📌 어닝콜에만 존재: {summary['only_in_earning_call_count']}개")
        lines.append(f"  📌 DSS에만 존재: {summary['only_in_dss_count']}개")
        lines.append(f"  매칭률: {summary['match_rate']:.1f}%")
        lines.append("")

        # DSS 수정사항 (최우선 표시)
        if result.get("corrections_needed"):
            lines.append("=" * 80)
            lines.append(f"📝 DSS 수정사항 ({len(result['corrections_needed'])}건)".center(80))
            lines.append("=" * 80)
            lines.append("")
            lines.append("⚠️  아래 항목들은 DSS에서 반드시 수정해야 합니다:")
            lines.append("")

            for idx, correction in enumerate(result["corrections_needed"], 1):
                lines.append(f"[{idx}] {correction['severity_label']} {correction['metric']} ({correction['period']})")
                lines.append(f"  ❌ 현재 DSS 값: {correction['dss_current_value']}")
                lines.append(f"  ✅ 올바른 값: {correction['correct_value']}")
                lines.append(f"  📋 수정 지침: {correction['correction']}")
                lines.append(f"  📊 차이: {correction['difference_pct']:+.2f}%")
                lines.append(f"  🔍 DSS 문맥: \"{correction['dss_context'][:60]}...\"")
                lines.append("")

        # 불일치 항목 상세
        if result["discrepancies"]:
            lines.append("=" * 80)
            lines.append(f"⚠️  불일치 항목 상세 ({len(result['discrepancies'])}건)".center(80))
            lines.append("=" * 80)
            lines.append("")

            for idx, disc in enumerate(result["discrepancies"], 1):
                ec = disc["earning_call"]
                dss = disc["dss"]

                lines.append(f"[{idx}] {ec['metric']} ({ec['period']})")
                lines.append(f"  📄 어닝콜 원본: {ec['value']:,.2f} {ec['unit']}")
                lines.append(f"     문맥: \"{ec['context'][:80]}...\"")
                lines.append(f"  📊 DSS 데이터: {dss['value']:,.2f} {dss['unit']}")
                lines.append(f"     문맥: \"{dss['context'][:80]}...\"")
                lines.append(f"  ⚖️  차이: {disc['difference']:+,.2f} {ec['unit']} ({disc['difference_pct']:+.2f}%)")
                lines.append(f"  🎯 항목 유사도: {disc['similarity']:.1%}")
                lines.append("")

        # 일치 항목 (간단히)
        if result["matched"]:
            lines.append("=" * 80)
            lines.append(f"✅ 일치 항목 ({len(result['matched'])}건)".center(80))
            lines.append("=" * 80)
            lines.append("")

            for match in result["matched"][:10]:  # 처음 10개만 표시
                ec = match["earning_call"]
                lines.append(f"  ✓ {ec['metric']} ({ec['period']}): {ec['value']:,.2f} {ec['unit']}")

            if len(result["matched"]) > 10:
                lines.append(f"  ... 외 {len(result['matched']) - 10}개 항목")
            lines.append("")

        return "\n".join(lines)

    def _format_markdown(self, result: Dict[str, Any]) -> str:
        """마크다운 형식 보고서"""

        summary = result["summary"]
        lines = []

        lines.append("# 어닝콜 vs DSS 데이터 검수 결과\n")

        # 요약 통계
        lines.append("## 📊 요약 통계\n")
        lines.append(f"- **총 어닝콜 항목**: {summary['total_earning_call_items']}개")
        lines.append(f"- **총 DSS 항목**: {summary['total_dss_items']}개")
        lines.append(f"- ✅ **일치**: {summary['matched_count']}개")
        lines.append(f"- ⚠️ **불일치**: {summary['discrepancy_count']}개")
        lines.append(f"- 📌 **어닝콜에만 존재**: {summary['only_in_earning_call_count']}개")
        lines.append(f"- 📌 **DSS에만 존재**: {summary['only_in_dss_count']}개")
        lines.append(f"- **매칭률**: {summary['match_rate']:.1f}%\n")

        # DSS 수정사항 (최우선 표시)
        if result.get("corrections_needed"):
            lines.append(f"## 📝 DSS 수정사항 ({len(result['corrections_needed'])}건)\n")
            lines.append("> ⚠️  **아래 항목들은 DSS에서 반드시 수정해야 합니다**\n")

            # 심각도별로 정렬
            corrections_sorted = sorted(
                result["corrections_needed"],
                key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}[x["severity"]]
            )

            for idx, correction in enumerate(corrections_sorted, 1):
                lines.append(f"### {correction['severity_label']} 수정 #{idx}: {correction['metric']} ({correction['period']})\n")
                lines.append(f"**❌ 현재 DSS 값**: `{correction['dss_current_value']}`")
                lines.append(f"**✅ 올바른 값**: `{correction['correct_value']}`\n")
                lines.append(f"**📋 수정 지침**:")
                lines.append(f"> {correction['correction']}\n")
                lines.append(f"**📊 차이**: {correction['difference_pct']:+.2f}%")
                lines.append(f"**🔍 DSS 문맥**: _{correction['dss_context'][:100]}..._\n")
                lines.append("---\n")

        # 불일치 항목 상세
        if result["discrepancies"]:
            lines.append(f"## ⚠️ 불일치 항목 상세 ({len(result['discrepancies'])}건)\n")

            for idx, disc in enumerate(result["discrepancies"], 1):
                ec = disc["earning_call"]
                dss = disc["dss"]

                lines.append(f"### 불일치 #{idx}: {ec['metric']} ({ec['period']})\n")
                lines.append(f"**어닝콜 원본**:")
                lines.append(f"- 금액: **{ec['value']:,.2f} {ec['unit']}**")
                lines.append(f"- 문맥: _{ec['context'][:100]}..._\n")
                lines.append(f"**DSS 데이터**:")
                lines.append(f"- 금액: **{dss['value']:,.2f} {dss['unit']}**")
                lines.append(f"- 문맥: _{dss['context'][:100]}..._\n")
                lines.append(f"**차이**:")
                lines.append(f"- 금액 차이: **{disc['difference']:+,.2f} {ec['unit']}**")
                lines.append(f"- 비율 차이: **{disc['difference_pct']:+.2f}%**")
                lines.append(f"- 항목 유사도: {disc['similarity']:.1%}\n")
                lines.append("---\n")

        return "\n".join(lines)


if __name__ == "__main__":
    # 테스트 코드
    import json

    # 샘플 데이터
    earning_call = [
        {"company": "테크코리아", "period": "2024-Q4", "metric": "매출액", "value": 1250, "unit": "억원", "context": "매출액은 1,250억원"},
        {"company": "테크코리아", "period": "2024-Q4", "metric": "영업이익", "value": 185, "unit": "억원", "context": "영업이익은 185억원"},
    ]

    dss = [
        {"company": "테크코리아", "period": "2024-Q4", "metric": "매출액", "value": 1250, "unit": "억원", "context": "매출액은 1조 2,500억원"},
        {"company": "테크코리아", "period": "2024-Q4", "metric": "영업이익", "value": 178, "unit": "억원", "context": "영업이익은 1,780억원"},
    ]

    detector = DiscrepancyDetector(threshold=0.01)
    result = detector.compare(earning_call, dss)

    print(detector.format_report(result, "text"))
