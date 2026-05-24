from __future__ import annotations
"""预置定时任务模板 — 20 个精心打磨的 prompt。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Template:
    name: str
    icon: str
    description: str
    preview: str
    prompt: str
    category: str           # morning | work | monitor | evening
    default_frequency: str  # daily | workday | weekly | monthly
    default_time: str       # "HH:MM"


TEMPLATES: list[Template] = [
    # ═══ 🌅 早上要做的事 ═══
    Template(
        name="天气提醒",
        icon="🌤",
        description="今日天气+穿衣建议",
        preview="查询今日天气，根据温度和天气状况给出生动的穿衣建议",
        prompt="查询今日天气和温度。根据天气状况给出简洁的穿衣建议和是否需要带伞的提醒。回复限制在 100 字以内，语气轻松活泼。",
        category="morning",
        default_frequency="daily",
        default_time="07:30",
    ),
    Template(
        name="AI 新闻",
        icon="📰",
        description="每日 AI 行业动态",
        preview="搜索过去 24 小时 AI 行业新闻，生成中文简报并标注来源",
        prompt="搜索过去 24 小时全球 AI 行业的重要新闻、论文发布、产品更新和融资事件。生成一份 500 字以内的中文简报，按重要性排序，每一条标注来源链接。忽略纯营销内容。",
        category="morning",
        default_frequency="daily",
        default_time="09:00",
    ),
    Template(
        name="通勤路况",
        icon="🚗",
        description="早高峰路况+预估",
        preview="检查通勤路线早高峰路况，给出预计耗时和出行建议",
        prompt="检查从家到公司的早高峰路况。给出当前预计耗时、是否有交通事故、建议的替代路线（如有）。回复简洁，重点突出时间预估。",
        category="morning",
        default_frequency="workday",
        default_time="07:45",
    ),
    Template(
        name="GitHub Trending",
        icon="📈",
        description="当日热门开源项目",
        preview="抓取 GitHub Trending 当日热门仓库，生成中文简介",
        prompt="查看 GitHub Trending 今日热门仓库（编程语言不限）。选出前 5 个，用中文简要介绍每个项目是什么、为什么热。每条 80 字以内。",
        category="morning",
        default_frequency="daily",
        default_time="09:30",
    ),
    Template(
        name="日程概览",
        icon="📅",
        description="今日日程+待办汇总",
        preview="汇总今天的日程安排和待办事项，给出时间分配建议",
        prompt="汇总今天的日程安排和待办事项。如果今天是工作日，按优先级和时间排序，给出合理的时间分配建议。如果今天是周末，提醒放松和休息。语气温和。",
        category="morning",
        default_frequency="daily",
        default_time="08:00",
    ),

    # ═══ 💼 工作中要用 ═══
    Template(
        name="站会摘要",
        icon="📋",
        description="昨日提交+今日计划",
        preview="总结昨天的 Git 提交记录，生成站会汇报稿",
        prompt="查看昨天的 Git 提交记录。总结做了什么、有什么值得注意的变化，生成一份简洁的站会汇报稿（3-5 句话即可）。突出关键进展和阻塞项。",
        category="work",
        default_frequency="workday",
        default_time="09:15",
    ),
    Template(
        name="周报生成",
        icon="📊",
        description="本周工作总结报告",
        preview="汇总本周 Git 提交和工作进展，生成结构化周报",
        prompt="汇总本周所有 Git 提交记录和工作进展。生成一份结构化周报：本周完成、进行中、下周计划、风险与问题。按模块分组，每条一句话。",
        category="work",
        default_frequency="weekly",
        default_time="17:00",
    ),
    Template(
        name="PR 审查",
        icon="🔍",
        description="检查未审查的 PR",
        preview="扫描仓库中待审查的 Pull Request，提醒相关人",
        prompt="检查仓库中所有待审查的 Pull Request。列出每个 PR 的标题、作者、创建时间和紧急程度。超过 24 小时未审查的标为高优先级。",
        category="work",
        default_frequency="workday",
        default_time="10:00",
    ),
    Template(
        name="代码质量",
        icon="✅",
        description="测试+lint 状态检查",
        preview="运行测试和 lint，报告代码质量状态",
        prompt="运行项目的测试套件和 lint 检查。报告通过率、失败的测试、代码异味。如果全部通过，回复简洁的「✅ 全部通过」。有问题的列出具体文件和建议。",
        category="work",
        default_frequency="daily",
        default_time="08:30",
    ),
    Template(
        name="会议准备",
        icon="📝",
        description="会前背景资料汇总",
        preview="检查今日会议安排，提前准备相关背景资料",
        prompt="检查今天是否有会议安排。如果有，为每个会议准备简要的背景资料：上次会议纪要要点、相关文档链接、需要讨论的事项。如果没有会议，回复「今天暂无会议」。",
        category="work",
        default_frequency="workday",
        default_time="08:30",
    ),

    # ═══ 🛡️ 帮我盯着 ═══
    Template(
        name="服务健康",
        icon="❤️",
        description="检查 URL 是否可达",
        preview="向指定 URL 发起健康检查请求，报告响应状态和延迟",
        prompt="向服务健康检查端点发送请求。检查 HTTP 状态码、响应延迟。如果正常，回复「✅ 所有服务正常」+ 各服务延迟。如果异常，立即报告具体哪个服务、什么错误。",
        category="monitor",
        default_frequency="daily",
        default_time="09:00",
    ),
    Template(
        name="目录变化",
        icon="📁",
        description="监控目录文件增减",
        preview="扫描指定目录是否有新文件添加或旧文件删除",
        prompt="扫描监控目录，对比上次扫描结果。列出新增的文件、被删除的文件、被修改的文件。只报告变化，无变化时回复「📁 无变化」。",
        category="monitor",
        default_frequency="daily",
        default_time="10:00",
    ),
    Template(
        name="日志扫描",
        icon="📜",
        description="扫描日志异常关键词",
        preview="扫描应用日志文件，搜索 ERROR/CRITICAL/WARNING 关键词",
        prompt="扫描最近的日志文件，搜索 ERROR、CRITICAL、FATAL、panic、timeout 等异常关键词。按严重程度分类报告，给出每种异常的出现次数和最新出现时间。如果日志干净，回复「📜 日志正常」。",
        category="monitor",
        default_frequency="daily",
        default_time="09:00",
    ),
    Template(
        name="证书过期",
        icon="🔒",
        description="检查 SSL 证书有效期",
        preview="检查域名的 SSL 证书剩余有效期，提前预警",
        prompt="检查指定域名的 SSL 证书有效期。如果剩余超过 30 天，简洁报告。如果 7-30 天，标黄提醒。如果少于 7 天，标红紧急提醒。给出证书到期具体日期。",
        category="monitor",
        default_frequency="weekly",
        default_time="09:00",
    ),
    Template(
        name="依赖更新",
        icon="📦",
        description="检查项目依赖更新",
        preview="扫描项目依赖，发现可用的安全更新和版本升级",
        prompt="扫描项目的依赖文件（package.json、pyproject.toml 等）。检查是否有已知的安全漏洞（CVE）需要修复，以及是否有主版本更新。按严重程度排序报告，给出升级命令。",
        category="monitor",
        default_frequency="weekly",
        default_time="10:00",
    ),

    # ═══ 🌙 下班后关心 ═══
    Template(
        name="股票监控",
        icon="📈",
        description="监控指定股票/资产价格",
        preview="查询指定股票或加密资产当前价格和涨跌幅",
        prompt="查询指定股票代码或加密资产的最新价格、24 小时涨跌幅、7 天走势。用简洁的表格展示。如果涨跌幅超过 5%，特别标注提醒。",
        category="evening",
        default_frequency="daily",
        default_time="16:00",
    ),
    Template(
        name="论文速递",
        icon="📄",
        description="ArXiv 新论文筛选",
        preview="从 ArXiv 抓取指定领域的新论文，筛选热门和高引作品",
        prompt="查看 ArXiv 今天在 AI/ML 领域的新论文。筛选出引用量高或话题热门的 3-5 篇，用中文给出论文标题、一句话摘要和链接。",
        category="evening",
        default_frequency="daily",
        default_time="18:00",
    ),
    Template(
        name="博客更新",
        icon="✍️",
        description="关注的技术博客更新",
        preview="检查关注的技术博客是否有新文章发布",
        prompt="检查关注的技术博客列表是否有新文章发布。列出更新日期、文章标题、简短摘要。按发布时间倒序排列，最多 5 篇。如果今天没有更新，回复「今日无新文章」。",
        category="evening",
        default_frequency="daily",
        default_time="19:00",
    ),
    Template(
        name="学习提醒",
        icon="📚",
        description="每日学习任务提醒",
        preview="提醒今日的学习目标，回顾昨日进度，推荐学习内容",
        prompt="提醒今天的学习目标和计划。回顾昨天的学习进度。根据学习路径推荐今天的学习内容和时长建议。语气鼓励。如果连续打卡可以表扬。",
        category="evening",
        default_frequency="daily",
        default_time="20:00",
    ),
    Template(
        name="明日准备",
        icon="🌙",
        description="明天的待办+天气+日程",
        preview="汇总明天天气、日程和待办，生成睡前简报",
        prompt="查询明天的天气预报。汇总明天的日程安排和待办事项。生成一份简洁的睡前简报：天气+穿衣、第一个日程的时间和内容、最重要的 3 个待办。语气温暖，祝晚安。",
        category="evening",
        default_frequency="daily",
        default_time="22:00",
    ),
]
