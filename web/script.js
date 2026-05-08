/* ============================================
   에이두 한글 에디터 — 프론트엔드 로직
   pywebview.api 브릿지를 통해 Python 백엔드와 통신
   ============================================ */

// pywebview API가 준비될 때까지 대기
let api = null;
let currentChatId = null;
let isProcessing = false;
let attachedFilePath = null;

// ============ 초기화 ============
window.addEventListener('pywebviewready', async () => {
    api = window.pywebview.api;
    await initApp();
});

async function initApp() {
    // 설정 로드
    const settings = await api.load_settings();
    if (settings.api_key) {
        document.getElementById('api-key-input').value = settings.api_key;
    }
    if (settings.selected_model) {
        document.getElementById('model-select').value = settings.selected_model;
    }

    // 대화 로그 로드
    await refreshChatLogList();

    // 이벤트 바인딩
    bindEvents();

    // API 키가 없으면 설정 모달 열기
    if (!settings.api_key) {
        showModal('settings-modal');
    }
}

// ============ 이벤트 바인딩 ============
function bindEvents() {
    // 새 대화
    document.getElementById('btn-new-chat').addEventListener('click', startNewChat);

    // 메시지 전송
    document.getElementById('btn-send').addEventListener('click', sendMessage);
    document.getElementById('message-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // 텍스트 입력 자동 높이 조절
    document.getElementById('message-input').addEventListener('input', autoResize);

    // 설정
    document.getElementById('btn-settings').addEventListener('click', () => showModal('settings-modal'));
    document.getElementById('btn-close-settings').addEventListener('click', () => hideModal('settings-modal'));
    document.getElementById('btn-save-settings').addEventListener('click', saveSettings);

    // 글로벌 드래그 앤 드롭 차단 및 처리
    document.addEventListener('dragover', (e) => e.preventDefault());
    document.addEventListener('drop', (e) => {
        e.preventDefault();
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            const lowerName = file.name.toLowerCase();
            console.log("File dropped:", file.name);

            if (lowerName.endsWith('.hwp') || lowerName.endsWith('.hwpx')) {
                // 배지 표시 (즉시 반응성 제공)
                showAttachedFile(file.name, null);
                
                const reader = new FileReader();
                reader.onload = function(e) {
                    console.log("File data read, sending to backend...");
                    const base64Data = e.target.result.split(',')[1];
                    api.handle_dropped_file_data(file.name, base64Data).then(safe_path => {
                        if (safe_path) {
                            console.log("File saved at:", safe_path);
                            window.onFileDropped(file.name, safe_path);
                        } else {
                            console.error("Failed to save dropped file.");
                            addSystemMessage("드롭된 파일을 처리하지 못했습니다.");
                            removeAttachedFile();
                        }
                    });
                };
                reader.onerror = (err) => console.error("FileReader error:", err);
                reader.readAsDataURL(file);
            }
        }
    });
    document.getElementById('link-api-studio').addEventListener('click', (e) => {
        e.preventDefault();
        api.open_url('https://aistudio.google.com/app/api-keys?project=gen-lang-client-0471748098');
    });

    // 문의
    document.getElementById('btn-inquiry').addEventListener('click', () => showModal('inquiry-modal'));
    document.getElementById('btn-close-inquiry').addEventListener('click', () => hideModal('inquiry-modal'));
    document.getElementById('btn-open-kakao').addEventListener('click', () => {
        api.open_url('https://open.kakao.com/o/sJ7qLXti');
        hideModal('inquiry-modal');
    });

    // 모달 오버레이 클릭으로 닫기
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', () => {
            overlay.parentElement.style.display = 'none';
        });
    });

    // 미리보기 패널
    document.getElementById('btn-close-preview').addEventListener('click', closePreview);
    document.getElementById('btn-fullscreen').addEventListener('click', openFullscreenPreview);

    // 파일 첨부 버튼
    document.getElementById('btn-attach-file').addEventListener('click', pickFile);

    // 파일 제거 버튼
    document.getElementById('btn-remove-file').addEventListener('click', removeAttachedFile);

    // 힌트 클릭
    document.querySelectorAll('.hint').forEach(hint => {
        hint.addEventListener('click', () => {
            document.getElementById('message-input').value = hint.textContent.replace(/"/g, '');
            autoResize();
            document.getElementById('message-input').focus();
        });
    });
}

