import { useJobs, useHealth, useCryptoStatus } from "@/hooks/useApi";
import {
  Activity,
  Cpu,
  Shield,
  AlertTriangle,
  CheckCircle,
  Clock,
} from "lucide-react";
import clsx from "clsx";
import type { JobStatus } from "@/types";

const statusColors: Record<JobStatus, string> = {
  pending: "bg-yellow-900/50 text-yellow-400 border-yellow-800",
  running: "bg-blue-900/50 text-blue-400 border-blue-800",
  completed: "bg-green-900/50 text-green-400 border-green-800",
  failed: "bg-red-900/50 text-red-400 border-red-800",
  cancelled: "bg-gray-800 text-gray-400 border-gray-700",
};

export function Dashboard() {
  const { data: jobsData, isLoading: jobsLoading } = useJobs({ limit: 10 });
  const { data: health } = useHealth();
  const { data: cryptoStatus } = useCryptoStatus();

  const jobs = jobsData?.items ?? [];
  const runningJobs = jobs.filter((j) => j.status === "running").length;
  const completedJobs = jobs.filter((j) => j.status === "completed").length;
  const failedJobs = jobs.filter((j) => j.status === "failed").length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <div className="flex items-center gap-2">
          {health?.status === "healthy" ? (
            <span className="flex items-center gap-1 text-green-400 text-sm">
              <CheckCircle className="w-4 h-4" />
              System Healthy
            </span>
          ) : (
            <span className="flex items-center gap-1 text-yellow-400 text-sm">
              <AlertTriangle className="w-4 h-4" />
              System Degraded
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-blue-900/50 rounded-lg">
              <Activity className="w-6 h-6 text-blue-400" />
            </div>
            <div>
              <p className="text-sm text-gray-400">Running Jobs</p>
              <p className="text-2xl font-bold">{runningJobs}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-green-900/50 rounded-lg">
              <CheckCircle className="w-6 h-6 text-green-400" />
            </div>
            <div>
              <p className="text-sm text-gray-400">Completed</p>
              <p className="text-2xl font-bold">{completedJobs}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-red-900/50 rounded-lg">
              <AlertTriangle className="w-6 h-6 text-red-400" />
            </div>
            <div>
              <p className="text-sm text-gray-400">Failed</p>
              <p className="text-2xl font-bold">{failedJobs}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-purple-900/50 rounded-lg">
              <Cpu className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <p className="text-sm text-gray-400">Total Jobs</p>
              <p className="text-2xl font-bold">{jobs.length}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Shield className="w-5 h-5 text-primary-500" />
            Crypto Status
          </h2>
          {cryptoStatus ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Implementation</span>
                <span
                  className={clsx(
                    "px-2 py-1 rounded text-sm font-medium",
                    cryptoStatus.liboqs_available
                      ? "bg-green-900/50 text-green-400"
                      : "bg-yellow-900/50 text-yellow-400",
                  )}
                >
                  {cryptoStatus.implementation}
                </span>
              </div>
              {cryptoStatus.security_warning && (
                <div className="flex items-start gap-2 p-3 bg-yellow-900/20 border border-yellow-800 rounded-lg">
                  <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-yellow-400">
                    {cryptoStatus.security_warning}
                  </p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-gray-500">Loading...</p>
          )}
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Clock className="w-5 h-5 text-primary-500" />
            Recent Jobs
          </h2>
          {jobsLoading ? (
            <p className="text-gray-500">Loading...</p>
          ) : jobs.length > 0 ? (
            <div className="space-y-2">
              {jobs.slice(0, 5).map((job) => (
                <div
                  key={job.id}
                  className="flex items-center justify-between p-3 bg-gray-800 rounded-lg"
                >
                  <div>
                    <p className="font-medium">{job.problem_type}</p>
                    <p className="text-xs text-gray-500">
                      {job.id.slice(0, 8)}...
                    </p>
                  </div>
                  <span
                    className={clsx(
                      "px-2 py-1 rounded text-xs font-medium border",
                      statusColors[job.status],
                    )}
                  >
                    {job.status}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500">No jobs yet</p>
          )}
        </div>
      </div>
    </div>
  );
}
