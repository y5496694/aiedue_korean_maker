# 에이두 한글 에디터 (Aiedu HWPX Editor)

이 프로그램은 AI(Gemini)를 활용하여 한글 문서(.hwp, .hwpx)를 자동으로 생성하고 편집하는 도구입니다. `jkf87/hwpx-skill`의 강력한 변환 엔진을 UI 기반으로 제공합니다.

## 주요 기능

1. **새로 만들기 (Workflow A)**:
   * AI에게 주제와 내용을 말하면 `government` 템플릿(관공서 스타일) 기반의 고품질 문서를 처음부터 생성합니다.
2. **편집하기 (Workflow F)**:
   * 기존 HWP/HWPX 파일을 불러와서 표 구조와 서식을 100% 유지한 채 AI가 내용을 수정합니다.
   * `.hwp` 파일은 자동으로 `.hwpx`로 변환 후 작업을 진행합니다.
3. **AI 통합 (Gemini 3 Flash Preview)**:
   * Gemini API를 통해 복잡한 교수학습과정안, 공문서 등의 내용을 지시어(Prompt)만으로 완성합니다.
4. **즉시 확인**:
   * 작업 완료 후 버튼 하나로 생성된 파일을 바로 열어볼 수 있습니다.

## 설치 및 준비 사항

### 1. Python 설치
* Python 3.10 이상의 버전이 필요합니다.

### 2. 의존성 패키지 설치
아래 명령어를 터미널에서 실행하여 필요한 라이브러리를 설치하세요.
pip install -r requirements.txt --break-system-packages
```

### 3. Gemini API 키 발급
* [Google AI Studio](https://aistudio.google.com/)에서 API 키를 발급받아 프로그램 설정에서 입력해야 합니다.

## 사용 방법

1. `에이두 한글 에디터.bat` 파일을 실행합니다. 
   * (Python이 없으면 자동으로 설치를 시도하며, 필요한 모든 라이브러리를 자동으로 다운로드합니다.)
2. **설정** 버튼을 눌러 API 키를 입력합니다.
3. **새로 만들기** 또는 **편집하기** 모드를 선택합니다.
4. 파일을 선택(편집 시)하고, AI에게 원하는 수정 사항을 입력합니다.
5. **실행** 버튼을 누르면 문서가 생성/편집되며 완료 후 **파일 열기** 버튼이 활성화됩니다.

## 프로젝트 구조

* `app.py`: 메인 UI 애플리케이션
* `hwpx_skill/`: HWPX 변환 및 생성 핵심 엔진 (스크립트 폴더)
* `requirements.txt`: 필요한 패키지 목록
* `settings.json`: API 키 및 설정 저장 파일

---
© 2026 Advanced Agentic Coding - Antigravity
