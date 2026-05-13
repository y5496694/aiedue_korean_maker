"""
에이두 한글 에디터 — pywebview 기반 ChatGPT 스타일 UI
Python 백엔드: Gemini AI 연동, HWPX 문서 생성/편집, 대화 로그 관리
"""
import os
import sys
import json
import subprocess
import shutil
import threading
import webbrowser
import http.server
import functools
import socketserver
import urllib.parse
import re
from pathlib import Path
from datetime import datetime

try:
    import windnd
except ImportError:
    windnd = None

# ──── pywebview AccessibilityObject 재귀 에러 억제 ────
# Windows WebView2 백엔드에서 .NET WinForms 접근성 트리를
# 재귀 탐색하며 발생하는 무해한 스팸 로그를 필터링합니다.
# pywebview는 logging이 아닌 print/stderr로 출력하므로 stderr를 래핑합니다.

class _FilteredStderr:
    """pywebview의 AccessibilityObject / CoreWebView2 스팸 출력 차단"""
    _blocked = ("AccessibilityObject", "CoreWebView2", "__abstractmethods__",
                "maximum recursion depth", "E_NOINTERFACE", "ControlCollection",
                "DockPaddingEdgesConverter")

    def __init__(self, original):
        self._original = original
        self._buffer = ""

    def write(self, text):
        self._buffer += text
        # 줄바꿈 단위로 필터링
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if not any(k in line for k in self._blocked):
                self._original.write(line + "\n")

    def flush(self):
        if self._buffer and not any(k in self._buffer for k in self._blocked):
            self._original.write(self._buffer)
        self._buffer = ""
        self._original.flush()

    def __getattr__(self, name):
        return getattr(self._original, name)

sys.stderr = _FilteredStderr(sys.stderr)

import webview
from google import genai

# ============ 전역 설정 ============
APP_DIR = Path(__file__).parent
SKILL_DIR = APP_DIR / "hwpx_skill"
SETTINGS_FILE = APP_DIR / "settings.json"
CHAT_LOGS_DIR = APP_DIR / "chat_logs"
PREVIEW_SCRIPT = APP_DIR / "preview_browser.py"
WEB_DIR = APP_DIR / "web"
WEBVIEW_CACHE = APP_DIR / ".webview_cache"

# 캐시 폴더 생성
WEBVIEW_CACHE.mkdir(exist_ok=True)
CHAT_LOGS_DIR.mkdir(exist_ok=True)
LIBRARY_DIR = APP_DIR / "보관함"
LIBRARY_DIR.mkdir(exist_ok=True)
os.environ['WEBVIEW2_USER_DATA_FOLDER'] = str(WEBVIEW_CACHE)

# hwpx_skill/scripts를 경로에 추가
sys.path.insert(0, str(SKILL_DIR / "scripts"))


# ============ 모드 판별 키워드 ============
NEW_KEYWORDS = ["만들어", "작성해", "새로", "생성해", "만들기", "작성하기", "생성하기", "써줘", "작성"]
EDIT_KEYWORDS = ["수정해", "바꿔", "변경해", "추가해", "삭제해", "편집해", "고쳐", "교체해", "수정하기", "바꾸기", "변경하기", "추가하기", "삭제하기"]


def detect_mode(text, has_context_file=False):
    """사용자 메시지에서 작업 모드를 판별합니다."""
    for kw in NEW_KEYWORDS:
        if kw in text:
            return "NEW"
    if has_context_file:
        for kw in EDIT_KEYWORDS:
            if kw in text:
                return "EDIT"
    return "CHAT"


