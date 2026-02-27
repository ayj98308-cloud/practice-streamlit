#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude API 키 및 모델 접근 권한 테스트 스크립트
"""
import os
import sys
from anthropic import Anthropic
from dotenv import load_dotenv

# Windows 인코딩 설정
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

# .env 파일 로드
load_dotenv()

def test_api_key():
    """API 키와 다양한 모델 접근 권한 테스트"""

    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        return

    print("=" * 80)
    print("Claude API 키 테스트")
    print("=" * 80)
    print(f"\n[KEY] API 키: {api_key[:20]}...{api_key[-10:]}")
    print()

    # 테스트할 모델 목록 (최신 모델부터 오래된 모델까지)
    models_to_test = [
        # Claude 3.5 Sonnet
        "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-20240620",
        "claude-3-5-sonnet",

        # Claude 3 Opus
        "claude-3-opus-20240229",
        "claude-3-opus",

        # Claude 3 Sonnet (older)
        "claude-3-sonnet-20240229",
        "claude-3-sonnet",

        # Claude 3 Haiku
        "claude-3-haiku-20240307",
        "claude-3-haiku",

        # Legacy models
        "claude-2.1",
        "claude-2.0",
    ]

    client = Anthropic(api_key=api_key)

    print("[TEST] 모델 접근 권한 테스트 중...\n")
    print("-" * 80)

    working_models = []
    failed_models = []

    for model in models_to_test:
        try:
            # 간단한 테스트 메시지 전송
            response = client.messages.create(
                model=model,
                max_tokens=10,
                messages=[
                    {"role": "user", "content": "Hi"}
                ]
            )

            status = "[OK] 작동"
            working_models.append(model)
            print(f"{status:15} | {model}")

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)

            if "not_found_error" in error_msg or "404" in error_msg:
                status = "[X] 없음"
            elif "permission" in error_msg.lower() or "unauthorized" in error_msg.lower():
                status = "[DENY] 권한없음"
            elif "rate_limit" in error_msg.lower():
                status = "[LIMIT] 제한"
            else:
                status = f"[ERR] {error_type}"

            failed_models.append((model, error_type))
            print(f"{status:15} | {model}")

    print("-" * 80)
    print("\n[RESULT] 테스트 결과:")
    print(f"   [OK] 사용 가능한 모델: {len(working_models)}개")
    print(f"   [X] 사용 불가능한 모델: {len(failed_models)}개")

    if working_models:
        print("\n[RECOMMEND] 권장 모델:")
        print(f"   {working_models[0]}")
        print("\n[ACTION] .env 파일을 다음과 같이 수정하세요:")
        print(f"   CLAUDE_MODEL={working_models[0]}")
    else:
        print("\n[WARNING] 사용 가능한 모델이 없습니다!")
        print("   API 키를 확인하거나 Anthropic 콘솔에서 권한을 확인하세요.")
        print("   https://console.anthropic.com/")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    try:
        test_api_key()
    except Exception as e:
        print(f"\n[ERROR] 오류 발생: {e}")
        import traceback
        traceback.print_exc()
