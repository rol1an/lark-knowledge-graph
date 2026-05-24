# 图谱可视化设计规格

可视化的设计哲学:**节点像在海中浮沉,连线像水波,只有探照灯下才显形**。

参考: Obsidian Graph View + Andy Matuschak 笔记网 + Apple HIG 深色规范。

## 1. 图库选型

**Cytoscape.js 3.30 + fcose 2.2** —— 不用 vis-network、d3、Sigma。

| 维度 | 为什么选 Cytoscape |
|---|---|
| Styling API | 比 vis-network 灵活,支持 `round-rectangle`、独立 border、text-outline |
| 布局稳定性 | fcose 用 spectral 初始化,2× 于 cose 的速度,小图不会"乱跳" |
| 视觉质量 | 圆形节点 + 抗锯齿曲线 + text-outline 标签描边 |
| 离线运行 | 4 个依赖(cytoscape + layout-base + cose-base + fcose)总共 ~700KB,全部 inline 到 HTML |

依赖顺序(UMD 依赖链):
```
cytoscape → layout-base → cose-base → cytoscape-fcose
```

## 2. 配色规格

来自 **Tokyo Night + One Dark** 调色板(工程师默认安全色,低饱和度 ~45%、统一 lightness ~65%)。

### 背景

| 用途 | 色值 |
|---|---|
| 主背景 | `#0e1116` (中性深色,去蓝调) |
| 侧栏 | `#161a21` |
| 分隔线 | `#262b33` |

### 节点 tag 配色

| 序号 | 色值 | 名称 |
|---|---|---|
| 1 | `#7AA2F7` | 雾蓝 |
| 2 | `#7DCFFF` | 浅青 |
| 3 | `#9ECE6A` | 苔绿 |
| 4 | `#73DACA` | 薄荷 |
| 5 | `#E0AF68` | 沙金 |
| 6 | `#E5C07B` | 米黄 |
| 7 | `#F7768E` | 玫粉 |
| 8 | `#BB9AF7` | 灰紫 |
| 9 | `#C0CAF5` | 月白 (中性 fallback) |

### 边

| 状态 | 色值 |
|---|---|
| 默认(强弱不分) | `rgba(148,163,184,0.05)` —— 几乎隐入背景 |
| Hover/Click 强 | `#E0AF68` (沙金) + `width 2.4` + 实线 |
| Hover/Click 弱 | `#D4A574` (浅麦) + `width 1.5` + 虚线 `[6,5]` + opacity 0.85 |
| Faded(其他边) | `opacity 0.08` |

**关键设计决策:默认态不区分强弱**(没有 dashed、没有箭头)—— 减少视觉噪声,结构关系只在 hover/click 时通过粗细+实/虚+颜色显形。

### 文字

| 用途 | 色值 |
|---|---|
| 默认 label | `#cbd5e1` (opacity 0.85) |
| 高亮/选中 | `#f8fafc` |
| Faded | `rgba(203,213,225,0.15)` |

### 主高亮色

`#E0AF68` (沙金) —— 只用于 hover/选中,不用饱和蓝绿。

## 3. 布局规格 (fcose)

```js
{
  name: 'fcose',
  quality: 'proof',
  randomize: false,           // spectral 初始化,稳定可复现
  animate: 'end',             // 一次性 ease-out,不持续物理抖动
  animationDuration: 700,
  animationEasing: 'ease-out',

  // 按边强度施加不同弹簧力(关键):
  // 强边短而紧,弱边长而松 → 相关节点自动靠拢
  idealEdgeLength: edge => edge.data('strength') === 'strong' ? 70 : 180,
  edgeElasticity:  edge => edge.data('strength') === 'strong' ? 0.7 : 0.25,

  nodeRepulsion: 5500,        // 默认 4500 → 5500,适度推开
  gravity: 0.28,              // 加重向心力,集群更紧凑
  numIter: 3000,              // 多迭代,小图给够收敛时间
  packComponents: true,       // 无连接子图也排好
  nodeDimensionsIncludeLabels: true,
  padding: 60
}
```

**不要开持续 physics 模拟** —— 节点抖动 = 不专业。布局完成后用 `requestAnimationFrame` 给每节点叠加 sin 偏移即可(见下方"海浪浮沉")。

## 4. 节点规格

