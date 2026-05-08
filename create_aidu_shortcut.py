import os
import sys
from pathlib import Path

def create_shortcut():
    try:
        import winshell
        from win32com.client import Dispatch
        from PIL import Image
    except ImportError:
        print("Required libraries missing. Installing...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "winshell", "pywin32", "Pillow"])
        import winshell
        from win32com.client import Dispatch
        from PIL import Image

    # 경로 설정
    current_dir = Path(__file__).resolve().parent
    target_bat = current_dir / "run_app.bat"
    
    if not target_bat.exists():
        # 대안: "에이두 한글 에디터.bat" 확인
        target_bat = current_dir / "에이두 한글 에디터.bat"
        if not target_bat.exists():
            print(f"Error: Target BAT file not found in {current_dir}")
            return

    # 아이콘 설정
    # 이전 단계에서 생성된 아이콘 경로 (정확한 파일명 확인 필요)
    # 여기서는 폴더 내의 .png 파일을 찾거나 기본 경로 사용
    icon_png = Path(r"C:\Users\USER\.gemini\antigravity\brain\b2aedf54-1361-4366-ac0a-31d2108046bc\aidu_app_icon_1778214549153.png")
    icon_ico = current_dir / "aidu_icon.ico"

    if icon_png.exists():
        print(f"Converting {icon_png.name} to .ico...")
        img = Image.open(icon_png)
        img.save(icon_ico, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    else:
        print("Warning: Custom icon PNG not found. Shortcut will use default icon.")
        icon_ico = None

    # 바로가기 생성 (바탕화면 및 현재 폴더)
    desktop = Path(winshell.desktop())
    shortcut_paths = [
        desktop / "에이두 한글 에디터.lnk",
        current_dir / "에이두 한글 에디터.lnk"
    ]

    for shortcut_path in shortcut_paths:
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.Targetpath = str(target_bat)
        shortcut.WorkingDirectory = str(current_dir)
        shortcut.Description = "에이두 AI 한글 에디터"
        if icon_ico and icon_ico.exists():
            shortcut.IconLocation = str(icon_ico)
        shortcut.save()
        print(f"Shortcut created: {shortcut_path}")

if __name__ == "__main__":
    create_shortcut()
