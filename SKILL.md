---
name: lark-knowledge-graph
description: 把微信公众号文章去广告、按知识结构重构后导入飞书知识库，并在 Bitable 里维护文章与文章之间的关联边，最后生成一份可交互的「节点云图」HTML 可视化（Cytoscape.js + fcose，无 CDN 依赖、离线可用、节点呼吸式浮沉动画）。当用户说「导入文章到飞书」「重构文章导入」「生成知识图谱」「画一下我知识库的关联图」「文章关系网络可视化」时使用。
---

# lark-knowledge-graph

把微信文章变成「**节点 + 边**」的知识图谱：

1. **导入阶段**：抓取微信公众号文章 → 去营销内容 → 按知识结构重写 → 写入飞书 wiki 作为新节点
2. **关联阶段**：和已有文章语义匹配 → 在 Bitable 边表里写入关联边（带强度/类型/描述）→ 双向回链
3. **可视化阶段**：拉 Bitable 节点 + 边表 → 渲染成交互式 HTML 图谱（Obsidian Graph View 风格）

## 前置准备

需要在飞书一次性建好两张表（首次使用前手动建，之后自动用）：

### 节点表「文章索引」

| 字段 | 类型 | 说明 |
|---|---|---|
| 标题 | text | 重构后的标题 |
| 原文链接 | url | 微信原文 URL |
| 文档链接 | url | 飞书 wiki 节点 URL |
| 文档Token | text | docx 的 obj_token（写边时引用）|
| 知识标签 | select | 主题分类（RAG / Agent / Claude Code 等）|
| 导入日期 | datetime | `yyyy/MM/dd` |
| 复习状态 | select | 未复习 / 已复习 |
| 复习轮次 | number | 0 起步 |
| 下次复习 | datetime | 导入日 +1 天 |

### 边表「文章关联图」

| 字段 | 类型 | 说明 |
|---|---|---|
| 关联关系 | text (primary) | 一句话标题，如 "A → B" |
| 源文章 | link → 文章索引 (bidirectional) | 反向字段建议叫"出边" |
| 目标文章 | link → 文章索引 (bidirectional) | 反向字段建议叫"入边" |
| 关联强度 | select | 强关联 / 弱关联 |
| 关联类型 | select | 同主题 / 对比扩展 / 前置概念 / 章节呼应 |
| 关联描述 | text | 一句话说明从源到目标的关联点 |
| 建立日期 | datetime | `YYYY-MM-DD HH:mm:ss` |

> 建表命令样例见 [references/bitable-schema.md](references/bitable-schema.md)。

## 配置（首次使用）

在仓库根目录创建 `.config.json`：

```json
{
  "lark_profile": "your_tenant",
  "wiki_space_id": "<your_space_id>",
  "bitable_token": "<your_base_token>",
  "node_table_id": "<tblXXX_文章索引>",
  "edge_table_id": "<tblXXX_文章关联图>"
}
```

`lark_profile` 是 `lark-cli auth login` 时创建的 profile 名。

## 执行流程

### Step 1 — 抓取微信文章

先 WebFetch；如返回 reCAPTCHA 错误，fallback 用 curl 加浏览器 UA：

```bash
curl -sL -o /tmp/wechat.html \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36' \
  -H 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8' \
  -H 'Accept-Language: zh-CN,zh;q=0.9' \
  '<wechat-url>'
```

提取字段（参考 [scripts/fetch_article.py](scripts/fetch_article.py)）：
- 标题 `var msg_title`
- 作者 `og:article:author`
- 发布时间 `var ct`（Unix 时间戳）
- 正文 `id="js_content"`
- 图片 `<img data-src="...">`（**URL 必须含 `?wx_fmt=png&from=appmsg` 等完整参数**，截断后下载会 0 bytes）
- 原文强调标记 `<strong>` `<b>` `style="color:..."`

### Step 2 — 清洗

删除关注引导、二维码、付费课程、社群引流、互推、营销话术。保留实战经验、面试答法、踩坑总结。

### Step 3 — 重构

目标：产出**易于复习的知识文档**，不是原文搬运。

