import { useState, useEffect, useCallback } from "react";
import { Clock, Plus, Play, Pause, RotateCcw, ChevronDown, ChevronUp, Search, X, Check, ArrowLeft } from "lucide-react";
import confetti from "canvas-confetti";
import {
  listSchedules, createSchedule, updateSchedule, deleteSchedule,
  toggleSchedule, runScheduleNow, resumeSchedule,
  listScheduleTemplates, parseScheduleInput,
} from "../lib/api";
import type { ScheduleTask, ScheduleTemplate } from "../lib/types";

const FREQUENCIES = [
  { key: "daily", label: "每天" },
  { key: "workday", label: "工作日" },
  { key: "weekly", label: "每周" },
  { key: "monthly", label: "每月" },
] as const;

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];

type Step = "create" | "confirm";

export function ScheduledTasks() {
  const [tasks, setTasks] = useState<ScheduleTask[]>([]);
  const [templates, setTemplates] = useState<ScheduleTemplate[]>([]);
  const [loading, setLoading] = useState(true);

  // Create flow state
  const [step, setStep] = useState<Step>("create");
  const [frequency, setFrequency] = useState<string>("daily");
  const [timeH, setTimeH] = useState("09");
  const [timeM, setTimeM] = useState("00");
  const [weekday, setWeekday] = useState(1);
  const [monthday, setMonthday] = useState(1);
  const [showTemplates, setShowTemplates] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<ScheduleTemplate | null>(null);
  const [customInput, setCustomInput] = useState("");
  const [customPreview, setCustomPreview] = useState("");
  const [editingTask, setEditingTask] = useState<ScheduleTask | null>(null);
  const [expandedTask, setExpandedTask] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [creating, setCreating] = useState(false);
  const [tryingNow, setTryingNow] = useState<string | null>(null);

  // Load data
  const load = useCallback(async () => {
    try {
      const [t, tmpls] = await Promise.all([listSchedules(), listScheduleTemplates()]);
      setTasks(t);
      setTemplates(tmpls);
    } catch { /* gateway may not be running */ }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  // Parse custom input on change
  useEffect(() => {
    if (!customInput.trim()) { setCustomPreview(""); return; }
    const timer = setTimeout(async () => {
      try {
        const result = await parseScheduleInput(customInput);
        setCustomPreview(result.matched ? result.preview || "" : "");
      } catch { setCustomPreview(""); }
    }, 300);
    return () => clearTimeout(timer);
  }, [customInput]);

  // ── Handlers ──

  const timeStr = `${timeH.padStart(2, "0")}:${timeM.padStart(2, "0")}`;

  function openCreate() {
    setStep("create");
    setFrequency("daily");
    setTimeH("09"); setTimeM("00");
    setWeekday(1); setMonthday(1);
    setSelectedTemplate(null);
    setCustomInput("");
    setCustomPreview("");
    setEditingTask(null);
  }

  function openEdit(task: ScheduleTask) {
    setEditingTask(task);
    setStep("create");
    setFrequency(task.frequency);
    const [h, m] = task.time_str.split(":");
    setTimeH(h || "09"); setTimeM(m || "00");
    setWeekday(task.weekday || 1);
    setMonthday(task.monthday || 1);
    setSelectedTemplate(null);
    setCustomInput(task.prompt);
    setCustomPreview("");
  }

  async function handleCreate() {
    setCreating(true);
    try {
      const prompt = editingTask ? (customInput || editingTask.prompt) : (selectedTemplate?.prompt || customInput || "");
      const name = editingTask ? editingTask.name : (selectedTemplate?.name || customInput.slice(0, 6) || "自定义任务");

      const body: Record<string, unknown> = {
        name, prompt, frequency, time_str: timeStr,
        weekday: frequency === "weekly" ? weekday : null,
        monthday: frequency === "monthly" ? monthday : null,
      };

      if (editingTask) {
        await updateSchedule(editingTask.id, body);
      } else {
        const created = await createSchedule(body as Parameters<typeof createSchedule>[0]);
        confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } });
        setTimeout(() => confetti({ particleCount: 50, spread: 90, origin: { y: 0.5 } }), 500);
        setTimeout(() => confetti({ particleCount: 40, spread: 100, origin: { y: 0.7 } }), 1000);
        setEditingTask(created);
      }
      await load();
      setStep("create");
      setSelectedTemplate(null);
      setCustomInput("");
      setEditingTask(null);
    } catch { /* handle error */ }
    setCreating(false);
  }

  async function handleToggle(taskId: string) {
    await toggleSchedule(taskId);
    await load();
  }

  async function handleRunNow(taskId: string) {
    setTryingNow(taskId);
    await runScheduleNow(taskId);
    setTryingNow(null);
    await load();
  }

  async function handleResume(taskId: string) {
    await resumeSchedule(taskId);
    await load();
  }

  async function handleDelete(taskId: string) {
    await deleteSchedule(taskId);
    await load();
  }

  function handleSelectTemplate(tmpl: ScheduleTemplate) {
    setSelectedTemplate(tmpl);
    setFrequency(tmpl.default_frequency);
    const [h, m] = tmpl.default_time.split(":");
    setTimeH(h || "09"); setTimeM(m || "00");
  }

  function confirmStep() {
    setStep("confirm");
  }

  // ── Render helpers ──

  function frequencyLabel(f: string) {
    return FREQUENCIES.find(x => x.key === f)?.label || f;
  }

  function formatNextRun(t: ScheduleTask): string {
    if (!t.next_run_at) return "—";
    try {
      const d = new Date(t.next_run_at);
      return `${d.getMonth() + 1}月${d.getDate()}日 ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    } catch { return t.next_run_at; }
  }

  function formatLastRun(t: ScheduleTask): string {
    if (!t.last_run_at) return "—";
    try {
      const d = new Date(t.last_run_at);
      return `${d.getMonth() + 1}月${d.getDate()}日 ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    } catch { return t.last_run_at; }
  }

  function statusDot(status: string | null) {
    if (status === "success") return <span className="inline-block w-2 h-2 rounded-full bg-emerald-500/60" />;
    if (status === "failed" || status === "timeout") return <span className="inline-block w-2 h-2 rounded-full bg-red-400/40" />;
    return <span className="inline-block w-2 h-2 rounded-full bg-muted-foreground/30" />;
  }

  function historyDots(history: ScheduleTask["run_history"]) {
    const dots = [];
    for (let i = 0; i < 5; i++) {
      const entry = history[history.length - 5 + i];
      if (!entry) dots.push(<span key={i} className="inline-block w-2.5 h-2.5 rounded-full bg-muted-foreground/20" />);
      else if (entry.status === "success") dots.push(<span key={i} className="inline-block w-2.5 h-2.5 rounded-full bg-emerald-500/60" />);
      else dots.push(<span key={i} className="inline-block w-2.5 h-2.5 rounded-full bg-red-400/40" />);
    }
    return <div className="flex gap-1.5 items-center">{dots}</div>;
  }

  const filteredTemplates = templates.filter(t =>
    !searchQuery || t.name.includes(searchQuery) || t.description.includes(searchQuery)
  );
  const categories = [...new Set(filteredTemplates.map(t => t.category))];
  const catLabels: Record<string, string> = { morning: "早上要做的事", work: "工作中要用", monitor: "帮我盯着", evening: "下班后关心" };

  // ════════════════ RENDER ════════════════

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-32 bg-muted rounded" />
        <div className="h-40 bg-card border border-border rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">定时任务</h1>
        <p className="text-muted-foreground text-sm mt-1">
          像设闹钟一样简单。选时间、选任务，AI 自动帮你跑。
        </p>
      </div>

      {/* Create Panel */}
      <div className="bg-card border border-border rounded-xl p-5 space-y-4">
        {/* Step indicator */}
        <div className="flex items-center gap-2 text-sm">
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${step === "create" ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"}`}>1</span>
          <span className={step === "create" ? "text-foreground" : "text-muted-foreground"}>设置</span>
          <span className="text-muted-foreground/50">→</span>
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${step === "confirm" ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"}`}>2</span>
          <span className={step === "confirm" ? "text-foreground" : "text-muted-foreground"}>确认</span>
        </div>

        {step === "create" ? (
          <>
            {/* Frequency segmented buttons */}
            <div>
              <label className="text-sm font-medium mb-1.5 block">频率</label>
              <div className="flex gap-1.5">
                {FREQUENCIES.map(f => (
                  <button
                    key={f.key}
                    onClick={() => setFrequency(f.key)}
                    className={`px-3.5 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                      frequency === f.key
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted hover:bg-muted/80 text-muted-foreground"
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Time + conditional selectors */}
            <div className="flex items-center gap-3 flex-wrap">
              <div>
                <label className="text-sm font-medium mb-1.5 block">时间</label>
                <div className="flex items-center gap-1">
                  <input
                    type="number" min={0} max={23} value={timeH}
                    onChange={e => setTimeH(e.target.value)}
                    className="w-14 h-10 text-center rounded-lg border border-border bg-background text-sm"
                  />
                  <span className="text-muted-foreground">:</span>
                  <input
                    type="number" min={0} max={59} value={timeM}
                    onChange={e => setTimeM(e.target.value.padStart(2, "0"))}
                    className="w-14 h-10 text-center rounded-lg border border-border bg-background text-sm"
                  />
                </div>
              </div>

              {frequency === "weekly" && (
                <div>
                  <label className="text-sm font-medium mb-1.5 block">星期</label>
                  <select
                    value={weekday} onChange={e => setWeekday(Number(e.target.value))}
                    className="h-10 px-2 rounded-lg border border-border bg-background text-sm"
                  >
                    {WEEKDAYS.map((d, i) => (
                      <option key={i + 1} value={i + 1}>{d}</option>
                    ))}
                  </select>
                </div>
              )}

              {frequency === "monthly" && (
                <div>
                  <label className="text-sm font-medium mb-1.5 block">日期</label>
                  <select
                    value={monthday} onChange={e => setMonthday(Number(e.target.value))}
                    className="h-10 px-2 rounded-lg border border-border bg-background text-sm"
                  >
                    {Array.from({ length: 31 }, (_, i) => i + 1).map(d => (
                      <option key={d} value={d}>{d}日</option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {/* Template picker trigger — only for new tasks */}
            <div>
              <label className="text-sm font-medium mb-1.5 block">
                {editingTask ? "任务内容" : "做什么"}
              </label>
              {editingTask ? (
                <textarea
                  value={customInput || editingTask.prompt}
                  onChange={e => setCustomInput(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm resize-none"
                  placeholder="描述要自动执行的任务..."
                />
              ) : selectedTemplate ? (
                <div className="flex items-center gap-3 p-3 bg-background border border-border rounded-lg">
                  <span className="text-xl">{selectedTemplate.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium">{selectedTemplate.name}</div>
                    <div className="text-xs text-muted-foreground">{selectedTemplate.preview}</div>
                  </div>
                  <button onClick={() => setSelectedTemplate(null)} className="text-muted-foreground hover:text-foreground">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setShowTemplates(true)}
                  className="w-full p-3 text-left border border-dashed border-border rounded-lg text-sm text-muted-foreground hover:border-ring/30 hover:text-foreground transition-colors"
                >
                  {customInput || "从模板中选择，或直接输入你要做什么..."}
                </button>
              )}

              {/* Custom input for non-template, non-edit mode */}
              {!editingTask && !selectedTemplate && (
                <div className="mt-2">
                  <input
                    type="text"
                    value={customInput}
                    onChange={e => setCustomInput(e.target.value)}
                    placeholder="✏️ 或自己写：帮我看看今天有什么大新闻"
                    className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm placeholder:text-muted-foreground/60"
                  />
                  {customPreview && (
                    <p className="text-xs text-muted-foreground mt-1">→ 将执行：{customPreview}</p>
                  )}
                </div>
              )}
            </div>

            <button
              onClick={confirmStep}
              disabled={editingTask ? !customInput.trim() && !editingTask.prompt : !selectedTemplate && !customInput.trim()}
              className="flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Clock className="w-4 h-4" />
              {editingTask ? "继续" : "继续设置"}
            </button>
          </>
        ) : (
          /* ── Confirm step ── */
          <div className="space-y-4">
            <div className="p-4 bg-background border border-border rounded-lg space-y-2">
              <div className="text-lg font-medium">
                {frequencyLabel(frequency)} {timeStr}
                {frequency === "weekly" && <> · 周{WEEKDAYS[weekday - 1]}</>}
                {frequency === "monthly" && <> · {monthday}日</>}
              </div>
              <div className="text-sm text-muted-foreground">
                将自动执行：{editingTask ? (customInput || editingTask.prompt) : (selectedTemplate?.preview || customInput || "—")}
              </div>
              <div className="text-xs text-muted-foreground/70">
                下次运行：计算中...（北京时间）
              </div>
              <div className="text-xs text-muted-foreground/70">
                将在默认工作区中执行
              </div>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => setStep("create")}
                className="flex items-center gap-1.5 px-4 py-2 border border-border rounded-lg text-sm hover:bg-muted transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                返回修改
              </button>
              <button
                onClick={handleCreate}
                disabled={creating}
                className="flex items-center gap-2 px-5 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                <Check className="w-4 h-4" />
                {creating ? "创建中..." : editingTask ? "✓ 确认更新" : "✓ 确认创建"}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Try-now prompt for newly created task */}
      {editingTask && step === "create" && !showTemplates && (
        <div className="bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800 rounded-xl p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-emerald-700 dark:text-emerald-300">任务已创建！</p>
              <p className="text-xs text-emerald-600/80 dark:text-emerald-400/80 mt-0.5">要不要现在先跑一次看看效果？</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={async () => { await handleRunNow(editingTask.id); setEditingTask(null); }}
                disabled={tryingNow === editingTask.id}
                className="px-3 py-1.5 bg-emerald-500 text-white rounded-lg text-xs font-medium hover:bg-emerald-600 transition-colors disabled:opacity-50"
              >
                {tryingNow === editingTask.id ? "执行中..." : "立即试用"}
              </button>
              <button onClick={() => setEditingTask(null)} className="px-3 py-1.5 border border-emerald-200 dark:border-emerald-700 rounded-lg text-xs text-emerald-600 dark:text-emerald-400 hover:bg-emerald-100 dark:hover:bg-emerald-900/30 transition-colors">
                不用了
              </button>
            </div>
          </div>
          {tryingNow === editingTask.id && (
            <div className="mt-3 h-1.5 bg-emerald-200 dark:bg-emerald-800 rounded-full overflow-hidden">
              <div className="h-full bg-emerald-400 animate-shimmer rounded-full w-2/3" />
            </div>
          )}
        </div>
      )}

      {/* Template Picker Modal */}
      {showTemplates && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh] bg-black/40 backdrop-blur-sm" onClick={() => setShowTemplates(false)}>
          <div className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-2xl max-h-[70vh] overflow-y-auto mx-4" onClick={e => e.stopPropagation()}>
            <div className="sticky top-0 bg-card border-b border-border px-5 py-3 flex items-center gap-3">
              <Search className="w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="搜索模板..."
                className="flex-1 bg-transparent text-sm outline-none"
              />
              <button onClick={() => setShowTemplates(false)} className="text-muted-foreground hover:text-foreground">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-6">
              {categories.map(cat => {
                const items = filteredTemplates.filter(t => t.category === cat);
                if (!items.length) return null;
                return (
                  <div key={cat}>
                    <h3 className="text-sm font-medium text-muted-foreground mb-3">{catLabels[cat] || cat}</h3>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                      {items.map(tmpl => (
                        <button
                          key={tmpl.name}
                          onClick={() => { handleSelectTemplate(tmpl); setShowTemplates(false); }}
                          className="flex flex-col items-start gap-1.5 p-3 bg-background border border-border rounded-xl hover:border-ring/50 hover:shadow-sm transition-all text-left group"
                        >
                          <span className="text-2xl">{tmpl.icon}</span>
                          <div>
                            <div className="text-sm font-medium group-hover:text-primary transition-colors">{tmpl.name}</div>
                            <div className="text-[10px] text-muted-foreground leading-tight mt-0.5">{tmpl.description}</div>
                          </div>
                          {/* Preview on hover */}
                          <div className="hidden group-hover:block text-[10px] text-muted-foreground/70 mt-1 leading-snug">
                            {tmpl.preview}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
              {!filteredTemplates.length && (
                <p className="text-center text-sm text-muted-foreground py-8">没有匹配的模板</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Task List */}
      <div className="bg-card border border-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium">我的任务</h3>
          <button
            onClick={openCreate}
            className="flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            新建
          </button>
        </div>

        {tasks.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <Clock className="w-8 h-8 mx-auto mb-3 opacity-30" />
            <p className="text-sm">暂无定时任务</p>
            <p className="text-xs text-muted-foreground/70 mt-1">点击「新建」来安排 AI 定期帮你完成工作</p>
          </div>
        ) : (
          <div className="space-y-3">
            {tasks.map(task => (
              <div
                key={task.id}
                onClick={() => openEdit(task)}
                className={`relative p-4 rounded-xl border transition-all cursor-pointer group ${
                  task.consecutive_failures >= 3
                    ? "border-red-300 dark:border-red-800 bg-red-50/50 dark:bg-red-950/10"
                    : task.is_running
                    ? "border-emerald-300 dark:border-emerald-800 bg-emerald-50/30 dark:bg-emerald-950/10"
                    : !task.enabled
                    ? "border-border bg-muted/30 opacity-70"
                    : "border-border bg-background hover:border-ring/30 hover:shadow-sm"
                }`}
              >
                {/* Top row */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5 min-w-0">
                    {/* Pulse dot when running */}
                    {task.is_running && (
                      <span className="relative flex h-2.5 w-2.5">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500/60" />
                      </span>
                    )}
                    <span className="text-sm font-medium truncate">{task.name}</span>
                    {!task.is_running && (
                      <span className="text-xs text-muted-foreground shrink-0">
                        {frequencyLabel(task.frequency)} {task.time_str}
                        {task.frequency === "weekly" && task.weekday ? `· 周${WEEKDAYS[task.weekday - 1]}` : ""}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1 shrink-0" onClick={e => e.stopPropagation()}>
                    {/* Pause/Resume */}
                    <button
                      onClick={() => handleToggle(task.id)}
                      className="p-1.5 rounded-lg hover:bg-muted transition-colors"
                      title={task.enabled ? "暂停" : "恢复"}
                    >
                      {task.enabled ? <Pause className="w-3.5 h-3.5 text-muted-foreground" /> : <Play className="w-3.5 h-3.5 text-muted-foreground" />}
                    </button>
                  </div>
                </div>

                {/* Run info */}
                {task.is_running ? (
                  <div className="mt-2 text-xs text-muted-foreground">
                    ⏳ 运行中... 开始于：{formatLastRun(task)}
                  </div>
                ) : (
                  <div className="mt-2 text-xs text-muted-foreground flex items-center gap-2 flex-wrap">
                    <span className="flex items-center gap-1">
                      上次：{formatLastRun(task)} {statusDot(task.last_status)}
                    </span>
                    <span className="text-muted-foreground/50">·</span>
                    <span>下次：{formatNextRun(task)}</span>
                  </div>
                )}

                {/* History dots */}
                {task.run_history.length > 0 && (
                  <div className="mt-2 flex items-center gap-2">
                    {historyDots(task.run_history)}
                    <span className="text-[10px] text-muted-foreground/70">
                      ({task.run_history.filter(h => h.status === "success").length}/{task.run_history.length})
                    </span>
                    <button
                      onClick={(e) => { e.stopPropagation(); setExpandedTask(expandedTask === task.id ? null : task.id); }}
                      className="text-[10px] text-muted-foreground/50 hover:text-muted-foreground transition-colors"
                    >
                      {expandedTask === task.id ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    </button>
                  </div>
                )}

                {/* Expanded history */}
                {expandedTask === task.id && task.run_history.length > 0 && (
                  <div className="mt-2 space-y-1 border-t border-border pt-2">
                    {[...task.run_history].reverse().map((h, i) => (
                      <div key={i} className="text-[10px] text-muted-foreground flex gap-2">
                        <span className="shrink-0">{h.time?.slice(11, 19) || "—"}</span>
                        {statusDot(h.status)}
                        <span className="truncate">{h.output_summary || h.status}</span>
                        <span className="shrink-0">{h.duration}s</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Last output preview */}
                {task.last_output && expandedTask !== task.id && (
                  <div className="mt-1.5 text-[10px] text-muted-foreground/70 truncate">
                    ▸ {task.last_output}
                  </div>
                )}

                {/* Failure state actions */}
                {task.consecutive_failures >= 3 && (
                  <div className="mt-2 flex gap-2" onClick={e => e.stopPropagation()}>
                    <button onClick={() => handleRunNow(task.id)} className="px-3 py-1 bg-red-500 text-white rounded text-xs font-medium hover:bg-red-600 transition-colors">
                      ▶ 立即执行
                    </button>
                    <button onClick={() => handleResume(task.id)} className="px-3 py-1 border border-border rounded text-xs hover:bg-muted transition-colors">
                      ↺ 恢复定时
                    </button>
                  </div>
                )}

                {/* Try-now failure feedback */}
                {tryingNow === task.id && task.last_status === "failed" && (
                  <div className="mt-2 p-2 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded text-xs text-amber-700 dark:text-amber-300">
                    这次没跑成功。可能是暂时的网络波动。任务会按时自动重试。
                    <button onClick={(e) => { e.stopPropagation(); handleRunNow(task.id); }} className="ml-2 underline">手动重试</button>
                  </div>
                )}

                {/* Delete — visible on hover */}
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(task.id); }}
                  className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 transition-all"
                  title="删除"
                >
                  <X className="w-3 h-3 text-red-500" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Advanced mode entry */}
        <div className="mt-6 pt-4 border-t border-border">
          <details className="text-xs text-muted-foreground/60">
            <summary className="cursor-pointer hover:text-muted-foreground/80 transition-colors">
              高级模式：cron 表达式 · HEARTBEAT.md · Webhook 触发 · 执行日志
            </summary>
            <div className="mt-3 p-3 bg-muted/30 rounded-lg space-y-2">
              <p>技术流用户可通过以下方式使用高级调度功能：</p>
              <ul className="list-disc list-inside space-y-1">
                <li>在自定义频率中使用标准 cron 表达式</li>
                <li>导出任务为 HEARTBEAT.md 文件（即将推出）</li>
                <li>通过 Webhook URL 触发任务执行（即将推出）</li>
              </ul>
            </div>
          </details>
        </div>
      </div>
    </div>
  );
}
