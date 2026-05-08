import xml.etree.ElementTree as ET
tree = ET.parse(r'c:\Users\USER\Desktop\antigravity\에이두 한글 에디터\hwpx_skill\templates\government\header.xml')
hh = '{http://www.hancom.co.kr/hwpml/2011/head}'
for pr in tree.getroot().findall(f'.//{hh}paraPr'):
    if pr.get('id') in ['3', '4', '8']:
        print(f"ID: {pr.get('id')}")
        for child in pr:
            print('  ', child.tag.split('}')[-1], child.attrib)
