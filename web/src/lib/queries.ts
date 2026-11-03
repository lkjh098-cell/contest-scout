import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { api, buildQuery } from "./api";
import type {
  Analytics,
  Contest,
  ContestDetail,
  ContestStatus,
  Dashboard,
  Facets,
  Paged,
  Project,
  ScoutRun,
  ScoutState,
  Settings,
  SourceOverview,
} from "./types";

export interface ContestFilters {
  q?: string;
  tier?: string[];
  tag?: string[];
  source?: string[];
  status?: string[];
  min_prize?: number;
  deadline_within?: number;
  include_inactive?: boolean;
  only_new_today?: boolean;
  sort?: string;
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

export const keys = {
  dashboard: ["dashboard"] as const,
  contests: (filters: ContestFilters) => ["contests", filters] as const,
  contest: (key: string) => ["contest", key] as const,
  facets: ["facets"] as const,
  scout: ["scout-status"] as const,
  runs: ["runs"] as const,
  sources: ["sources"] as const,
  analytics: ["analytics"] as const,
  settings: ["settings"] as const,
  projects: ["projects"] as const,
};

export function useDashboard() {
  return useQuery({
    queryKey: keys.dashboard,
    queryFn: () => api.get<Dashboard>("/api/dashboard"),
  });
}

export function useContests(filters: ContestFilters, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: keys.contests(filters),
    queryFn: () => api.get<Paged<Contest>>(`/api/contests${buildQuery(filters)}`),
    placeholderData: (previous) => previous,
    enabled: options?.enabled ?? true,
  });
}

export function useContest(key: string | undefined) {
  return useQuery({
    queryKey: keys.contest(key ?? ""),
    queryFn: () => api.get<ContestDetail>(`/api/contests/${encodeURIComponent(key!)}`),
    enabled: Boolean(key),
  });
}

export function useFacets() {
  return useQuery({ queryKey: keys.facets, queryFn: () => api.get<Facets>("/api/contests/facets") });
}

/** Scout이 도는 동안에만 폴링한다. 평소에는 요청하지 않는다.
 *
 * 수집은 30초 넘게 걸리기도 해서 그 사이 다른 탭으로 넘어가는 일이 흔하다.
 * 기본값대로면 탭이 가려진 동안 폴링이 멈춰 돌아왔을 때 "준비 중"에 굳어 있으므로,
 * 이 질의만 배경에서도 계속 돌리고 복귀 시 즉시 한 번 더 읽는다.
 */
export function useScoutStatus(options?: Partial<UseQueryOptions<ScoutState>>) {
  return useQuery<ScoutState>({
    queryKey: keys.scout,
    queryFn: () => api.get<ScoutState>("/api/scout/status"),
    refetchInterval: (query) => (query.state.data?.phase === "running" ? 1500 : false),
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    ...options,
  });
}

export function useRuns() {
  return useQuery({ queryKey: keys.runs, queryFn: () => api.get<ScoutRun[]>("/api/scout/runs") });
}

export function useSources() {
  return useQuery({
    queryKey: keys.sources,
    queryFn: () => api.get<SourceOverview[]>("/api/sources"),
  });
}

export function useAnalytics() {
  return useQuery({ queryKey: keys.analytics, queryFn: () => api.get<Analytics>("/api/analytics") });
}

export function useSettings() {
  return useQuery({ queryKey: keys.settings, queryFn: () => api.get<Settings>("/api/settings") });
}

export function useProjects() {
  return useQuery({
    queryKey: keys.projects,
    queryFn: () => api.get<{ items: Project[]; stages: string[] }>("/api/projects"),
  });
}

// ---------------------------------------------------------------------- //
// 변경
// ---------------------------------------------------------------------- //
export function useRunScout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body?: { sources?: string[]; pages?: number; limit?: number }) =>
      api.post<ScoutState>("/api/scout/run", body ?? {}),
    onSuccess: (state) => {
      client.setQueryData(keys.scout, state);
      void client.invalidateQueries({ queryKey: keys.scout });
    },
  });
}

export function useSetStatus() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ key, status }: { key: string; status: ContestStatus | "SHORTLISTED" }) =>
      api.patch<ContestDetail>(`/api/contests/${encodeURIComponent(key)}/status`, { status }),
    onSuccess: (updated) => {
      client.setQueryData(keys.contest(updated.key), updated);
      void client.invalidateQueries({ queryKey: ["contests"] });
      void client.invalidateQueries({ queryKey: keys.dashboard });
      void client.invalidateQueries({ queryKey: keys.facets });
      void client.invalidateQueries({ queryKey: keys.analytics });
    },
  });
}

export function useStartProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (contestKey: string) =>
      api.post<Project>("/api/projects", { contest_key: contestKey }),
    onSuccess: (project) => {
      void client.invalidateQueries({ queryKey: keys.projects });
      void client.invalidateQueries({ queryKey: keys.contest(project.contest_key) });
      void client.invalidateQueries({ queryKey: ["contests"] });
      void client.invalidateQueries({ queryKey: keys.dashboard });
    },
  });
}

export function useUpdateProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      contestKey,
      ...body
    }: {
      contestKey: string;
      stage?: string;
      next_action?: string;
    }) => api.patch<Project>(`/api/projects/${encodeURIComponent(contestKey)}`, body),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.projects });
      void client.invalidateQueries({ queryKey: ["contests"] });
    },
  });
}

export function useSaveSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.patch<Settings>("/api/settings", body),
    onSuccess: (settings) => {
      client.setQueryData(keys.settings, settings);
      void client.invalidateQueries({ queryKey: ["contests"] });
      void client.invalidateQueries({ queryKey: keys.dashboard });
      void client.invalidateQueries({ queryKey: keys.analytics });
      void client.invalidateQueries({ queryKey: keys.facets });
    },
  });
}
