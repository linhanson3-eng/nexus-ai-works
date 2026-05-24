import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Zap, Key, Blocks, Play, ArrowRight, Check } from "lucide-react";

type Step = 0 | 1 | 2 | 3;

const steps = [
  {
    icon: Zap,
    title: "欢迎使用 Nexus AI Works",
    description: "一个开源、自进化的 AI 工作平台。配置你的 LLM、创建项目、运行工作流——全部在浏览器中完成。",
    action: "开始配置",
    path: "/settings",
  },
  {
    icon: Key,
    title: "配置 LLM 提供商",
    description: "在设置中添加至少一个 LLM 提供商的 API Key。支持 Anthropic、DeepSeek、OpenAI、SiliconFlow、Moonshot 等。",
    action: "前往设置",
    path: "/settings",
  },
  {
    icon: Blocks,
    title: "创建第一个项目",
    description: "项目是隔离的 AI 团队空间。每个项目有自己的 Agent、工作流、看板和记忆。你可以创建多个项目用于不同业务场景。",
    action: "前往项目",
    path: "/workshops",
  },
  {
    icon: Play,
    title: "运行第一个工作流",
    description: "展开项目，输入任务描述，选择工作流模板，点击执行。Agent 将自动完成任务并生成结果。",
    action: "开始使用",
    path: "/workshops",
  },
];

export function Onboarding({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState<Step>(0);
  const navigate = useNavigate();

  const current = steps[step];
  const isLast = step === steps.length - 1;

  const handleNext = () => {
    if (isLast) {
      onDone();
    } else {
      setStep(s => (s + 1) as Step);
    }
    navigate(current.path);
  };

  const handleSkip = () => onDone();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-2xl p-8 w-full max-w-md mx-4 shadow-lg">
        {/* Step indicator */}
        <div className="flex items-center gap-1.5 mb-6">
          {steps.map((_, i) => (
            <div
              key={i}
              className={`h-1 flex-1 rounded-full transition-colors ${
                i <= step ? "bg-accent" : "bg-border"
              }`}
            />
          ))}
        </div>

        {/* Icon */}
        <div className="w-14 h-14 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-5">
          {<current.icon className="w-7 h-7 text-primary" />}
        </div>

        {/* Content */}
        <h2 className="text-xl font-bold text-foreground mb-2">{current.title}</h2>
        <p className="text-sm text-muted-foreground leading-relaxed mb-8">{current.description}</p>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleSkip}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors px-3 py-2"
          >
            跳过引导
          </button>
          <button
            onClick={handleNext}
            className="flex-1 flex items-center justify-center gap-2 px-5 py-2.5 bg-accent text-primary-foreground rounded-xl text-sm font-semibold hover:bg-primary/80 transition-colors"
          >
            {isLast ? (
              <>
                <Check className="w-4 h-4" /> 开始使用
              </>
            ) : (
              <>
                {current.action} <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
