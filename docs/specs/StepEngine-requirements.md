# StepEngine — 可配置的多 Agent 协作步骤引擎

> 一个引擎，多份配置。3 个步骤就 3 个 config，10 个就 10 个。
> 发 Codex review 用。

---

## 一、核心模型

### 一句话

**StepEngine(config) → 拉起 Claude Code 多 agent team → 内部讨论收敛 → 产出 + 质量评分**

### 两层架构

```
外环（平台/引擎）                    内环（Claude Code 团队）
─────────────────                   ──────────────────────
步骤顺序、输入输出规范、质量门禁       Lead agent 组织讨论
全部由 engine 控制                   Specialist agents 各自负责
不交给 agent 决策                    内部质疑、辩论、修改、收敛
```

---

## 二、StepEngine 要做什么

### 输入

1. **step_config** — 一个步骤的完整定义（见第三节）
2. **input_data** — 上一步传过来的产出物（字符串或结构化数据）
3. **workspace** — 工作区路径（可选，默认当前项目）

### 执行流程

```
1. 读取 step_config，校验
2. 在 workspace 下准备执行环境（目录、git worktree 可选）
3. 根据 config.team 创建 Claude Code subagent 实例
4. agent 们开始讨论/协作，引擎监控：
   - 每轮讨论结束 → 检查质量门禁
   - 不通过 → 反馈给 team → 继续讨论/修改
   - 通过 → 停止，收集最终产出
   - 超过 max_rounds → 返回当前最优结果 + 未达标标记
5. 返回结果
```

### 输出

```
StepResult:
  - output: str                  # 最终产出
  - quality_score: float         # 质量评分
  - passed: bool                 # 是否通过门禁
  - rounds: int                  # 讨论轮数
  - transcript: list             # 完整讨论记录
  - artifacts: dict              # 附加产出文件列表
  - cost: float                  # token 费用
```

---

## 三、Config 结构（一个步骤的完整定义）

```yaml
# example: 加工步骤的 config
step:
  name: package-refine           # 步骤唯一标识
  description: "搬运GitHub项目并适配平台规范"

  # ── 输入输出规范 ──
  input:
    schema:                      # 期望的输入结构
      - name: repo_url
        type: string
        required: true
        description: "GitHub 仓库地址"
      - name: requirements
        type: string
        required: false
    validation:                  # 输入校验规则（可选）

  output:
    schema:                      # 产出物规范
      - name: refined_package
        type: directory
        description: "适配后的方案包目录"
      - name: changelog
        type: file
        description: "修改记录"
    format: markdown             # 产出格式要求

  # ── 团队定义 ──
  team:
    mode: council                # 讨论模式: council | pipeline | watchdog
    
    lead:
      name: architect            # 名称
      role: "技术负责人，负责分析项目结构、分配任务、最终决策"
      model: sonnet              # opus | sonnet | haiku
    
    members:
      - name: coder
        role: "负责代码修改和适配"
        model: sonnet
        
      - name: reviewer
        role: "负责代码审查，质疑实现方案，提出改进建议"
        model: sonnet
        
      - name: tester
        role: "负责验证修改后的代码能正常运行"
        model: haiku

    team_size:                    # 不指定 members 时的备选方案
      count: 4
      roles: [architect, coder, reviewer, tester]

  # ── 讨论规则 ──
  discussion:
    mode: council                 # council = 辩论达成共识
    max_rounds: 10                # 最多 10 轮讨论
    min_rounds: 2                 # 至少 2 轮
    round_timeout_seconds: 300    # 每轮超时
    converge_rule: "所有 member 明确表示同意，或 lead 做出最终决策"
    
    # Council 模式规则
    council:
      debate_required: true       # 必须有反对意见
      lead_tiebreaker: true       # 僵持时 lead 决策
      min_disagreement_rounds: 1  # 至少 1 轮有人提出质疑

  # ── 任务描述 ──
  task:
    description: |
      将 {repo_url} 搬运到 ai-factory 平台，适配方案包规范。
      要求：
      1. 分析项目结构，理解核心逻辑
      2. 按平台规范修改 agent 配置和工作流
      3. 通过所有测试
      4. 生成修改记录
    context_injection:            # 注入到每个 agent 的上下文
      - "平台方案包规范文档"
      - "类似方案的改造案例"

  # ── 质量门禁 ──
  quality_gate:
    rules:
      - name: test_pass
        type: auto                # auto = 引擎自动检查, manual = 人工审核
        check: "所有测试通过"
        weight: 40
        
      - name: code_review_score
        type: agent               # agent = 由 team 内部 agent 评分
        check: "代码审查评分 >= 7/10"
        weight: 30
        evaluator: reviewer       # 指定哪个 agent 负责评分
        
      - name: security_scan
        type: auto
        check: "无高危安全漏洞"
        weight: 30
    
    pass_threshold: 75            # 加权总分 >= 75 才算通过
    fail_action: feedback         # feedback = 反馈给 team 修改; abort = 直接终止

  # ── 产线链接（可选）──
  next_step: package-seal         # 下一步骤名称（不填就是最后一步）
  on_failure: retry               # retry | skip | abort | manual_review
```

---

## 四、讨论模式

### Council（辩论模式）

```
Round 1: Lead 分发任务 → 各 member 独立工作 → 产出初稿
Round 2: Reviewer 审查 → 提出质疑 → Coder 回应/修改
Round 3: 继续辩论 → 收敛
...
Round N: 所有 member 同意 → 输出 + 评分
```

