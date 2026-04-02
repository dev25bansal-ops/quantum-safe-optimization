import { useState } from "react";
import { useSubmitJob } from "@/hooks/useApi";
import { Atom, Play, Loader2 } from "lucide-react";
import toast from "react-hot-toast";
import type { AlgorithmType, BackendType, MaxCutConfig } from "@/types";

const algorithms: AlgorithmType[] = ["QAOA", "VQE", "ANNEALING", "GROVER"];
const backends: BackendType[] = [
  "qiskit_aer",
  "ibm_quantum",
  "aws_braket",
  "azure_quantum",
  "dwave_leap",
];

export function JobForm() {
  const [algorithm, setAlgorithm] = useState<AlgorithmType>("QAOA");
  const [backend, setBackend] = useState<BackendType>("qiskit_aer");
  const [layers, setLayers] = useState(2);
  const [shots, setShots] = useState(1024);
  const [optimizer, setOptimizer] = useState("COBYLA");
  const [edges, setEdges] = useState("[[0,1],[1,2],[2,0]]");

  const submitJob = useSubmitJob();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      const edgesArray = JSON.parse(edges);
      const problemConfig: MaxCutConfig = {
        type: "maxcut",
        graph: { edges: edgesArray },
      };

      await submitJob.mutateAsync({
        problem_type: algorithm,
        problem_config: problemConfig,
        parameters: {
          layers,
          shots,
          optimizer,
          backend,
        },
      });

      toast.success("Job submitted successfully!");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to submit job");
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
        <Atom className="w-6 h-6 text-primary-500" />
        New Optimization Job
      </h1>

      <form onSubmit={handleSubmit} className="card space-y-6">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Algorithm
            </label>
            <select
              value={algorithm}
              onChange={(e) => setAlgorithm(e.target.value as AlgorithmType)}
              className="input"
            >
              {algorithms.map((alg) => (
                <option key={alg} value={alg}>
                  {alg}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Backend
            </label>
            <select
              value={backend}
              onChange={(e) => setBackend(e.target.value as BackendType)}
              className="input"
            >
              {backends.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Layers (p)
            </label>
            <input
              type="number"
              value={layers}
              onChange={(e) => setLayers(Number(e.target.value))}
              min={1}
              max={10}
              className="input"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Shots
            </label>
            <input
              type="number"
              value={shots}
              onChange={(e) => setShots(Number(e.target.value))}
              min={100}
              max={100000}
              step={100}
              className="input"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Optimizer
            </label>
            <select
              value={optimizer}
              onChange={(e) => setOptimizer(e.target.value)}
              className="input"
            >
              <option value="COBYLA">COBYLA</option>
              <option value="SPSA">SPSA</option>
              <option value="ADAM">ADAM</option>
              <option value="L-BFGS-B">L-BFGS-B</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-400 mb-2">
            Graph Edges (JSON)
          </label>
          <textarea
            value={edges}
            onChange={(e) => setEdges(e.target.value)}
            rows={3}
            className="input font-mono"
            placeholder="[[0,1],[1,2],[2,0]]"
          />
          <p className="text-xs text-gray-500 mt-1">
            Define graph edges as JSON array of [node1, node2] pairs
          </p>
        </div>

        <button
          type="submit"
          disabled={submitJob.isPending}
          className="btn-primary flex items-center gap-2"
        >
          {submitJob.isPending ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Submitting...
            </>
          ) : (
            <>
              <Play className="w-4 h-4" />
              Submit Job
            </>
          )}
        </button>
      </form>
    </div>
  );
}