// ============ 대화 관리 ============
async function startNewChat() {
    const chatId = await api.new_chat();
    currentChatId = chatId;
    clearChatUI();
    await refreshChatLogList();
}

async function loadChat(chatId) {
    currentChatId = chatId;
    const chatData = await api.load_chat(chatId);
    clearChatUI();

    // 메시지 렌더링
    if (chatData.messages) {
        for (const msg of chatData.messages) {
            appendMessage(msg.role, msg.content, msg.status_logs || [], false);
        }
    }

    // 파일 바 업데이트
    if (chatData.files && chatData.files.length > 0) {
        updateFileBar(chatData.files);
    }

    await refreshChatLogList();
    scrollToBottom();
}

async function refreshChatLogList() {
    const logs = await api.get_chat_logs();
    const container = document.getElementById('chat-log-list');
    container.innerHTML = '';

    for (const log of logs) {
        const item = document.createElement('div');
        item.className = `chat-log-item${log.id === currentChatId ? ' active' : ''}`;
        item.innerHTML = `
            <span class="log-icon">📝</span>
            <span class="log-title">${escapeHtml(log.title)}</span>
            <button class="btn-delete-chat" title="삭제">×</button>
        `;
        item.addEventListener('click', (e) => {
            if (!e.target.classList.contains('btn-delete-chat')) {
                loadChat(log.id);
            }
        });
        item.querySelector('.btn-delete-chat').addEventListener('click', async (e) => {
            e.stopPropagation();
            await api.delete_chat(log.id);
            if (currentChatId === log.id) {
                currentChatId = null;
                clearChatUI();
            }
            await refreshChatLogList();
        });
        container.appendChild(item);
    }
}

