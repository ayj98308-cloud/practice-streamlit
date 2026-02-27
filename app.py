# -*- coding: utf-8 -*-
"""
어닝콜 DSS 검수 시스템 - 웹 애플리케이션
Flask 기반 웹 UI
"""

from flask import Flask, render_template, request, jsonify, send_file
import os
import json
from pathlib import Path
from werkzeug.utils import secure_filename
from datetime import datetime
from bs4 import BeautifulSoup
import re
import requests
from PyPDF2 import PdfReader
from io import BytesIO

from src.financial_parser import FinancialDataParser
from src.discrepancy_detector import DiscrepancyDetector
from src.claude_skills import EarningCallSkills

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['SECRET_KEY'] = 'earning-call-validator-secret-key'

# 업로드 폴더 생성
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('output', exist_ok=True)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'csv', 'html', 'htm', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'}


def allowed_file(filename):
    """허용된 파일 확장자 확인"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_html(html_content: str) -> str:
    """
    HTML에서 실제 텍스트 내용만 추출
    PDF viewer 페이지인 경우 PDF URL을 추출하여 PDF를 다운로드하고 파싱

    Args:
        html_content: HTML 문자열

    Returns:
        추출된 텍스트
    """
    # PDF viewer 페이지 감지 (Naver Stock 등)
    if 'm.stock.naver.com/pdf' in html_content or ('canvas' in html_content[:1000] and 'pdf' in html_content.lower()[:500]):
        # PDF URL 추출 시도 - stock.pstatic.net에서 직접 호스팅되는 PDF 찾기
        pdf_url_match = re.search(r'https://stock\.pstatic\.net/[^\s"\'<>]+\.pdf', html_content)
        if pdf_url_match:
            pdf_url = pdf_url_match.group(0)
            try:
                print(f"PDF 다운로드 시도: {pdf_url}")
                # PDF 다운로드
                response = requests.get(pdf_url, timeout=30)
                response.raise_for_status()

                print(f"PDF 다운로드 완료: {len(response.content)} bytes")

                # PDF 헤더 검증
                if not response.content.startswith(b'%PDF'):
                    print(f"경고: PDF 헤더가 없습니다. 실제 content-type: {response.headers.get('content-type')}")
                    # PDF가 아닌 경우 일반 HTML 추출로 폴백
                    return ""

                # PDF 파싱
                pdf_file = BytesIO(response.content)
                reader = PdfReader(pdf_file)

                # 모든 페이지에서 텍스트 추출
                text_parts = []
                for page in reader.pages:
                    text_parts.append(page.extract_text())

                extracted_text = '\n\n'.join(text_parts)
                print(f"PDF 텍스트 추출 완료: {len(extracted_text)} characters")

                if extracted_text.strip():
                    return extracted_text.strip()
                else:
                    print("경고: PDF에서 텍스트를 추출했지만 비어있습니다")
                    return ""  # PDF에서 텍스트 추출 실패

            except Exception as e:
                print(f"PDF 다운로드/파싱 실패: {e}")
                import traceback
                traceback.print_exc()
                return ""  # PDF 처리 실패

    # 일반 HTML에서 텍스트 추출
    soup = BeautifulSoup(html_content, 'html.parser')

    # script, style 태그 제거
    for script in soup(["script", "style", "meta", "link", "noscript"]):
        script.decompose()

    # 텍스트 추출
    text = soup.get_text(separator='\n', strip=True)

    # 연속된 공백/줄바꿈 정리
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)

    # 의미있는 내용 확인
    if len(text.strip()) < 200:
        print(f"경고: HTML에서 추출한 텍스트가 너무 짧습니다: {len(text.strip())} characters")
        return ""

    print(f"HTML 텍스트 추출 완료: {len(text.strip())} characters")
    return text.strip()


def extract_text_from_image(image_data: bytes, image_type: str) -> str:
    """
    이미지에서 텍스트 추출 (Claude Vision API 사용)

    Args:
        image_data: 이미지 바이트 데이터
        image_type: 이미지 타입 (예: 'image/jpeg', 'image/png')

    Returns:
        추출된 텍스트
    """
    try:
        import anthropic
        import base64
        from PIL import Image

        # API 키 로드
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("경고: ANTHROPIC_API_KEY가 설정되지 않았습니다")
            return ""

        # 이미지 크기 확인 및 리사이즈
        image = Image.open(BytesIO(image_data))
        width, height = image.size
        print(f"원본 이미지 크기: {width}x{height}")

        # Claude API 제한: 최대 8000픽셀
        MAX_SIZE = 8000
        if width > MAX_SIZE or height > MAX_SIZE:
            # 비율을 유지하면서 리사이즈
            ratio = min(MAX_SIZE / width, MAX_SIZE / height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            print(f"리사이즈된 이미지 크기: {new_width}x{new_height}")

            # 리사이즈된 이미지를 bytes로 변환
            output = BytesIO()
            # PNG로 저장하여 품질 손실 방지
            image.save(output, format='PNG')
            image_data = output.getvalue()
            image_type = 'image/png'

        # 이미지를 base64로 인코딩
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        # Claude API 클라이언트 생성
        client = anthropic.Anthropic(api_key=api_key)

        # Claude에게 이미지에서 텍스트 추출 요청
        message = client.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-3-haiku-20240307"),
            max_tokens=4000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image_type,
                                "data": image_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": """이 이미지는 기업의 어닝콜 자료 또는 재무 보고서입니다.
