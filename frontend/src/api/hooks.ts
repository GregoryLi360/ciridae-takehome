import { useMutation, useQuery } from "@tanstack/react-query";
import type { JobResponse, ItemsResponse } from "./types";

async function createJob(files: { jdr: File; insurance: File }) {
  const form = new FormData();
  form.append("jdr", files.jdr);
  form.append("insurance", files.insurance);
  const res = await fetch("/api/jobs", { method: "POST", body: form });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return (await res.json()) as JobResponse;
}

export function useCreateJob() {
  return useMutation({ mutationFn: createJob });
}

export function useJobStatus(jobId: string | null) {
  return useQuery({
    queryKey: ["job", jobId],
    queryFn: async () => {
      const res = await fetch(`/api/jobs/${jobId}`);
      if (!res.ok) throw new Error(`Poll failed: ${res.status}`);
      return (await res.json()) as JobResponse;
    },
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "complete" || status === "error") return false;
      return 2000;
    },
  });
}

export function useJobItems(jobId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["job-items", jobId],
    queryFn: async () => {
      const res = await fetch(`/api/jobs/${jobId}/items`);
      if (!res.ok) throw new Error(`Items failed: ${res.status}`);
      return (await res.json()) as ItemsResponse;
    },
    enabled: !!jobId && enabled,
  });
}
