import { useState, useRef, useCallback } from "react";
import { getAuthHeaders } from "../lib/api";

export interface RunStatus {
  status: string;
  detail: string;
}

export interface RunResult {
  status: string;
  final_output: string;
  node_results: Record<
    string,
    { node_id: string; agent_name: string; status: string; output: string; error: string }
  >;
}

interface ToastLike {
  error: (msg: string) => void;
  success: (msg: string) => void;
}

interface Options {
  workflowName: string;
  workspace: string;
  saveTemplate: () => Promise<boolean>;
  toast: ToastLike;
}

export function useWorkflowExecution({ workflowName, workspace, saveTemplate, toast }: Options) {
  const [running, setRunning] = useState(false);
  const [runStatus, setRunStatus] = useState<Record<string, RunStatus>>({});
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  const [showRunDialog, setShowRunDialog] = useState(false);
  const [task, setTask] = useState("");
  const [runWorkspace, setRunWorkspace] = useState("");
  const [executingNode, setExecutingNode] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const execute = useCallback(async () => {
    if (!workflowName.trim() || !task.trim()) return;

    const saved = await saveTemplate();
    if (!saved) {
      toast.error("请先保存工作流");
      return;
    }

    setRunning(true);
    setRunStatus({});
    setRunResult(null);
    setShowRunDialog(false);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(
        `/api/workflows/${encodeURIComponent(workflowName)}/execute`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", ...getAuthHeaders() },
          credentials: "include",
          body: JSON.stringify({
            task: task.trim(),
            workshop: runWorkspace || workspace,
          }),
          signal: controller.signal,
        }
      );

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "执行失败");
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response stream");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        let eventName = "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventName = line.slice(7).trim();
          } else if (line.startsWith("data: ") && eventName) {
            try {
              const data = JSON.parse(line.slice(6));
              if (eventName === "node_status") {
                setRunStatus((prev) => ({
                  ...prev,
                  [data.node_id]: { status: data.status, detail: data.detail },
                }));
              } else if (eventName === "completed") {
                setRunResult(data);
              } else if (eventName === "error") {
                toast.error(data.message || "执行出错");
              }
            } catch {
              /* skip malformed SSE */
            }
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        toast.error(err instanceof Error ? err.message : "执行失败");
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }, [workflowName, workspace, runWorkspace, task, saveTemplate, toast]);

  const executeSingleNode = useCallback(
    async (_nodeId: string) => {
      if (!workflowName.trim()) return;

      const saved = await saveTemplate();
      if (!saved) {
        toast.error("请先保存工作流");
        setExecutingNode(null);
        return;
      }

      setExecutingNode(_nodeId);
      toast.success("将通过完整执行来测试此节点");
      setExecutingNode(null);
    },
    [workflowName, saveTemplate, toast]
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setRunning(false);
  }, []);

  return {
    running,
    runStatus,
    setRunStatus,
    runResult,
    showRunDialog,
    setShowRunDialog,
    task,
    setTask,
    runWorkspace,
    setRunWorkspace,
    executingNode,
    execute,
    executeSingleNode,
    cancel,
  };
}