이미지에서 모든 텍스트를 정확하게 추출해주세요.

추출 시 다음 사항을 주의해주세요:
1. 모든 숫자와 단위를 정확하게 추출
2. 표 형식의 데이터는 구조를 유지
3. 재무 지표명을 정확하게 추출 (매출액, 영업이익, 당기순이익 등)
4. 기간 정보를 정확하게 추출 (2024년 4분기, 2025년 1분기 등)

추출한 텍스트만 반환해주세요. 추가 설명이나 해석은 필요하지 않습니다."""
                        }
                    ],
                }
            ],
        )

        extracted_text = message.content[0].text
        print(f"이미지 텍스트 추출 완료: {len(extracted_text)} characters")
        return extracted_text.strip()

    except Exception as e:
        print(f"이미지 텍스트 추출 실패: {e}")
        import traceback
        traceback.print_exc()
        return ""


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """
    PDF 바이트 데이터에서 텍스트 추출 (OCR 폴백 포함)

    Args:
        pdf_bytes: PDF 파일의 바이트 데이터

    Returns:
        추출된 텍스트
    """
    try:
        # PDF 파싱 - 먼저 일반 텍스트 추출 시도
        pdf_file = BytesIO(pdf_bytes)
        reader = PdfReader(pdf_file)

        # 모든 페이지에서 텍스트 추출
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text())

        extracted_text = '\n\n'.join(text_parts)
        print(f"PDF 텍스트 추출 (PyPDF2): {len(extracted_text)} characters")

        # 텍스트가 너무 적으면 pdfplumber로 재시도
        if len(extracted_text.strip()) < 100:
            print("PyPDF2 추출 실패 - pdfplumber로 재시도...")
            try:
                import pdfplumber
                pdf_file_plumber = BytesIO(pdf_bytes)
                with pdfplumber.open(pdf_file_plumber) as pdf:
                    text_parts_plumber = []
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            text_parts_plumber.append(text)
                    extracted_text_plumber = '\n\n'.join(text_parts_plumber)
                    print(f"pdfplumber 추출: {len(extracted_text_plumber)} characters")

                    if len(extracted_text_plumber.strip()) >= 100:
                        return extracted_text_plumber.strip()
            except Exception as e:
                print(f"pdfplumber 실패: {e}")

        # 여전히 텍스트가 적으면 이미지 기반 PDF로 판단하고 Claude Vision 사용
        if len(extracted_text.strip()) < 100:
            print("텍스트가 너무 적음 - Claude Vision으로 OCR 시도...")
            try:
                import fitz  # PyMuPDF
                import base64
                import anthropic

                # PDF를 다시 열기
                pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
                page_texts = []

                # API 키 로드
                api_key = os.getenv('ANTHROPIC_API_KEY')
                if not api_key:
                    print("경고: ANTHROPIC_API_KEY가 설정되지 않았습니다")
                    return extracted_text.strip()

                client = anthropic.Anthropic(api_key=api_key)

                # 전체 페이지 처리 (정확도 우선)
                max_pages = len(pdf_document)  # 모든 페이지 처리
                print(f"총 {max_pages}개 페이지를 OCR 처리합니다...")

                # 모든 페이지를 이미지로 변환
                page_images = []
                for page_num in range(max_pages):
                    page = pdf_document[page_num]
                    # 페이지를 이미지로 렌더링 (150 DPI로 낮춰서 속도 개선)
                    pix = page.get_pixmap(matrix=fitz.Matrix(150/72, 150/72))
                    img_data = pix.tobytes("png")
                    page_images.append((page_num + 1, img_data))
                    print(f"페이지 {page_num + 1} 이미지 변환 완료: {len(img_data)} bytes")

                pdf_document.close()

                # 배치로 묶어서 처리 (모든 페이지를 한 번에)
                batch_size = 5  # 5페이지 한 번에 처리
                for batch_start in range(0, len(page_images), batch_size):
                    batch_end = min(batch_start + batch_size, len(page_images))
                    batch = page_images[batch_start:batch_end]

                    print(f"배치 처리 중: 페이지 {batch[0][0]}-{batch[-1][0]} ({len(batch)}개)")

                    # Claude API에 보낼 content 구성
                    content = []
                    for page_num, img_data in batch:
                        content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": base64.b64encode(img_data).decode('utf-8'),
                            },
                        })

                    # 텍스트 추출 요청
                    content.append({
                        "type": "text",
                        "text": f"""이 {len(batch)}개 이미지는 기업의 어닝콜 자료 또는 재무 보고서의 연속된 페이지입니다.