1. 提炼 1–3 个核心观点
2. 梳理知识脉络，按「概念 → 原理 → 应用 → 总结」重组
3. Paraphrase 重写，保留术语、数据、案例
4. 每节加 callout 总纲（一句话本节要点）
5. 论文类文章**必须保留所有公式和图表**：`<equation-block>LaTeX</equation-block>` + `<img href="完整URL"/>`
6. 原文强调标记原封不动还原（作者的 `<b>` 保留为 `<b>`；我们加的标签用 `<span text-color="blue">` 不加粗）

详细审美规范见 [references/aesthetic-spec.md](references/aesthetic-spec.md)。

### Step 4 — 写飞书 wiki

```bash
# 1. 建节点（拿到 obj_token + node_url）
lark-cli wiki +node-create --profile <profile> --space-id <space_id> --title "<重构标题>"

# 2. 写文档内容（用 DocxXML，先不写「相关知识」callout，留到 Step 6 用 append）
lark-cli docs +update --profile <profile> --api-version v2 \
  --doc <obj_token> --command overwrite --content @./article_docx.xml
```

**⚠️ `wiki +node-create` 成功即创建节点，永不重跑**——重跑会创建同名空节点。

### Step 5 — 写「文章索引」节点表

```bash
lark-cli base +record-upsert --profile <profile> --as bot \
  --base-token <base_token> --table-id <node_table_id> \
  --json '{"标题":"...","原文链接":"...","文档链接":"...","文档Token":"...",
          "知识标签":"...","导入日期":"2026/05/24","复习状态":"未复习",
          "复习轮次":0,"下次复习":"2026/05/25"}'
```

**关键坑点**：
- `--json` 是平铺 `Map<FieldName, CellValue>`，**不是** `{"records":[{"fields":...}]}`
- `知识标签` / `复习状态` 是单值 select，传字符串不传数组
- 日期格式 `yyyy/MM/dd`，写边时的 datetime 是 `YYYY-MM-DD HH:mm:ss`
- 写 Bitable 必须 `--as bot`，user 身份常因权限不足报 91403

### Step 6 — 关联推断（一次拉表 + 本地匹配）

**这一层借鉴 codegraph 的预构建索引思想，避免多轮 LLM 搜索调用。**

#### 6.1 一次拉全表 metadata

```bash
lark-cli base +record-list --profile <profile> --as bot \
  --base-token <base_token> --table-id <node_table_id>
```

⚠️ **必须用 `record-list` 不能用 `record-search`**：
- `record-search` 强制要 `keyword` + `search_fields`，不传就报 800010701
- `record-search` 还命中 `OpenAPISearchRecord` 的 QPS 限流（连调 4 次就限）
- `record-list` 配额独立，一次返回所有节点的全部字段，≤ 500 token

#### 6.2 本地匹配（在主 agent 内完成）

主 agent 已知当前文章的核心观点、标签、章节，对每条已有文章打分：

| 信号 | 权重 | 例子 |
|---|---|---|
| 标签精确匹配 | 高 | `RAG` ↔ `RAG` |
| 标签同语义簇 | 中 | `Agent工程` ↔ `Claude Code` |
| 标题术语重叠 | 中 | "harness" / "CLAUDE.md" / "skill" 共现 |
| 主题相关但无重叠 | 低 | 只是同领域 |

判断规则：
- **强关联**：标签精确匹配 + 术语重叠 ≥ 1 → 双向引用 + 段落级关联
- **弱关联**：标签同语义簇 或 术语重叠 ≥ 1 → 列入"相关知识"
- **不关联**：不写

#### 6.3 当前文档末尾插入「相关知识」callout

```xml
<callout emoji="🔗" background-color="light-blue" border-color="blue">
  <p><span text-color="blue">相关知识</span></p>
  <ul>
    <li>📄 <a href="飞书URL">相关文章标题</a>：一句话说明关联点</li>
  </ul>
</callout>
```

#### 6.4 强关联文章末尾追加回链（双向）

```bash
lark-cli docs +update --profile <profile> --api-version v2 \
  --doc <已有文章obj_token> --command append --content @./xref.xml
```

#### 6.5 写「文章关联图」边表

