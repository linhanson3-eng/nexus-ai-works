import { createContext, useContext, useState, useCallback, useEffect } from "react";
import type { Artifact } from "./artifacts";

interface ArtifactContextValue {
  artifacts: Artifact[];
  selectedId: string | null;
  selected: Artifact | null;
  count: number;
  rightOpen: boolean;
  setRightOpen: (v: boolean) => void;
  setSelectedId: (id: string | null) => void;
  addArtifact: (a: Artifact) => void;
  removeArtifact: (id: string) => void;
  updateArtifact: (id: string, content: string) => void;
  clearArtifacts: () => void;
}

const ArtifactCtx = createContext<ArtifactContextValue>({
  artifacts: [],
  selectedId: null,
  selected: null,
  count: 0,
  rightOpen: false,
  setRightOpen: () => {},
  setSelectedId: () => {},
  addArtifact: () => {},
  removeArtifact: () => {},
  updateArtifact: () => {},
  clearArtifacts: () => {},
});

export function ArtifactProvider({ children }: { children: React.ReactNode }) {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [rightOpen, setRightOpen] = useState(false);

  const addArtifact = useCallback((a: Artifact) => {
    setArtifacts((prev) => {
      const idx = prev.findIndex((x) => x.id === a.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = a;
        return next;
      }
      return [...prev, a];
    });
  }, []);

  const removeArtifact = useCallback((id: string) => {
    setArtifacts((prev) => prev.filter((a) => a.id !== id));
    setSelectedId((prev) => (prev === id ? null : prev));
  }, []);

  const updateArtifact = useCallback((id: string, content: string) => {
    setArtifacts((prev) =>
      prev.map((a) => (a.id === id ? { ...a, content, size: new Blob([content]).size } : a))
    );
  }, []);

  const clearArtifacts = useCallback(() => {
    setArtifacts([]);
    setSelectedId(null);
  }, []);

  const selected = selectedId ? artifacts.find((a) => a.id === selectedId) ?? null : null;

  // Listen for SSE artifact events from ChatPanel
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail as Artifact;
      addArtifact(detail);
      setRightOpen(true);
      setSelectedId(detail.id);
    };
    window.addEventListener("nexus:artifact", handler);
    return () => window.removeEventListener("nexus:artifact", handler);
  }, [addArtifact]);

  return (
    <ArtifactCtx.Provider
      value={{
        artifacts,
        selectedId,
        selected,
        count: artifacts.length,
        rightOpen,
        setRightOpen,
        setSelectedId,
        addArtifact,
        removeArtifact,
        updateArtifact,
        clearArtifacts,
      }}
    >
      {children}
    </ArtifactCtx.Provider>
  );
}

export function useArtifactContext() {
  return useContext(ArtifactCtx);
}
