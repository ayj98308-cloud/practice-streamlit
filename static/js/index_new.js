// Global state
let validationResult = null;
let selectedDiscrepancyIndex = null;
let itemStatuses = {}; // Track status of each item by ID
let itemEditedTexts = {}; // Track manually edited texts by ID

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
});

function initializeEventListeners() {
    const form = document.getElementById('uploadForm');
    if (form) {
        form.addEventListener('submit', handleFormSubmit);
    }

    // Input method toggle
    const urlRadio = document.getElementById('inputUrl');
    const textRadio = document.getElementById('inputText');
    const urlInput = document.getElementById('urlInputSection');
    const textInput = document.getElementById('textInputSection');

    if (urlRadio && textRadio) {
        urlRadio.addEventListener('change', function() {
            if (this.checked) {
                urlInput.style.display = 'block';
                textInput.style.display = 'none';
            }
        });

        textRadio.addEventListener('change', function() {
            if (this.checked) {
                urlInput.style.display = 'none';
                textInput.style.display = 'block';
            }
        });
    }

    // URL conversion button
    const convertBtn = document.getElementById('convertUrlBtn');
    if (convertBtn) {
        convertBtn.addEventListener('click', handleUrlConversion);
    }
}

function handleUrlConversion() {
    const urlInput = document.getElementById('earningCallUrl');
    const url = urlInput.value.trim();

    if (!url) {
        alert('URL을 먼저 입력해주세요.');
        return;
    }

    let convertedUrl = url;
    let wasConverted = false;

    // 1. 네이버 모바일 뷰어 URL에서 url 파라미터 추출 및 디코딩
    // 예: https://m.stock.naver.com/pdf?url=https%3A%2F%2Fstock.pstatic.net%2F...
    // -> https://stock.pstatic.net/...
    if (url.includes('m.stock.naver.com/pdf?url=')) {
        try {
            const urlObj = new URL(url);
            const urlParam = urlObj.searchParams.get('url');

            if (urlParam) {
                convertedUrl = decodeURIComponent(urlParam);
                wasConverted = true;
                console.log('네이버 모바일 뷰어 URL에서 PDF URL 추출:', convertedUrl);
            }
        } catch (e) {
            console.error('네이버 모바일 뷰어 URL 파싱 오류:', e);
        }
    }

    // 2. URL 디코딩 (인코딩된 문자 변환)
    if (!wasConverted) {
        try {
            const decodedUrl = decodeURIComponent(url);
            if (decodedUrl !== url) {
                convertedUrl = decodedUrl;
                wasConverted = true;
                console.log('URL 디코딩:', convertedUrl);
            }
        } catch (e) {
            console.log('URL 디코딩 불필요 또는 실패:', e);
        }
    }

    // 3. 네이버 증권 뷰어 URL을 직접 PDF URL로 변환
    if (convertedUrl.includes('stock.pstatic.net') && convertedUrl.includes('/viewer/')) {
        try {
            // viewer URL에서 파일명 추출
            const match = convertedUrl.match(/\/viewer\/.*?\/([^?]+)/);
            if (match) {
                // 직접 PDF URL 생성
                convertedUrl = convertedUrl.replace(/\/viewer\//, '/').split('?')[0];
                wasConverted = true;
                console.log('뷰어 URL 변환:', convertedUrl);
            }
        } catch (e) {
            console.error('뷰어 URL 변환 오류:', e);
        }
    }

    // 4. .pdf 확장자 확인 및 추가
    if (!convertedUrl.endsWith('.pdf')) {
        convertedUrl = convertedUrl + '.pdf';
        wasConverted = true;
        console.log('.pdf 확장자 추가:', convertedUrl);
    }

    // 5. 결과 표시
    if (wasConverted) {
        urlInput.value = convertedUrl;
        alert('URL이 변환되었습니다!\n\n변환된 URL:\n' + convertedUrl + '\n\n새 탭에서 열립니다.');
        // 변환된 URL을 새 탭에서 열기
        window.open(convertedUrl, '_blank');
    } else {
        // 변환이 필요 없더라도 URL 정규화 (공백 제거 등)
        const normalizedUrl = convertedUrl.trim();
        if (normalizedUrl !== url) {
            urlInput.value = normalizedUrl;
            alert('URL이 정규화되었습니다!');
        } else {
            alert('이미 올바른 형식의 PDF URL입니다.\n\nURL: ' + convertedUrl);
        }
    }
}

async function handleFormSubmit(e) {
    e.preventDefault();

    const inputMethod = document.querySelector('input[name="inputMethod"]:checked').value;
    const dssDataText = document.getElementById('dssDataText').value;

    if (!dssDataText.trim()) {
        alert('DSS 데이터를 입력해주세요.');
        return;
    }

    const formData = new FormData();
    formData.append('dss_data_text', dssDataText);

    if (inputMethod === 'url') {
        const earningCallUrl = document.getElementById('earningCallUrl').value;
        if (!earningCallUrl.trim()) {
            alert('어닝콜 URL을 입력해주세요.');
            return;
        }
        formData.append('earning_call_url', earningCallUrl);
    } else {
        const earningCallText = document.getElementById('earningCallText').value;
        if (!earningCallText.trim()) {
            alert('어닝콜 텍스트를 입력해주세요.');
            return;
        }
        formData.append('earning_call_text', earningCallText);
    }

    showLoading(true);

    try {
        const response = await fetch('/api/validate', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('검증 요청 실패');
        }

        const data = await response.json();

        // Backend returns { success: true, result: {...} }
        // We need to extract the nested result
        if (data.success && data.result) {
            validationResult = data.result;
            itemStatuses = {}; // Reset item statuses for new validation
        } else {
            throw new Error(data.error || '알 수 없는 오류가 발생했습니다');
        }

        // Hide input section, show results
        document.getElementById('inputSection').style.display = 'none';
        document.getElementById('mainApp').style.display = 'flex';

        // Render results
        renderResults(validationResult);

    } catch (error) {
        console.error('Error:', error);
        alert('검증 중 오류가 발생했습니다: ' + error.message);
    } finally {
        showLoading(false);
    }
}

function renderResults(result) {
    // Update header
    updateHeader(result);

    // Organize data by section type
    const sections = organizeBySections(result);

    // Update tab badges
    updateTabBadges(sections);

    // Initialize tabs
    initializeTabs(sections);

    // Render initial active section
    const activeSection = '실적발표';
    renderSection(activeSection, sections[activeSection]);

    // Render navigation sidebar
    renderNavigationSidebar(sections);

    // Update progress stats
    updateProgressStats(sections);
}

function organizeBySections(result) {
    const sections = {
        '실적발표': { corrections: [], issues: [], items: [] },
        '가이던스': { corrections: [], issues: [], items: [] },
        'Q&A': { corrections: [], issues: [], items: [] }
    };

    // Organize corrections
    if (result.corrections_needed && result.corrections_needed.length > 0) {
        result.corrections_needed.forEach((item, idx) => {
            const type = item.type || '실적';
            const sectionName = type === '실적' ? '실적발표' : type === '가이던스' ? '가이던스' : 'Q&A';
            if (sections[sectionName]) {
                const itemId = `correction-${idx}`;
                const status = itemStatuses[itemId] || 'pending';
                const itemWithId = { ...item, id: itemId, itemType: 'correction', status: status };
                sections[sectionName].corrections.push(itemWithId);
                sections[sectionName].items.push(itemWithId);
            }
        });
    }

    // Organize interpretation issues
    if (result.interpretation_validation?.interpretation_issues) {
        result.interpretation_validation.interpretation_issues.forEach((issue, idx) => {
            const type = issue.type || '실적';
            const sectionName = type === '실적' ? '실적발표' : type === '가이던스' ? '가이던스' : 'Q&A';
            if (sections[sectionName]) {
                const itemId = `issue-${idx}`;
                const status = itemStatuses[itemId] || 'pending';
                const itemWithId = { ...issue, id: itemId, itemType: 'issue', status: status };
                sections[sectionName].issues.push(itemWithId);
                sections[sectionName].items.push(itemWithId);
            }
        });
    }

    return sections;
}

function updateTabBadges(sections) {
    Object.keys(sections).forEach(sectionName => {
        const section = sections[sectionName];
        const totalIssues = section.corrections.length + section.issues.length;
        const badge = document.getElementById(`badge-${sectionName}`);
        if (badge) {
            badge.textContent = totalIssues;
            badge.style.display = totalIssues > 0 ? 'inline-flex' : 'none';
        }
    });
}

function initializeTabs(sections) {
    const tabItems = document.querySelectorAll('.tab-item');
    tabItems.forEach(tab => {
        tab.addEventListener('click', function() {
            const sectionName = this.getAttribute('data-section');

            // Update active tab
            tabItems.forEach(t => t.classList.remove('active'));
            this.classList.add('active');

            // Render section content
            if (sectionName === '최종수정안') {
                renderFinalDraft(sections);
            } else {
                renderSection(sectionName, sections[sectionName]);
            }
        });
    });
}

function renderSection(sectionName, section) {
    const container = document.getElementById('sectionsContent');
    if (!container) return;

    if (!section || section.items.length === 0) {
        container.innerHTML = `
            <div class="text-center text-muted p-5">
                <i class="fas fa-check-circle fa-3x mb-3"></i>
                <h5>이 섹션에는 문제가 없습니다</h5>
            </div>
        `;
        return;
    }

    let html = '';

    // Render each item (correction or issue)
    section.items.forEach((item, idx) => {
        html += renderSectionCard(sectionName, item, idx);
    });

    container.innerHTML = html;
}

function renderSectionCard(sectionName, item, idx) {
    const cardId = `card-${sectionName}-${item.id}`;

    if (item.itemType === 'correction') {
        return renderCorrectionCard(sectionName, item, idx, cardId);
    } else {
        return renderIssueCard(sectionName, item, idx, cardId);
    }
}

function renderCorrectionCard(sectionName, item, idx, cardId) {
    const dssContext = item.dss_context || '';
    const dssValue = String(item.dss_current_value || '');
    const correctValue = String(item.correct_value || '');

    // Debug logging
    console.log(`[DEBUG] renderCorrectionCard for ${item.metric}`);
    console.log(`  dss_context: "${dssContext.substring(0, 100)}..."`);
    console.log(`  dss_current_value: "${dssValue}"`);
    console.log(`  correct_value: "${correctValue}"`);

    // Create actual corrected text for afterText
    let correctedContext = dssContext;
    let replacementMade = false;

    // Strategy 1: Try direct string replacement
    if (dssValue && dssContext.includes(dssValue)) {
        correctedContext = dssContext.replace(dssValue, correctValue);
        replacementMade = true;
        console.log('  ✓ Strategy 1 succeeded: direct string replacement');
    }
    // Strategy 2: Try with flexible spacing/commas in numbers
    else if (dssValue) {
        // Remove spaces and normalize for matching
        const normalizedDss = dssValue.replace(/\s/g, '');
        const normalizedContext = dssContext.replace(/\s/g, '');

        if (normalizedContext.includes(normalizedDss)) {
            // Find the actual position with spaces
            const pattern = dssValue.split('').map(c => {
                if (/\d/.test(c)) return c;
                if (c === ',') return ',?\\s*';
                return '\\s*' + escapeRegex(c);
            }).join('');

            const regex = new RegExp(pattern);
            const match = dssContext.match(regex);

            if (match) {
                correctedContext = dssContext.replace(regex, correctValue);
                replacementMade = true;
                console.log('  ✓ Strategy 2 succeeded: flexible spacing match');
            }
        }
    }
    // Strategy 3: Try numeric part only
    if (!replacementMade && dssValue) {
        const numMatch = dssValue.match(/[\d,\.]+/);
        if (numMatch) {
            const numericPart = numMatch[0];
            if (dssContext.includes(numericPart)) {
                // Extract numeric part from correct value
                const correctNumMatch = correctValue.match(/[\d,\.]+/);
                const correctNumeric = correctNumMatch ? correctNumMatch[0] : correctValue;

                correctedContext = dssContext.replace(numericPart, correctNumeric);
                replacementMade = true;
                console.log(`  ✓ Strategy 3 succeeded: numeric match "${numericPart}" -> "${correctNumeric}"`);
            }
        }
    }

    // If no replacement made, just use the original context
    if (!replacementMade) {
        console.log('  ✗ No replacement strategy succeeded, using original + correct value');
        correctedContext = dssContext; // 원본 유지
    }

    // Now create highlighted versions for display
    let beforeText = escapeHtml(dssContext);
    let afterText = escapeHtml(correctedContext);

    // Add highlighting for the changed parts
    const escapedDssValue = escapeHtml(dssValue);
    const escapedCorrectValue = escapeHtml(correctValue);

    // Highlight in before text (red removal)
    if (beforeText.includes(escapedDssValue)) {
        beforeText = beforeText.replace(
            new RegExp(escapeRegex(escapedDssValue), 'g'),
            `<span class="highlight-removal">${escapedDssValue}</span>`
        );
    } else {
        // Try numeric part
        const numMatch = dssValue.match(/[\d,\.]+/);
        if (numMatch && beforeText.includes(escapeHtml(numMatch[0]))) {
            const escapedNumeric = escapeHtml(numMatch[0]);
            beforeText = beforeText.replace(
                new RegExp(escapeRegex(escapedNumeric), 'g'),
                `<span class="highlight-removal">${escapedNumeric}</span>`
            );
        }
    }

    // Highlight in after text (green addition)
    if (afterText.includes(escapedCorrectValue)) {
        afterText = afterText.replace(
            new RegExp(escapeRegex(escapedCorrectValue), 'g'),
            `<span class="highlight-addition">${escapedCorrectValue}</span>`
        );
    } else {
        // Try numeric part
        const correctNumMatch = correctValue.match(/[\d,\.]+/);
        if (correctNumMatch && afterText.includes(escapeHtml(correctNumMatch[0]))) {
            const escapedCorrectNumeric = escapeHtml(correctNumMatch[0]);
            afterText = afterText.replace(
                new RegExp(escapeRegex(escapedCorrectNumeric), 'g'),
                `<span class="highlight-addition">${escapedCorrectNumeric}</span>`
            );
        }
    }

    return `
        <div class="section-card" id="${cardId}">
            <div class="section-header">
                <div>
                    <strong>${escapeHtml(item.metric || 'N/A')}</strong>
                    <small class="text-muted ms-2">${escapeHtml(item.period || '')}</small>
                </div>
                <span class="badge bg-danger">불일치</span>
            </div>

            <!-- Diff View -->
            <div class="diff-container">
                <div class="diff-panel">
                    <div class="diff-label before">
                        <i class="fas fa-minus-circle"></i>
                        <span>변경 전 (DSS 원본)</span>
                    </div>
                    <div class="diff-text">${beforeText}</div>
                </div>
                <div class="diff-panel">
                    <div class="diff-label after">
                        <i class="fas fa-plus-circle"></i>
                        <span>변경 후 (수정)</span>
                    </div>
                    <div class="diff-text">${afterText}</div>
                </div>
            </div>

            <!-- Discrepancy Details -->
            <div class="discrepancy-list">
                <div class="discrepancy-card">
                    <div class="discrepancy-header">
                        <div>
                            <div class="fw-bold mb-1">${escapeHtml(item.metric || 'N/A')}</div>
                            <small class="text-muted">${escapeHtml(item.period || '')}</small>
                        </div>
                    </div>

                    <div class="value-comparison">
                        <div class="value-box">
                            <div class="value-label">DSS 원본 값</div>
                            <div class="value-text text-danger">${escapeHtml(dssValue)}</div>
                        </div>
                        <div><i class="fas fa-arrow-right text-muted"></i></div>
                        <div class="value-box">
                            <div class="value-label">수정된 값</div>
                            <div class="value-text text-success">${escapeHtml(correctValue)}</div>
                        </div>
                    </div>

                    <div class="mb-2">
                        <small class="text-muted"><i class="fas fa-info-circle"></i> 수정 이유</small>
                        <div class="mt-1">${escapeHtml(item.correction || 'N/A')}</div>
                    </div>

                    <div class="mb-2">
                        <small class="text-muted"><i class="fas fa-book"></i> 어닝콜 원문 근거</small>
                        <div class="mt-1" style="line-height: 1.6; color: #6b7280;">
                            ${escapeHtml(item.earning_call_context || '원문에서 근거를 찾지 못했습니다')}
                        </div>
                    </div>

                    <div class="action-buttons">
                        <button class="btn-accept" onclick="acceptItem('${item.id}', event)">
                            <i class="fas fa-check"></i> 승인
                        </button>
                        <button class="btn-reject" onclick="rejectItem('${item.id}', event)">
                            <i class="fas fa-times"></i> 거부
                        </button>
                        <button class="btn-manual" onclick="manualEditItem('${item.id}', event)">
                            <i class="fas fa-pencil"></i> 수동
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function renderIssueCard(sectionName, item, idx, cardId) {
    const dssText = escapeHtml(item.dss_sentence || item.dss_statement || item.issue || '');
    const recommendation = item.recommendation || '';
    const earningCallContext = item.earning_call_context || '';
    const metric = item.metric || '문맥 이슈';
    const issueType = item.issue_type || '';

    // 일치함 여부 확인
    const isPassed = metric === '일치함' || item.validation_status === 'passed';

    // 이슈 타입에 따른 아이콘 및 색상 설정
    let badgeIcon = '';
    let badgeColor = '';
    let badgeText = '';
    let diffLabelIcon = '';
    let diffLabelColor = '';
    let highlightClass = '';

    if (isPassed) {
        // 문제 없음 (일치함)
        badgeIcon = 'fa-check-circle';
        badgeColor = 'bg-success';
        badgeText = '일치함';
        diffLabelIcon = 'fa-check-circle';
        diffLabelColor = 'success';
        highlightClass = ''; // 하이라이트 없음
    } else if (issueType === '수치오류' || issueType === '수치' || metric.includes('수치')) {
        // 수치 이슈
        badgeIcon = 'fa-times-circle';
        badgeColor = 'bg-danger';
        badgeText = '수치 이슈';
        diffLabelIcon = 'fa-exclamation-triangle';
        diffLabelColor = 'danger';
        highlightClass = 'highlight-removal';
    } else {
        // 문맥 이슈 (경미한 이슈)
        badgeIcon = 'fa-exclamation-triangle';
        badgeColor = 'bg-warning text-dark';
        badgeText = '문맥 이슈';
        diffLabelIcon = 'fa-exclamation-triangle';
        diffLabelColor = 'warning';
        highlightClass = 'highlight-removal';
    }

    // 권장사항이 없거나 불확실한 경우 판단
    let recommendationDisplay = '';
    let recommendationClass = '';

    if (isPassed) {
        recommendationDisplay = '<span style="color: #10b981; font-weight: 600;"><i class="fas fa-check-circle me-1"></i>문제 없음</span>';
        recommendationClass = 'passed';
    } else if (!recommendation || recommendation.trim() === '' || recommendation.toLowerCase().includes('n/a')) {
        recommendationDisplay = '<span style="color: #f59e0b; font-weight: 600;"><i class="fas fa-question-circle me-1"></i>판단 어려움 - 수동 검토 필요</span>';
        recommendationClass = 'uncertain';
    } else if (recommendation.toLowerCase().includes('검토') || recommendation.toLowerCase().includes('확인')) {
        recommendationDisplay = `<span style="color: #f59e0b;"><i class="fas fa-exclamation-triangle me-1"></i>${escapeHtml(recommendation)}</span>`;
        recommendationClass = 'review-needed';
    } else {
        recommendationDisplay = escapeHtml(recommendation);
        recommendationClass = 'has-recommendation';
    }

    return `
        <div class="section-card" id="${cardId}">
            <div class="section-header">
                <div>
                    <strong>${escapeHtml(metric)}</strong>
                    <small class="text-muted ms-2">${escapeHtml(item.period || '')}</small>
                </div>
                <span class="badge ${badgeColor}"><i class="fas ${badgeIcon} me-1"></i>${badgeText}</span>
            </div>

            <!-- Diff View -->
            <div class="diff-container">
                <div class="diff-panel">
                    <div class="diff-label before ${isPassed ? '' : 'before'}">
                        <i class="fas ${isPassed ? 'fa-file-alt' : diffLabelIcon}"></i>
                        <span>현재 (DSS 원본)</span>
                    </div>
                    <div class="diff-text">
                        ${isPassed ? dssText : `<span class="${highlightClass}">${dssText}</span>`}
                    </div>
                </div>
                <div class="diff-panel">
                    <div class="diff-label after ${isPassed ? '' : 'after'}">
                        <i class="fas ${isPassed ? 'fa-check-circle' : 'fa-lightbulb'}"></i>
                        <span>${isPassed ? '검증 결과' : '권장 수정안'}</span>
                    </div>
                    <div class="diff-text ${recommendationClass}">${recommendationDisplay}</div>
                </div>
            </div>

            <!-- Discrepancy Details -->
            <div class="discrepancy-list">
                <div class="discrepancy-card">
                    <div class="discrepancy-header">
                        <div>
                            <div class="fw-bold mb-1">문맥 이슈 상세</div>
                            ${item.issue_type ? `<span class="badge bg-secondary mt-1">${escapeHtml(item.issue_type)}</span>` : ''}
                        </div>
                    </div>

                    <div class="mb-2">
                        <small class="text-muted"><i class="fas fa-exclamation-circle"></i> 발견된 문제</small>
                        <div class="mt-1">${escapeHtml(item.issue || 'N/A')}</div>
                    </div>

                    ${earningCallContext ? `
                    <div class="mb-2">
                        <small class="text-muted"><i class="fas fa-book"></i> 어닝콜 원문</small>
                        <div class="mt-1" style="line-height: 1.6; color: #6b7280;">
                            ${escapeHtml(earningCallContext)}
                        </div>
                    </div>
                    ` : ''}

                    <div class="mb-2">
                        <small class="text-muted"><i class="fas fa-lightbulb"></i> 권장 조치</small>
                        <div class="mt-1 ${recommendationClass}" style="line-height: 1.6;">
                            ${recommendationDisplay}
                        </div>
                    </div>

                    <div class="action-buttons">
                        <button class="btn-accept" onclick="acceptItem('${item.id}', event)">
                            <i class="fas fa-check"></i> 승인
                        </button>
                        <button class="btn-reject" onclick="rejectItem('${item.id}', event)">
                            <i class="fas fa-times"></i> 거부
                        </button>
                        <button class="btn-manual" onclick="manualEditItem('${item.id}', event)">
                            <i class="fas fa-pencil"></i> 수동
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function updateProgressStats(sections) {
    let totalItems = 0;
    let acceptedCount = 0;
    let rejectedCount = 0;
    let manualCount = 0;
    let pendingCount = 0;

    Object.keys(sections).forEach(sectionName => {
        const section = sections[sectionName];
        totalItems += section.items.length;

        section.items.forEach(item => {
            if (item.status === 'accepted') acceptedCount++;
            else if (item.status === 'rejected') rejectedCount++;
            else if (item.status === 'manual') manualCount++;
            else pendingCount++;
        });
    });

    // Update counts
    document.getElementById('acceptedCount').textContent = acceptedCount;
    document.getElementById('rejectedCount').textContent = rejectedCount;
    document.getElementById('manualCount').textContent = manualCount;
    document.getElementById('pendingCount').textContent = pendingCount;

    // Update progress bar
    const progressPercent = totalItems > 0 ? Math.round(((acceptedCount + rejectedCount + manualCount) / totalItems) * 100) : 0;
    document.getElementById('progressPercent').textContent = `${progressPercent}%`;
    document.getElementById('progressBar').style.width = `${progressPercent}%`;
}

function acceptItem(itemId, event) {
    event.stopPropagation();
    updateItemStatus(itemId, 'accepted');
}

function rejectItem(itemId, event) {
    event.stopPropagation();
    updateItemStatus(itemId, 'rejected');
}

function manualEditItem(itemId, event) {
    event.stopPropagation();

    // Find the item in validationResult
    let item = null;
    let itemType = null;

    if (validationResult.corrections_needed) {
        const correctionIdx = parseInt(itemId.replace('correction-', ''));
        if (!isNaN(correctionIdx) && validationResult.corrections_needed[correctionIdx]) {
            item = validationResult.corrections_needed[correctionIdx];
            itemType = 'correction';
        }
    }

    if (!item && validationResult.interpretation_validation?.interpretation_issues) {
        const issueIdx = parseInt(itemId.replace('issue-', ''));
        if (!isNaN(issueIdx) && validationResult.interpretation_validation.interpretation_issues[issueIdx]) {
            item = validationResult.interpretation_validation.interpretation_issues[issueIdx];
            itemType = 'issue';
        }
    }

    if (!item) {
        alert('항목을 찾을 수 없습니다.');
        return;
    }

    // Show edit modal
    showEditModal(itemId, item, itemType);
}

function showEditModal(itemId, item, itemType) {
    const currentText = itemEditedTexts[itemId] ||
                       (itemType === 'correction' ? item.dss_context : item.dss_sentence || item.dss_statement || '');

    const recommendText = itemType === 'correction' ?
                         `${item.dss_context.replace(item.dss_current_value || '', item.correct_value || '')}` :
                         (item.recommendation || '');

    const modalHTML = `
        <div id="editModal" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 10000; display: flex; align-items: center; justify-content: center;">
            <div style="background: white; padding: 30px; border-radius: 8px; max-width: 800px; width: 90%; max-height: 80vh; overflow-y: auto;">
                <h4 style="margin-bottom: 20px;">수동 편집</h4>

                <div style="margin-bottom: 15px;">
                    <label style="display: block; font-weight: bold; margin-bottom: 5px;">원본 텍스트:</label>
                    <div style="padding: 10px; background: #f5f5f5; border-radius: 4px; margin-bottom: 10px;">
                        ${escapeHtml(currentText)}
                    </div>
                </div>

                <div style="margin-bottom: 15px;">
                    <label style="display: block; font-weight: bold; margin-bottom: 5px;">권장 수정안:</label>
                    <div style="padding: 10px; background: #e8f5e9; border-radius: 4px; margin-bottom: 10px;">
                        ${escapeHtml(recommendText)}
                    </div>
                </div>

                <div style="margin-bottom: 20px;">
                    <label style="display: block; font-weight: bold; margin-bottom: 5px;">최종 수정 텍스트:</label>
                    <textarea id="editTextarea" style="width: 100%; height: 150px; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px;">${escapeHtml(recommendText)}</textarea>
                </div>

                <div style="display: flex; gap: 10px; justify-content: flex-end;">
                    <button onclick="closeEditModal()" style="padding: 10px 20px; border: 1px solid #ddd; background: white; border-radius: 4px; cursor: pointer;">취소</button>
                    <button onclick="saveManualEdit('${itemId}')" style="padding: 10px 20px; border: none; background: #2563eb; color: white; border-radius: 4px; cursor: pointer;">저장</button>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);
}

function closeEditModal() {
    const modal = document.getElementById('editModal');
    if (modal) {
        modal.remove();
    }
}

function saveManualEdit(itemId) {
    const textarea = document.getElementById('editTextarea');
    if (!textarea) return;

    const editedText = textarea.value.trim();
    if (!editedText) {
        alert('수정 텍스트를 입력해주세요.');
        return;
    }

    // Save edited text
    itemEditedTexts[itemId] = editedText;

    // Update status to manual
    updateItemStatus(itemId, 'manual');

    // Close modal
    closeEditModal();

    alert('수정 내용이 저장되었습니다.');
}

function updateItemStatus(itemId, status) {
    // Store status in global object
    itemStatuses[itemId] = status;

    // Re-organize sections with updated statuses
    const sections = organizeBySections(validationResult);

    // Re-render progress stats
    updateProgressStats(sections);

    // Re-render sidebar
    renderNavigationSidebar(sections);

    // Update the card badge
    const statusLabels = {
        'accepted': '승인됨',
        'rejected': '거부됨',
        'manual': '수동'
    };

    // Find all possible card IDs (we need to check all sections)
    Object.keys(sections).forEach(sectionName => {
        const cardId = `card-${sectionName}-${itemId}`;
        const card = document.getElementById(cardId);
        if (card) {
            const header = card.querySelector('.section-header');
            if (header) {
                const existingBadge = header.querySelector('.badge');
                if (existingBadge) {
                    existingBadge.className = 'badge';
                    if (status === 'accepted') existingBadge.className += ' bg-success';
                    else if (status === 'rejected') existingBadge.className += ' bg-danger';
                    else if (status === 'manual') existingBadge.className += ' bg-primary';
                    existingBadge.textContent = statusLabels[status];
                }
            }
        }
    });
}

function renderNavigationSidebar(sections) {
    const sidebarNav = document.getElementById('sidebarNav');
    if (!sidebarNav) return;

    let html = '';
    const sectionIcons = {
        '실적발표': 'fa-chart-line',
        '가이던스': 'fa-compass',
        'Q&A': 'fa-comments'
    };

    Object.keys(sections).forEach(sectionName => {
        const section = sections[sectionName];
        const totalIssues = section.items.length;

        // Skip empty sections
        if (totalIssues === 0) return;

        html += `
            <div class="nav-section-title">
                <i class="fas ${sectionIcons[sectionName]} me-1"></i>
                ${sectionName}
                <span class="badge bg-danger ms-2">${totalIssues}</span>
            </div>
        `;

        // Add all items to nav
        section.items.forEach((item, idx) => {
            const cardId = `card-${sectionName}-${item.id}`;
            const isCorrection = item.itemType === 'correction';
            const metric = item.metric || (isCorrection ? 'N/A' : '문맥 이슈');
            const isPassed = metric === '일치함' || item.validation_status === 'passed';
            const issueType = item.issue_type || '';

            // 아이콘 및 색상 설정
            let itemIcon = '';
            let itemColor = '';
            let badgeText = '';
            let statusColor = 'bg-warning';

            // 일치함 판정 우선
            if (isPassed) {
                itemIcon = 'fa-check-circle';
                itemColor = 'var(--color-success)';
                badgeText = '일치함';
                statusColor = 'bg-success';
            } else if (isCorrection || issueType === '수치오류' || issueType === '수치') {
                itemIcon = 'fa-times-circle';
                itemColor = 'var(--color-danger)';
                badgeText = isCorrection ? '불일치' : '수치';
                statusColor = 'bg-danger';
            } else {
                itemIcon = 'fa-exclamation-triangle';
                itemColor = 'var(--color-warning)';
                badgeText = '문맥';
                statusColor = 'bg-warning';
            }

            // 상태 변경 시 badge 업데이트
            if (item.status === 'accepted') {
                badgeText = '승인됨';
                statusColor = 'bg-success';
            } else if (item.status === 'rejected') {
                badgeText = '거부됨';
                statusColor = 'bg-danger';
            } else if (item.status === 'manual') {
                badgeText = '수동';
                statusColor = 'bg-primary';
            }

            html += `
                <div class="sidebar-item" onclick="scrollToCard('${cardId}', '${sectionName}', event)">
                    <div style="width: 100%;">
                        <div class="d-flex justify-content-between align-items-start mb-1">
                            <div class="fw-bold" style="font-size: 0.8rem; color: ${itemColor};">
                                <i class="fas ${itemIcon} me-1"></i>
                                ${metric}
                            </div>
                            <span class="badge ${statusColor}" style="font-size: 0.65rem;">
                                ${badgeText}
                            </span>
                        </div>
                        ${isCorrection ? `
                            <div class="text-muted" style="font-size: 0.7rem; line-height: 1.3;">
                                ${item.dss_current_value || ''} → ${item.correct_value || ''}
                            </div>
                        ` : isPassed ? `
                            <div class="text-muted" style="font-size: 0.7rem; line-height: 1.3;">
                                문제 없음
                            </div>
                        ` : `
                            <div class="text-muted" style="font-size: 0.7rem; line-height: 1.3;">
                                ${(item.issue || '').substring(0, 80)}${(item.issue || '').length > 80 ? '...' : ''}
                            </div>
                        `}
                    </div>
                </div>
            `;
        });
    });

    if (html === '') {
        html = '<div class="text-muted small text-center p-3">검토 항목 없음</div>';
    }

    sidebarNav.innerHTML = html;
}

function scrollToCard(cardId, sectionName, evt) {
    // First, switch to the correct tab if needed
    const currentActiveTab = document.querySelector('.tab-item.active');
    if (currentActiveTab && currentActiveTab.getAttribute('data-section') !== sectionName) {
        document.querySelectorAll('.tab-item').forEach(tab => {
            if (tab.getAttribute('data-section') === sectionName) {
                tab.click();
            }
        });
    }

    // Wait a bit for tab content to render, then scroll
    setTimeout(() => {
        const element = document.getElementById(cardId);
        if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });

            // Highlight temporarily
            element.style.boxShadow = '0 0 0 4px rgba(59, 130, 246, 0.4)';
            setTimeout(() => {
                element.style.boxShadow = '';
            }, 2000);

            // Update active state in sidebar
            document.querySelectorAll('.sidebar-item').forEach(item => {
                item.classList.remove('active');
            });
            if (evt && evt.target) {
                evt.target.closest('.sidebar-item')?.classList.add('active');
            }
        }
    }, 100);
}

function updateHeader(result) {
    const companyName = extractCompanyName(result);
    const period = extractPeriod(result);

    // Update company name
    const companyNameEl = document.getElementById('companyName');
    if (companyNameEl) {
        companyNameEl.textContent = companyName || '회사명';
    }

    // Update period
    const fiscalPeriodEl = document.getElementById('fiscalPeriod');
    if (fiscalPeriodEl) {
        fiscalPeriodEl.textContent = period || '2025 Q4';
    }
}

function extractCompanyName(result) {
    // Try corrections_needed first
    if (result.corrections_needed && result.corrections_needed.length > 0) {
        const company = result.corrections_needed[0].company;
        if (company && company !== 'N/A') return company;
    }
    // Try interpretation issues
    if (result.interpretation_validation?.interpretation_issues &&
        result.interpretation_validation.interpretation_issues.length > 0) {
        const company = result.interpretation_validation.interpretation_issues[0].company;
        if (company && company !== 'N/A' && company !== '') return company;
    }
    // Try matched
    if (result.matched && result.matched.length > 0) {
        const company = result.matched[0].company;
        if (company && company !== 'N/A') return company;
    }
    return null;
}

function extractPeriod(result) {
    if (result.corrections_needed && result.corrections_needed.length > 0) {
        return result.corrections_needed[0].period;
    }
    if (result.matched && result.matched.length > 0) {
        return result.matched[0].period;
    }
    return null;
}


function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function getSeverityClass(severity) {
    switch(severity) {
        case 'Critical': return 'danger';
        case 'High': return 'warning';
        case 'Medium': return 'info';
        case 'Low': return 'secondary';
        default: return 'secondary';
    }
}

function showLoading(show) {
    const loadingOverlay = document.getElementById('loadingOverlay');
    if (loadingOverlay) {
        loadingOverlay.style.display = show ? 'flex' : 'none';
    }
}

function resetValidation() {
    if (confirm('새로운 검증을 시작하시겠습니까? 현재 결과는 사라집니다.')) {
        validationResult = null;
        selectedDiscrepancyIndex = null;
        itemStatuses = {}; // Clear all item statuses
        itemEditedTexts = {}; // Clear all edited texts

        document.getElementById('inputSection').style.display = 'block';
        document.getElementById('mainApp').style.display = 'none';

        // Reset form
        document.getElementById('uploadForm').reset();
    }
}

function downloadResults() {
    if (validationResult && validationResult.result_file) {
        window.location.href = `/api/download/${validationResult.result_file}`;
    } else {
        alert('다운로드할 결과 파일이 없습니다.');
    }
}

function renderFinalDraft(sections) {
    const container = document.getElementById('sectionsContent');
    if (!container) return;

    // Re-organize sections with current statuses to get latest data
    const currentSections = organizeBySections(validationResult);

    // Collect all corrected sentences by section
    const correctedSentences = {
        '실적발표': [],
        '가이던스': [],
        'Q&A': []
    };

    // Process all sections
    Object.keys(currentSections).forEach(sectionName => {
        if (sectionName === '최종수정안') return;

        const section = currentSections[sectionName];
        section.items.forEach(item => {
            const status = item.status;

            if (status === 'accepted') {
                // Approved: use correction
                if (item.itemType === 'correction') {
                    // For corrections, replace the value in context
                    let correctedSentence = item.dss_context || '';
                    const dssValue = item.dss_current_value || '';
                    const correctValue = item.correct_value || '';

                    if (dssValue && correctValue && correctedSentence) {
                        // Strategy 1: Try direct replacement
                        if (correctedSentence.includes(dssValue)) {
                            correctedSentence = correctedSentence.replace(dssValue, correctValue);
                        } else {
                            // Strategy 2: Try fuzzy matching with regex
                            // Escape special regex characters and allow flexible spacing/commas
                            const escapeRegex = (str) => str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                            const dssPattern = escapeRegex(dssValue)
                                .replace(/,/g, ',?\\s*')  // Make commas optional with optional space
                                .replace(/\s+/g, '\\s*');  // Make spaces flexible

                            const regex = new RegExp(dssPattern, 'g');
                            if (regex.test(correctedSentence)) {
                                correctedSentence = correctedSentence.replace(regex, correctValue);
                            } else {
                                // Strategy 3: Extract numbers and try to replace
                                // Extract just the number part
                                const dssNumMatch = dssValue.match(/[\d.,]+/);
                                const correctNumMatch = correctValue.match(/[\d.,]+/);

                                if (dssNumMatch && correctNumMatch) {
                                    const dssNum = dssNumMatch[0];
                                    const correctNum = correctNumMatch[0];

                                    // Try to replace the number
                                    if (correctedSentence.includes(dssNum)) {
                                        correctedSentence = correctedSentence.replace(dssNum, correctNum);

                                        // Also update the unit if different
                                        const dssUnit = dssValue.replace(dssNum, '').trim();
                                        const correctUnit = correctValue.replace(correctNum, '').trim();
                                        if (dssUnit !== correctUnit && dssUnit && correctUnit) {
                                            correctedSentence = correctedSentence.replace(dssUnit, correctUnit);
                                        }
                                    }
                                }
                            }
                        }
                    }

                    correctedSentences[sectionName].push({
                        sentence: correctedSentence,
                        metric: item.metric
                    });
                } else {
                    // For issues, use recommendation
                    correctedSentences[sectionName].push({
                        sentence: item.recommendation || '',
                        metric: item.metric || '문맥 이슈'
                    });
                }
            } else if (status === 'manual') {
                // Manually edited: use edited text
                const editedText = itemEditedTexts[item.id] || item.recommendation || '';
                correctedSentences[sectionName].push({
                    sentence: editedText,
                    metric: item.metric || '문맥 이슈'
                });
            } else if (status === 'rejected') {
                // Rejected: use original DSS sentence
                const originalSentence = item.dss_context || item.dss_sentence || '';
                if (originalSentence) {
                    correctedSentences[sectionName].push({
                        sentence: originalSentence,
                        metric: item.metric || '원본 유지'
                    });
                }
            }
            // 'pending' items are not included
        });
    });

    // Generate DSS-formatted output
    let dssOutput = '';
    const sectionHeaders = {
        '실적발표': '### 실적 발표',
        '가이던스': '### 가이던스',
        'Q&A': '### Q&A'
    };

    ['실적발표', '가이던스', 'Q&A'].forEach(sectionName => {
        const sentences = correctedSentences[sectionName];

        if (sentences.length > 0) {
            dssOutput += sectionHeaders[sectionName] + '\n';
            sentences.forEach(item => {
                dssOutput += '## ' + item.sentence + '\n\n';
            });
        }
    });

    // Count total changes
    const totalChanges = Object.values(correctedSentences).reduce((sum, arr) => sum + arr.length, 0);

    // Render final draft in DSS format
    let html = `
        <div style="padding: 30px; max-width: 1200px; margin: 0 auto;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;">
                <div>
                    <h3 style="margin: 0 0 10px 0; font-size: 24px; font-weight: 600;">최종 수정안</h3>
                    <p style="margin: 0; color: #6b7280; font-size: 14px;">승인된 ${totalChanges}개 항목이 반영된 DSS 요약본입니다</p>
                </div>
                <button onclick="copyFinalDraft()" style="padding: 10px 20px; border: none; background: #2563eb; color: white; border-radius: 6px; cursor: pointer; font-size: 14px;">
                    <i class="fas fa-copy"></i> 전체 복사
                </button>
            </div>

            <div id="finalDraftContent" style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 25px; white-space: pre-wrap; font-family: inherit; line-height: 1.8;">`;

    if (totalChanges === 0) {
        html += `
                <div style="text-align: center; padding: 60px 20px; color: #9ca3af;">
                    <i class="fas fa-inbox" style="font-size: 48px; margin-bottom: 20px;"></i>
                    <p style="font-size: 16px;">승인된 수정사항이 없습니다.</p>
                    <p style="font-size: 14px;">검증 결과에서 항목을 승인하거나 수동 편집하여 최종안을 만드세요.</p>
                </div>`;
    } else {
        // Render each section
        ['실적발표', '가이던스', 'Q&A'].forEach(sectionName => {
            const sentences = correctedSentences[sectionName];

            if (sentences.length > 0) {
                html += `
                <div style="margin-bottom: 30px;">
                    <h3 style="font-size: 20px; font-weight: 700; margin-bottom: 15px; color: #1f2937; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px;">
                        ${sectionHeaders[sectionName]}
                    </h3>`;

                sentences.forEach((item, idx) => {
                    const sentenceId = `final-${sectionName}-${idx}`;
                    html += `
                    <div id="${sentenceId}" style="margin-bottom: 8px; padding: 8px 12px; background: #f9fafb; border-radius: 4px; border-left: 3px solid #10b981; display: flex; justify-content: space-between; align-items: center;">
                        <div style="font-size: 14px; line-height: 1.5; color: #111827; flex: 1;">
                            ## <span id="${sentenceId}-text">${escapeHtml(item.sentence)}</span>
                        </div>
                        <button onclick="editFinalSentence('${sentenceId}', '${sectionName}', ${idx})"
                                style="margin-left: 10px; padding: 4px 10px; border: 1px solid #d1d5db; background: white; border-radius: 4px; cursor: pointer; font-size: 12px; white-space: nowrap;">
                            <i class="fas fa-edit"></i> 편집
                        </button>
                    </div>`;
                });

                html += `</div>`;
            }
        });
    }

    html += `
            </div>

            <div style="margin-top: 30px; padding: 20px; background: #f0f9ff; border-radius: 8px; text-align: center;">
                <div style="font-size: 16px; color: #1e40af;">
                    <i class="fas fa-check-circle"></i> 총 <strong>${totalChanges}개</strong>의 항목이 최종안에 반영되었습니다.
                </div>
            </div>
        </div>
    `;

    container.innerHTML = html;

    // Store the data for editing
    window.finalDraftSentences = correctedSentences;

    // Store the plain DSS output for copying
    window.finalDraftDSSOutput = dssOutput;
}

function editFinalSentence(sentenceId, sectionName, idx) {
    // Get current sentence
    const sentences = window.finalDraftSentences;
    if (!sentences || !sentences[sectionName] || !sentences[sectionName][idx]) {
        alert('문장을 찾을 수 없습니다.');
        return;
    }

    const currentSentence = sentences[sectionName][idx].sentence;

    // Create modal
    const modalHTML = `
        <div id="editFinalModal" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 10000;">
            <div style="background: white; padding: 25px; border-radius: 8px; max-width: 800px; width: 90%; max-height: 80vh; overflow-y: auto;">
                <h3 style="margin: 0 0 20px 0; font-size: 20px; font-weight: 600;">문장 편집</h3>

                <div style="margin-bottom: 20px;">
                    <label style="display: block; margin-bottom: 8px; font-weight: 600; color: #374151;">수정할 문장:</label>
                    <textarea id="finalEditTextarea" style="width: 100%; min-height: 120px; padding: 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px; line-height: 1.6; font-family: inherit; resize: vertical;">${escapeHtml(currentSentence)}</textarea>
                </div>

                <div style="display: flex; gap: 10px; justify-content: flex-end;">
                    <button onclick="closeFinalEditModal()" style="padding: 8px 16px; border: 1px solid #d1d5db; background: white; border-radius: 6px; cursor: pointer; font-size: 14px;">
                        취소
                    </button>
                    <button onclick="saveFinalEdit('${sentenceId}', '${sectionName}', ${idx})" style="padding: 8px 16px; border: none; background: #2563eb; color: white; border-radius: 6px; cursor: pointer; font-size: 14px;">
                        <i class="fas fa-save"></i> 저장
                    </button>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);

    // Focus textarea
    setTimeout(() => {
        const textarea = document.getElementById('finalEditTextarea');
        if (textarea) {
            textarea.focus();
            textarea.setSelectionRange(textarea.value.length, textarea.value.length);
        }
    }, 100);
}

function closeFinalEditModal() {
    const modal = document.getElementById('editFinalModal');
    if (modal) {
        modal.remove();
    }
}

function saveFinalEdit(sentenceId, sectionName, idx) {
    const textarea = document.getElementById('finalEditTextarea');
    if (!textarea) return;

    const newText = textarea.value.trim();
    if (!newText) {
        alert('문장을 입력해주세요.');
        return;
    }

    // Update the stored data
    if (window.finalDraftSentences && window.finalDraftSentences[sectionName] && window.finalDraftSentences[sectionName][idx]) {
        window.finalDraftSentences[sectionName][idx].sentence = newText;

        // Update UI
        const textElement = document.getElementById(`${sentenceId}-text`);
        if (textElement) {
            textElement.textContent = newText;
        }

        // Regenerate DSS output
        regenerateFinalDraftOutput();
    }

    closeFinalEditModal();
    alert('문장이 수정되었습니다.');
}

function regenerateFinalDraftOutput() {
    // Regenerate DSS-formatted output with updated sentences
    let dssOutput = '';
    const sectionHeaders = {
        '실적발표': '### 실적 발표',
        '가이던스': '### 가이던스',
        'Q&A': '### Q&A'
    };

    const sentences = window.finalDraftSentences;
    if (!sentences) return;

    ['실적발표', '가이던스', 'Q&A'].forEach(sectionName => {
        const sectionSentences = sentences[sectionName];

        if (sectionSentences && sectionSentences.length > 0) {
            dssOutput += sectionHeaders[sectionName] + '\n';
            sectionSentences.forEach(item => {
                dssOutput += '## ' + item.sentence + '\n\n';
            });
        }
    });

    window.finalDraftDSSOutput = dssOutput;
}

function copyFinalDraft() {
    // Use the stored DSS-formatted output
    const dssText = window.finalDraftDSSOutput || '';

    if (!dssText) {
        alert('복사할 내용이 없습니다.');
        return;
    }

    navigator.clipboard.writeText(dssText).then(() => {
        alert('최종 수정안이 클립보드에 복사되었습니다.\n\nDSS 요약본 형식으로 복사되었습니다.');
    }).catch(err => {
        console.error('Copy failed:', err);
        alert('복사에 실패했습니다.');
    });
}

function copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        const text = element.innerText;
        navigator.clipboard.writeText(text).then(() => {
            alert('클립보드에 복사되었습니다.');
        }).catch(err => {
            console.error('Copy failed:', err);
            alert('복사에 실패했습니다.');
        });
    }
}

function resetApplication() {
    // 확인 메시지
    const confirmed = confirm('새로 시작하시겠습니까?\n\n모든 검증 결과와 입력 내용이 초기화됩니다.');

    if (!confirmed) {
        return;
    }

    // 전역 변수 초기화
    validationResult = null;
    selectedDiscrepancyIndex = null;
    itemStatuses = {};
    itemEditedTexts = {};
    window.finalDraftSentences = null;
    window.finalDraftDSSOutput = null;

    // 업로드 폼 초기화
    const form = document.getElementById('uploadForm');
    if (form) {
        form.reset();
    }

    // 입력 필드 초기화
    const earningCallUrl = document.getElementById('earningCallUrl');
    const earningCallText = document.getElementById('earningCallText');
    const dssFile = document.getElementById('dssFile');
    const dssText = document.getElementById('dssText');

    if (earningCallUrl) earningCallUrl.value = '';
    if (earningCallText) earningCallText.value = '';
    if (dssFile) dssFile.value = '';
    if (dssText) dssText.value = '';

    // 라디오 버튼을 URL 입력으로 초기화
    const urlRadio = document.getElementById('inputUrl');
    const textRadio = document.getElementById('inputText');
    const urlInput = document.getElementById('urlInputSection');
    const textInput = document.getElementById('textInputSection');

    if (urlRadio) urlRadio.checked = true;
    if (textRadio) textRadio.checked = false;
    if (urlInput) urlInput.style.display = 'block';
    if (textInput) textInput.style.display = 'none';

    // 화면 전환: mainApp 숨기고 uploadScreen 표시
    const mainApp = document.getElementById('mainApp');
    const uploadScreen = document.getElementById('uploadScreen');

    if (mainApp) mainApp.style.display = 'none';
    if (uploadScreen) uploadScreen.style.display = 'flex';

    // 진행 표시 숨기기
    const progressContainer = document.getElementById('progressContainer');
    if (progressContainer) {
        progressContainer.style.display = 'none';
    }

    console.log('애플리케이션이 초기화되었습니다.');
}