function clearChatUI() {
    const chatMessages = document.getElementById('chat-messages');
    chatMessages.innerHTML = `
        <div class="welcome-message">
            <div class="welcome-icon">📝</div>
            <h2>에이두 한글 에디터</h2>
            <p>한글 문서를 AI로 만들고 편집하세요.</p>
            <div class="welcome-hints">
                <div class="hint">"현장체험학습 운영계획서 만들어줘"</div>
                <div class="hint">"이 파일 내용 요약해줘" (📎 파일 첨부)</div>
                <div class="hint">"날짜를 5월 15일로 수정해줘"</div>
            </div>
        </div>
    `;
    // 힌트 리바인딩
    chatMessages.querySelectorAll('.hint').forEach(hint => {
        hint.addEventListener('click', () => {
            document.getElementById('message-input').value = hint.textContent.replace(/"/g, '');
            autoResize();
            document.getElementById('message-input').focus();
        });
    });

    document.getElementById('file-bar').style.display = 'none';
    document.getElementById('file-bar').innerHTML = '';
    removeAttachedFile();
}

// ============ 메시지 처리 ============
async function sendMessage() {
    if (isProcessing) return;

    const input = document.getElementById('message-input');
    const text = input.value.trim();
    if (!text && !attachedFilePath) return;

    // 새 대화가 없으면 생성
    if (!currentChatId) {
        currentChatId = await api.new_chat();
        await refreshChatLogList();
    }

    // 웰컴 메시지 제거
    const welcome = document.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    // 사용자 메시지 표시
    let displayText = text;
    if (attachedFilePath) {
        const fileName = attachedFilePath.split(/[/\\]/).pop();
        // 파일 정보가 포함된 특수 마커를 텍스트 앞에 붙임
        displayText = `[FILE_ATTACHMENT:${fileName}|${attachedFilePath.replace(/\\/g, '/')}]\n${text}`;
    }
    appendMessage('user', displayText, [], false);

    // 입력 초기화
    input.value = '';
    autoResize();
    isProcessing = true;
    document.getElementById('btn-send').disabled = true;

    // AI 응답 placeholder
    const aiMsgId = appendMessage('assistant', '', [], true);

    try {
        const result = await api.send_message(currentChatId, text, attachedFilePath);
        
        // AI 응답 업데이트
        updateMessage(aiMsgId, result.content, result.status_logs || []);
        
        // 파일이 생성/편집됐으면 파일 바 업데이트
        if (result.files && result.files.length > 0) {
            updateFileBar(result.files);
        }

        // 대화 로그 새로고침 (제목 갱신)
        await refreshChatLogList();

    } catch (error) {
        updateMessage(aiMsgId, `오류가 발생했습니다: ${error}`, []);
    }

    attachedFilePath = null;
    document.getElementById('attached-file-badge').style.display = 'none';
    isProcessing = false;
    document.getElementById('btn-send').disabled = false;
    scrollToBottom();
}

function appendMessage(role, content, statusLogs = [], isLoading = false) {
    const chatMessages = document.getElementById('chat-messages');
    const msgId = 'msg-' + Date.now() + '-' + Math.random().toString(36).substr(2, 5);

    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.id = msgId;

    const avatar = role === 'user' ? '👤' : '🤖';
    const roleName = role === 'user' ? '나' : '에이두 AI';

    let statusHtml = '';
    if (statusLogs.length > 0) {
        const items = statusLogs.map(log => `<div class="status-log-item">${escapeHtml(log)}</div>`).join('');
        statusHtml = `<div class="status-logs">${items}</div>`;
    }

    let contentHtml = '';
    if (isLoading) {
        contentHtml = `<div class="typing-indicator"><span></span><span></span><span></span></div>`;
        statusHtml = `<div class="status-logs"><div class="status-log-item active">생각중...</div></div>`;
    } else {
        contentHtml = formatContent(content);
    }

    div.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-body">
            <div class="message-role">${roleName}</div>
            <div class="message-content">${contentHtml}</div>
            ${statusHtml}
        </div>
    `;

    chatMessages.appendChild(div);
    scrollToBottom();
    return msgId;
}

function updateMessage(msgId, content, statusLogs = []) {
    const msg = document.getElementById(msgId);
    if (!msg) return;

    const contentEl = msg.querySelector('.message-content');
    contentEl.innerHTML = formatContent(content);

    // 상태 로그 업데이트
    const oldLogs = msg.querySelector('.status-logs');
    if (oldLogs) oldLogs.remove();

    if (statusLogs.length > 0) {
        const items = statusLogs.map(log => `<div class="status-log-item">${escapeHtml(log)}</div>`).join('');
        const logsDiv = document.createElement('div');
        logsDiv.className = 'status-logs';
        logsDiv.innerHTML = items;
        msg.querySelector('.message-body').appendChild(logsDiv);
    }
}

function formatContent(content) {
    if (!content) return '';
    
    return content.split('\n').map(line => {
        // 파일 첨부 마커 처리: [FILE_ATTACHMENT:이름|경로]
        const fileMatch = line.match(/^\[FILE_ATTACHMENT:(.*?)\|(.*?)\]$/);
        if (fileMatch) {
            const fileName = fileMatch[1];
            const filePath = fileMatch[2];
            return `
                <div class="message-file-btn-wrapper">
                    <button class="message-file-btn" onclick="openPreview('${escapeJs(fileName)}', '${escapeJs(filePath)}')">
                        <span class="file-icon">📎</span>
                        <span class="file-name">${escapeHtml(fileName)}</span>
                        <span class="file-action">미리보기</span>
                    </button>
                </div>
            `;
        }
        
        // 일반 텍스트는 기존처럼 p 태그로 감싸되, 빈 줄은 공백으로 처리
        const trimmed = line.trim();
        if (!trimmed && line.length > 0) return '<p>&nbsp;</p>';
        if (!trimmed) return '';
        return `<p>${escapeHtml(line)}</p>`;
    }).join('');
}

// ============ 파일 관련 ============
async function pickFile() {
    if (!api) return;
    const result = await api.pick_file();
    if (result && result.success) {
        attachedFilePath = result.path;
        showAttachedFile(result.name, result.path);
    }
}

function showAttachedFile(fileName, filePath) {
    attachedFilePath = filePath || null;
    document.getElementById('attached-file-name').textContent = `📎 ${fileName}`;
    document.getElementById('attached-file-badge').style.display = 'flex';
    document.getElementById('message-input').focus();
}

function removeAttachedFile() {
    attachedFilePath = null;
    document.getElementById('attached-file-badge').style.display = 'none';
}

function updateFileBar(files) {
    const bar = document.getElementById('file-bar');
    bar.style.display = 'flex';
    bar.innerHTML = '';

    for (const file of files) {
        const container = document.createElement('div');
        container.className = 'file-btn-container';
        
        const btn = document.createElement('button');
        btn.className = 'file-btn';
        btn.innerHTML = `<span class="file-icon">📄</span>${escapeHtml(file.name)}`;
        btn.addEventListener('click', () => openPreview(file.name, file.path));
        
        const folderBtn = document.createElement('button');
        folderBtn.className = 'folder-btn';
        folderBtn.innerHTML = '📁';
        folderBtn.title = '폴더 열기';
        folderBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            api.open_folder(file.path);
        });

        container.appendChild(btn);
        container.appendChild(folderBtn);
        bar.appendChild(container);
    }
}

// ============ RHWP 미리보기 ============
let currentPreviewPath = null;

window.openPreview = async function(fileName, filePath) {
    currentPreviewPath = filePath;
    const url = await api.get_rhwp_url(filePath);
    document.getElementById('preview-title').textContent = fileName;
    document.getElementById('preview-iframe').src = url;
    document.getElementById('preview-panel').style.display = 'flex';
}

function closePreview() {
    document.getElementById('preview-panel').style.display = 'none';
    document.getElementById('preview-iframe').src = 'about:blank';
    currentPreviewPath = null;
}

async function openFullscreenPreview() {
    if (currentPreviewPath) {
        await api.open_fullscreen_preview(currentPreviewPath);
    }
}

// ============ 설정 ============
async function saveSettings() {
    const apiKey = document.getElementById('api-key-input').value.trim();
    const model = document.getElementById('model-select').value;

    if (!apiKey) {
        alert('API Key를 입력하세요.');
        return;
    }

    await api.save_settings(apiKey, model);
    hideModal('settings-modal');
}

// ============ 모달 ============
function showModal(id) {
    document.getElementById(id).style.display = 'flex';
}

function hideModal(id) {
    document.getElementById(id).style.display = 'none';
}

// ============ 유틸리티 ============
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeJs(text) {
    if (!text) return '';
    return text.replace(/'/g, "\\'").replace(/"/g, '\\"');
}

function autoResize() {
    const input = document.getElementById('message-input');
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 160) + 'px';
}

function scrollToBottom() {
    const chatMessages = document.getElementById('chat-messages');
    setTimeout(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }, 50);
}

// ============ Python에서 호출하는 JS 함수들 ============

// 상태 로그 실시간 업데이트 (생각중... 영역)
window.updateStatusLog = function(msgId, log) {
    const msg = document.getElementById(msgId);
    if (!msg) return;

    let logsDiv = msg.querySelector('.status-logs');
    if (!logsDiv) {
        logsDiv = document.createElement('div');
        logsDiv.className = 'status-logs';
        msg.querySelector('.message-body').appendChild(logsDiv);
    }

    // 기존 active 해제
    logsDiv.querySelectorAll('.status-log-item.active').forEach(el => el.classList.remove('active'));

    const item = document.createElement('div');
    item.className = 'status-log-item active';
    item.textContent = log;
    logsDiv.appendChild(item);
};

// 파일 드롭 처리 (Python에서 호출)
window.onFileDropped = function(fileName, filePath) {
    attachedFilePath = filePath;
    showAttachedFile(fileName, filePath);
};

// 파일 목록 실시간 갱신 (Python에서 호출 가능)
window.refreshFileList = async function() {
    if (!currentChatId) return;
    console.log("Refreshing file list...");
    const chatData = await api.load_chat(currentChatId);
    if (chatData && chatData.files) {
        updateFileBar(chatData.files);
    }
};

// AI 메시지 ID 반환 (Python에서 사용)
window.getLatestAiMsgId = function() {
    const msgs = document.querySelectorAll('.message.assistant');
    if (msgs.length > 0) {
        return msgs[msgs.length - 1].id;
    }
    return null;
};
