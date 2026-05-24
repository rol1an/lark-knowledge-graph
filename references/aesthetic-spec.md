# 文档审美规范

重构文章写入飞书 wiki 时,**视觉一致性 >> 信息密度**。下面是 6 个硬性约束。

## 1. 原文强调样式必须保留

- 抓取 HTML 后用 `scripts/fetch_article.py` 自动提取 `<strong>`/`<b>`/`style="color:..."` 列表
- 原文加粗 → 飞书 `<b>`
- 原文彩色短语 → 飞书 `<span text-color="...">`
- 原文引用块 → `<blockquote>` 或 `<callout>`

## 2. 我们添加的标签用深蓝色不加粗

- "核心观点"、"本节要点"、"面试答法"、"加分点"、"来源"、"作者"、"复习元数据" 等
- 一律用 `<span text-color="blue">` **深蓝色字体**
- **不要 `<b>` 加粗** —— 只有原文作者自己用加粗的内容才保留 `<b>`

## 3. 色彩约束:每篇最多 4 色

| 用途 | 色系 |
|---|---|
| 🔵 来源/元数据/标签强调 | light-blue / blue |
| 🟡 核心观点/重要提示 | light-yellow / yellow |
| ⚪ 章节要点总纲 | light-gray / gray |
| 🟢 末尾复习元数据 | light-green / green |

## 4. Emoji 规范

- 每个列表项前用语义化 emoji 辅助扫读: 🔄 流程 / 🧠 记忆 / 🔧 工具 / 🛡️ 安全 / 📊 对比
- 章节标题用 emoji 前缀: `## 🧠 记忆机制`
- 同一章节内 emoji 风格统一,不同章节间区分
- 表格 header **不加 emoji**

## 5. 表格使用约束

- 表格只放**结构对齐的短文本**(每单元格 2-3 行内)
- 长段落内容(面试答法、实战经验、原理解释)**禁止塞表格** —— 改用表格下方的独立 callout 承载
- 强行塞会出现"同行其他列空白、该列堆一大块"的丑陋排版

## 6. 论文类文章保留所有公式和图表

- 行内公式: `<equation>LaTeX</equation>`
- 独立公式块: `<equation-block>LaTeX</equation-block>`
- 图片: `<img href="完整URL" caption="图注或语义描述"/>` —— 飞书 API 会自动拉取上传
- 图片 URL 必须**完整 query params**(`?wx_fmt=png&from=appmsg`),`&amp;` decode 成 `&`,**不能截断**
- 实验图/消融图下方必须有解读段落(规律、拐点、与 baseline 差距)

## XML 模板

```xml
<title>重构后的标题(准确反映核心知识点,而非营销标题)</title>

<callout emoji="📖" background-color="light-blue" border-color="blue">
  <p><span text-color="blue">来源</span>:公众号名 | <span text-color="blue">作者</span>:xxx | <span text-color="blue">日期</span>:yyyy-mm-dd</p>
  <p><span text-color="blue">原文链接</span>:<a href="原文URL">原文</a></p>
</callout>

<callout emoji="🎯" background-color="light-yellow" border-color="yellow">
  <p><span text-color="blue">核心观点</span></p>
  <ul>
    <li>💡 <b>观点1</b>:一句话总结</li>
    <li>💡 <b>观点2</b>:一句话总结</li>
  </ul>
</callout>

<hr/>

<h1>🔧 章节标题</h1>
<callout emoji="📌" background-color="light-gray" border-color="gray">
  <p><span text-color="blue">本节要点</span>:一句话概括</p>
</callout>
<p>重构后的正文内容...</p>

<hr/>

<callout emoji="🔗" background-color="light-blue" border-color="blue">
  <p><span text-color="blue">相关知识</span></p>
  <ul>
    <li>📄 <a href="飞书URL">相关文章标题</a>:一句话说明关联点</li>
  </ul>
</callout>

<callout emoji="🧠" background-color="light-green" border-color="green">
  <p><span text-color="blue">复习元数据</span></p>
  <ul>
    <li>📅 <span text-color="blue">导入日期</span>:{TODAY}</li>
    <li>🏷️ <span text-color="blue">知识标签</span>:tag1, tag2</li>
    <li>🔄 <span text-color="blue">下次复习</span>:{TODAY+1d}</li>
  </ul>
</callout>
```

## 论文类文章的额外细则

- **多方案对比**(如 RAG vs RL vs 本文方案):各方案**分段单独分析**局限性,不要混在一起笼统描述
- **核心设计点**后加 "为什么这样设计能解决 X" callout,用直觉语言解释技术动机(例:为什么后验概率能解决信用分配难题)
- **实验图必须附解读段落**,说明图表展示了什么规律(简单任务 vs 复杂任务的差异、关键拐点、与 baseline 的差距)
