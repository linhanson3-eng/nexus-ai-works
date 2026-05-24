# WebUI 瑞士极简全站改造 · 设计规格

## 目标

将 Nexus AI Works WebUI 从当前「暗色单主题 + 琥珀单色」改造为生产级国际化 SaaS 界面：
瑞士极简主义 + 亮暗双模 + shadcn/ui 组件底座 + Geist 字体家族。

## 设计 Token 体系

### 色彩
- 中性轴：暖灰系列 (`oklch`)，亮底 `98.5%` → 暗底 `14%`
- 主强调色：靛紫 `oklch(55% 0.18 270)`
- 语义色（低饱和）：success(翡翠绿)、warning(琥珀)、destructive(玫瑰红)
- 暗色模式通过 `.dark` 类切换

### 圆角
4 级体系：`sm(6px)` / `md(8px)` / `lg(12px)` / `xl(16px)`
替代全站统一 `rounded-[20px]`

### 间距
`--space-section: clamp(2rem, 2rem+3vw, 4rem)` 控制区块间距

### 字体
- `Geist Sans` (正文/UI)
- `Geist Mono` (代码/技术内容)
- 字重仅用 400/500/600，瑞士风格不用粗黑

## 组件体系

引入 shadcn/ui 以下组件，定制为瑞士极简风格：
- Button(6 variants)、Card、Input、Badge、Tabs、Dialog
- Select → Command（带搜索的下拉）
- Toast → Sonner
- Skeleton、Accordion

不引入：Sheet、Drawer、Dropdown(用Popover)、Table、DataTable、Carousel

## 布局改造

### 侧栏
- 240px → 56px 折叠，下划线指示器 + 靛紫色选中态
- 用户区移顶部，Logo 缩小

### 新增顶栏
- 面包屑 + 全局搜索(Command) + 主题切换按钮
- 仅桌面端，48px

### 内容区
- max-w 按页面类型约束
- 页面标题统一间距

## 页面改造要点

### Dashboard
- Hero 数字保留，白底+border+hover阴影
- 项目列表改表格行
- 新增最近活动 timeline

### ChatPanel（拆分）
- 文件拆为 ChatPanel + ChatMessage + ChatInput + ToolCallCard
- 气泡方角处理，assistant白底+border，user靛紫底
- 推理块用 Accordion
- 工具栏合并模型/推理/项目选择

### WorkshopList
- 手风琴展开 → 右侧滑出详情面板（Linear 风格）

### WorkflowList
- 卡片网格 3 栏 + hover 阴影 + 迷你节点图

### KanbanBoard
- 卡片硬阴影 + 左边缘颜色条 + 空列 placeholder

### Marketplace
- 列表行 + 缩略图替代纯卡片
- 详情弹窗 → 右侧滑出面板

### Settings
- 统一表单组件，API Key 加眼睛切换+复制

### AuthPage
- 左右分栏：品牌区 + 表单区

### Onboarding
- 换 Dialog 组件 + 简单插图

## 动效体系

- 快切 150ms（hover、focus）
- 标准过渡 200ms（路由切换、面板进出）
- 滑出面板 300ms（cubic-bezier 缓出）
- 骨架屏替代 pulse 动画

## 技术路径

1. 安装 shadcn/ui + 字体
2. 建立 CSS token 层 + 亮暗切换
3. 逐组件替换（优先通用组件）
4. 逐页面改造（优先 ChatPanel 拆分 + Dashboard）
5. 亮色主题适配
6. 动效 + 微交互
7. 响应式验证
