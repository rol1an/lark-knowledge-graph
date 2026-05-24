# Bitable 建表速查

首次使用前需要在飞书建好两张表。下面给出 `lark-cli` 一次建好的 JSON。

## 1. 「文章索引」节点表

```bash
lark-cli base +table-create --profile <profile> --as bot \
  --base-token <base_token> \
  --name "文章索引" \
  --fields '[
    {"name": "标题", "type": "text"},
    {"name": "原文链接", "type": "url"},
    {"name": "文档链接", "type": "url"},
    {"name": "文档Token", "type": "text"},
    {"name": "知识标签", "type": "select", "multiple": false,
     "options": [
       {"name": "RAG", "hue": "Blue"},
       {"name": "GraphRAG", "hue": "Wathet"},
       {"name": "Agent", "hue": "Green"},
       {"name": "Agent Memory", "hue": "Turquoise"},
       {"name": "Agent工程", "hue": "Orange"},
       {"name": "Agent框架", "hue": "Yellow"},
       {"name": "Agent 设计", "hue": "Carmine"},
       {"name": "Claude Code", "hue": "Purple"},
       {"name": "Transformer", "hue": "Gray"}
     ]},
    {"name": "导入日期", "type": "datetime"},
    {"name": "复习状态", "type": "select", "multiple": false,
     "options": [
       {"name": "未复习", "hue": "Yellow"},
       {"name": "已复习", "hue": "Green"}
     ]},
    {"name": "复习轮次", "type": "number"},
    {"name": "下次复习", "type": "datetime"}
  ]'
```

返回的 `id` 字段就是 `node_table_id`,写进 `.config.json`。

## 2. 「文章关联图」边表

> 必须先建好节点表才能建边表(link 字段需要引用节点表 ID)。

```bash
# 先创建空表 + primary 字段
lark-cli base +table-create --profile <profile> --as bot \
  --base-token <base_token> \
  --name "文章关联图" \
  --fields '[{"name":"关联关系","type":"text"}]'
```

记下返回的 `id` (`tblXXX`),然后加 link 字段(必须分两步,因为 link 字段创建时要传 link_table):

```bash
# 源文章 link (bidirectional, 反向字段叫"出边")
lark-cli base +field-create --profile <profile> --as bot \
  --base-token <base_token> --table-id <edge_table_id> \
  --json '{
    "name": "源文章",
    "type": "link",
    "link_table": "<node_table_id>",
    "bidirectional": true,
    "bidirectional_link_field_name": "出边"
  }'

# 目标文章 link (bidirectional, 反向字段叫"入边")
lark-cli base +field-create --profile <profile> --as bot \
  --base-token <base_token> --table-id <edge_table_id> \
  --json '{
    "name": "目标文章",
    "type": "link",
    "link_table": "<node_table_id>",
    "bidirectional": true,
    "bidirectional_link_field_name": "入边"
  }'

# 关联强度 select
lark-cli base +field-create --profile <profile> --as bot \
  --base-token <base_token> --table-id <edge_table_id> \
  --json '{
    "name": "关联强度", "type": "select", "multiple": false,
    "options": [
      {"name": "强关联", "hue": "Red", "lightness": "Light"},
      {"name": "弱关联", "hue": "Yellow", "lightness": "Light"}
    ]
  }'

# 关联类型 select
lark-cli base +field-create --profile <profile> --as bot \
  --base-token <base_token> --table-id <edge_table_id> \
  --json '{
    "name": "关联类型", "type": "select", "multiple": false,
    "options": [
      {"name": "同主题", "hue": "Green", "lightness": "Light"},
      {"name": "对比扩展", "hue": "Purple", "lightness": "Light"},
      {"name": "前置概念", "hue": "Wathet", "lightness": "Light"},
      {"name": "章节呼应", "hue": "Turquoise", "lightness": "Light"}
    ]
  }'

# 关联描述 + 建立日期
lark-cli base +field-create --profile <profile> --as bot \
  --base-token <base_token> --table-id <edge_table_id> \
  --json '{"name":"关联描述","type":"text"}'

lark-cli base +field-create --profile <profile> --as bot \
  --base-token <base_token> --table-id <edge_table_id> \
  --json '{"name":"建立日期","type":"datetime"}'
```

## 3. 双向 link 字段做了什么

设置 `bidirectional: true` 后:
- 在「文章索引」表里会自动多出"出边""入边"两个反向 link 字段
- 在某篇文章的行,点击"出边"列就能看到所有它作为源的关联边
- 点击"入边"列就能看到所有指向它的边
- 这就形成了真正的图数据库结构,不用任何 SQL 也能做 graph traversal

## 4. 可用 hue 值

`Red` / `Orange` / `Yellow` / `Lime` / `Green` / `Turquoise` / `Wathet` / `Blue` / `Carmine` / `Purple` / `Gray`

> ⚠️ 不要传 `Indigo`,飞书 API 不识别,会报 invalid_request。

## 5. CellValue 格式速查

| 类型 | 写入 |
|---|---|
| text | `"some string"` |
| select (单值) | `"强关联"` (字符串,**非数组**) |
| select (多值) | `["tag1", "tag2"]` |
| number | `0` |
| datetime | `"2026-05-24 18:00:00"` 或 `"2026/05/24"` |
| url | `"https://..."` |
| link | `[{"id": "rec..."}]` (对象数组,**不是字符串**) |
| user | `[{"id": "ou_..."}]` |
