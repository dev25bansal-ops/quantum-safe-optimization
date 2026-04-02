import { useState, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "react-hot-toast";
import { useAuthStore } from "@/hooks/useAuth";
import { Layout } from "@/components/Layout";
import { Dashboard } from "@/components/Dashboard";
import { JobsList } from "@/components/JobsList";
import { JobForm } from "@/components/JobForm";
import { Login } from "@/components/Login";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function AppContent() {
  const { isAuthenticated, checkAuth } = useAuthStore();
  const [activeSection, setActiveSection] = useState("dashboard");

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  if (!isAuthenticated) {
    return <Login />;
  }

  const renderContent = () => {
    switch (activeSection) {
      case "dashboard":
        return <Dashboard />;
      case "jobs":
        return <JobsList />;
      case "new-job":
        return <JobForm />;
      case "keys":
        return (
          <div className="card">
            <h1 className="text-2xl font-bold mb-4">Key Management</h1>
            <p className="text-gray-400">PQC key management coming soon...</p>
          </div>
        );
      case "settings":
        return (
          <div className="card">
            <h1 className="text-2xl font-bold mb-4">Settings</h1>
            <p className="text-gray-400">Settings coming soon...</p>
          </div>
        );
      default:
        return <Dashboard />;
    }
  };

  return (
    <Layout activeSection={activeSection} onNavigate={setActiveSection}>
      {renderContent()}
    </Layout>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 3000,
          style: {
            background: "#1f2937",
            color: "#f3f4f6",
            border: "1px solid #374151",
          },
        }}
      />
      <AppContent />
    </QueryClientProvider>
  );
}
