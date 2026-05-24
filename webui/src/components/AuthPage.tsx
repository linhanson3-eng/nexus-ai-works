import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Zap, Loader2, Eye, EyeOff } from "lucide-react";
import { useAuth } from "../lib/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Mode = "login" | "register";

export function AuthPage() {
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const { login, register, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  if (isAuthenticated) {
    navigate("/chat", { replace: true });
    return null;
  }

  const submit = async () => {
    setError("");
    if (!username.trim() || !password.trim()) {
      setError("请填写用户名和密码");
      return;
    }
    if (username.trim().length < 3) {
      setError("用户名至少 3 个字符");
      return;
    }
    if (password.length < 6) {
      setError("密码至少 6 个字符");
      return;
    }

    setLoading(true);
    try {
      if (mode === "login") {
        await login(username.trim(), password);
      } else {
        await register(username.trim(), password);
      }
      navigate("/chat", { replace: true });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "操作失败";
      if (msg.includes("401") || msg.includes("Unauthorized")) setError("用户名或密码错误");
      else if (msg.includes("409") || msg.includes("Conflict")) setError("用户名已存在，请直接登录");
      else if (msg.includes("422")) setError("用户名或密码格式不符合要求");
      else setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const switchMode = () => {
    setMode((m) => (m === "login" ? "register" : "login"));
    setError("");
    setPassword("");
  };

  return (
    <div className="flex h-full min-h-[500px]">
      {/* Left brand panel */}
      <div className="hidden lg:flex w-[420px] bg-muted/30 border-r border-border flex-col items-center justify-center p-12 shrink-0">
        <div className="w-16 h-16 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-6">
          <Zap className="w-8 h-8 text-primary" />
        </div>
        <h1 className="text-2xl font-semibold tracking-tight mb-2">Nexus AI Works</h1>
        <p className="text-muted-foreground text-sm text-center max-w-[260px] leading-relaxed">
          开源、自进化的多 Agent 协作平台。构建、编排、交付——全在浏览器中完成。
        </p>
        <div className="mt-8 flex gap-3 text-[10px] text-muted-foreground/60">
          <span>瑞士精工</span>
          <span>·</span>
          <span>亮暗双模</span>
          <span>·</span>
          <span>v1.0</span>
        </div>
      </div>

      {/* Right form panel */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <div className="lg:hidden text-center mb-8">
            <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center mx-auto mb-3">
              <Zap className="w-6 h-6 text-primary" />
            </div>
            <h1 className="text-xl font-semibold tracking-tight">Nexus AI Works</h1>
          </div>

          <div className="bg-card border border-border rounded-xl p-6 space-y-4">
            {/* Mode tabs */}
            <div className="flex bg-muted rounded-lg p-1">
              <button
                onClick={() => setMode("login")}
                className={`flex-1 py-2 rounded-md text-sm font-medium transition-all ${
                  mode === "login"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                登录
              </button>
              <button
                onClick={() => setMode("register")}
                className={`flex-1 py-2 rounded-md text-sm font-medium transition-all ${
                  mode === "register"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                注册
              </button>
            </div>

            {/* Username */}
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">用户名</label>
              <Input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submit()}
                placeholder="输入用户名"
                autoFocus
                autoComplete="username"
              />
            </div>

            {/* Password */}
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">密码</label>
              <div className="relative">
                <Input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && submit()}
                  placeholder="输入密码"
                  autoComplete={mode === "login" ? "current-password" : "new-password"}
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((p) => !p)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {mode === "register" && (
                <p className="text-[10px] text-muted-foreground mt-1">至少 6 个字符</p>
              )}
            </div>

            {/* Error */}
            {error && (
              <div className="bg-destructive/5 border border-destructive/20 rounded-lg px-3 py-2 text-xs text-destructive">
                {error}
              </div>
            )}

            {/* Submit */}
            <Button
              onClick={submit}
              disabled={loading || !username.trim() || !password}
              className="w-full"
            >
              {loading && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              {mode === "login" ? "登录" : "注册"}
            </Button>

            {/* Switch mode */}
            <p className="text-center text-xs text-muted-foreground">
              {mode === "login" ? "还没有账户？" : "已有账户？"}
              <button onClick={switchMode} className="text-primary hover:underline ml-1 font-medium">
                {mode === "login" ? "立即注册" : "去登录"}
              </button>
            </p>
          </div>

          <p className="text-center text-[10px] text-muted-foreground mt-6">
            登录即表示同意服务条款和隐私政策
          </p>
        </div>
      </div>
    </div>
  );
}