# ============ API 클래스 (pywebview JS 브릿지) ============
class Api:
    def __init__(self):
        self.window = None
        self.server_thread = None
        self.server_port = 8888
        self.preview_process = None
        self._settings = self._load_settings_file()
        self._current_context_file = None  # 현재 대화에서 활성화된 파일 경로

    def on_native_drop(self, files):
        if files and self.window:
            try:
                # windnd에서 전달되는 파일 경로는 bytes일 수 있음
                fpath = files[0].decode('cp949') if isinstance(files[0], bytes) else files[0]
                if os.path.exists(fpath):
                    print(f"Native Drop Detected: {fpath}")
                    self._current_context_file = fpath
                    fname = os.path.basename(fpath)
                    # JS 콜백 실행
                    js = f"window.onFileDropped({json.dumps(fname)}, {json.dumps(fpath)})"
                    self.window.evaluate_js(js)
            except Exception as de:
                print(f"Drop processing error: {de}")

    # ---- 설정 ----
    def _load_settings_file(self):
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        return {}

    def _save_settings_file(self, settings):
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)

    def load_settings(self):
        return self._settings

    def save_settings(self, api_key, selected_model):
        self._settings["api_key"] = api_key
        self._settings["selected_model"] = selected_model
        self._save_settings_file(self._settings)
        return {"success": True}

    # ---- 대화 로그 ----
    def get_chat_logs(self):
        logs = []
        for f in sorted(CHAT_LOGS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    logs.append({"id": data["id"], "title": data.get("title", "새 대화")})
            except Exception:
                pass
        return logs

    def new_chat(self):
        chat_id = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        chat_data = {
            "id": chat_id,
            "title": "새 대화",
            "created_at": datetime.now().isoformat(),
            "messages": [],
            "files": []
        }
        self._save_chat(chat_data)
        self._current_context_file = None
        return chat_id

    def load_chat(self, chat_id):
        path = CHAT_LOGS_DIR / f"{chat_id}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 컨텍스트 파일 복원
                if data.get("files"):
                    self._current_context_file = data["files"][-1].get("path")
                else:
                    self._current_context_file = None
                return data
        return {"id": chat_id, "title": "새 대화", "messages": [], "files": []}

    def delete_chat(self, chat_id):
        path = CHAT_LOGS_DIR / f"{chat_id}.json"
        if path.exists():
            path.unlink()
        return {"success": True}

    def _save_chat(self, chat_data):
        path = CHAT_LOGS_DIR / f"{chat_data['id']}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(chat_data, f, ensure_ascii=False, indent=2)

    def handle_dropped_file_data(self, filename, base64_data):
        """자바스크립트에서 전달된 드롭된 파일 데이터를 임시 폴더에 저장"""
        try:
            import base64
            file_data = base64.b64decode(base64_data)
            
            # 임시 디렉토리에 파일 저장
            temp_dir = APP_DIR / ".temp_drops"
            temp_dir.mkdir(exist_ok=True)
            
            # 윈도우 금지 문자만 제거 (\/:*?"<>|)
            safe_filename = re.sub(r'[\\/:*?"<>|]', '', filename)
            file_path = temp_dir / safe_filename
            
            with open(file_path, "wb") as f:
                f.write(file_data)
            
            self._current_context_file = str(file_path)
            return str(file_path)
        except Exception as e:
            print(f"드롭된 파일 처리 실패: {e}")
            return None

    def _load_chat_data(self, chat_id):
        path = CHAT_LOGS_DIR / f"{chat_id}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    # ---- 메시지 처리 (핵심) ----
    def send_message(self, chat_id, text, file_path=None):
        """사용자 메시지를 처리하고 AI 응답을 반환합니다."""
        chat_data = self._load_chat_data(chat_id)
        if not chat_data:
            chat_data = {"id": chat_id, "title": "새 대화", "messages": [], "files": []}

        # 파일 업로드 처리
        if file_path and os.path.exists(file_path):
            self._current_context_file = file_path
            file_name = os.path.basename(file_path)
            # 파일 목록에 추가 (중복 방지)
            existing_paths = [f["path"] for f in chat_data.get("files", [])]
            if file_path not in existing_paths:
                chat_data.setdefault("files", []).append({"name": file_name, "path": file_path})

        # 사용자 메시지 저장
        chat_data["messages"].append({"role": "user", "content": text})

        # 첫 메시지면 대화 제목 설정
        if len(chat_data["messages"]) == 1:
            chat_data["title"] = text[:30] + ("..." if len(text) > 30 else "")

        # 모드 판별
        has_context = self._current_context_file is not None
        mode = detect_mode(text, has_context)

        status_logs = []
        response_text = ""
        result_files = []

        try:
            api_key = self._settings.get("api_key", "")
            model_name = self._settings.get("selected_model", "gemini-3.1-flash-lite-preview")

            if not api_key:
                response_text = "API Key가 설정되지 않았습니다. 왼쪽 하단의 '설정'에서 API Key를 먼저 입력해 주세요."
            elif mode == "NEW":
                response_text, status_logs, result_files = self._process_new(api_key, model_name, text, chat_id)
            elif mode == "EDIT":
                response_text, status_logs, result_files = self._process_edit(api_key, model_name, text, chat_id)
            else:
                response_text, status_logs = self._process_chat(api_key, model_name, text, chat_data)

        except Exception as e:
            response_text = f"오류가 발생했습니다: {str(e)}"
            status_logs.append(f"오류: {str(e)}")

        # AI 응답 저장
        chat_data["messages"].append({
            "role": "assistant",
            "content": response_text,
            "status_logs": status_logs
        })

        # 파일 목록 업데이트
        if result_files:
            for rf in result_files:
                # 기존 파일 목록에서 동일한 기본 이름을 가진 파일이 있는지 확인 (확장자 변경 대응)
                base_name = Path(rf["name"]).stem
                new_files = []
                replaced = False
                
                for f in chat_data.get("files", []):
                    # 같은 이름을 가진 파일이거나, 확장자만 다른 같은 파일인 경우 교체
                    if f["name"] == rf["name"] or Path(f["name"]).stem == base_name:
                        new_files.append(rf)
                        replaced = True
                    else:
                        new_files.append(f)
                
                if not replaced:
                    new_files.append(rf)
                
                chat_data["files"] = new_files
                self._current_context_file = rf["path"]

        self._save_chat(chat_data)

        # UI 파일 목록 실시간 갱신 (저장 후 호출해야 최신 데이터 반영됨)
        if self.window:
            self.window.evaluate_js("if(window.refreshFileList) window.refreshFileList();")

        return {
            "content": response_text,
            "status_logs": status_logs,
            "files": chat_data.get("files", [])
        }

    def _update_status(self, msg):
        """UI에 상태 로그를 실시간 업데이트합니다."""
        if self.window:
            safe_msg = json.dumps(msg)
            js = f"window.updateStatusLog(window.getLatestAiMsgId(), {safe_msg});"
            try:
                self.window.evaluate_js(js)
            except Exception:
                pass

    # ---- 새 문서 만들기 ----
    def _process_new(self, api_key, model_name, user_prompt, chat_id):
        status_logs = []

        status_logs.append(f"모델 준비 중 ({model_name})...")
        self._update_status(status_logs[-1])

        client = genai.Client(api_key=api_key)

        status_logs.append("AI가 문서 구조를 설계 중...")
        self._update_status(status_logs[-1])

        ai_prompt = f"""
당신은 HWPX 문서 생성 전문가입니다. 사용자의 요청에 따라 '관공서 스타일' 문서 구성 계획을 JSON으로 작성하세요.
문서는 반드시 화려한 컬러 배너와 섹션 바를 포함해야 하며, 본문 문단은 내용의 성격에 따라 적절한 말머리 기호를 사용해야 합니다.

[사용자 요청]
{user_prompt}

[작성 규칙]
1. 모든 세부 항목은 '가. 나. 다.' 형태의 말머리를 순서대로 붙이세요 (type: "item").
2. 일반 설명이나 본문 문단은 기호 없이 작성하세요 (type: "text").
3. 표 형태의 데이터가 필요하다면 'table' 타입을 사용하고 2열 형태의 2차원 배열(rows)로 데이터를 제공하세요 (type: "table").

[응답 형식 (JSON만 출력)]
{{
  "title": "전체 문서 제목",
  "subtitle": "부제",
  "date": "날짜",
  "sections": [
    {{
      "number": "I",
      "title": "장 제목",
      "content": [
        {{ "type": "item", "marker": "가", "text": "첫 번째 항목 내용" }},
        {{ "type": "text", "text": "일반 설명 문단" }},
        {{ "type": "table", "rows": [["구분", "내용"], ["일시", "2026-10-15"]] }}
      ]
    }}
  ]
}}
"""
        response = client.models.generate_content(
            model=model_name,
            contents=ai_prompt
        )
        plan_text = response.text.strip()

        if "```json" in plan_text:
            plan_text = plan_text.split("```json")[1].split("```")[0].strip()
        elif "```" in plan_text:
            plan_text = plan_text.split("```")[1].split("```")[0].strip()

        plan = json.loads(plan_text)
        plan_file = APP_DIR / "temp_plan.json"
        plan_file.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

        # 출력 폴더 및 파일명
        LIBRARY_DIR.mkdir(exist_ok=True)
        safe_title = "".join([c for c in plan.get("title", "new_document") if c.isalnum() or c in (" ", "_", "-")]).strip()
        output_name = f"{safe_title}.hwpx"
        output_path = LIBRARY_DIR / output_name

        status_logs.append("문서 빌드 중...")
        self._update_status(status_logs[-1])

        # 빌드 스크립트 실행
        build_script = f"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(r"{SKILL_DIR / 'scripts'}")))
from hwpx_helpers import *
import subprocess

REF_HWPX = Path(r"{SKILL_DIR / 'assets' / 'government-reference.hwpx'}")
GOV_HEADER = Path(r"{SKILL_DIR / 'templates' / 'government' / 'header.xml'}")
OUTPUT = Path(r"{output_path}")
TEMP_SECTION = Path(r"{APP_DIR / 'temp_section.xml'}")
PLAN_FILE = Path(r"{plan_file}")

with open(PLAN_FILE, "r", encoding="utf-8") as f:
    plan = json.load(f)

secpr, colpr = extract_secpr_and_colpr(str(REF_HWPX))
parts = []
parts.append('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>')
parts.append(f'<hs:sec {{NS_DECL}}>')
parts.append(make_first_para(secpr, colpr))

# 표지
parts.extend(make_cover_page(plan.get("title", "제목")))

# 섹션별 반복
for i, sec in enumerate(plan.get("sections", [])):
    parts.append(make_section_bar(sec.get("number", str(i+1)), sec.get("title", "제목")))
    parts.append(make_empty_line())
    
    for item in sec.get("content", []):
        ctype = item.get("type", "text")
        
        if ctype == "item":
            marker = item.get("marker", "가")
            text = item.get("text", "")
            parts.append(make_body_para(f"{{marker}}.", text))
        elif ctype == "table":
            parts.append(make_data_table(item.get("rows", [])))
        else:
            text = item.get("text", "")
            parts.append(make_text_para(text, charpr="38", parapr="4"))
            
    parts.append(make_empty_line())

parts.append('</hs:sec>')
TEMP_SECTION.write_text("\\n".join(parts), encoding="utf-8")

subprocess.run([
    "python", r"{SKILL_DIR / 'scripts' / 'build_hwpx.py'}",
    "--header", str(GOV_HEADER),
    "--section", str(TEMP_SECTION),
    "--output", str(OUTPUT)
], check=True, capture_output=True)

subprocess.run(["python", r"{SKILL_DIR / 'scripts' / 'fix_namespaces.py'}", str(OUTPUT)], check=True, capture_output=True)
"""
        temp_script = APP_DIR / "temp_builder.py"
        temp_script.write_text(build_script, encoding="utf-8")
        subprocess.run([sys.executable, str(temp_script)], check=True)

        status_logs.append("문서 생성 완료!")
        self._update_status(status_logs[-1])

        result_files = [{"name": output_name, "path": str(output_path)}]
        response_text = f"'{plan.get('title', '문서')}'를 성공적으로 만들었습니다!\n상단의 파일 버튼을 눌러 미리보기할 수 있습니다."

        return response_text, status_logs, result_files

    # ---- 문서 편집 ----
    def _process_edit(self, api_key, model_name, user_prompt, chat_id):
        status_logs = []

        if not self._current_context_file or not os.path.exists(self._current_context_file):
            return "편집할 파일이 없습니다. 파일을 먼저 업로드하거나, 새 문서를 만들어 주세요.", status_logs, []

        input_path = Path(self._current_context_file)
        hwpx_path = input_path

        # HWP → HWPX 변환
        if input_path.suffix.lower() == ".hwp":
            status_logs.append("HWP를 HWPX로 변환 중...")
            self._update_status(status_logs[-1])
            output_hwpx = input_path.with_suffix(".hwpx")
            conv_result = subprocess.run(
                [sys.executable, str(SKILL_DIR / "scripts" / "convert_hwp.py"), str(input_path), "-o", str(output_hwpx)],
                capture_output=True, text=True
            )
            if conv_result.returncode != 0:
                err_msg = conv_result.stderr.strip() or conv_result.stdout.strip() or "알 수 없는 오류"
                return f"HWP → HWPX 변환에 실패했습니다.\n{err_msg}", status_logs, []
            hwpx_path = output_hwpx

        status_logs.append(f"모델 준비 중 ({model_name})...")
        self._update_status(status_logs[-1])

        client = genai.Client(api_key=api_key)

        # 텍스트 추출 및 정밀 분석
        status_logs.append("문서 데이터 정밀 분석 중...")
        self._update_status(status_logs[-1])
        
        # 1. 시각적 이해를 위한 전체 텍스트 추출
        res_text = subprocess.run([sys.executable, str(SKILL_DIR / "scripts" / "text_extract.py"), str(hwpx_path)], capture_output=True)
        extracted_text = res_text.stdout.decode("utf-8", errors="replace")
        
        # 2. 기술적 치환을 위한 데이터 조각(Fragment) 분석
        analyze_file = APP_DIR / "temp_analyze.json"
        subprocess.run([
            sys.executable, str(SKILL_DIR / "scripts" / "clone_form.py"),
            "--auto-analyze", str(analyze_file), str(hwpx_path)
        ], capture_output=True)
        
        fragments_str = ""
        if analyze_file.exists():
            with open(analyze_file, "r", encoding="utf-8") as f:
                analyze_data = json.load(f)
            fragments = list(analyze_data.get("template_map", {}).keys())
            # 너무 많으면 상위 1000개로 제한 (컨텍스트 보호)
            fragments_str = "\n".join([f"- {f}" for f in fragments[:1000]])

        # AI 매핑 요청
        status_logs.append("AI가 문서를 분석하며 수정을 계획 중...")
        self._update_status(status_logs[-1])

        ai_prompt = f"""
당신은 HWPX 문서 편집 전문가입니다. 사용자의 요청에 따라 문서를 수정하기 위해, 아래 제공된 '텍스트 조각(Fragment)'들을 어떻게 바꿀지 결정하세요.

[문서 정보]
- 파일명: {hwpx_path.name}
- 전체 경로: {hwpx_path.absolute()}

[전체 문서 내용 (참고용)]
{extracted_text}

[수정 가능한 텍스트 조각 목록]
{fragments_str}

[사용자 요청]
{user_prompt}

[응답 지침]
1. 먼저 어떤 내용을 수정할지 요약(한 줄 단위 리스트)을 '---SUMMARY---' 섹션에 작성하세요.
2. 그 다음 실제 치환할 JSON 데이터를 '---JSON---' 섹션에 작성하세요.
3. 반드시 위 '텍스트 조각 목록'에 있는 문자열(Key)을 정확히 사용하여 치환 맵을 만드세요.
4. 여러 조각에 걸쳐 있는 문장을 수정할 때는 각 조각별로 나누어 적절히 수정값을 지정하세요.

[응답 형식 예시]
---SUMMARY---
- '3학년'을 '1학년'으로 변경
- '나눗셈' 단원을 '수 세기' 단원으로 변경
---JSON---
{{
  "replacements": {{
    "원본 조각": "수정된 내용"
  }}
}}
"""
        # 스트리밍 응답 처리
        response = client.models.generate_content_stream(
            model=model_name,
            contents=ai_prompt,
            config={
                "response_mime_type": "text/plain"
            }
        )
        
        full_text = ""
        shown_summaries = set()
        
        for chunk in response:
            if not chunk.text: continue
            full_text += chunk.text
            
            # SUMMARY 섹션 실시간 표시
            if "---SUMMARY---" in full_text and "---JSON---" not in full_text:
                summary_part = full_text.split("---SUMMARY---")[-1]
                lines = [l.strip() for l in summary_part.split("\n") if l.strip().startswith("-")]
                for line in lines:
                    clean_line = line[1:].strip()
                    if clean_line and clean_line not in shown_summaries:
                        shown_summaries.add(clean_line)
                        status_logs.append(f"AI 제안: {clean_line}")
                        self._update_status(status_logs[-1])

        # 결과 추출
        mapping_text = ""
        if "---JSON---" in full_text:
            mapping_text = full_text.split("---JSON---")[-1].strip()
        
        if "```json" in mapping_text:
            mapping_text = mapping_text.split("```json")[1].split("```")[0].strip()
        elif "```" in mapping_text:
            mapping_text = mapping_text.split("```")[1].split("```")[0].strip()

        try:
            mapping = json.loads(mapping_text)
            full_keywords = mapping.get("replacements", {})
            if not full_keywords and "keywords" in mapping:
                full_keywords = mapping.get("keywords", {})
        except Exception:
            # JSON 파싱 실패 시 예외 처리 (수동 추출 시도 등 가능)
            full_keywords = {}

        kw_file = APP_DIR / "temp_kw.json"
        with open(kw_file, "w", encoding="utf-8") as f:
            json.dump(full_keywords, f, ensure_ascii=False)

        # Clone & Replace — 동일한 파일 이름/경로에 덮어쓰기
        status_logs.append("문서 양식 복제 및 정밀 치환 중...")
        self._update_status(status_logs[-1])

        # 임시 출력 경로
        temp_output = hwpx_path.parent / f"_temp_edit_{hwpx_path.name}"

        subprocess.run([
            sys.executable, str(SKILL_DIR / "scripts" / "clone_form.py"),
            str(hwpx_path), str(temp_output),
            "--keywords", str(kw_file)
        ], check=True)

        subprocess.run([sys.executable, str(SKILL_DIR / "scripts" / "fix_namespaces.py"), str(temp_output)], check=True)

        # 기존 파일 삭제 후 동일 이름으로 교체
        # HWP인 경우 원본 HWP 삭제하고 HWPX로 대체
        original_path = Path(self._current_context_file)
        if original_path.suffix.lower() == ".hwp":
            if original_path.exists():
                original_path.unlink()
            
            # 파일 목록 업데이트는 send_message에서 처리되므로 여기서는 컨텍스트 경로만 업데이트
            self._current_context_file = str(hwpx_path)
            
            # (삭제됨) 파일 목록 업데이트는 send_message에서 최종 처리

        if hwpx_path.exists():
            try:
                hwpx_path.unlink()
            except:
                pass
        temp_output.rename(hwpx_path)

        status_logs.append("정밀 편집 완료!")
        self._update_status(status_logs[-1])

        result_files = [{"name": hwpx_path.name, "path": str(hwpx_path)}]
        
        is_temp = ".temp_drops" in str(hwpx_path)
        if is_temp:
            response_text = f"'{hwpx_path.name}' 파일을 성공적으로 수정했습니다!\n\n⚠️ 주의: 드래그 앤 드롭으로 올린 파일은 보안상 임시 폴더({hwpx_path.parent})에서 작업됩니다. 원본 위치의 파일을 직접 수정하시려면 '파일 열기' 버튼으로 파일을 선택해 주세요."
        else:
            response_text = f"'{hwpx_path.name}' 파일을 성공적으로 수정하여 원본 경로({hwpx_path})에 덮어씌웠습니다!"

        return response_text, status_logs, result_files

    # ---- 일반 대화 (CHAT) ----
    def _process_chat(self, api_key, model_name, user_prompt, chat_data):
        status_logs = []

        status_logs.append(f"모델 준비 중 ({model_name})...")
        self._update_status(status_logs[-1])

        client = genai.Client(api_key=api_key)

        # 컨텍스트 파일이 있으면 텍스트 추출하여 컨텍스트로 제공
        context = ""
        if self._current_context_file and os.path.exists(self._current_context_file):
            file_path = Path(self._current_context_file)
            if file_path.suffix.lower() in (".hwpx", ".hwp"):
                status_logs.append("문서 텍스트 분석 중...")
                self._update_status(status_logs[-1])
                try:
                    hwpx_path = file_path
                    if file_path.suffix.lower() == ".hwp":
                        hwpx_path = file_path.with_suffix(".hwpx")
                        if not hwpx_path.exists():
                            subprocess.run([sys.executable, str(SKILL_DIR / "scripts" / "convert_hwp.py"), str(file_path), "-o", str(hwpx_path)], check=True)
                    res = subprocess.run([sys.executable, str(SKILL_DIR / "scripts" / "text_extract.py"), str(hwpx_path)], capture_output=True)
                    extracted = res.stdout.decode("utf-8", errors="replace")
                    context = f"\n\n[참고 문서 정보]\n- 파일명: {file_path.name}\n- 전체 경로: {file_path.absolute()}\n\n[문서 내용]\n{extracted}"
                except Exception:
                    pass

        # 대화 히스토리 구성
        history_text = ""
        recent_messages = chat_data.get("messages", [])[-10:]  # 최근 10개 메시지
        for msg in recent_messages:
            role = "사용자" if msg["role"] == "user" else "AI"
            history_text += f"[{role}] {msg['content']}\n"

        ai_prompt = f"""당신은 '에이두 한글 에디터'의 AI 어시스턴트입니다. 한글 문서 관련 질문뿐 아니라 일반적인 질문에도 친절하고 도움되는 답변을 해주세요.

[대화 히스토리]
{history_text}
{context}

[사용자 메시지]
{user_prompt}

자연스럽고 친절한 한국어로 답변해주세요."""

        status_logs.append("답변 생성 중...")
        self._update_status(status_logs[-1])

        response = client.models.generate_content(
            model=model_name,
            contents=ai_prompt
        )
        response_text = response.text.strip()

        status_logs.append("완료")
        return response_text, status_logs

    # ---- RHWP 미리보기 ----
    def get_rhwp_url(self, file_path):
        """RHWP 미리보기 URL을 생성합니다."""
        if not self.server_thread:
            self._start_server()

        # 드라이브 루트 기준 절대 경로 사용 (예: C:/Users/.../file.hwpx)
        abs_path = os.path.abspath(file_path)
        # 드라이브 루트 기준 상대 경로 (예: Users/.../file.hwpx)
        drive_root = os.path.splitdrive(abs_path)[0] + os.sep  # C:\
        rel_from_root = os.path.relpath(abs_path, drive_root)
        url_path = urllib.parse.quote(rel_from_root.replace("\\", "/"))
        return f"https://edwardkim.github.io/rhwp/?url=http://127.0.0.1:{self.server_port}/{url_path}"

    def open_fullscreen_preview(self, file_path):
        """전체화면 미리보기를 별도 프로세스로 엽니다."""
        rhwp_url = self.get_rhwp_url(file_path)

        if self.preview_process and self.preview_process.poll() is None:
            self.preview_process.terminate()

        if PREVIEW_SCRIPT.exists():
            try:
                self.preview_process = subprocess.Popen(
                    [sys.executable, str(PREVIEW_SCRIPT), rhwp_url],
                    cwd=str(APP_DIR)
                )
            except Exception:
                webbrowser.open(rhwp_url)
        else:
            webbrowser.open(rhwp_url)
        return {"success": True}

    def _start_server(self):
        # 드라이브 루트를 서버 루트로 사용하여 모든 경로의 파일을 서빙
        drive_root = os.path.splitdrive(os.path.abspath(str(APP_DIR)))[0] + os.sep

        class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=drive_root, **kwargs)

            def end_headers(self):
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET')
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
                return super().end_headers()

            def log_message(self, format, *args):
                pass

        def run_server():
            while True:
                try:
                    with socketserver.TCPServer(("", self.server_port), CORSRequestHandler) as httpd:
                        httpd.serve_forever()
                except Exception:
                    self.server_port += 1

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

    # ---- 유틸리티 ----
    def open_url(self, url):
        """외부 URL을 기본 브라우저에서 엽니다."""
        webbrowser.open(url)
        return {"success": True}

    def upload_file(self, file_path):
        """파일을 현재 대화 컨텍스트에 등록합니다."""
        if os.path.exists(file_path):
            self._current_context_file = file_path
            return {"success": True, "name": os.path.basename(file_path)}
        return {"success": False}

    def open_folder(self, file_path):
        """파일이 있는 폴더를 열고 파일을 선택합니다."""
        if os.path.exists(file_path):
            abs_path = os.path.abspath(file_path)
            subprocess.run(['explorer', '/select,', abs_path])
            return {"success": True}
        return {"success": False}

    def pick_file(self):
        """네이티브 파일 선택 다이얼로그를 엽니다."""
        file_types = ('한글 파일 (*.hwp;*.hwpx)', 'All files (*.*)')
        result = self.window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=file_types
        )
        if result and len(result) > 0:
            file_path = result[0]
            if file_path and os.path.exists(file_path):
                self._current_context_file = file_path
                file_name = os.path.basename(file_path)
                return {"success": True, "name": file_name, "path": file_path}
        return {"success": False}


# ============ 메인 실행 ============
if __name__ == "__main__":
    api_instance = Api()

    window = webview.create_window(
        "에이두 한글 에디터",
        url=str(WEB_DIR / "index.html"),
        js_api=api_instance,
        width=1100,
        height=750,
        min_size=(800, 500),
        resizable=True,
        text_select=True
    )

    def on_loaded(window):
        if getattr(api_instance, '_initialized', False):
            return
        api_instance._initialized = True

        api_instance.window = window
        
        # Native Drag and Drop 지원
        if windnd:
            try:
                hwnd = None
                # pywebview 버전에 따라 다를 수 있음
                if hasattr(window, 'native') and hasattr(window.native, 'Handle'):
                    hwnd = window.native.Handle.ToInt64()
                
                if hwnd:
                    # Windows 아이콘 설정
                    try:
                        import ctypes
                        ICON_PATH = str(APP_DIR / "icon.ico")
                        if os.path.exists(ICON_PATH):
                            hicon = ctypes.windll.user32.LoadImageW(0, ICON_PATH, 1, 0, 0, 0x10 | 0x20)
                            if hicon:
                                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon)
                                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon)
                    except Exception as ie:
                        print(f"Icon error: {ie}")

                    # windnd 후킹
                    # api_instance.on_native_drop를 사용하여 참조 유지
                    if hasattr(windnd, 'hook_dropfiles'):
                        windnd.hook_dropfiles(hwnd, func=api_instance.on_native_drop)
                    elif hasattr(windnd, 'hook_drop'):
                        windnd.hook_drop(hwnd, func=api_instance.on_native_drop)
                    
                    print(f"Native Drop Hooked to HWND: {hwnd}")
                else:
                    print("Failed to get HWND for native drop hook")
            except Exception as e:
                print(f"Native Drop Hook Failed: {e}")

    webview.start(
        on_loaded,
        window,
        private_mode=False,
        storage_path=str(WEBVIEW_CACHE),
        debug=False,
        icon=str(APP_DIR / "icon.ico")
    )

