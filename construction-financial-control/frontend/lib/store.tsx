"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, getToken, type Project, type User } from "@/lib/api";

type AppState = {
  user: User | null;
  projects: Project[];
  project: Project | null;
  loading: boolean;
  selectProject: (id: number) => void;
  refreshProjects: () => Promise<void>;
};

const AppContext = createContext<AppState | null>(null);

const PROJECT_KEY = "cfcs_project_id";

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshProjects = useCallback(async () => {
    const list = await api<Project[]>("/projects");
    setProjects(list);
    setProjectId((current) => {
      if (current && list.some((p) => p.id === current)) return current;
      let saved: number | null = null;
      try {
        saved = Number(localStorage.getItem(PROJECT_KEY)) || null;
      } catch {
        /* ignore */
      }
      if (saved && list.some((p) => p.id === saved)) return saved;
      return list[0]?.id ?? null;
    });
  }, []);

  useEffect(() => {
    if (!getToken()) {
      window.location.href = "/login";
      return;
    }
    (async () => {
      try {
        const [me] = await Promise.all([api<User>("/auth/me"), refreshProjects()]);
        setUser(me);
      } finally {
        setLoading(false);
      }
    })();
  }, [refreshProjects]);

  const selectProject = useCallback((id: number) => {
    setProjectId(id);
    try {
      localStorage.setItem(PROJECT_KEY, String(id));
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo<AppState>(
    () => ({
      user,
      projects,
      project: projects.find((p) => p.id === projectId) ?? null,
      loading,
      selectProject,
      refreshProjects,
    }),
    [user, projects, projectId, loading, selectProject, refreshProjects],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppState {
  const context = useContext(AppContext);
  if (!context) throw new Error("useApp outside AppProvider");
  return context;
}
