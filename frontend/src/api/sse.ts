import { fetchEventSource } from "@microsoft/fetch-event-source";
import { notifications } from "@mantine/notifications";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useAuth, useUi } from "../stores";
import { api, API_BASE } from "./client";
import { invalidateData } from "./hooks";
import type { Job, JobStep } from "./types";

class Retry extends Error {}

/** Global live updates: data_changed → invalidate queries (throttled). Mount once. */
export function useLiveEvents(onInsightsReady?: (runId: number) => void) {
  const token = useAuth((s) => s.token);
  const qc = useQueryClient();
  const { setLive, touch } = useUi.getState();
  const readyRef = useRef(onInsightsReady);
  readyRef.current = onInsightsReady;

  useEffect(() => {
    if (!token) return;
    const ctrl = new AbortController();
    let pending: string | undefined;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let lastRun = 0;
    const flush = () => {
      timer = null;
      lastRun = Date.now();
      invalidateData(qc, pending);
      pending = undefined;
      touch();
    };
    const schedule = (entity?: string) => {
      pending = pending && pending !== entity ? undefined : entity;
      if (timer) return;
      const wait = Math.max(0, 1500 - (Date.now() - lastRun));
      timer = setTimeout(flush, wait);
    };
    let backoff = 1000;
    fetchEventSource(`${API_BASE}/events/stream`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: ctrl.signal,
      openWhenHidden: true,
      async onopen(res) {
        if (res.ok) {
          setLive("connected");
          backoff = 1000;
          return;
        }
        throw new Retry();
      },
      onmessage(msg) {
        if (!msg.event || msg.event === "ping") return;
        const data = msg.data ? JSON.parse(msg.data) : {};
        if (msg.event === "data_changed") schedule(data.entity);
        if (msg.event === "job_finished") {
          if (data.type === "INSIGHTS_RUN") {
            ["insightsLatest", "insightRuns", "insightsRunning", "dashboard", "plans"].forEach((k) =>
              qc.invalidateQueries({ queryKey: [k] }));
            if (data.result_id && !data.failed) readyRef.current?.(data.result_id);
          } else {
            qc.invalidateQueries({ queryKey: ["chatSession"] });
          }
        }
        if (msg.event === "ai_status") qc.invalidateQueries({ queryKey: ["aiStatus"] });
      },
      onerror() {
        setLive("offline");
        backoff = Math.min(backoff * 2, 30000);
        return backoff;
      },
      onclose() {
        setLive("offline");
        throw new Retry();
      },
    }).catch(() => setLive("offline"));
    return () => {
      ctrl.abort();
      if (timer) clearTimeout(timer);
    };
  }, [token, qc, setLive, touch]);
}

export interface JobProgress {
  status: Job["status"] | null;
  steps: JobStep[];
  currentTool: string | null;
  error: string | null;
  resultId: number | null;
}

/** Follow one job over SSE (falls back to polling if the stream drops). */
export function useJobEvents(jobId: string | null | undefined, onDone?: (p: JobProgress) => void): JobProgress {
  const token = useAuth((s) => s.token);
  const [state, setState] = useState<JobProgress>({ status: null, steps: [], currentTool: null, error: null, resultId: null });
  const doneRef = useRef(onDone);
  doneRef.current = onDone;

  useEffect(() => {
    if (!jobId || !token) return;
    setState({ status: "QUEUED", steps: [], currentTool: null, error: null, resultId: null });
    const ctrl = new AbortController();
    let finished = false;
    let poll: ReturnType<typeof setInterval> | null = null;

    const finish = (p: JobProgress) => {
      if (finished) return;
      finished = true;
      setState(p);
      doneRef.current?.(p);
      ctrl.abort();
      if (poll) clearInterval(poll);
    };
    const applyJob = (j: Job) => {
      const p: JobProgress = { status: j.status, steps: j.steps, currentTool: null, error: j.error, resultId: j.result_id };
      if (j.status === "SUCCEEDED" || j.status === "FAILED") finish(p);
      else setState((s) => ({ ...p, currentTool: s.currentTool }));
    };
    const startPolling = () => {
      if (poll || finished) return;
      poll = setInterval(() => {
        api<Job>(`/jobs/${jobId}`).then(applyJob).catch(() => undefined);
      }, 3000);
    };

    fetchEventSource(`${API_BASE}/jobs/${jobId}/events`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: ctrl.signal,
      openWhenHidden: true,
      async onopen(res) {
        if (!res.ok) throw new Error("stream failed");
      },
      onmessage(msg) {
        if (!msg.event || !msg.data) return;
        const data = JSON.parse(msg.data);
        if (msg.event === "snapshot") applyJob(data as Job);
        else if (msg.event === "step") {
          setState((s) => ({
            ...s,
            status: "RUNNING",
            steps: s.steps.map((st) => (st.key === data.key ? { ...st, ...data } : st)),
            currentTool: data.status === "RUNNING" ? null : s.currentTool,
          }));
        } else if (msg.event === "tool") setState((s) => ({ ...s, currentTool: data.label }));
        else if (msg.event === "done") {
          api<Job>(`/jobs/${jobId}`).then(applyJob).catch(() =>
            finish({ status: "SUCCEEDED", steps: [], currentTool: null, error: null, resultId: data.result_id }));
        } else if (msg.event === "error") {
          setState((s) => {
            const p = { ...s, status: "FAILED" as const, error: data.message };
            finish(p);
            return p;
          });
        }
      },
      onerror() {
        startPolling();
        throw new Error("stop");
      },
      onclose() {
        if (!finished) startPolling();
      },
    }).catch(() => startPolling());

    return () => {
      finished = true;
      ctrl.abort();
      if (poll) clearInterval(poll);
    };
  }, [jobId, token]);

  return state;
}

export function notifyInsightsReady(onView: () => void) {
  notifications.show({
    id: "insights-ready",
    color: "gold",
    title: "✨ Your AI insights are ready",
    message: "Click to open the Insights page.",
    autoClose: 8000,
    onClick: onView,
    style: { cursor: "pointer" },
  });
}
