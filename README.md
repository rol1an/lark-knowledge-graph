# lark-knowledge-graph

> 把微信文章变成「**节点 + 边**」的飞书知识图谱。

一个 Claude Skill，做三件事：

1. 把微信公众号文章去广告、按知识结构重构后**导入飞书 wiki**
2. 和已有文章语义匹配后**在 Bitable 边表里写入关联边**，节点表和边表自动形成图数据库
3. 拉表 → 生成一份 **Obsidian Graph View 风格的交互式 HTML 图谱**，节点像海面浮沉，hover 才显现连线

---

## 为什么写这个

我每周往飞书知识库里塞几篇微信文章。文章之间其实有大量的关联——
RAG 知识体系 ↔ RAG 评估 ↔ GraphRAG，Claude Code 架构 ↔ Skills 机制 ↔ 大代码库实践——
但散落在飞书文档里，**关联只能靠记**。

参考 codegraph 的设计：与其每次现搜，不如**预构建一张图**。
Bitable 的双向 link 字段天然就是图数据库——节点是文章，边是关联，存进去就能查
"这篇文章被哪些文章引用"、"和哪些文章同主题"。

然后用 Cytoscape + fcose 把这张图画出来，**强相关的文章自动靠拢，无关的自然分散**，
肉眼一看就知道哪些知识是一个簇、哪些是孤岛。

```
微信文章 ──► 飞书 wiki 节点 ──► 关联推断 ──► Bitable 边表
                                                 │
                                                 ▼
                                       自包含 HTML 知识图谱
```

---

## ✨ 特性

| 维度 | 做法 |
|---|---|
| **抓取** | curl + 浏览器 UA 绕过微信 reCAPTCHA；保留 `<strong>`/`<b>`/彩色文本 等原文强调标记 |
| **重构** | LLM 提炼核心观点 → 章节重组 → 加 callout 总纲 → 论文图保留 LaTeX + 原图 |
| **写入** | 飞书 wiki 节点 + DocxXML，**色彩约束 4 种内**，emoji 语义化辅助扫读 |
| **关联** | 一次 `record-list` 拉全表 metadata + 本地匹配，**比多轮 LLM keyword 搜索省 4× token** |
| **双向引用** | 强关联文章会在彼此末尾互相 append `<callout>` 链接，知识库随时间自然形成网状 |
| **图数据库** | Bitable 双向 link 字段，每节点直接看到出边/入边，无需 SQL 也能 graph traversal |
| **可视化** | Cytoscape.js + fcose，按边强度施加不同弹簧力，相关节点自动靠拢 |
| **离线** | 所有 JS 库内联（700KB），单 HTML 文件双击即可打开 |

---

## 🎬 演示

打开生成的 `article_graph.html` 后：

```
┌─────────────────────────────────────────────────────────────────────┐
│ 📚 知识库文章关联图谱                                                 │
├──────────────────────────────────────────┬──────────────────────────┤
│                                          │  16 articles · 25 links  │
│                ●                         │  11 strong · 14 weak     │
│             ╱     ╲                      ├──────────────────────────┤
│           ●         ●                    │  主题集群                 │
│          /  \      / \                   │  ● RAG          3        │
│         ●    ●━━━━●   ●                  │  ● GraphRAG     1        │
│         |   /      \  |                  │  ● Agent        2        │
│         ● ●          ●●                  │  ● Memory       1        │
│         (节点轻微浮沉,边几乎隐入背景)       │  ● Agent 工程   3        │
│                                          │  ● Claude Code  3        │
│                                          │  ...                     │
│  ┌─ hover 任一节点 ─┐                     ├──────────────────────────┤
│  │  邻接节点保留     │                    │  📄 节点详情              │
│  │  其余 fade       │                    │  (单击节点查看)           │
│  │  连线变金亮起    │                    │                          │
│  └──────────────────┘                    └──────────────────────────┘
```

- **🌊 浮沉动画**：fcose 布局完成后，每节点叠加独立相位的 sin 偏移（竖向 3.5-5.5px、周期 7-11s）
- **🔦 探照灯交互**：hover 节点 → 一阶邻居高亮、其余 fade 到 opacity 0.18
- **🏷️ Tag chips 筛选**：点击侧栏 tag chip → 仅显示该 tag 节点
- **🖱️ 双击跳转**：双击任意节点直接打开飞书文档
- **📌 单击锁定**：单击 = 锁定高亮 + 侧栏详情；ESC 清空

---

## 🚀 快速开始

### 前置

