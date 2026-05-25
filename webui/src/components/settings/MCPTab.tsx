import { useState, useEffect } from "react";
import { Copy, Check, Trash2, RefreshCw } from "lucide-react";
import { api, issueMCPToken, revokeMCPToken, type MCPTokenResponse } from "../../lib/api";

interface MCPTabProps {
  toast: { show: (message: string, type?: "success" | "error") => void };
}

export function MCPTab({ toast }: MCPTabProps) {
  const [workshops, setWorkshops] = useState<{ name: string }[]>([]);
  const [selectedWorkshop, setSelectedWorkshop] = useState("");
  const [tokenData, setTokenData] = useState<MCPTokenResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.listWorkshops().then(setWorkshops).catch(() => {});
  }, []);

  async function handleGenerate() {
    if (!selectedWorkshop) return;
    setLoading(true);
    try {
      const data = await issueMCPToken(selectedWorkshop);
      setTokenData(data);
      toast.show("MCP Token 已生成", "success");
    } catch {
      toast.show("生成 Token 失败", "error");
    } finally {
      setLoading(false);
    }
  }

  async function handleRevoke() {
    if (!tokenData) return;
    try {
      const parts = tokenData.token.split(".");
      if (parts.length !== 3) return;
      const header = JSON.parse(atob(parts[0]));
      const payload = JSON.parse(atob(parts[1]));
      const jti = payload.jti;
      if (!jti) return;
      await revokeMCPToken(jti);
      setTokenData(null);
      toast.show("Token 已吊销", "success");
    } catch {
      toast.show("吊销失败", "error");
    }
  }

  function handleCopy() {
    if (!tokenData) return;
    navigator.clipboard.writeText(tokenData.token);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const curlExample = tokenData
    ? `curl -X POST ${window.location.origin}/mcp \\
  -H "Authorization: Bearer ${tokenData.token.slice(0, 30)}..." \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'`
    : "";

  const mcpConfig = tokenData
    ? JSON.stringify({
        mcpServers: {
          "nexus-ai-works": {
            type: "streamable-http",
            url: `${window.location.origin}/mcp`,
            headers: {
              Authorization: `Bearer ${tokenData.token}`,
            },
          },
        },
      }, null, 2)
    : "";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">MCP 连接</h2>
        <p className="text-muted-foreground text-sm mt-1">
          生成 MCP (Model Context Protocol) Token，让 AI Agent 通过标准协议连接 ai-factory 平台。
        </p>
      </div>

      <div className="flex items-end gap-3">
        <div className="flex-1">
          <label className="block text-sm font-medium mb-1.5">选择工作区</label>
          <select
            value={selectedWorkshop}
            onChange={(e) => setSelectedWorkshop(e.target.value)}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          >
            <option value="">-- 选择工作区 --</option>
            {workshops.map((w) => (
              <option key={w.name} value={w.name}>{w.name}</option>
            ))}
          </select>
        </div>
        <button
          onClick={handleGenerate}
          disabled={!selectedWorkshop || loading}
          className="flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          生成 Token
        </button>
      </div>

      {tokenData && (
        <div className="space-y-4">
          <div className="bg-card border border-border rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Token</span>
              <div className="flex gap-2">
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied ? "已复制" : "复制"}
                </button>
                <button
                  onClick={handleRevoke}
                  className="flex items-center gap-1 text-xs text-red-500 hover:text-red-600"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  吊销
                </button>
              </div>
            </div>
            <code className="block text-xs bg-muted rounded-lg p-3 break-all font-mono">
              {tokenData.token}
            </code>
            <div className="text-xs text-muted-foreground">
              工作区: {tokenData.workshop_name} · 会话: {tokenData.session_id}
            </div>
          </div>

          <div className="bg-card border border-border rounded-xl p-4 space-y-2">
            <span className="text-sm font-medium">curl 示例</span>
            <pre className="text-xs bg-muted rounded-lg p-3 overflow-x-auto font-mono">
              {curlExample}
            </pre>
          </div>

          <div className="bg-card border border-border rounded-xl p-4 space-y-2">
            <span className="text-sm font-medium">Claude Code MCP 配置</span>
            <p className="text-xs text-muted-foreground">
              将以下 JSON 添加到 Claude Code 的 MCP 配置文件中:
            </p>
            <pre className="text-xs bg-muted rounded-lg p-3 overflow-x-auto font-mono">
              {mcpConfig}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
