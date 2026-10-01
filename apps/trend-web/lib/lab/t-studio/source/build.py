# 시안 t-studio 의 원본(src/, data/)을 합쳐 한 파일짜리 화면을 만들고, Next 가 내보낼 ../prototype-html.ts 로 쓴다: python3 build.py
# prototype-html.ts 는 생성 파일 — 손으로 고치지 않는다.
import os
D = os.path.dirname(os.path.abspath(__file__))
js = ['data/v2-data-full.js', 'data/extra.js', 'src/data-app.js', 'src/copy.js', 'src/app-core.js', 'src/page-radar.js', 'src/page-studio.js', 'src/page-more.js']
code = '\n'.join(open(os.path.join(D, f), encoding='utf8').read() for f in js)
css = open(os.path.join(D, 'src/styles.css'), encoding='utf8').read()
head = ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<title>트렌드 통역</title>\n<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">\n'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap">\n')
page = head + '<style>\n' + css + '\n</style>\n</head>\n<body>\n<div id="app"></div>\n<script>\n(function(){\n"use strict";\n' + code + '\napplyTheme();\nrender(true);\n})();\n</script>\n</body>\n</html>\n'
import json
ts = ('// 생성 파일 — lib/lab/t-studio/source/build.py 가 만든다. 손으로 고치지 않는다.\n'
      '// 시안 t-studio 의 한 파일짜리 화면(예시 데이터). app/lab/t-studio/proto/route.ts 가 그대로 내보낸다.\n'
      'export const PROTOTYPE_HTML: string = ' + json.dumps(page, ensure_ascii=False) + ';\n')
open(os.path.join(D, '..', 'prototype-html.ts'), 'w', encoding='utf8').write(ts)
print('prototype-html.ts', len(ts), 'bytes')
