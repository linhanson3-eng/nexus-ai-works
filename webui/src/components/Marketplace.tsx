import { useState, useEffect, useCallback } from "react";
import { Search, ShoppingBag, Package, X, Clock, Shield, Download, User, LogIn, Tag, Crown } from "lucide-react";
import { api } from "../lib/api";
import type { MarketPackage, MarketSubscription, UserInfo } from "../lib/types";
import { useToast } from "./Toast";

const CATEGORIES = [
  "全部",
  "市场分析",
  "内容创作",
  "代码工具",
  "数据处理",
  "法务合规",
  "营销推广",
  "客服支持",
  "项目管理",
  "金融分析",
  "教育培训",
  "医疗健康",
  "其他",
];

function formatPrice(price: number): string {
  if (price === 0) return "免费";
  return `¥${price.toFixed(2)}`;
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "--";
  return new Date(dateStr).toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

function formatExpiry(dateStr: string): string {
  if (!dateStr) return "--";
  const expiry = new Date(dateStr);
  const now = new Date();
  const diffMs = expiry.getTime() - now.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays <= 0) return "已过期";
  if (diffDays <= 30) return `${diffDays} 天后到期`;
  return formatDate(dateStr);
}

export function Marketplace() {
  const toast = useToast();
  // ── State ──
  const [packages, setPackages] = useState<MarketPackage[]>([]);
  const [selected, setSelected] = useState<MarketPackage | null>(null);
  const [category, setCategory] = useState("全部");
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  // Auth
  const [user, setUser] = useState<UserInfo | null>(null);
  const [token, setToken] = useState<string | null>(null);

  // My tab
  const [tab, setTab] = useState<"browse" | "my">("browse");
  const [mySubs, setMySubs] = useState<MarketSubscription[]>([]);
  const [subsLoading, setSubsLoading] = useState(false);

  // Login modal
  const [loginOpen, setLoginOpen] = useState(false);
  const [loginUser, setLoginUser] = useState("");
  const [loginPass, setLoginPass] = useState("");
  const [loginMode, setLoginMode] = useState<"login" | "register">("login");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loginLoading, setLoginLoading] = useState(false);

  // Detail modal
  const [detailOpen, setDetailOpen] = useState(false);

  // ── Load catalog ──
  const loadCatalog = useCallback(async () => {
    setLoading(true);
    try {
      const cat = category === "全部" ? "" : category;
      const data = await api.marketCatalog(cat);
      setPackages(data);
    } catch {
      setPackages([]);
    } finally {
      setLoading(false);
    }
  }, [category]);

  useEffect(() => {
    loadCatalog();
  }, [loadCatalog]);

  // ── Load my subscriptions ──
  const loadMySubs = useCallback(async () => {
    if (!token) return;
    setSubsLoading(true);
    try {
      const data = await api.marketMy(token);
      setMySubs(data);
    } catch {
      setMySubs([]);
    } finally {
      setSubsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (tab === "my" && token) {
      loadMySubs();
    }
  }, [tab, token, loadMySubs]);

  // ── Auth actions ──
  const handleLogin = async () => {
    setLoginError(null);
    setLoginLoading(true);
    try {
      const fn = loginMode === "login" ? api.marketLogin : api.marketRegister;
      const result = await fn(loginUser, loginPass);
      setToken(result.token);
      setUser(result.user);
      setLoginOpen(false);
      setLoginUser("");
      setLoginPass("");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setLoginError(msg);
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = () => {
    setToken(null);
    setUser(null);
    setMySubs([]);
    setTab("browse");
  };

  // ── Install ──
  const handleInstall = async (pkg: MarketPackage) => {
    if (!token) {
      setDetailOpen(false);
      setLoginOpen(true);
      return;
    }
    try {
      await api.marketInstall(pkg.id, token);
      toast.success(`"${pkg.name}" 安装成功！`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`安装失败: ${msg}`);
    }
  };

  // ── Open detail ──
  const openDetail = (pkg: MarketPackage) => {
    setSelected(pkg);
    setDetailOpen(true);
  };

  // ── Filter by search ──
  const filteredPackages = packages.filter((p) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      p.name.toLowerCase().includes(q) ||
      p.description.toLowerCase().includes(q) ||
      p.tags.some((t) => t.toLowerCase().includes(q))
    );
  });

  // ── Render ──
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">解决方案</h1>
          <p className="text-muted text-sm mt-1">浏览、购买和安装解决方案包</p>
        </div>

        {/* Auth section */}
        <div className="flex items-center gap-3">
          {user ? (
            <div className="flex items-center gap-3">
              {user.is_vip && (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-accent/15 border border-accent/30 text-accent text-xs font-semibold">
                  <Crown className="w-3 h-3" />
                  VIP
                </span>
              )}
              <span className="text-sm text-white font-medium">{user.username}</span>
              <button
                onClick={handleLogout}
                className="text-xs text-muted hover:text-warning transition-colors"
              >
                退出
              </button>
            </div>
          ) : (
            <button
              onClick={() => setLoginOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors"
            >
              <LogIn className="w-3.5 h-3.5" />
              登录
            </button>
          )}
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex items-center gap-1 p-1 bg-card rounded-xl border border-border w-fit">
        <button
          onClick={() => setTab("browse")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === "browse"
              ? "bg-accent/15 text-accent border border-accent/20"
              : "text-muted hover:text-white"
          }`}
        >
          浏览
        </button>
        <button
          onClick={() => {
            if (!token) {
              setLoginOpen(true);
              return;
            }
            setTab("my");
          }}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === "my"
              ? "bg-accent/15 text-accent border border-accent/20"
              : "text-muted hover:text-white"
          }`}
        >
          我的
        </button>
      </div>

      {/* ── Browse Tab ── */}
      {tab === "browse" && (
        <>
          {/* Search */}
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
            <input
              type="text"
              placeholder="搜索方案..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 bg-card border border-border rounded-xl text-white placeholder-muted text-sm focus:outline-none focus:border-accent/40 transition-colors"
            />
          </div>

          {/* Category chips */}
          <div className="flex flex-wrap gap-2">
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => setCategory(cat)}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  category === cat
                    ? "bg-accent text-black"
                    : "bg-card border border-border text-muted hover:text-white hover:border-border-hover"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          {/* Package grid */}
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className="bg-card rounded-[20px] border border-border p-5 h-44 animate-pulse"
                />
              ))}
            </div>
          ) : filteredPackages.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 gap-4">
              <div className="w-14 h-14 rounded-2xl bg-card border border-border flex items-center justify-center">
                <Package className="w-7 h-7 text-muted" />
              </div>
              <div className="text-center">
                <p className="text-white font-semibold">暂无方案</p>
                <p className="text-sm text-muted mt-1">
                  {search ? "没有匹配的搜索结果" : "该分类下暂无可用方案"}
                </p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredPackages.map((pkg) => (
                <button
                  key={pkg.id}
                  onClick={() => openDetail(pkg)}
                  className="bg-card rounded-[20px] border border-border p-5 text-left hover:bg-card-hover hover:border-border-hover transition-all group relative overflow-hidden"
                >
                  {/* Top accent bar */}
                  <div className="absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r from-accent/40 via-accent/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center flex-shrink-0">
                        <ShoppingBag className="w-5 h-5 text-accent" />
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-semibold text-white text-sm truncate group-hover:text-accent transition-colors">
                          {pkg.name}
                        </h3>
                        <p className="text-xs text-muted">{pkg.author}</p>
                      </div>
                    </div>
                    <span className="text-[10px] px-2 py-0.5 rounded-md bg-accent/10 text-accent font-medium flex-shrink-0">
                      v{pkg.version}
                    </span>
                  </div>

                  <p className="text-sm text-muted line-clamp-2 mb-3 leading-relaxed">
                    {pkg.description}
                  </p>

                  <div className="flex items-center justify-between">
                    <div className="flex flex-wrap gap-1">
                      {pkg.tags.slice(0, 3).map((t) => (
                        <span
                          key={t}
                          className="text-[10px] px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-400"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-bold text-accent">
                        {formatPrice(pkg.plan_monthly_price)}
                      </div>
                      <div className="text-[10px] text-muted">
                        {pkg.plan_monthly_price > 0 ? "/月" : ""}
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </>
      )}

      {/* ── My Tab ── */}
      {tab === "my" && (
        <>
          {subsLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="bg-card rounded-[20px] border border-border p-5 h-20 animate-pulse"
                />
              ))}
            </div>
          ) : mySubs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 gap-4">
              <div className="w-14 h-14 rounded-2xl bg-card border border-border flex items-center justify-center">
                <Download className="w-7 h-7 text-muted" />
              </div>
              <div className="text-center">
                <p className="text-white font-semibold">暂无已购方案</p>
                <p className="text-sm text-muted mt-1">前往浏览标签页发现方案</p>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {mySubs.map((sub) => {
                const isExpired = new Date(sub.expires_at).getTime() < Date.now();
                return (
                  <div
                    key={sub.package_id}
                    className={`bg-card rounded-[20px] border p-5 flex items-center justify-between transition-colors ${
                      isExpired ? "border-warning/20 opacity-60" : "border-border hover:bg-card-hover"
                    }`}
                  >
                    <div className="flex items-center gap-4">
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                        isExpired ? "bg-warning/10" : "bg-accent/10"
                      }`}>
                        <Package className={`w-5 h-5 ${isExpired ? "text-warning" : "text-accent"}`} />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold text-white text-sm">{sub.name}</h3>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
                            v{sub.version}
                          </span>
                          {isExpired && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-warning/10 text-warning font-medium">
                              已过期
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 mt-1">
                          <span className="text-xs text-muted flex items-center gap-1">
                            <Tag className="w-3 h-3" />
                            {sub.category}
                          </span>
                          <span className="text-xs text-muted flex items-center gap-1">
                            <Shield className="w-3 h-3" />
                            {sub.plan_type === "monthly" ? "月付" : sub.plan_type === "yearly" ? "年付" : sub.plan_type}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <div className="flex items-center gap-1.5 text-xs text-muted">
                        <Clock className="w-3 h-3" />
                        {formatExpiry(sub.expires_at)}
                      </div>
                      <p className="text-[10px] text-muted mt-0.5">
                        购买于 {formatDate(sub.created_at)}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* ── Login Modal ── */}
      {loginOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => {
              setLoginOpen(false);
              setLoginError(null);
            }}
          />

          {/* Modal */}
          <div className="relative bg-card border border-border rounded-[20px] p-6 w-full max-w-sm mx-4 shadow-2xl animate-in zoom-in">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-bold text-white">
                {loginMode === "login" ? "登录解决方案" : "注册账号"}
              </h2>
              <button
                onClick={() => {
                  setLoginOpen(false);
                  setLoginError(null);
                }}
                className="w-7 h-7 rounded-lg flex items-center justify-center text-muted hover:text-white hover:bg-white/5 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Tab switcher */}
            <div className="flex gap-1 p-1 bg-surface rounded-lg mb-4">
              <button
                onClick={() => { setLoginMode("login"); setLoginError(null); }}
                className={`flex-1 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  loginMode === "login"
                    ? "bg-accent/15 text-accent"
                    : "text-muted hover:text-white"
                }`}
              >
                登录
              </button>
              <button
                onClick={() => { setLoginMode("register"); setLoginError(null); }}
                className={`flex-1 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  loginMode === "register"
                    ? "bg-accent/15 text-accent"
                    : "text-muted hover:text-white"
                }`}
              >
                注册
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs text-muted mb-1.5 font-medium">用户名</label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
                  <input
                    type="text"
                    value={loginUser}
                    onChange={(e) => setLoginUser(e.target.value)}
                    placeholder="请输入用户名"
                    className="w-full pl-10 pr-4 py-2.5 bg-surface border border-border rounded-xl text-white placeholder-muted text-sm focus:outline-none focus:border-accent/40 transition-colors"
                    onKeyDown={(e) => e.key === "Enter" && handleLogin()}
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs text-muted mb-1.5 font-medium">密码</label>
                <input
                  type="password"
                  value={loginPass}
                  onChange={(e) => setLoginPass(e.target.value)}
                  placeholder="请输入密码"
                  className="w-full px-4 py-2.5 bg-surface border border-border rounded-xl text-white placeholder-muted text-sm focus:outline-none focus:border-accent/40 transition-colors"
                  onKeyDown={(e) => e.key === "Enter" && handleLogin()}
                />
              </div>

              {loginError && (
                <p className="text-xs text-warning bg-warning/5 border border-warning/10 rounded-lg px-3 py-2">
                  {loginError}
                </p>
              )}

              <button
                onClick={handleLogin}
                disabled={loginLoading || !loginUser.trim() || !loginPass.trim()}
                className="w-full py-2.5 bg-accent text-black rounded-xl text-sm font-semibold hover:bg-accent/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {loginLoading ? "请稍候..." : loginMode === "login" ? "登录" : "注册"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Detail Modal ── */}
      {detailOpen && selected && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh]">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setDetailOpen(false)}
          />

          {/* Modal */}
          <div className="relative bg-card border border-border rounded-[20px] w-full max-w-lg mx-4 shadow-2xl animate-in zoom-in max-h-[80vh] overflow-y-auto">
            {/* Gradient top bar */}
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-accent/60 via-accent/30 to-transparent" />

            <div className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center flex-shrink-0">
                    <ShoppingBag className="w-6 h-6 text-accent" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-white">{selected.name}</h2>
                    <p className="text-sm text-muted">{selected.author}</p>
                  </div>
                </div>
                <button
                  onClick={() => setDetailOpen(false)}
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-muted hover:text-white hover:bg-white/5 transition-colors flex-shrink-0"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Tags */}
              <div className="flex flex-wrap gap-1.5 mb-4">
                <span className="text-[10px] px-2 py-0.5 rounded-md bg-accent/10 text-accent font-medium">
                  {selected.category}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-400">
                  v{selected.version}
                </span>
                {selected.tags.map((t) => (
                  <span
                    key={t}
                    className="text-[10px] px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-400"
                  >
                    {t}
                  </span>
                ))}
              </div>

              {/* Description */}
              <div className="mb-5">
                <h3 className="text-xs uppercase tracking-widest text-muted font-medium mb-2">方案详情</h3>
                <p className="text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap">
                  {selected.long_description || selected.description}
                </p>
              </div>

              {/* Meta info */}
              <div className="grid grid-cols-2 gap-3 mb-5">
                <div className="bg-surface rounded-xl p-3">
                  <div className="flex items-center gap-1.5 text-xs text-muted mb-1">
                    <Download className="w-3.5 h-3.5" />
                    下载量
                  </div>
                  <p className="text-sm font-semibold text-white">{selected.download_count.toLocaleString()}</p>
                </div>
                <div className="bg-surface rounded-xl p-3">
                  <div className="flex items-center gap-1.5 text-xs text-muted mb-1">
                    <Package className="w-3.5 h-3.5" />
                    包大小
                  </div>
                  <p className="text-sm font-semibold text-white">
                    {selected.package_size > 1024 * 1024
                      ? `${(selected.package_size / (1024 * 1024)).toFixed(1)} MB`
                      : `${(selected.package_size / 1024).toFixed(0)} KB`}
                  </p>
                </div>
              </div>

              {/* Pricing */}
              <div className="bg-surface rounded-xl p-4 mb-5 border border-border">
                <h3 className="text-xs uppercase tracking-widest text-muted font-medium mb-3">价格方案</h3>
                <div className="flex gap-3">
                  <div className="flex-1 bg-card rounded-xl p-3 border border-border">
                    <p className="text-[10px] uppercase tracking-wider text-muted mb-1">月付</p>
                    <p className="text-lg font-bold text-accent">
                      {selected.plan_monthly_price === 0 ? "免费" : `¥${selected.plan_monthly_price.toFixed(2)}`}
                    </p>
                    {selected.plan_monthly_price > 0 && (
                      <p className="text-[10px] text-muted mt-0.5">/月</p>
                    )}
                  </div>
                  <div className="flex-1 bg-card rounded-xl p-3 border border-accent/20 relative overflow-hidden">
                    <div className="absolute top-0 right-0">
                      <div className="bg-accent text-black text-[9px] font-bold px-2 py-0.5 rounded-bl-lg">
                        省{(selected.plan_monthly_price * 12 - selected.plan_yearly_price).toFixed(2)}
                      </div>
                    </div>
                    <p className="text-[10px] uppercase tracking-wider text-muted mb-1">年付</p>
                    <p className="text-lg font-bold text-accent">
                      {selected.plan_yearly_price === 0 ? "免费" : `¥${selected.plan_yearly_price.toFixed(2)}`}
                    </p>
                    {selected.plan_yearly_price > 0 && (
                      <p className="text-[10px] text-muted mt-0.5">/年</p>
                    )}
                  </div>
                </div>
              </div>

              {/* Action */}
              <button
                onClick={() => handleInstall(selected)}
                className="w-full py-3 bg-accent text-black rounded-xl text-sm font-semibold hover:bg-accent/90 transition-colors flex items-center justify-center gap-2"
              >
                <Download className="w-4 h-4" />
                {token ? "安装方案" : "登录后安装"}
              </button>

              {!token && (
                <p className="text-xs text-muted text-center mt-2">
                  需要登录解决方案账号才能安装
                </p>
              )}

              {/* Creation date */}
              <p className="text-[10px] text-muted text-center mt-3">
                创建于 {formatDate(selected.created_at)} · 更新于 {formatDate(selected.updated_at)}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
