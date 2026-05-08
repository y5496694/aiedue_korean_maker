import os
files = [
    r'c:\Users\USER\Desktop\antigravity\에이두 한글 에디터\hwpx_skill\scripts\hwpx_helpers.py',
    r'c:\Users\USER\Desktop\antigravity\에이두 한글 에디터\hwpx_skill\scripts\md2hwpx.py'
]

for p in files:
    if os.path.exists(p):
        with open(p, 'r', encoding='utf-8') as f:
            content = f.read()
        if 'editable="0"' in content:
            # Replace editable="0" with editable="1" or just remove it
            # Let's remove it to keep it standard, or set it to editable="1"
            # It's usually not present. Let's remove it.
            new_content = content.replace(' editable="0"', '')
            new_content = new_content.replace('editable="0"', '')
            with open(p, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Removed editable=0 from {os.path.basename(p)}")
