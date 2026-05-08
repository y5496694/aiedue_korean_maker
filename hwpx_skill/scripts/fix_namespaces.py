#!/usr/bin/env python3
"""
HWPX 네임스페이스 후처리 유틸리티

python-hwpx가 생성한 HWPX 파일의 XML 네임스페이스 프리픽스를
한컴오피스 표준 프리픽스로 교체한다.

이 스크립트를 실행하지 않으면 한글 Viewer(특히 macOS)에서
문서가 빈 페이지로 표시될 수 있다.

사용법:
  CLI:    python fix_namespaces.py <file.hwpx>
  Import: exec(open("fix_namespaces.py").read())
          fix_hwpx_namespaces("output.hwpx")
"""

import zipfile
import os
import re
import sys


def _fix_item_counts(header_xml):
    """header.xml의 itemCnt 속성을 실제 자식 요소 수와 일치시킨다.

    charPr, borderFill 등을 추가/삭제한 뒤 itemCnt가 불일치하면
    한컴 뷰어가 추가된 스타일을 무시하므로 반드시 보정해야 한다.
    """
    count_map = {
        "charProperties": r"<hh:charPr ",
        "borderFills": r"<hh:borderFill ",
        "paraProperties": r"<hh:paraPr ",
        "styles": r"<hh:style ",
    }
    for container, child_re in count_map.items():
        actual = len(re.findall(child_re, header_xml))
        if actual > 0:
            header_xml = re.sub(
                rf"(<hh:{container}\s+itemCnt=\")\d+(\")",
                rf"\g<1>{actual}\2",
                header_xml,
            )
    return header_xml


def fix_hwpx_namespaces(hwpx_path):
    """
    HWPX 파일의 ns0:/ns1: 등 자동 생성 프리픽스를
    한컴오피스 표준 프리픽스(hh/hc/hp/hs)로 교체한다.

    Args:
        hwpx_path: 수정할 .hwpx 파일 경로
    """
    NS_MAP = {
        'http://www.hancom.co.kr/hwpml/2011/head': 'hh',
        'http://www.hancom.co.kr/hwpml/2011/core': 'hc',
        'http://www.hancom.co.kr/hwpml/2011/paragraph': 'hp',
        'http://www.hancom.co.kr/hwpml/2011/section': 'hs',
        'http://www.hancom.co.kr/hwpml/2011/app': 'ha',
        'http://www.hancom.co.kr/hwpml/2016/paragraph': 'hp10',
        'http://www.hancom.co.kr/hwpml/2011/history': 'hhs',
        'http://www.hancom.co.kr/hwpml/2011/master-page': 'hm',
        'http://www.hancom.co.kr/schema/2011/hpf': 'hpf',
        'http://purl.org/dc/elements/1.1/': 'dc',
        'http://www.idpf.org/2007/opf/': 'opf',
        'http://www.hancom.co.kr/hwpml/2016/ooxmlchart': 'ooxmlchart',
        'http://www.hancom.co.kr/hwpml/2016/HwpUnitChar': 'hwpunitchar',
        'http://www.idpf.org/2007/ops': 'epub',
        'urn:oasis:names:tc:opendocument:xmlns:config:1.0': 'config'
    }

    tmp_path = hwpx_path + ".tmp"

    with zipfile.ZipFile(hwpx_path, "r") as zin:
        filenames = zin.namelist()
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
            # 1. mimetype은 반드시 첫 번째로 (OCF 표준)
            if "mimetype" in filenames:
                data = zin.read("mimetype")
                zout.writestr("mimetype", data, compress_type=zipfile.ZIP_STORED)

            for item in zin.infolist():
                if item.filename == "mimetype":
                    continue
                
                data = zin.read(item.filename)

                # XML 또는 HPF 파일인 경우 내용 처리
                is_target_file = item.filename.endswith((".xml", ".hpf", ".rels"))
                
                if is_target_file:
                    try:
                        text = data.decode("utf-8")
                    except UnicodeDecodeError:
                        zout.writestr(item, data)
                        continue

                    ns_aliases = {}
                    for match in re.finditer(r'xmlns:(ns\d+)="([^"]+)"', text):
                        alias, uri = match.group(1), match.group(2)
                        if uri in NS_MAP:
                            ns_aliases[alias] = NS_MAP[uri]

                    for old_prefix, new_prefix in ns_aliases.items():
                        text = re.sub(rf'xmlns:{old_prefix}=', f'xmlns:{new_prefix}=', text)
                        text = re.sub(rf'<{old_prefix}:', f'<{new_prefix}:', text)
                        text = re.sub(rf'</{old_prefix}:', f'</{new_prefix}:', text)
                        text = re.sub(rf'\s{old_prefix}:', f' {new_prefix}:', text)

                    if item.filename == "Contents/header.xml":
                        text = _fix_item_counts(text)

                    data = text.encode("utf-8")
                    
                # 데이터가 변경된 경우(XML) 또는 원본 그대로인 경우 모두
                # 새로운 ZipInfo를 생성하도록 filename과 compress_type만 전달하는 것이 안전함
                zout.writestr(item.filename, data, compress_type=item.compress_type)

    os.replace(tmp_path, hwpx_path)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python fix_namespaces.py <file.hwpx>")
        print("  Fixes namespace prefixes for Hangul Viewer compatibility.")
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"Error: File not found: {path}")
        sys.exit(1)

    fix_hwpx_namespaces(path)
    print(f"Fixed namespaces: {path}")
