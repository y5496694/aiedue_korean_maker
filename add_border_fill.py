import sys
path = r'c:\Users\USER\Desktop\antigravity\에이두 한글 에디터\hwpx_skill\templates\government\header.xml'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Update itemCnt
content = content.replace('<hh:borderFills itemCnt="50">', '<hh:borderFills itemCnt="51">')

new_bf = '<hh:borderFill id="51" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0"><hh:slash type="NONE" Crooked="0" isCounter="0"/><hh:backSlash type="NONE" Crooked="0" isCounter="0"/><hh:leftBorder type="SOLID" width="0.12 mm" color="#000000"/><hh:rightBorder type="SOLID" width="0.12 mm" color="#000000"/><hh:topBorder type="SOLID" width="0.12 mm" color="#000000"/><hh:bottomBorder type="SOLID" width="0.12 mm" color="#000000"/><hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/><hc:fillBrush><hc:winBrush faceColor="#F5F5F5" hatchColor="#999999" alpha="0"/></hc:fillBrush></hh:borderFill></hh:borderFills>'

if '<hh:borderFill id="51"' not in content:
    content = content.replace('</hh:borderFills>', new_bf)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('header.xml successfully injected with ID 51.')