각 이미지에서 모든 텍스트를 정확하게 추출해주세요.

추출 시:
1. 모든 숫자와 단위를 정확하게 추출
2. 표 형식의 데이터는 구조를 유지
3. 재무 지표명을 정확하게 추출
4. 기간 정보를 정확하게 추출

각 페이지의 텍스트를 순서대로 반환해주세요."""
                    })

                    # Claude API 호출
                    message = client.messages.create(
                        model=os.getenv("CLAUDE_MODEL", "claude-3-haiku-20240307"),
                        max_tokens=4000,
                        messages=[{"role": "user", "content": content}],
                    )

                    batch_text = message.content[0].text
                    page_texts.append(batch_text)
                    print(f"배치 OCR 완료: {len(batch_text)} characters")

                if page_texts:
                    extracted_text = '\n\n'.join(page_texts)
                    print(f"Claude Vision OCR 완료: 총 {len(extracted_text)} characters")

            except ImportError:
                print("PyMuPDF (fitz) 라이브러리가 설치되지 않았습니다. pip install PyMuPDF")
            except Exception as e:
                print(f"Claude Vision OCR 실패: {e}")
                import traceback
                traceback.print_exc()

        return extracted_text.strip()

    except Exception as e:
        print(f"PDF 텍스트 추출 실패: {e}")
        import traceback
        traceback.print_exc()
        return ""


def download_and_extract_pdf_from_url(url: str) -> str:
    """
    URL에서 PDF를 다운로드하고 텍스트를 추출
    네이버 증권 PDF 뷰어 URL도 자동으로 처리

    Args:
        url: PDF URL 또는 네이버 증권 PDF 뷰어 URL

    Returns:
        추출된 텍스트
    """
    print(f"download_and_extract_pdf_from_url 호출됨: {url[:100]}...")  # 디버그

    try:
        import urllib.parse

        # 네이버 증권 PDF 뷰어 URL인 경우 실제 PDF URL 추출
        print(f"URL 타입 확인 중...")  # 디버그
        if 'm.stock.naver.com/pdf' in url or 'stock.naver.com/pdf' in url:
            print("네이버 증권 PDF 뷰어 URL 감지")  # 디버그
            # URL 파라미터에서 실제 PDF URL 추출
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            print(f"파싱된 쿼리 파라미터: {params}")  # 디버그

            if 'url' in params:
                pdf_url = params['url'][0]
                print(f"네이버 증권 PDF 뷰어에서 실제 PDF URL 추출: {pdf_url}")
            else:
                print(f"경고: URL 파라미터에서 PDF URL을 찾을 수 없습니다. 파라미터: {list(params.keys())}")
                return ""
        else:
            # 직접 PDF URL
            print("직접 PDF URL로 인식")  # 디버그
            pdf_url = url
            print(f"사용할 PDF URL: {pdf_url}")  # 디버그

        # PDF 다운로드
        print(f"PDF 다운로드 시도: {pdf_url}")
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()

        print(f"PDF 다운로드 완료: {len(response.content)} bytes")

        # PDF 헤더 검증
        if not response.content.startswith(b'%PDF'):
            print(f"경고: PDF 헤더가 없습니다. Content-Type: {response.headers.get('content-type')}")
            return ""

        # PDF 텍스트 추출 (OCR 폴백 포함)
        return extract_text_from_pdf_bytes(response.content)

    except Exception as e:
        error_msg = f"URL에서 PDF 다운로드/추출 실패: {type(e).__name__}: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        import sys
        sys.stdout.flush()  # 로그 즉시 출력
        return ""


@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index_new.html')


@app.route('/new')
def index_new():
    """새로운 UI 페이지"""
    return render_template('index_new.html')


@app.route('/api/validate', methods=['POST'])
def validate():
    """검수 실행 API"""
    try:
        # 디버그: 받은 form 데이터 확인
        print("=" * 80)
        print("validate() 함수 호출됨")
        print(f"Form keys: {list(request.form.keys())}")
        print(f"Files keys: {list(request.files.keys())}")
        for key in request.form.keys():
            value = request.form.get(key)
            print(f"  Form[{key}]: {value[:100] if value and len(value) > 100 else value}")
        print("=" * 80)
        import sys
        sys.stdout.flush()

        # 타임스탬프 생성 (결과 파일명 등에 사용)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # 텍스트 직접 입력 vs 파일 업로드 구분
        ec_text = None
        dss_text = None

        # 어닝콜 데이터 가져오기
        print("어닝콜 데이터 처리 시작...")
        sys.stdout.flush()
        if request.form.get('earning_call_text'):
            print("→ 텍스트 직접 입력 모드")
            sys.stdout.flush()
            # 텍스트 직접 입력
            ec_text = request.form.get('earning_call_text')
        elif request.form.get('earning_call_url'):
            print("→ URL 입력 모드")
            # URL 입력
            ec_url = request.form.get('earning_call_url')
            print(f"→ 받은 URL: {ec_url}")
            sys.stdout.flush()
            ec_text = download_and_extract_pdf_from_url(ec_url)
            print(f"→ 다운로드 결과: {len(ec_text) if ec_text else 0} characters")
            sys.stdout.flush()
            if not ec_text:
                print("→ 오류: URL에서 텍스트 추출 실패")
                sys.stdout.flush()
                return jsonify({'error': 'URL에서 PDF를 다운로드하거나 텍스트를 추출할 수 없습니다. URL이 올바른지 확인해주세요.'}), 400
        elif 'earning_call' in request.files:
            # 파일 업로드
            earning_call_file = request.files['earning_call']
            if earning_call_file.filename != '':
                if not allowed_file(earning_call_file.filename):
                    return jsonify({'error': '어닝콜 파일 형식이 허용되지 않습니다'}), 400

                original_filename = earning_call_file.filename

                # PDF 파일인 경우 직접 파싱 (OCR 폴백 포함)
                if original_filename.lower().endswith('.pdf'):
                    try:
                        pdf_bytes = earning_call_file.read()
                        ec_text = extract_text_from_pdf_bytes(pdf_bytes)

                        if not ec_text.strip():
                            return jsonify({'error': 'PDF에서 텍스트를 추출할 수 없습니다. 다시 시도해주세요.'}), 400
                    except Exception as e:
                        return jsonify({'error': f'PDF 파싱 실패: {str(e)}'}), 400

                # 이미지 파일인 경우 Claude Vision으로 텍스트 추출
                elif original_filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')):
                    try:
                        image_data = earning_call_file.read()

                        # 이미지 타입 결정
                        ext = original_filename.lower().rsplit('.', 1)[1]
                        image_type_map = {
                            'jpg': 'image/jpeg',
                            'jpeg': 'image/jpeg',
                            'png': 'image/png',
                            'gif': 'image/gif',
                            'bmp': 'image/bmp',
                            'webp': 'image/webp'
                        }
                        image_type = image_type_map.get(ext, 'image/jpeg')

                        ec_text = extract_text_from_image(image_data, image_type)

                        if not ec_text.strip():
                            return jsonify({'error': '이미지에서 텍스트를 추출할 수 없습니다. 이미지가 흐리거나 텍스트가 없을 수 있습니다.'}), 400
                    except Exception as e:
                        return jsonify({'error': f'이미지 처리 실패: {str(e)}'}), 400

                else:
                    # 텍스트 기반 파일 (TXT, HTML 등)
                    ec_filename = secure_filename(f"{timestamp}_earning_call.txt")
                    ec_path = os.path.join(app.config['UPLOAD_FOLDER'], ec_filename)
                    earning_call_file.save(ec_path)

                    with open(ec_path, 'r', encoding='utf-8') as f:
                        ec_text = f.read()

                    # HTML 파일인 경우 텍스트 추출 (PDF 자동 다운로드 포함)
                    if original_filename.lower().endswith(('.html', '.htm')) or ec_text.strip().startswith('<!DOCTYPE') or ec_text.strip().startswith('<html'):
                        extracted = extract_text_from_html(ec_text)
                        if not extracted:
                            return jsonify({'error': '어닝콜 HTML 파일에서 텍스트를 추출할 수 없습니다. PDF를 직접 업로드하거나 텍스트를 복사하여 "텍스트 입력" 탭에 붙여넣어주세요.'}), 400
                        ec_text = extracted

        # DSS 데이터 가져오기
        if request.form.get('dss_data_text'):
            # 텍스트 직접 입력
            dss_text = request.form.get('dss_data_text')
        elif request.form.get('dss_data_url'):
            # URL 입력
            dss_url = request.form.get('dss_data_url')
            dss_text = download_and_extract_pdf_from_url(dss_url)
            if not dss_text:
                return jsonify({'error': 'URL에서 PDF를 다운로드하거나 텍스트를 추출할 수 없습니다. URL이 올바른지 확인해주세요.'}), 400
        elif 'dss_data' in request.files:
            # 파일 업로드
            dss_file = request.files['dss_data']
            if dss_file.filename != '':
                if not allowed_file(dss_file.filename):
                    return jsonify({'error': 'DSS 파일 형식이 허용되지 않습니다'}), 400

                original_filename = dss_file.filename

                # PDF 파일인 경우 직접 파싱 (OCR 폴백 포함)
                if original_filename.lower().endswith('.pdf'):
                    try:
                        pdf_bytes = dss_file.read()
                        dss_text = extract_text_from_pdf_bytes(pdf_bytes)

                        if not dss_text.strip():
                            return jsonify({'error': 'PDF에서 텍스트를 추출할 수 없습니다. 다시 시도해주세요.'}), 400
                    except Exception as e:
                        return jsonify({'error': f'PDF 파싱 실패: {str(e)}'}), 400

                # 이미지 파일인 경우 Claude Vision으로 텍스트 추출
                elif original_filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')):
                    try:
                        image_data = dss_file.read()

                        # 이미지 타입 결정
                        ext = original_filename.lower().rsplit('.', 1)[1]
                        image_type_map = {
                            'jpg': 'image/jpeg',
                            'jpeg': 'image/jpeg',
                            'png': 'image/png',
                            'gif': 'image/gif',
                            'bmp': 'image/bmp',
                            'webp': 'image/webp'
                        }
                        image_type = image_type_map.get(ext, 'image/jpeg')

                        dss_text = extract_text_from_image(image_data, image_type)

                        if not dss_text.strip():
                            return jsonify({'error': '이미지에서 텍스트를 추출할 수 없습니다. 이미지가 흐리거나 텍스트가 없을 수 있습니다.'}), 400
                    except Exception as e:
                        return jsonify({'error': f'이미지 처리 실패: {str(e)}'}), 400

                else:
                    # 텍스트 기반 파일 (TXT, HTML 등)
                    dss_filename = secure_filename(f"{timestamp}_dss_data.txt")
                    dss_path = os.path.join(app.config['UPLOAD_FOLDER'], dss_filename)
                    dss_file.save(dss_path)

                    with open(dss_path, 'r', encoding='utf-8') as f:
                        dss_text = f.read()

                    # HTML 파일인 경우 텍스트 추출 (PDF 자동 다운로드 포함)
                    if original_filename.lower().endswith(('.html', '.htm')) or dss_text.strip().startswith('<!DOCTYPE') or dss_text.strip().startswith('<html'):
                        extracted = extract_text_from_html(dss_text)
                        if not extracted:
                            return jsonify({'error': 'DSS 파일에서 텍스트를 추출할 수 없습니다. HTML에서 PDF를 자동 추출하려 했으나 실패했습니다. 실제 텍스트를 복사하여 "텍스트 입력" 탭에 붙여넣어주세요.'}), 400
                        dss_text = extracted

        # 데이터 검증
        if not ec_text or not dss_text:
            print(f"[ERROR] 데이터 누락: ec_text={bool(ec_text)}, dss_text={bool(dss_text)}")
            return jsonify({'error': '어닝콜 문서와 DSS 데이터를 모두 입력해주세요'}), 400

        print(f"[OK] 데이터 검증 완료: ec_text={len(ec_text)} chars, dss_text={len(dss_text)} chars")
        sys.stdout.flush()

        try:
            parser = FinancialDataParser()
            print("[OK] FinancialDataParser 초기화 성공")
            sys.stdout.flush()
        except Exception as e:
            print(f"[ERROR] FinancialDataParser 초기화 실패: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
            return jsonify({'error': f'파서 초기화 실패: {str(e)}'}), 500

        # 빠른 처리를 위해 한 번의 API 호출로 두 문서 모두 파싱
        print("[DEBUG] 배치 파싱 블록 진입 직전...")
        sys.stdout.flush()
        try:
            print("[FAST] 배치 파싱 시작 (한 번의 API 호출)...")
            sys.stdout.flush()
            ec_raw_data, dss_raw_data = parser.extract_both_documents(ec_text, dss_text)
            print(f"DEBUG: ec_raw_data type={type(ec_raw_data)}, length={len(ec_raw_data) if isinstance(ec_raw_data, list) else 'N/A'}")
            print(f"DEBUG: dss_raw_data type={type(dss_raw_data)}, length={len(dss_raw_data) if isinstance(dss_raw_data, list) else 'N/A'}")
            sys.stdout.flush()

            ec_data = parser.normalize_financial_data(ec_raw_data)
            dss_data = parser.normalize_financial_data(dss_raw_data)
            print(f"[OK] 파싱 완료: 어닝콜 {len(ec_data)}개 항목, DSS {len(dss_data)}개 항목")
            sys.stdout.flush()
        except Exception as e:
            print(f"[ERROR] 배치 파싱 오류: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
            return jsonify({'error': f'배치 파싱 실패: {str(e)}'}), 500

        # 2단계: 비교 및 불일치 감지
        detector = DiscrepancyDetector(threshold=0.01)
        comparison_result = detector.compare(ec_data, dss_data)

        # 2-0.5단계: Corrections을 ### 마크다운 헤더 기반으로 재태깅
        print("[재태깅] Corrections을 섹션별로 재분류 중...")
        sys.stdout.flush()
        comparison_result['corrections_needed'] = parser.retag_corrections_by_sections(
            comparison_result.get('corrections_needed', []),
            dss_text
        )
        print(f"[재태깅] 완료: {len(comparison_result['corrections_needed'])}개 corrections 재분류됨")
        sys.stdout.flush()

        # 2-1단계: DSS 해석 정확성 검증 (문맥, 과장, 확대해석 체크)
        # financial_parser.py에서 상세한 로그 출력
        interpretation_validation = parser.validate_dss_interpretation(ec_text, dss_text)

        # 2-2단계: DSS 수정본 생성 (3가지 버전)
        print("[DSS] 수정본 생성 시작...")
        sys.stdout.flush()
        corrected_dss_versions = parser.generate_corrected_dss_versions(
            original_dss=dss_text,
            ec_text=ec_text,
            corrections=comparison_result.get('corrections_needed', []),
            interpretation_issues=interpretation_validation.get('interpretation_issues', [])
        )
        print(f"[DSS] 수정본 생성 완료 (3가지 버전)")
        sys.stdout.flush()

        # 3단계: 결과 저장
        full_result = {
            **comparison_result,
            'interpretation_validation': interpretation_validation
        }
        result_filename = f"{timestamp}_result.json"
        result_path = os.path.join('output', result_filename)

        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(full_result, f, ensure_ascii=False, indent=2)

        # 4단계: 응답 생성
        return jsonify({
            'success': True,
            'result': {
                'summary': comparison_result['summary'],
                'matched': comparison_result['matched'][:20],  # 처음 20개
                'discrepancies': comparison_result['discrepancies'][:20],  # 처음 20개
                'corrections_needed': comparison_result['corrections_needed'],  # DSS 수정사항 (전체)
                'only_in_earning_call': comparison_result['only_in_earning_call'][:10],  # 어닝콜에만 있는 항목
                'only_in_dss': comparison_result['only_in_dss'][:10],  # DSS에만 있는 항목
                'interpretation_validation': interpretation_validation,  # 문맥 및 해석 검증 결과
                'corrected_dss_versions': corrected_dss_versions,  # DSS 수정본 (3가지 버전)
                'result_file': result_filename,
                'earning_call_metrics': len(ec_data),
                'dss_metrics': len(dss_data)
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/skills/search', methods=['POST'])
def skill_search():
    """Claude Skill: 키워드 검색"""
    try:
        data = request.json
        keyword = data.get('keyword')
        earning_call_text = data.get('earning_call_text')

        if not keyword or not earning_call_text:
            return jsonify({'error': '필수 파라미터가 없습니다'}), 400

        skills = EarningCallSkills(earning_call_text, "")
        result = skills.search_original_document_for_keywords(keyword, context_lines=2)

        return jsonify({'success': True, 'result': result})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/skills/explain', methods=['POST'])
def skill_explain():
    """Claude Skill: 불일치 분석"""
    try:
        data = request.json

        metric_name = data.get('metric_name')
        earning_call_value = data.get('earning_call_value')
        dss_value = data.get('dss_value')
        period = data.get('period')
        earning_call_text = data.get('earning_call_text')
        dss_text = data.get('dss_text')

        if not all([metric_name, earning_call_value is not None, dss_value is not None, period]):
            return jsonify({'error': '필수 파라미터가 없습니다'}), 400

        skills = EarningCallSkills(earning_call_text, dss_text)
        result = skills.explain_discrepancy(
            metric_name=metric_name,
            earning_call_value=float(earning_call_value),
            dss_value=float(dss_value),
            period=period
        )

        return jsonify({'success': True, 'result': result})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/skills/propose', methods=['POST'])
def skill_propose():
    """Claude Skill: DSS 수정 제안"""
    try:
        data = request.json

        metric_name = data.get('metric_name')
        current_value = data.get('current_value')
        correct_value = data.get('correct_value')
        period = data.get('period')
        reason = data.get('reason', '')

        if not all([metric_name, current_value is not None, correct_value is not None, period]):
            return jsonify({'error': '필수 파라미터가 없습니다'}), 400

        skills = EarningCallSkills("", "")
        result = skills.propose_dss_update_for_review(
            metric_name=metric_name,
            current_dss_value=float(current_value),
            correct_value=float(correct_value),
            period=period,
            reason=reason
        )

        return jsonify({'success': True, 'result': result})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/<filename>')
def download(filename):
    """결과 파일 다운로드"""
    try:
        file_path = os.path.join('output', secure_filename(filename))
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({'error': '파일을 찾을 수 없습니다'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health')
def health():
    """헬스 체크"""
    return jsonify({'status': 'ok', 'service': 'earning-call-validator'})


if __name__ == '__main__':
    print("=" * 80)
    print("어닝콜 DSS 검수 시스템 - 웹 서버 시작".center(80))
    print("=" * 80)
    print("\n서버 주소: http://localhost:5000")
    print("브라우저에서 위 주소로 접속하세요.\n")
    print("종료하려면 Ctrl+C를 누르세요.\n")

    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
