#!/usr/bin/env python3
"""
lark-knowledge-graph / fetch_article.py

抓取微信公众号文章并提取结构化数据:
  - 标题 / 作者 / 发布日期
  - 正文 HTML(保留 <strong>/<b>/<span style="color:...">)
  - 图片列表(完整 URL + 前后文,用于 LLM 判断每张图的类型/位置)

用法:
  python3 scripts/fetch_article.py <wechat_url>
  python3 scripts/fetch_article.py <wechat_url> --output article.json
"""
import argparse
import datetime
import html as html_lib
import json
import re
import subprocess
import sys
from pathlib import Path


WECHAT_UA = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/125.0.0.0 Safari/537.36'
)


def fetch_html(url: str, out_path: Path):
    """用 curl + 浏览器 UA 抓微信文章 HTML(WebFetch 会被 reCAPTCHA 拦)."""
    cmd = [
        'curl', '-sL', '--max-time', '20',
        '-H', f'User-Agent: {WECHAT_UA}',
        '-H', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        '-H', 'Accept-Language: zh-CN,zh;q=0.9,en;q=0.8',
        url, '-o', str(out_path)
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[ERR] curl failed: {proc.stderr}", file=sys.stderr)
        sys.exit(1)
    if out_path.stat().st_size < 1024:
        print(f"[ERR] HTML too small ({out_path.stat().st_size} bytes), possibly blocked", file=sys.stderr)
        sys.exit(1)


def extract_meta(html: str):
    """提取标题/作者/日期."""
    title_m = re.search(r"var msg_title\s*=\s*['\"]([^'\"]+)['\"]", html)
    author_m = re.search(r'<meta[^>]*property="og:article:author"[^>]*content="([^"]+)"', html)
    if not author_m:
        author_m = re.search(r'<a[^>]*id="js_name"[^>]*>\s*([^\s<]+)', html)
    ct_m = re.search(r"var ct\s*=\s*['\"](\d+)['\"]", html)

    return {
        'title': title_m.group(1) if title_m else None,
        'author': author_m.group(1).strip() if author_m else None,
        'date': (
            datetime.datetime.fromtimestamp(int(ct_m.group(1))).strftime('%Y-%m-%d')
            if ct_m else None
        )
    }


def extract_content(html: str):
    """提取 id=js_content 内的 HTML."""
    m = re.search(r'<div[^>]*id="js_content"[^>]*>(.*?)</div>\s*<script', html, re.DOTALL)
    return m.group(1) if m else None


def extract_images_with_context(content_html: str):
    """切分正文 → 输出每张图的完整 URL + 前后文."""
    parts = re.split(r'(<img[^>]+>)', content_html)
    images = []
    for i, part in enumerate(parts):
        if part.startswith('<img'):
            url_m = re.search(r'data-src="([^"]+)"', part)
            if not url_m:
                continue
            # HTML 实体 decode + 保留完整 query params(wx_fmt=png&from=appmsg)
            url = url_m.group(1).replace('&amp;', '&')
            prev = re.sub(r'<[^>]+>', '', parts[i-1] if i > 0 else '')[-150:].strip()
            nxt = re.sub(r'<[^>]+>', '', parts[i+1] if i < len(parts)-1 else '')[:150].strip()
            images.append({
                'idx': len(images) + 1,
                'url': url,
                'prev_context': prev,
                'next_context': nxt
            })
    return images


def extract_emphasis(content_html: str):
    """提取原文的强调标记(粗体/彩色文本)以便重构时还原."""
    bolds = []
    for m in re.finditer(r'<(?:strong|b)[^>]*>(.*?)</(?:strong|b)>', content_html, re.DOTALL):
        text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if text and len(text) < 200:
            bolds.append(text)
    colors = []
    for m in re.finditer(r'style="[^"]*color\s*:\s*([^;"]+)[^"]*"[^>]*>(.*?)<', content_html):
        text = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        if text and len(text) < 200:
            colors.append({'color': m.group(1).strip(), 'text': text})
    return {'bold': bolds, 'colored': colors}


def html_to_text(content_html: str):
    """正文转纯文本,便于 LLM 重构."""
    text = re.sub(r'<img[^>]+>', '\n[IMG]\n', content_html)
    text = re.sub(r'</(p|div|section|h\d|li|blockquote|br)[^>]*>', '\n', text)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    # 用标准库 html.unescape 处理所有命名实体(&nbsp; &middot; &mdash; ...)
    # 和数字实体(&#39; &#x2014; ...),比手工列表全面得多
    text = html_lib.unescape(text)
    # &nbsp; ( ) 转回普通空格,避免后续 split/strip 时不识别
    text = text.replace(' ', ' ')
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url', help='微信公众号文章 URL')
    parser.add_argument('--output', type=Path, help='输出 JSON 路径(默认 stdout)')
    parser.add_argument('--html-cache', type=Path, default=Path('/tmp/wechat_article.html'))
    args = parser.parse_args()

    print(f"[1/4] 抓取 HTML → {args.html_cache}", file=sys.stderr)
    fetch_html(args.url, args.html_cache)
    html = args.html_cache.read_text(encoding='utf-8')

    print("[2/4] 提取元信息", file=sys.stderr)
    meta = extract_meta(html)
    if not meta['title']:
        print("[ERR] 未提取到标题, HTML 可能被反爬拦截", file=sys.stderr)
        sys.exit(1)

    print("[3/4] 切分正文 + 图片 + 强调标记", file=sys.stderr)
    content = extract_content(html)
    if not content:
        print("[ERR] 未找到 js_content 块", file=sys.stderr)
        sys.exit(1)

    images = extract_images_with_context(content)
    emphasis = extract_emphasis(content)
    text = html_to_text(content)

    result = {
        'url': args.url,
        'meta': meta,
        'text': text,
        'images': images,
        'emphasis': emphasis,
        'content_html_path': str(args.html_cache)
    }

    print(f"[4/4] ✅ 标题: {meta['title']}", file=sys.stderr)
    print(f"      作者: {meta['author']}  日期: {meta['date']}", file=sys.stderr)
    print(f"      正文: {len(text)} 字符  图片: {len(images)} 张", file=sys.stderr)

    out = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(out, encoding='utf-8')
        print(f"      JSON 写入 {args.output}", file=sys.stderr)
    else:
        print(out)


if __name__ == '__main__':
    main()
