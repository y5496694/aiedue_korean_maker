"""
에이두 한글 에디터 - 문서 미리보기 브라우저
pywebview를 사용하여 RHWP 미리보기를 네이티브 웹뷰 창으로 표시합니다.
별도 프로세스로 실행되어 메인 앱과 독립적으로 동작합니다.
"""
import sys
import os
import tempfile

# WebView2 user data folder를 명시적으로 지정하여 E_ACCESSDENIED 방지
# 앱 디렉토리 내에 캐시 폴더를 만듦
APP_DIR = os.path.dirname(os.path.abspath(__file__))
WEBVIEW_CACHE = os.path.join(APP_DIR, ".webview_cache")
os.makedirs(WEBVIEW_CACHE, exist_ok=True)

# pywebview의 WebView2 환경 변수 설정 (cache 경로 지정)
os.environ['WEBVIEW2_USER_DATA_FOLDER'] = WEBVIEW_CACHE

import webview

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: preview_browser.py <url>")
        sys.exit(1)
    
    url = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else "📄 문서 미리보기 - 에이두 한글 에디터"
    
    window = webview.create_window(
        title,
        url,
        width=750,
        height=850,
        resizable=True,
        text_select=True,
    )
    
    # Windows에서 Edge WebView2 사용, private_mode=False로 캐시 허용
    try:
        webview.start(private_mode=False, storage_path=WEBVIEW_CACHE, debug=False)
    except Exception as e:
        print(f"[pywebview 실행 실패] {e}")
        # 최후의 폴백: 기본 브라우저
        import webbrowser
        webbrowser.open(url)