- **形状**: `ellipse` (正圆)
- **大小**: `width = height = 12 + degree * 2`,clamp 到 `[16, 32]` —— 中枢节点自然更大
- **背景**: 对应 tag 色
- **border**: `2px solid rgba(255,255,255,0.12)` —— 给立体感但不刺眼
- **hover border**: `2.5px solid #f8fafc`
- **不要 box-shadow / glow / 渐变填充** —— 纯色 + 细 border 是关键
- **label**:
  - position: `text-valign: bottom; text-margin-y: 8`
  - font: `Inter, -apple-system, "PingFang SC", sans-serif`
  - size: `11.5px` (hover 时 `12.5px`)
  - weight: `500`
  - color: `#cbd5e1`
  - **text-outline**: `3px #0e1116` —— 深色描边让标签悬浮在边之上,可读性 +50%
  - text-wrap, max-width 110px

## 5. 边规格

- **curve-style**: `unbundled-bezier` (微弧,不要直线)
- **control-point-distances**: `[22]`,weights `[0.5]`
- **箭头**: 默认 `target-arrow-shape: 'none'`,**仅 focused 时显示** `triangle` —— 默认 25 个小三角是视觉噪声的元凶
- **arrow-scale**: `0.5`
- **target-distance-from-node**: `3px` (箭头不贴节点)
- **不要给边加 label** —— 关联描述放侧栏即可

## 6. 海浪浮沉动画

布局完成 (`layoutstop` 事件) 后启动:

```js
const anchors = new Map();  // id → {x, y}(layout 给出的目标位置)
const phases  = new Map();  // id → {px, py, fx, fy, ax, ay}

function initBob() {
  cy.nodes().forEach(n => {
    anchors.set(n.id(), n.position());
    phases.set(n.id(), {
      px: Math.random() * Math.PI * 2,
      py: Math.random() * Math.PI * 2,
      fy: 0.00060 + Math.random() * 0.00035,   // 周期 7-11s 竖向
      fx: 0.00040 + Math.random() * 0.00025,   // 横向更慢
      ay: 3.5 + Math.random() * 2.0,            // 竖向振幅 3.5-5.5px
      ax: 1.5 + Math.random() * 1.0             // 横向 1.5-2.5px
    });
  });
  requestAnimationFrame(bobTick);
}

function bobTick(now) {
  cy.batch(() => {
    cy.nodes().forEach(n => {
      const a = anchors.get(n.id());
      const p = phases.get(n.id());
      n.position({
        x: a.x + Math.sin(now * p.fx + p.px) * p.ax,
        y: a.y + Math.sin(now * p.fy + p.py) * p.ay
      });
    });
  });
  requestAnimationFrame(bobTick);
}
```

**关键点**:
- 每节点**独立相位 + 独立频率**,不整齐划一才像真实海面
- 竖向:横向 ≈ 3:1,浮力主要竖向
- 拖拽时跳过该节点的 bob,松手后用新位置作为 anchor 继续

## 7. 交互规格

| 动作 | 反馈 |
|---|---|
| **hover 节点** | 200ms 内:该节点 + 一阶邻居保留,其余 fade 至 opacity 0.18;邻接边变金亮起;label 略放大 |
| **单击节点** | 锁定上述高亮 + 侧栏切到详情(标题、tag、出入边列表 + 飞书链接) |
| **双击节点** | 打开飞书 URL (`window.open`) |
| **单击空白** | 清除所有高亮,恢复全图 |
| **拖动节点** | 允许,松手位置保留(不弹回 layout) |
| **滚轮** | zoom,限制 `[0.4, 2.5]` |
| **ESC** | 清除选择 + tag 筛选 |

所有 transition: `cubic-bezier(0.4, 0, 0.2, 1)`,时长 180-280ms。

## 8. 侧栏 & 控件

宽 280px,三段式:

1. **顶部统计**: `N articles · M links` + `X strong · Y weak`,12px,`#64748b`
2. **Tag chips**: 圆形色块 10px + 标签 12px;点击 chip → 仅高亮该 tag 节点
3. **节点详情**(默认空,选中后显示): 标题(15px/600)、tag chip、所有出入边的目标 + 边描述、飞书链接按钮

**Header 压到 48px**,只放标题 + 副标题。**不要 minimap、搜索、edge legend** —— 16 节点不需要这些。

## 9. 避坑清单

- ❌ box-shadow / drop-shadow —— 深色背景下阴影 = 廉价
- ❌ 节点用饱和原色 `#ff0000` 类
- ❌ 边粗于 2.5px —— 粗边 = 流程图,不是知识图
- ❌ 节点直接放长文字标题 —— 用 text-max-width 截断 + tooltip 显示全名
- ❌ 持续 physics 模拟 —— 节点抖动 = 不专业
- ❌ 默认箭头 + dashed —— 25 个小三角 + 虚线节奏 = 视觉噪声元凶
- ❌ 节点上叠 icon + 数字 + 标签 —— 信息密度堆在节点 = 后台管理系统
- ❌ 中文字体让浏览器默认 —— 显式 fallback `PingFang SC, Noto Sans SC`
