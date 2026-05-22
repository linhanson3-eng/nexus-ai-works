import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Zap, Loader2, Eye, EyeOff } from "lucide-react";
import { useAuth } from "../lib/AuthContext";

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

  // Redirect if already logged in
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
      if (msg.includes("401") || msg.includes("Unauthorized")) {
        setError("用户名或密码错误");
      } else if (msg.includes("409") || msg.includes("Conflict")) {
        setError("用户名已存在，请直接登录");
      } else if (msg.includes("422")) {
        setError("用户名或密码格式不符合要求");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  const switchMode = () => {
    setMode(m => (m === "login" ? "register" : "login"));
    setError("");
    setPassword("");
  };

  return (
    <div className="flex items-center justify-center h-full min-h-[400px]">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-accent/20 flex items-center justify-center mx-auto mb-4">
            <Zap className="w-6 h-6 text-accent" />
          </div>
          <h1 className="text-xl font-black tracking-tight text-white">Nexus AI Works</h1>
          <p className="text-sm text-muted mt-2">
            {mode === "login" ? "登录你的账户" : "创建新账户"}
          </p>
        </div>

        <div className="bg-card border border-border rounded-[20px] p-6 space-y-4">
          {/* Mode tabs */}
          <div className="flex bg-surface rounded-xl p-1">
            <button
              onClick={() => setMode("login")}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                mode === "login"
                  ? "bg-accent/10 text-accent border border-accent/20"
                  : "text-muted hover:text-white"
              }`}
            >
              登录
            </button>
            <button
              onClick={() => setMode("register")}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                mode === "register"
                  ? "bg-accent/10 text-accent border border-accent/20"
                  : "text-muted hover:text-white"
              }`}
            >
              注册
            </button>
          </div>

          {/* Username */}
          <div>
            <label className="text-[10px] uppercase tracking-widest text-muted">用户名</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              onKeyDown={e => e.key === "Enter" && submit()}
              placeholder="输入用户名"
              autoFocus
              autoComplete="username"
              className="w-full bg-surface border border-border rounded-xl px-3 py-2.5 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 mt-1"
            />
          </div>

          {/* Password */}
          <div>
            <label className="text-[10px] uppercase tracking-widest text-muted">密码</label>
            <div className="relative mt-1">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={e => setPassword(e.target.value)}
                onKeyDown={e => e.key === "Enter" && submit()}
                placeholder="输入密码"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                className="w-full bg-surface border border-border rounded-xl px-3 py-2.5 pr-10 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30"
              />
              <button
                type="button"
                onClick={() => setShowPassword(p => !p)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-white transition-colors"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {mode === "register" && (
              <p className="text-[10px] text-muted mt-1">至少 6 个字符</p>
            )}
          </div>

          {/* Error */}
          {error && (
            <div className="bg-warning/5 border border-warning/20 rounded-xl px-3 py-2 text-xs text-warning">
              {error}
            </div>
          )}

          {/* Submit */}
          <button
            onClick={submit}
            disabled={loading || !username.trim() || !password}
            className="w-full py-2.5 bg-accent text-black rounded-xl text-sm font-semibold hover:bg-amber-400 transition-colors disabled:opacity-30 flex items-center justify-center gap-2"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            {mode === "login" ? "登录" : "注册"}
          </button>

          {/* Switch mode */}
          <p className="text-center text-xs text-muted">
            {mode === "login" ? "还没有账户？" : "已有账户？"}
            <button onClick={switchMode} className="text-accent hover:underline ml-1">
              {mode === "login" ? "立即注册" : "去登录"}
            </button>
          </p>
        </div>

        <p className="text-center text-[10px] text-muted mt-6">
          登录即表示同意服务条款和隐私政策
        </p>
      </div>
    </div>
  );
}