适用于：加工、筛选——需要深度讨论和博弈的环节

### Pipeline（流水线模式）

```
Phase 1: Agent A 产出 → Phase 2: Agent B 审查/加工 → Phase 3: Agent C 验证
每阶段有明确的输入输出，不回溯
```

适用于：封装、上架——流程标准化的环节

### Watchdog（监控模式）

```
主 agent 工作 → 后台 agent 持续监控
发现问题 → spawn 修复 agent → 修复 → 主 agent 继续
```

适用于：测试、反馈跟进——需要持续监控的环节

---

## 五、Agent 间通讯机制

不需要复杂的 MCP 或消息中间件。文件系统就够了：

### 消息队列（每个 step 一个）

```
workspace/.step-mailbox/
├── inbox/                    # 每个 agent 的收件箱
│   ├── architect.jsonl       # 追加写入
│   ├── coder.jsonl
│   ├── reviewer.jsonl
│   └── tester.jsonl
├── broadcast.jsonl           # 全员可见的广播
└── artifacts/                # 共享产出物
    ├── current_draft/        # 当前工作版本
    └── review_notes.md       # 审查意见
```

### 通讯原语

```
put(to_agent, message)     → 发送消息到指定 agent 收件箱
take()                     → 从自己收件箱取一条消息（阻塞）
peek()                     → 查看收件箱但不取走
broadcast(message)         → 发送广播
check_pending()            → 检查是否有未读消息
```

### 讨论轮次推进

```
一轮结束的条件：
1. 所有 agent 都已经 take 并回复了当前轮的消息
2. 或超过 round_timeout_seconds
3. 或 lead agent 发出 next_round 信号
```

---

## 六、引擎 API

```python
class StepEngine:
    def __init__(self, step_config: dict):
        """加载并校验步骤配置"""
    
    async def run(self, input_data: dict) -> StepResult:
        """
        执行一个步骤：
        1. 校验输入
        2. 创建 agent team
        3. 启动讨论循环
        4. 质量门禁检查
        5. 收敛后返回结果
        """
    
    @classmethod
    async def run_pipeline(
        cls, 
        steps: list[dict],     # 多个步骤 config，按顺序
        input_data: dict
    ) -> list[StepResult]:
        """
        按顺序跑多个步骤。
        前一步的 output 自动成为后一步的 input。
        """
```

---

## 七、和 ai-factory 现有代码的关系

### 复用的部分
- `factory/engine/bridge.py` — Claude Code agent 创建和管理
- `factory/runner.py` — 单 agent 执行、session resume
- `factory/memory/` — 每步的产出存入 Memory Tree
- `factory/kanban/` — 每步执行状态同步到看板
- `marketplace/` — 步骤产出最终进入方案市场

### 不碰的部分
- `factory/workflow/engine.py` — 当前 DAG 引擎不动，StepEngine 是独立新模块
- `factory/workflow/models.py` — 用自己的 config schema

### 新增的部分
```
factory/
  step_engine/
    __init__.py
    engine.py           # StepEngine 主类
    config.py           # Config 加载和校验
    team.py             # Agent team 管理（spawn, monitor, cleanup）
    mailbox.py          # 文件系统消息队列
    discussion.py       # 讨论模式实现（council, pipeline, watchdog）
    quality_gate.py     # 质量门禁检查
    models.py           # StepConfig, StepResult, Message 等 dataclass
    templates/          # 内置步骤模板（调研、搜索、筛选、加工、封装...）
      research.yaml
      github_search.yaml
      screen.yaml
      refine.yaml
      package.yaml
      publish.yaml
      feedback.yaml
```

---

## 八、使用示例

```python
# 加载一个步骤配置
config = load_step_config("templates/refine.yaml")

# 创建引擎
engine = StepEngine(config)

# 执行
result = await engine.run({
    "repo_url": "https://github.com/xxx/awesome-tool",
    "requirements": "需要适配为 ai-factory 方案包"
})

if result.passed:
    print(f"加工完成，质量评分: {result.quality_score}")
    print(f"讨论轮数: {result.rounds}")
    print(f"产出: {result.output[:200]}")
else:
    print(f"未通过质量门禁: {result.quality_score}")
    # 查看讨论记录定位问题
    for msg in result.transcript:
        print(f"[{msg.round}] {msg.agent}: {msg.content[:100]}")

# 或者跑整条产线
results = await StepEngine.run_pipeline(
    steps=["templates/research.yaml", 
           "templates/search.yaml",
           "templates/screen.yaml", 
           "templates/refine.yaml",
           "templates/package.yaml"],
    input_data={"task": "找一个好的电商后台管理系统并适配"}
)
```

---

## 九、关键约束

1. **不依赖 Agent Teams 实验性 flag** — 只使用 Claude Code 成熟的 subagent 机制
2. **文件系统即通讯层** — 不引入 Redis、消息队列、MCP 等额外依赖
3. **配置驱动，引擎逻辑不动** — 加新步骤 = 新增 yaml 文件
4. **每步可独立运行，也可串联** — run() 和 run_pipeline() 都支持
5. **失败可回溯** — 每轮的讨论记录、产出物全部落盘
6. **和 ai-factory 现有基建松耦合** — StepEngine 不 import workflow/engine.py