- macOS / Linux
- Python 3.9+
- [`lark-cli`](https://github.com/larksuite/lark-cli)（飞书命令行工具，需要先 `lark-cli auth login` 配好 profile）
- 飞书 Bitable 一个，建好两张表（节点表 + 边表）

### 1. 建表

```bash
# 跟着 references/bitable-schema.md 里的命令一次建好
# 节点表"文章索引" + 边表"文章关联图"(双向 link 字段)
```

### 2. 配置

```bash
cp .config.example.json .config.json
# 编辑 .config.json,填入你的 profile / space_id / base_token / 两个 table_id
```

### 3. 在 Claude Code 中使用

把 SKILL.md 软链到 Claude Code 的 skills 目录（或用 `npx skills install`）：

```bash
mkdir -p ~/.claude/skills
ln -s "$(pwd)" ~/.claude/skills/lark-knowledge-graph
```

然后对 Claude 说：

```
@lark-knowledge-graph 帮我把 <wechat-url> 导入飞书知识库
```

Claude 会按 SKILL.md 里的 7 步流程：抓取 → 清洗 → 重构 → 写 wiki → 写节点表 → 关联推断 → 写边表。

### 4. 生成图谱

```bash
python3 scripts/build_graph.py
# 输出: ./article_graph.html
# 在浏览器打开: file:///$(pwd)/article_graph.html
```

每次有新文章导入后跑一次脚本，HTML 就更新。

---

## 📦 仓库结构

```
lark-knowledge-graph/
├── README.md                       # 你正在看
├── SKILL.md                        # Claude Skill 主文件(L2,description 命中后加载)
├── .config.example.json            # 配置模板
├── references/                     # L3 懒加载:具体规格
│   ├── bitable-schema.md          # 飞书 Bitable 建表速查
│   ├── aesthetic-spec.md          # 文档审美规范(色彩/emoji/表格)
│   └── graph-design-spec.md       # 图谱可视化设计规格(Tokyo Night + fcose)
├── scripts/                        # L3 懒加载:可执行脚本
│   ├── fetch_article.py           # 微信文章抓取 + 结构化提取
│   └── build_graph.py             # 拉 Bitable + 注入模板 → 输出 HTML
└── templates/
    └── graph_template.html         # 图谱 HTML 模板(Cytoscape + fcose 内联)
```

---

## 🧭 设计哲学

### 1. 节点表 + 边表 = 图数据库

借鉴 [codegraph](https://github.com/iVis-at-Bilkent/cytoscape.js-fcose) 的核心思想：**与其每次现搜，不如预构建一张图**。

Bitable 的双向 link 字段让你不用任何 SQL 就能做图遍历：
- 在某篇文章的行，点击"出边"列 → 所有它指向的相关文章
- 点击"入边"列 → 所有指向它的文章
- 数据是结构化的，可以用 lookup/rollup 做衍生分析（"被引用最多的文章 TOP10"等）

### 2. 用 `record-list` 不用 `record-search`

被这个坑过两次：
- ❌ `record-search` 强制要 `keyword` + `search_fields` 两个必填参数，不传就报 `800010701`
- ❌ `record-search` 命中 `OpenAPISearchRecord` 配额，**单 session 连调 4 次就限流**
- ✅ `record-list` 配额独立，**一次全表拉 ≤ 500 token**，本地匹配

这就是把 Bitable 当作"预构建的关键词索引"——所有筛选/排序/打分在客户端完成，API 只负责吐数据。

### 3. Obsidian Graph View 风格的可视化

| 原则 | 做法 |
|---|---|
| **默认极淡** | 边 alpha 0.05，箭头隐藏，强弱不分 |
| **hover 才显形** | 一阶邻居高亮 + 邻接边变金，结构关系按需"探照灯" |
| **按强度施力** | fcose `idealEdgeLength`：强边 70px、弱边 180px → 强相关节点自动靠拢 |
| **海浪浮沉** | 每节点独立相位 sin 偏移，10 节点 ≠ 100 节点的整齐齐排列感 |
| **离线运行** | 4 个依赖 700KB 全部内联，单 HTML 双击就能用 |

### 4. progressive disclosure 三层加载

遵循 [Anthropic Claude Skills](https://docs.anthropic.com/claude/docs/claude-skills) 协议：

- **L1 frontmatter**（≤ 200 字）：始终扫描的 description，决定何时加载
- **L2 SKILL.md 正文**：description 命中后加载，写完整流程（300-500 行）
- **L3 references/scripts/**：L2 显式引用 `[reference](references/xxx.md)` 才加载

主流程不臃肿，细节按需展开。

---

## 🛠️ 常见问题

**Q: 飞书 API 报 `91403`？**
A: Bitable 写操作必须 `--as bot`，user 身份没权限。

**Q: 飞书 API 报 `800004135 OpenAPISearchRecord limited`？**
A: `record-search` 的 QPS 限流。换 `record-list`。

**Q: 微信图片下载是 0 bytes？**
A: `data-src` 提取时 URL 被截断了。必须保留 `?wx_fmt=png&from=appmsg` 等完整 query params，且 `&amp;` decode 成 `&`。

**Q: 浏览器看不到图谱（白屏）？**
A: 大概率是 CDN 加载失败（国内代理）。本仓库的模板已经把所有库内联进 HTML，理论上不会发生。如果还有问题打开 DevTools Console 看第一行错误。

**Q: 节点位置每次刷新都不一样？**
A: fcose 用 `randomize: false` + spectral 初始化，应该是稳定的。如果还想要完全可复现，可以保存 layout 后的 position 到 `.config.json` 里。

---

## 🎨 致谢

- **图库**：[Cytoscape.js](https://js.cytoscape.org/) + [fcose layout](https://github.com/iVis-at-Bilkent/cytoscape.js-fcose)
- **设计灵感**：[Obsidian Graph View](https://obsidian.md/) · [Andy Matuschak 笔记网](https://notes.andymatuschak.org/) · Apple HIG Dark Mode
- **配色**：[Tokyo Night](https://github.com/folke/tokyonight.nvim) · [One Dark](https://github.com/atom/one-dark-syntax)
- **Skill 协议**：[Anthropic Claude Skills](https://docs.anthropic.com/claude/docs/claude-skills)
- **思想源头**：[forbidden-fruit / yanyu-import](https://github.com/rol1an/forbidden-fruit)（前作，纯导入场景；本仓库在它的基础上加了图数据库 + 可视化）

---

## 📄 License

MIT
