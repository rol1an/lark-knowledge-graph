#!/usr/bin/env python3
"""
lark-knowledge-graph / build_graph.py

拉飞书 Bitable 节点表 + 边表 → 注入 templates/graph_template.html
→ 输出自包含的 article_graph.html

用法:
  python3 scripts/build_graph.py
  python3 scripts/build_graph.py --config ./.config.json --output ./out.html
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def run_lark(args, parse_json=True):
    """运行 lark-cli 并返回 JSON。失败时抛异常。"""
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[ERR] lark-cli failed: {' '.join(args)}", file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        sys.exit(1)
    if not parse_json:
        return proc.stdout
    # lark-cli 默认输出 JSON,但带 [WARN] 头,需要剥离
    out = proc.stdout
    json_start = out.find('{')
    if json_start < 0:
        print(f"[ERR] no JSON in output: {out[:500]}", file=sys.stderr)
        sys.exit(1)
    return json.loads(out[json_start:])


def list_records(profile, base_token, table_id):
    """拉一张表的所有记录."""
    result = run_lark([
        'lark-cli', 'base', '+record-list',
        '--profile', profile, '--as', 'bot',
        '--base-token', base_token,
        '--table-id', table_id,
        '--output', 'json'
    ])
    if not result.get('ok'):
        print(f"[ERR] record-list failed: {result}", file=sys.stderr)
        sys.exit(1)
    return result['data']['records']


def normalize_tag(raw):
    """select 字段从飞书拉下来是 list 形式,统一成 string."""
    if isinstance(raw, list) and raw:
        return raw[0]
    if isinstance(raw, str):
        return raw
    return ''


def normalize_link(raw):
    """link 字段是 [{'id':'rec...','text':'...'}] 形式,提取首个 record_id."""
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, dict):
            return first.get('id') or first.get('record_id')
    return None


def short_title(title, max_len=12):
    """从全标题压缩出 12 字以内的短标签."""
    # 去掉"NO.XXX " 前缀和冒号后的副标题
    t = re.sub(r'^NO\.\d+\s*', '', title)
    t = re.split(r'[:：—\-]', t, maxsplit=1)[0].strip()
    if len(t) > max_len:
        t = t[:max_len].rstrip() + '…'
    return t


def infer_tag_palette(tags):
    """根据当前数据里出现的 tag 集合,从 Tokyo Night 调色板里挑色."""
    base_colors = [
        ('#7AA2F7', '雾蓝'),
        ('#7DCFFF', '浅青'),
        ('#9ECE6A', '苔绿'),
        ('#73DACA', '薄荷'),
        ('#E0AF68', '沙金'),
        ('#E5C07B', '米黄'),
        ('#F7768E', '玫粉'),
        ('#BB9AF7', '灰紫'),
        ('#C0CAF5', '月白')
    ]
    palette = {}
    for i, tag in enumerate(sorted(tags)):
        color, _ = base_colors[i % len(base_colors)]
        palette[tag] = {'c': color, 'label': tag}
    return palette


def build(config_path: Path, output_path: Path):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    profile = config['lark_profile']
    base_token = config['bitable_token']
    node_table = config['node_table_id']
    edge_table = config['edge_table_id']

    print(f"[1/4] 拉节点表 {node_table}…")
    raw_nodes = list_records(profile, base_token, node_table)
    print(f"      → {len(raw_nodes)} 条节点")

    print(f"[2/4] 拉边表 {edge_table}…")
    raw_edges = list_records(profile, base_token, edge_table)
    print(f"      → {len(raw_edges)} 条边")

    # 构造 record_id → 节点 id 映射(用数据库内自增序号 1..N)
    rec_to_id = {}
    nodes = []
    for i, r in enumerate(raw_nodes, start=1):
        rec_id = r['record_id']
        f = r['fields']
        title = f.get('标题', '')
        rec_to_id[rec_id] = i
        nodes.append({
            'id': i,
            'num': f.get('ID', f'NO.{i:03d}'),
            'title': title,
            'short': short_title(title),
            'tag': normalize_tag(f.get('知识标签', '')),
            'url': f.get('文档链接', '')
        })

    # 转换边
    edges = []
    for r in raw_edges:
        f = r['fields']
        src_rec = normalize_link(f.get('源文章'))
        tgt_rec = normalize_link(f.get('目标文章'))
        if not src_rec or not tgt_rec:
            continue
        src_id = rec_to_id.get(src_rec)
        tgt_id = rec_to_id.get(tgt_rec)
        if not src_id or not tgt_id:
            continue
        strength_raw = normalize_tag(f.get('关联强度', '弱关联'))
        strength = 'strong' if '强' in strength_raw else 'weak'
        edges.append({
            'from': src_id,
            'to': tgt_id,
            'strength': strength,
            'type': normalize_tag(f.get('关联类型', '')),
            'desc': f.get('关联描述', '')
        })

    print(f"[3/4] 节点 {len(nodes)} · 边 {len(edges)}")

    # 自动按当前 tag 分配 Tokyo Night 配色
    tags_in_use = {n['tag'] for n in nodes if n['tag']}
    palette = infer_tag_palette(tags_in_use)

    # 读模板 + 注入
    template_path = REPO_ROOT / 'templates' / 'graph_template.html'
    template = template_path.read_text(encoding='utf-8')

    nodes_js = json.dumps(nodes, ensure_ascii=False, indent=2)
    edges_js = json.dumps(edges, ensure_ascii=False, indent=2)

    # 替换占位符
    template = template.replace('/*__NODES_JSON__*/[]', nodes_js)
    template = template.replace('/*__EDGES_JSON__*/[]', edges_js)

    # 同时替换 TAG_PALETTE(可选,如果想完全跟数据动态)
    # 这里保留模板里写死的 TAG_PALETTE,因为常见 tag 已经覆盖
    # 如果你的 tag 集合差异大,在此处再生成 palette JS 字面量
    if any(t not in extract_template_tags(template) for t in tags_in_use):
        palette_js = 'const TAG_PALETTE = ' + json.dumps(palette, ensure_ascii=False, indent=2) + ';'
        template = re.sub(
            r'const TAG_PALETTE = \{[^}]+\};',
            palette_js,
            template, count=1, flags=re.DOTALL
        )

    output_path.write_text(template, encoding='utf-8')
    print(f"[4/4] ✅ 写入 {output_path}  ({output_path.stat().st_size/1024:.1f} KB)")
    print(f"     用浏览器打开: file://{output_path.resolve()}")


def extract_template_tags(template):
    """从模板的 TAG_PALETTE 块里抽出已经定义的 tag key."""
    m = re.search(r"const TAG_PALETTE = \{([^}]+)\};", template, re.DOTALL)
    if not m:
        return set()
    return set(re.findall(r"'([^']+)':\s*\{", m.group(1)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=REPO_ROOT / '.config.json',
                        help='配置文件路径(默认 ./.config.json)')
    parser.add_argument('--output', type=Path, default=REPO_ROOT / 'article_graph.html',
                        help='输出 HTML 路径(默认 ./article_graph.html)')
    args = parser.parse_args()

    if not args.config.exists():
        print(f"[ERR] 找不到配置文件: {args.config}", file=sys.stderr)
        print(f"      请参考 SKILL.md 创建 .config.json", file=sys.stderr)
        sys.exit(1)

    build(args.config, args.output)


if __name__ == '__main__':
    main()
