import { useState, useCallback } from "react";

export interface Artifact {
  id: string;
  name: string;
  type: "code" | "text" | "markdown" | "json" | "yaml" | "image" | "html" | "css";
  content: string;
  nodeId?: string;
  nodeLabel?: string;
  workspace: string;
  createdAt: string;
  size: number;
}

export function useArtifacts() {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const addArtifact = useCallback((a: Artifact) => {
    setArtifacts((prev) => {
      const existing = prev.findIndex((x) => x.id === a.id);
      if (existing >= 0) {
        const next = [...prev];
        next[existing] = a;
        return next;
      }
      return [...prev, a];
    });
  }, []);

  const removeArtifact = useCallback((id: string) => {
    setArtifacts((prev) => prev.filter((a) => a.id !== id));
    setSelectedId((prev) => (prev === id ? null : prev));
  }, []);

  const clearArtifacts = useCallback(() => {
    setArtifacts([]);
    setSelectedId(null);
  }, []);

  const selected = selectedId ? artifacts.find((a) => a.id === selectedId) ?? null : null;

  return {
    artifacts,
    selected,
    selectedId,
    setSelectedId,
    addArtifact,
    removeArtifact,
    clearArtifacts,
    count: artifacts.length,
  };
}
