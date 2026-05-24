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
    """拉一张表的所有记录(自动分页).

    lark-cli record-list --format json 返回的是并行数组结构:
      data.data: 二维数组 N行 × M列 (实际值)
      data.fields: 列名数组 (长度 M)
      data.record_id_list: 行 record_id 数组 (长度 N)
    本函数把它们 zip 成 [{record_id, fields: {name: value}}, ...] 格式.
    """
    all_records = []
    offset = 0
    while True:
        result = run_lark([
            'lark-cli', 'base', '+record-list',
            '--profile', profile, '--as', 'bot',
            '--base-token', base_token,
            '--table-id', table_id,
            '--format', 'json',
            '--limit', '200',
            '--offset', str(offset)
        ])
        if not result.get('ok'):
            print(f"[ERR] record-list failed: {result}", file=sys.stderr)
            sys.exit(1)
        data = result.get('data') or {}
        rows = data.get('data') or []
        fields = data.get('fields') or []
        rec_ids = data.get('record_id_list') or []

        # zip 成字典列表
        for rec_id, row in zip(rec_ids, rows):
            row_dict = {name: value for name, value in zip(fields, row)}
            all_records.append({'record_id': rec_id, 'fields': row_dict})

        # 翻页判断
        if len(rows) < 200 or not data.get('has_more'):
            break
        offset += 200
    return all_records


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


# 模板里默认 TAG_PALETTE 已经覆盖的 tag(和 graph_template.html 同步).
# 在这 9 个集合里的 tag 不用注入 EXTRA_PALETTE,直接走默认调色.
DEFAULT_PALETTE_KEYS = {
    'RAG', 'GraphRAG', 'Agent', 'Agent Memory',
    'Agent工程', 'Agent框架', 'Agent 设计',
    'Claude Code', 'Transformer'
}

# Tokyo Night 调色板,给未覆盖的 tag 按顺序分配
EXTRA_COLOR_ROTATION = [
    '#7AA2F7', '#7DCFFF', '#9ECE6A', '#73DACA',
    '#E0AF68', '#E5C07B', '#F7768E', '#BB9AF7', '#C0CAF5'
]


def build_extra_palette(tags):
    """为不在默认 TAG_PALETTE 里的 tag 生成补充调色板.

    返回 {tag: {c, label}} 字典,模板里的 EXTRA_PALETTE 占位符注入此值.
    模板的 getPalette() 会按 TAG_PALETTE → EXTRA_PALETTE → 灰色兜底的顺序取色,
    所以这里只需要补充未覆盖的 tag.
    """
    extras = sorted(t for t in tags if t and t not in DEFAULT_PALETTE_KEYS)
    palette = {}
    for i, tag in enumerate(extras):
        palette[tag] = {
            'c': EXTRA_COLOR_ROTATION[i % len(EXTRA_COLOR_ROTATION)],
            'label': tag
        }
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

    # 给未在默认 TAG_PALETTE 覆盖的 tag 生成补充调色板
    tags_in_use = {n['tag'] for n in nodes if n['tag']}
    extra_palette = build_extra_palette(tags_in_use)
    extra_tags = sorted(extra_palette.keys())
    if extra_tags:
        print(f"      [+] 补充调色板覆盖 {len(extra_tags)} 个自定义 tag: {extra_tags}")
    empty_tag_nodes = [n for n in nodes if not n['tag']]
    if empty_tag_nodes:
        print(f"      [!] {len(empty_tag_nodes)} 个节点的 tag 为空, 将用灰色'其他'显示")

    # 读模板 + 注入
    template_path = REPO_ROOT / 'templates' / 'graph_template.html'
    template = template_path.read_text(encoding='utf-8')

    nodes_js = json.dumps(nodes, ensure_ascii=False, indent=2)
    edges_js = json.dumps(edges, ensure_ascii=False, indent=2)
    extra_js = json.dumps(extra_palette, ensure_ascii=False, indent=2)

    # 全部走占位符替换,不再用脆弱的正则解析模板
    template = template.replace('/*__NODES_JSON__*/[]', nodes_js)
    template = template.replace('/*__EDGES_JSON__*/[]', edges_js)
    template = template.replace('/*__EXTRA_PALETTE_JSON__*/{}', extra_js)

    output_path.write_text(template, encoding='utf-8')
    print(f"[4/4] ✅ 写入 {output_path}  ({output_path.stat().st_size/1024:.1f} KB)")
    print(f"     用浏览器打开: file://{output_path.resolve()}")


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
