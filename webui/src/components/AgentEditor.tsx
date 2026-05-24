import { useState, useEffect } from "react";
import { X, Zap, Bot, FileText, Wrench, Shield, Loader2 } from "lucide-react";
import { api, getAuthHeaders } from "../lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import type { ToastFn } from "./Toast";
import type { AgentInfo } from "../lib/types";

const AVAILABLE_TOOLS = [
  "think", "search", "deep_search", "read_file", "write_file",
  "execute_command", "task", "web_fetch", "ask_user_question",
];

interface AgentEditorProps {
  workshopName: string;
  existingAgent: AgentInfo | null;
  onClose: () => void;
  onSaved: () => void;
  toast: ToastFn;
}

export function AgentEditor({ workshopName, existingAgent, onClose, onSaved, toast }: AgentEditorProps) {
  const [form, setForm] = useState({
    name: "", mode: "super" as "super" | "normal",
    model: "",
    system_prompt: "", guide_file: "", guide_content: "", skills: "",
    tools: "" as string | string[],
    file_write: true, shell_exec: true, subagent_spawn: true,
  });
  const [saving, setSaving] = useState(false);
  const [availableSkills, setAvailableSkills] = useState<{ name: string; description: string }[]>([]);
  const [skillsDropdownOpen, setSkillsDropdownOpen] = useState(false);
  const [providerGroups, setProviderGroups] = useState<{ name: string; hasKey: boolean; models: string[] }[]>([]);
  const [initialized, setInitialized] = useState(false);

  const isEditing = !!existingAgent;

  useEffect(() => {
    api.listProviders().then((providers: Record<string, { models?: string[]; api_key?: string }>) => {
      const groups: { name: string; hasKey: boolean; models: string[] }[] = [];
      for (const [pname, cfg] of Object.entries(providers)) {
        if (cfg.models?.length) groups.push({ name: pname, hasKey: !!cfg.api_key, models: cfg.models });
      }
      setProviderGroups(groups);
    }).catch(() => {});
    api.listSkills().then((data: { name: string; description?: string }[]) => {
      setAvailableSkills(data.map((s) => ({ name: s.name, description: s.description || "" })));
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!skillsDropdownOpen) return;
    const handler = () => setSkillsDropdownOpen(false);
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [skillsDropdownOpen]);

  useEffect(() => {
    if (initialized) return;
    if (existingAgent) {
      let guideContent = "";
      if (existingAgent.guide_file) {
        fetch(`/api/workshops/${workshopName}/files/${existingAgent.guide_file}`, { headers: { ...getAuthHeaders() }, credentials: "include" })
          .then((res) => res.ok ? res.json() : null)
          .then((data) => { if (data) guideContent = data.content || ""; })
          .catch(() => {});
      }
      setForm({
        name: existingAgent.name,
        mode: existingAgent.mode || (existingAgent.is_super ? "super" : "normal"),
        model: existingAgent.model,
        system_prompt: existingAgent.system_prompt || "",
        guide_file: existingAgent.guide_file || "GUIDE.md",
        guide_content: guideContent,
        skills: (existingAgent.skills || []).join(", "),
        tools: existingAgent.tools_all ? "" : (existingAgent.tools || []).join(", "),
        file_write: existingAgent.permissions?.file_write ?? false,
        shell_exec: existingAgent.permissions?.shell_exec ?? false,
        subagent_spawn: existingAgent.permissions?.subagent_spawn ?? false,
      });
    } else {
      setForm({
        name: "", mode: "super", model: "",
        system_prompt: "", guide_file: "GUIDE.md", guide_content: "", skills: "",
        tools: "", file_write: true, shell_exec: true, subagent_spawn: true,
      });
    }
    setInitialized(true);
  }, [existingAgent, workshopName, initialized]);

  const save = async () => {
    if (!form.name.trim()) return;
    setSaving(true);
    const mode = form.mode;
    const isSuper = mode === "super";
    const toolsStr = typeof form.tools === "string" ? form.tools : form.tools.join(", ");
    const tools: string[] = isSuper ? [] : (toolsStr ? toolsStr.split(",").map((t) => t.trim()).filter(Boolean) : ["think", "search", "read_file"]);
    const payload: Record<string, unknown> = {
      name: form.name.trim(), mode, model: form.model, tools,
      system_prompt: form.system_prompt, guide_file: form.guide_file, guide_content: form.guide_content,
      skills: form.skills ? form.skills.split(",").map((s) => s.trim()).filter(Boolean) : [],
      permissions: { file_write: form.file_write, shell_exec: form.shell_exec, subagent_spawn: form.subagent_spawn },
    };
    try {
      if (isEditing) {
        await api.updateAgent(workshopName, existingAgent.name, payload);
        toast.success(`Agent "${payload.name}" 已更新`);
      } else {
        await api.createAgent(workshopName, payload);
        toast.success(`Agent "${payload.name}" 已创建`);
      }
      onSaved(); onClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "保存失败");
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-card border border-border rounded-xl p-6 w-full max-w-lg space-y-4 shadow-lg max-h-[85vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">{isEditing ? `编辑 Agent: ${existingAgent.name}` : "新建 Agent"}</h2>
          <button onClick={onClose} className="p-1.5 rounded-md text-muted-foreground hover:text-foreground transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Name */}
        <div>
          <label className="text-xs font-medium text-muted-foreground mb-1.5 block">名称</label>
          <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            placeholder="Agent 名称" disabled={isEditing} />
        </div>

        {/* Mode + Model */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">模式</label>
            <div className="flex gap-2">
              <button type="button" onClick={() => setForm((f) => ({ ...f, mode: "super", tools: "", file_write: true, shell_exec: true, subagent_spawn: true }))}
                className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium border transition-colors ${
                  form.mode === "super" ? "bg-destructive/10 text-destructive border-destructive/30" : "bg-background border-border text-muted-foreground hover:text-foreground"
                }`}>
                <Zap className="w-3.5 h-3.5" /> 超级
              </button>
              <button type="button" onClick={() => setForm((f) => ({ ...f, mode: "normal", tools: "think, search, read_file", file_write: false, shell_exec: false, subagent_spawn: false }))}
                className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium border transition-colors ${
                  form.mode === "normal" ? "bg-primary/10 text-primary border-primary/30" : "bg-background border-border text-muted-foreground hover:text-foreground"
                }`}>
                <Bot className="w-3.5 h-3.5" /> 普通
              </button>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">模型</label>
            <select value={form.model} onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))}
              className="w-full h-9 bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:border-ring/50">
              {providerGroups.map((g) => (
                <optgroup key={g.name} label={`${g.name} ${g.hasKey ? '✓' : '(未配置 Key)'}`}>
                  {g.models.map((m) => <option key={`${g.name}/${m}`} value={`${g.name}/${m}`}>{m}</option>)}
                </optgroup>
              ))}
              <option value="__custom__">自定义输入...</option>
            </select>
            {form.model === "__custom__" && (
              <Input value="" onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))}
                placeholder="输入模型名" autoFocus className="mt-1" />
            )}
          </div>
        </div>

        {/* System prompt */}
        <div>
          <label className="text-xs font-medium text-muted-foreground mb-1.5 flex items-center gap-1.5">
            <FileText className="w-3 h-3" /> 系统提示词
          </label>
          <textarea value={form.system_prompt} onChange={(e) => setForm((f) => ({ ...f, system_prompt: e.target.value }))}
            placeholder="Agent 的系统级指令..." rows={3}
            className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:border-ring/50 resize-none" />
        </div>

        {/* Tools */}
        {form.mode === "normal" && (
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 flex items-center gap-1.5">
              <Wrench className="w-3 h-3" /> 工具
            </label>
            <Input value={typeof form.tools === "string" ? form.tools : form.tools.join(", ")}
              onChange={(e) => setForm((f) => ({ ...f, tools: e.target.value }))}
              placeholder="think, search, read_file, write_file..." />
            <div className="flex flex-wrap gap-1 mt-1.5">
              {AVAILABLE_TOOLS.map((t) => {
                const toolsStr = typeof form.tools === "string" ? form.tools : form.tools.join(", ");
                const selected = toolsStr.includes(t);
                return (
                  <button key={t} type="button"
                    onClick={() => {
                      const current = toolsStr.split(",").map((s) => s.trim()).filter(Boolean);
                      const next = selected ? current.filter((x) => x !== t) : [...current, t];
                      setForm((f) => ({ ...f, tools: next.join(", ") }));
                    }}
                    className={`text-[10px] px-2 py-0.5 rounded-md border transition-colors ${
                      selected ? "bg-primary/10 text-primary border-primary/30" : "bg-background border-border text-muted-foreground hover:text-foreground"
                    }`}>{t}</button>
                );
              })}
            </div>
          </div>
        )}

        {/* Guide */}
        <div>
          <label className="text-xs font-medium text-muted-foreground mb-1.5 flex items-center gap-1.5">
            <FileText className="w-3 h-3" /> 引导文件
          </label>
          <div className="flex gap-2">
            <Input value={form.guide_file} onChange={(e) => setForm((f) => ({ ...f, guide_file: e.target.value }))}
              placeholder="GUIDE.md" className="w-36" />
            <span className="text-[10px] text-muted-foreground self-center">.md Markdown 文件</span>
          </div>
          <textarea value={form.guide_content} onChange={(e) => setForm((f) => ({ ...f, guide_content: e.target.value }))}
            placeholder={"# Agent 引导指令\n\n## 角色\n你是一个...\n\n## 工作流程\n1. ...\n2. ...\n\n## 规则\n- ..."}
            rows={8}
            className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:border-ring/50 mt-2 resize-none font-mono" />
        </div>

        {/* Skills */}
        <div className="relative">
          <label className="text-xs font-medium text-muted-foreground mb-1.5 flex items-center gap-1.5">
            <Zap className="w-3 h-3" /> 技能
          </label>
          <div className="flex flex-wrap gap-1 mb-1.5">
            {form.skills ? form.skills.split(",").map((s) => s.trim()).filter(Boolean).map((skill) => (
              <Badge key={skill} variant="outline" className="gap-1 text-xs">
                {skill}
                <button onClick={() => {
                  const current = form.skills.split(",").map((s) => s.trim()).filter(Boolean);
                  setForm((f) => ({ ...f, skills: current.filter((x) => x !== skill).join(", ") }));
                }}>
                  <X className="w-3 h-3" />
                </button>
              </Badge>
            )) : null}
          </div>
          <button type="button" onClick={(e) => { e.stopPropagation(); setSkillsDropdownOpen(!skillsDropdownOpen); }}
            className="w-full flex items-center justify-between bg-background border border-border rounded-md px-3 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors">
            <span>{form.skills ? "已选 " + form.skills.split(",").filter(Boolean).length + " 个技能" : "选择技能..."}</span>
            <span className="text-[10px]">{skillsDropdownOpen ? "▲" : "▼"}</span>
          </button>
          {skillsDropdownOpen && (
            <div className="absolute z-50 w-full mt-1 bg-card border border-border rounded-md shadow-lg max-h-48 overflow-auto">
              {availableSkills.length === 0 ? (
                <p className="text-xs text-muted-foreground p-3">暂无可用技能，请先在设置中同步</p>
              ) : (
                availableSkills.map((skill) => {
                  const selected = form.skills.split(",").map((s) => s.trim()).includes(skill.name);
                  return (
                    <button key={skill.name} type="button" onClick={() => {
                      const current = form.skills ? form.skills.split(",").map((s) => s.trim()).filter(Boolean) : [];
                      const next = selected ? current.filter((x) => x !== skill.name) : [...current, skill.name];
                      setForm((f) => ({ ...f, skills: next.join(", ") }));
                    }}
                      className={`w-full text-left px-3 py-2 text-xs hover:bg-accent transition-colors flex items-center justify-between ${
                        selected ? "text-primary" : "text-foreground/80"
                      }`}>
                      <span>{skill.name}</span>
                      {skill.description && <span className="text-[10px] text-muted-foreground truncate ml-2 max-w-[200px]">{skill.description}</span>}
                    </button>
                  );
                })
              )}
            </div>
          )}
        </div>

        {/* Permissions */}
        <div>
          <label className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1.5">
            <Shield className="w-3 h-3" /> 权限
          </label>
          <div className="space-y-2">
            {([
              { key: "file_write", label: "文件写入", desc: "允许读写项目文件" },
              { key: "shell_exec", label: "Shell 执行", desc: "允许执行终端命令" },
              { key: "subagent_spawn", label: "子 Agent", desc: "允许创建子 Agent 执行子任务" },
            ] as const).map((perm) => (
              <label key={perm.key} className="flex items-center justify-between p-2.5 bg-background border border-border rounded-md cursor-pointer hover:border-ring/30 transition-colors">
                <div>
                  <span className="text-sm">{perm.label}</span>
                  <p className="text-[10px] text-muted-foreground">{perm.desc}</p>
                </div>
                <button type="button" onClick={() => { setForm((f) => ({ ...f, [perm.key]: !f[perm.key] })); }}
                  className={`w-9 h-5 rounded-full transition-colors relative ${form[perm.key] ? "bg-primary" : "bg-muted"}`}>
                  <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-background transition-transform ${form[perm.key] ? "left-4" : "left-0.5"}`} />
                </button>
              </label>
            ))}
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={save} disabled={saving || !form.name.trim()}>
            {saving && <Loader2 className="w-4 h-4 animate-spin mr-2" />} 保存
          </Button>
        </div>
      </div>
    </div>
  );
}