```bash
lark-cli base +record-batch-create --profile <profile> --as bot \
  --base-token <base_token> --table-id <edge_table_id> \
  --json @./edges_batch.json
```

`edges_batch.json` 结构：
```json
{
  "fields": ["关联关系","源文章","目标文章","关联强度","关联类型","关联描述","建立日期"],
  "rows": [
    [
      "新文章 → 已有文章",
      [{"id":"<新文章record_id>"}],
      [{"id":"<已有文章record_id>"}],
      "强关联",
      "章节呼应",
      "一句话关联点",
      "2026-05-24 18:00:00"
    ]
  ]
}
```

link 字段值是 `[{"id":"<record_id>"}]` 对象数组，不是字符串。

### Step 7 — 生成图谱可视化（可选）

```bash
python3 scripts/build_graph.py
```

脚本会：
1. `record-list` 拉「文章索引」全表 → 节点
2. `record-list` 拉「文章关联图」全表 → 边
3. 按 tag 分配 Tokyo Night 配色
4. 注入 [templates/graph_template.html](templates/graph_template.html) 输出 `article_graph.html`

输出文件是**完全自包含**的单 HTML（Cytoscape.js + fcose + layout-base + cose-base 全部内联，~700KB），离线双击即可打开。

## 设计要点

### 节点表 + 边表 = 知识图谱预构建索引

借鉴 codegraph：把 Bitable 当作**预构建的图数据库**。节点是文章，边是关联，链接字段双向绑定让你在节点行直接看到出边/入边。`record-list` 一次拉表 ≤ 500 token，远好于多轮 keyword search。

### Obsidian Graph View 风格的可视化

- **极淡默认边**（`rgba(148,163,184,0.05)`）：默认态不承担"强/弱"区分，结构关系靠 hover 才显形
- **fcose 按边强度施加不同弹簧力**：强边 `idealEdgeLength: 70`、弱边 `180`；强边的拉力 `0.7`、弱边 `0.25` → 相关节点自动靠拢，无关节点自然分散
- **节点呼吸式浮沉**：fcose 布局完成后 `requestAnimationFrame` 给每节点叠加独立相位的 sin 偏移（竖向振幅 3.5–5.5px、横向 1.5–2.5px、周期 7–11s），像海面浮力
- **hover/click 双层级**：hover = 临时探照灯（一阶邻居高亮、其余 fade）；click = 锁定 + 侧栏详情；ESC 清空
- **CDN 三级回退 + 全量内联**：jsdelivr → BootCDN → unpkg，最终全部 inline 进 HTML，国内离线也能跑

## 常见问题

**Q: 飞书 API 报 `800004135 OpenAPISearchRecord limited`?**
A: 短期 QPS 限流。`record-search` 在同 session 内不要超过 2 次。需要全表扫描时用 `record-list`。

**Q: 飞书 API 报 `800010701 Request validation failed`?**
A: 你用 `record-search` 但没传 keyword/search_fields。换 `record-list`。

**Q: 写记录报 `91403`?**
A: Bitable 写操作必须 `--as bot`，user 身份没权限。

**Q: 微信图片下载是 0 bytes?**
A: `data-src` 提取时 URL 被截断了。必须保留 `?wx_fmt=png&from=appmsg` 等完整 query params，且 HTML 实体 `&amp;` 要 decode 成 `&`。

## 子文档

- [references/aesthetic-spec.md](references/aesthetic-spec.md) — 重构后文档的视觉规范（color/emoji/表格用法）
- [references/bitable-schema.md](references/bitable-schema.md) — 飞书 Bitable 建表的字段 JSON
- [references/graph-design-spec.md](references/graph-design-spec.md) — 图谱可视化的设计规格（Tokyo Night 配色 + fcose 调参）
- [scripts/fetch_article.py](scripts/fetch_article.py) — 微信 HTML 解析
- [scripts/build_graph.py](scripts/build_graph.py) — 拉表 + 注入模板
- [templates/graph_template.html](templates/graph_template.html) — 图谱 HTML 模板（占位符 `/*__NODES_JSON__*/[]`、`/*__EDGES_JSON__*/[]`、`/*__EXTRA_PALETTE_JSON__*/{}` 由 build_graph.py 替换）
