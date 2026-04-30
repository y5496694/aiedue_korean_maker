import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import os
import json
import subprocess
import sys
from pathlib import Path
import google.generativeai as genai
import threading
import webbrowser
import http.server
import socketserver
try:
    import windnd
except ImportError:
    windnd = None

# 전역 설정
APP_DIR = Path(__file__).parent
SKILL_DIR = APP_DIR / "hwpx_skill"
SETTINGS_FILE = APP_DIR / "settings.json"

# hwpx_skill/scripts를 경로에 추가
sys.path.insert(0, str(SKILL_DIR / "scripts"))

class HWPXEditorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("에이두 한글 에디터")
        self.geometry("800x650")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.api_key = self.load_settings().get("api_key", "")
        self.last_output_file = ""
        self.server_thread = None
        self.server_port = 8888

        self.setup_ui()
        self.check_api_and_update_ui()
        if windnd:
            windnd.hook_dropfiles(self, func=self.on_drop)

    def load_settings(self):
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        return {}

    def save_settings(self, settings):
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)

    def setup_ui(self):
        # 사이드바
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.pack(side="left", fill="y")

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="에이두 한글 에디터", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.pack(pady=20)

        self.btn_new = ctk.CTkButton(self.sidebar_frame, text="새로 만들기", command=self.mode_new)
        self.btn_new.pack(pady=10, padx=20)

        self.btn_edit = ctk.CTkButton(self.sidebar_frame, text="편집하기", command=self.mode_edit)
        self.btn_edit.pack(pady=10, padx=20)

        self.btn_settings = ctk.CTkButton(self.sidebar_frame, text="설정", command=self.show_settings)
        self.btn_settings.pack(side="bottom", pady=20, padx=20)

        # 메인 영역
        self.main_frame = ctk.CTkFrame(self, corner_radius=15)
        self.main_frame.pack(side="right", fill="both", expand=True, padx=20, pady=20)

        self.mode_label = ctk.CTkLabel(self.main_frame, text="작업 모드를 선택하세요", font=ctk.CTkFont(size=24))
        # 초기에는 숨김 (API 키 확인 후 표시)
        
        # 가이드 영역 (최초 실행 시)
        self.guide_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        
        self.guide_title = ctk.CTkLabel(self.guide_frame, text="[최초 실행 필독]", font=ctk.CTkFont(size=22, weight="bold"), text_color="#3498db")
        self.guide_title.pack(pady=(50, 20))
        
        guide_text = "1. 아래 버튼을 눌러 구글 AI 스튜디오에 접속합니다.\n\n2. 로그인 후 'Create API key'를 눌러 키를 생성합니다.\n\n3. 생성된 키를 복사한 후, 왼쪽 하단의 '설정' 버튼을 눌러 입력하세요."
        self.guide_desc = ctk.CTkLabel(self.guide_frame, text=guide_text, font=ctk.CTkFont(size=16), justify="left")
        self.guide_desc.pack(pady=20)
        
        self.btn_link = ctk.CTkButton(self.guide_frame, text="구글 AI 스튜디오 바로가기 (API 키 발급)", 
                                     fg_color="#db4437", hover_color="#c13b2e",
                                     command=lambda: webbrowser.open("https://aistudio.google.com/app/api-keys?project=gen-lang-client-0471748098"))
        self.btn_link.pack(pady=10)

        # 공통 입력부 (모드 선택 시 표시)
        self.input_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        
        self.file_label = ctk.CTkLabel(self.input_frame, text="파일 선택 안됨", text_color="gray")
        self.btn_select_file = ctk.CTkButton(self.input_frame, text="파일 선택", command=self.select_file)
        
        self.prompt_label = ctk.CTkLabel(self.main_frame, text="AI 지시 사항 (Prompt):")
        self.prompt_text = ctk.CTkTextbox(self.main_frame, height=200)
        
        self.btn_run = ctk.CTkButton(self.main_frame, text="AI 작업 시작", fg_color="#2ecc71", hover_color="#27ae60", command=self.start_process_thread)
        
        self.status_label = ctk.CTkLabel(self.main_frame, text="준비됨", text_color="gray")
        self.progress = ctk.CTkProgressBar(self.main_frame)
        
        self.btn_open_file = ctk.CTkButton(self.main_frame, text="생성된 파일 열기", command=self.open_last_file, state="disabled")

        self.current_mode = ""
        self.selected_file = ""

    def check_api_and_update_ui(self):
        if self.api_key:
            # API 키가 있으면 가이드 숨기고 버튼 활성화
            self.guide_frame.pack_forget()
            self.btn_new.configure(state="normal")
            self.btn_edit.configure(state="normal")
            if not self.current_mode:
                self.mode_label.pack(pady=20)
        else:
            # API 키가 없으면 가이드 표시하고 버튼 비활성화
            self.mode_label.pack_forget()
            self.guide_frame.pack(fill="both", expand=True)
            self.btn_new.configure(state="disabled")
            self.btn_edit.configure(state="disabled")

    def switch_to_main(self):
        self.guide_frame.pack_forget()
        self.mode_label.pack(pady=20)

    def mode_new(self):
        self.current_mode = "NEW"
        self.mode_label.configure(text="새 문서 만들기 (Workflow A)")
        self.btn_select_file.pack_forget()
        self.file_label.pack_forget()
        self.show_inputs()

    def mode_edit(self):
        self.current_mode = "EDIT"
        self.mode_label.configure(text="기존 문서 편집하기 (Workflow F)")
        self.btn_select_file.pack(pady=5)
        self.file_label.pack(pady=5)
        self.show_inputs()

    def show_inputs(self):
        self.input_frame.pack(fill="x", padx=40)
        self.prompt_label.pack(pady=(20, 5), padx=40, anchor="w")
        self.prompt_text.pack(fill="x", padx=40, pady=5)
        self.btn_run.pack(pady=20)
        self.status_label.pack()
        self.progress.pack(fill="x", padx=40, pady=10)
        self.progress.set(0)
        self.btn_open_file = ctk.CTkButton(self.input_frame, text="생성된 파일 열기", command=self.open_last_file, fg_color="#27ae60", hover_color="#2ecc71")
        self.btn_open_file.pack(pady=10)
        
        self.btn_rhwp = ctk.CTkButton(self.input_frame, text="RHWP로 미리보기 (웹)", command=self.open_rhwp_preview, fg_color="#e67e22", hover_color="#d35400")
        self.btn_rhwp.pack(pady=5)

    def select_file(self):
        filename = filedialog.askopenfilename(filetypes=[("Hangul Files", "*.hwp *.hwpx")])
        if filename:
            self.selected_file = filename
            self.file_label.configure(text=os.path.basename(filename), text_color="white")

    def on_drop(self, filenames):
        if filenames:
            # 첫 번째 파일만 사용
            file_path = filenames[0].decode('cp949') if isinstance(filenames[0], bytes) else filenames[0]
            if file_path.lower().endswith(('.hwp', '.hwpx')):
                self.selected_file = file_path
                self.file_label.configure(text=os.path.basename(file_path), text_color="white")
                if self.current_mode != "EDIT":
                    self.mode_edit() # 자동으로 편집 모드로 전환

    def show_settings(self):
        dialog = ctk.CTkInputDialog(text="Gemini API Key를 입력하세요:", title="설정")
        key = dialog.get_input()
        if key:
            self.api_key = key
            self.save_settings({"api_key": key})
            messagebox.showinfo("완료", "API Key가 저장되었습니다. 이제 모든 기능을 사용할 수 있습니다.")
            self.check_api_and_update_ui()

    def open_last_file(self):
        if self.last_output_file and os.path.exists(self.last_output_file):
            os.startfile(self.last_output_file)
        else:
            messagebox.showwarning("경고", "열 수 있는 파일이 없습니다.")

    def open_rhwp_preview(self):
        if not self.last_output_file or not os.path.exists(self.last_output_file):
            messagebox.showwarning("경고", "미리보기할 파일이 없습니다.")
            return

        # Start local server if not running
        if self.server_thread is None:
            self.start_server_in_thread()
        
        # Construct URL
        # We need the relative path from the current working directory
        rel_path = os.path.relpath(self.last_output_file, os.getcwd())
        # Replace backslashes for URL
        url_path = rel_path.replace("\\", "/")
        
        rhwp_url = f"https://edwardkim.github.io/rhwp/?url=http://127.0.0.1:{self.server_port}/{url_path}"
        webbrowser.open(rhwp_url)

    def start_server_in_thread(self):
        class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
            def end_headers(self):
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET')
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
                return super().end_headers()
            
            def log_message(self, format, *args):
                # Silence server logs
                pass

        def run_server():
            while True:
                try:
                    with socketserver.TCPServer(("", self.server_port), CORSRequestHandler) as httpd:
                        httpd.serve_forever()
                except Exception:
                    # If port in use, try next one
                    self.server_port += 1

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

    def start_process_thread(self):
        if not self.api_key:
            messagebox.showerror("오류", "설정에서 API Key를 먼저 입력하세요.")
            return
        
        prompt = self.prompt_text.get("1.0", "end-1c")
        if not prompt:
            messagebox.showerror("오류", "AI 지시 사항을 입력하세요.")
            return

        if self.current_mode == "EDIT" and not self.selected_file:
            messagebox.showerror("오류", "편집할 파일을 선택하세요.")
            return

        self.btn_run.configure(state="disabled")
        self.progress.set(0)
        threading.Thread(target=self.process, daemon=True).start()

    def process(self):
        try:
            prompt = self.prompt_text.get("1.0", "end-1c")
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel('gemini-3-flash-preview')

            if self.current_mode == "EDIT":
                self.process_edit(model, prompt)
            else:
                self.process_new(model, prompt)

            self.status_label.configure(text="작업 완료!", text_color="#2ecc71")
            self.btn_open_file.configure(state="normal")
        except Exception as e:
            self.status_label.configure(text=f"오류 발생: {str(e)}", text_color="#e74c3c")
            messagebox.showerror("작업 실패", str(e))
        finally:
            self.btn_run.configure(state="normal")

    def process_edit(self, model, user_prompt):
        # 1. 출력 폴더 생성
        edit_dir = APP_DIR / "편집한 파일"
        edit_dir.mkdir(exist_ok=True)

        # 2. HWP -> HWPX 변환 (필요시)
        input_path = Path(self.selected_file)
        hwpx_path = input_path
        if input_path.suffix.lower() == ".hwp":
            self.status_label.configure(text="HWP를 HWPX로 변환 중...")
            self.progress.set(0.1)
            output_hwpx = input_path.with_suffix(".hwpx")
            subprocess.run(["python", str(SKILL_DIR / "scripts" / "convert_hwp.py"), str(input_path), "-o", str(output_hwpx)], check=True)
            hwpx_path = output_hwpx

        # 2. 텍스트 추출
        self.status_label.configure(text="문서 텍스트 분석 중...")
        self.progress.set(0.3)
        res = subprocess.run(["python", str(SKILL_DIR / "scripts" / "text_extract.py"), str(hwpx_path)], capture_output=True)
        extracted_text = res.stdout.decode("utf-8", errors="replace")

        # 3. Gemini에게 매핑 요청
        self.status_label.configure(text="AI가 수정을 제안하는 중...")
        ai_prompt = f"""
당신은 HWPX 문서 편집 전문가입니다. 아래 문서의 내용을 사용자 요청에 맞춰 수정하기 위한 JSON 매핑(replacements와 keywords)을 생성하세요.
원본 구조를 최대한 유지하면서 내용만 자연스럽게 바꾸어야 합니다.

[원본 문서 텍스트]
{extracted_text}

[사용자 요청]
{user_prompt}

[응답 형식 (JSON만 출력)]
{{
  "replacements": {{ "기존 긴 문구": "새로운 문구", ... }},
  "keywords": {{ "기존 단어": "새 단어", ... }}
}}
"""
        response = model.generate_content(ai_prompt)
        mapping_text = response.text.strip()
        # Markdown backticks 제거
        if "```json" in mapping_text:
            mapping_text = mapping_text.split("```json")[1].split("```")[0].strip()
        elif "```" in mapping_text:
            mapping_text = mapping_text.split("```")[1].split("```")[0].strip()
        
        mapping = json.loads(mapping_text)
        
        # 모든 제안 사항을 하나의 키워드 맵으로 병합 ( Phase 2의 안전한 치환을 위함 )
        full_keywords = mapping.get("keywords", {})
        full_keywords.update(mapping.get("replacements", {}))
        
        kw_file = APP_DIR / "temp_kw.json"
        with open(kw_file, "w", encoding="utf-8") as f: 
            json.dump(full_keywords, f, ensure_ascii=False)

        # 4. Clone & Replace
        self.status_label.configure(text="문서 양식 복제 및 치환 중...")
        self.progress.set(0.6)
        output_file = edit_dir / f"edited_{hwpx_path.name}"
        # 모든 치환을 --keywords로 전달하여 <hp:t> 태그 내부에서만 안전하게 치환되도록 함 (문서 망가짐 방지)
        subprocess.run([
            "python", str(SKILL_DIR / "scripts" / "clone_form.py"),
            str(hwpx_path), str(output_file),
            "--keywords", str(kw_file)
        ], check=True)

        # 5. Namespace Fix
        subprocess.run(["python", str(SKILL_DIR / "scripts" / "fix_namespaces.py"), str(output_file)], check=True)
        
        self.last_output_file = str(output_file)
        self.progress.set(1.0)

    def process_new(self, model, user_prompt):
        self.status_label.configure(text="AI가 문서 구조 및 서식을 설계 중...")
        self.progress.set(0.2)
        
        # 1. Gemini에게 문서 구성 계획(JSON) 요청
        ai_prompt = f"""
당신은 HWPX 문서 생성 전문가입니다. 사용자의 요청에 따라 '관공서 스타일' 문서 구성 계획을 JSON으로 작성하세요.
문서는 반드시 화려한 컬러 배너와 섹션 바를 포함해야 하며, 본문 문단은 내용의 성격에 따라 적절한 말머리 기호를 사용해야 합니다.

[사용자 요청]
{user_prompt}

[작성 규칙]
1. 순서가 중요한 항목은 '가. 나. 다.' 형태의 말머리를 붙이세요 (type: "ordered").
2. 단순 나열형 항목은 '●' 기호를 말머리로 사용하세요 (type: "bullet").
3. 일반 설명 문단은 기호 없이 작성하세요 (type: "text").

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
        {{ "type": "ordered", "marker": "가", "text": "첫 번째 순서 내용" }},
        {{ "type": "bullet", "text": "나열형 내용" }},
        {{ "type": "text", "text": "일반 설명 문단" }}
      ]
    }}
  ]
}}
"""
        response = model.generate_content(ai_prompt)
        plan_text = response.text.strip()
        if "```json" in plan_text:
            plan_text = plan_text.split("```json")[1].split("```")[0].strip()
        elif "```" in plan_text:
            plan_text = plan_text.split("```")[1].split("```")[0].strip()
        
        plan = json.loads(plan_text)
        plan_file = APP_DIR / "temp_plan.json"
        plan_file.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

        # 출력 폴더 및 파일명 결정
        new_dir = APP_DIR / "새로 만든 파일"
        new_dir.mkdir(exist_ok=True)
        
        # 제목을 파일명으로 사용 (특수문자 제거)
        safe_title = "".join([c for c in plan.get("title", "new_document") if c.isalnum() or c in (" ", "_", "-")]).strip()
        output_name = f"{safe_title}.hwpx"
        output_path = new_dir / output_name

        # 2. Python 빌드 스크립트 실행
        self.status_label.configure(text="지능적 서식 적용 및 문서 빌드 중...")
        self.progress.set(0.5)
        
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
parts.extend(make_cover_page(plan.get("title", "제목"), plan.get("subtitle", ""), plan.get("date", "")))

# 섹션별 반복
for i, sec in enumerate(plan.get("sections", [])):
    parts.append(make_section_bar(sec.get("number", str(i+1)), sec.get("title", "제목")))
    parts.append(make_empty_line())
    
    for item in sec.get("content", []):
        ctype = item.get("type", "text")
        text = item.get("text", "")
        
        if ctype == "ordered":
            marker = item.get("marker", "가")
            parts.append(make_body_para(f"{{marker}}.", text))
        elif ctype == "bullet":
            parts.append(make_body_para("●", text))
        else:
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
        subprocess.run(["python", str(temp_script)], check=True)
        
        self.last_output_file = str(output_path)
        self.progress.set(1.0)

if __name__ == "__main__":
    app = HWPXEditorApp()
    app.mainloop()
