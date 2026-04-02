import { useJobs, useCancelJob } from "@/hooks/useApi";
import {
  Clock,
  XCircle,
  CheckCircle,
  Loader2,
  AlertCircle,
} from "lucide-react";
import clsx from "clsx";
import type { JobStatus } from "@/types";
import toast from "react-hot-toast";

const statusIcons: Record<JobStatus, React.ReactNode> = {
  pending: <Clock className="w-4 h-4" />,
  running: <Loader2 className="w-4 h-4 animate-spin" />,
  completed: <CheckCircle className="w-4 h-4" />,
  failed: <AlertCircle className="w-4 h-4" />,
  cancelled: <XCircle className="w-4 h-4" />,
};

const statusColors: Record<JobStatus, string> = {
  pending: "text-yellow-400 bg-yellow-900/20 border-yellow-800",
  running: "text-blue-400 bg-blue-900/20 border-blue-800",
  completed: "text-green-400 bg-green-900/20 border-green-800",
  failed: "text-red-400 bg-red-900/20 border-red-800",
  cancelled: "text-gray-400 bg-gray-800 border-gray-700",
};

export function JobsList() {
  const { data: jobsData, isLoading, error } = useJobs({ limit: 50 });
  const cancelJob = useCancelJob();

  const jobs = jobsData?.items ?? [];

  const handleCancel = async (jobId: string) => {
    try {
      await cancelJob.mutateAsync(jobId);
      toast.success("Job cancelled");
    } catch {
      toast.error("Failed to cancel job");
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card text-center text-red-400">
        <AlertCircle className="w-8 h-8 mx-auto mb-2" />
        <p>Failed to load jobs</p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Jobs</h1>

      {jobs.length === 0 ? (
        <div className="card text-center text-gray-500">
          <p>No jobs yet. Create a new job to get started.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => (
            <div
              key={job.id}
              className="card flex items-center justify-between"
            >
              <div className="flex items-center gap-4">
                <div
                  className={clsx(
                    "p-2 rounded-lg border",
                    statusColors[job.status],
                  )}
                >
                  {statusIcons[job.status]}
                </div>
                <div>
                  <p className="font-medium">{job.problem_type}</p>
                  <p className="text-sm text-gray-500">
                    {job.id.slice(0, 8)}... • {job.created_at}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-4">
                {job.progress > 0 && job.status === "running" && (
                  <div className="w-24">
                    <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary-500 transition-all"
                        style={{ width: `${job.progress * 100}%` }}
                      />
                    </div>
                  </div>
                )}

                <span
                  className={clsx(
                    "px-2 py-1 rounded text-xs font-medium border",
                    statusColors[job.status],
                  )}
                >
                  {job.status}
                </span>

                {(job.status === "pending" || job.status === "running") && (
                  <button
                    onClick={() => handleCancel(job.id)}
                    className="text-gray-400 hover:text-red-400 transition-colors"
                  >
                    <XCircle className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
