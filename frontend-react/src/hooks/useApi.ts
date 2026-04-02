import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { Job, JobCreateRequest, PaginatedResponse } from "@/types";

export function useJobs(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: ["jobs", params],
    queryFn: () => apiClient.getJobs(params),
    refetchInterval: 5000,
  });
}

export function useJob(jobId: string) {
  return useQuery({
    queryKey: ["job", jobId],
    queryFn: () => apiClient.getJob(jobId),
    enabled: !!jobId,
    refetchInterval: (data) => {
      if (
        data?.status === "completed" ||
        data?.status === "failed" ||
        data?.status === "cancelled"
      ) {
        return false;
      }
      return 3000;
    },
  });
}

export function useSubmitJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: JobCreateRequest) => apiClient.submitJob(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useCancelJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (jobId: string) => apiClient.cancelJob(jobId),
    onSuccess: (_, jobId) => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
    },
  });
}

export function useJobResult(jobId: string, enabled: boolean = false) {
  return useQuery({
    queryKey: ["jobResult", jobId],
    queryFn: () => apiClient.getJobResult(jobId),
    enabled,
  });
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => apiClient.getHealth(),
    refetchInterval: 30000,
  });
}

export function useCryptoStatus() {
  return useQuery({
    queryKey: ["cryptoStatus"],
    queryFn: () => apiClient.getCryptoStatus(),
    refetchInterval: 60000,
  });
}

export function useKeys() {
  return useQuery({
    queryKey: ["keys"],
    queryFn: () => apiClient.getKeys(),
  });
}

export function useGenerateKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      keyType,
      securityLevel,
    }: {
      keyType: "kem" | "signing";
      securityLevel?: number;
    }) => apiClient.generateKey(keyType, securityLevel),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["keys"] });
    },
  });
}
