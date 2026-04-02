import { useState } from "react";
import { useAuthStore } from "@/hooks/useAuth";
import { Activity, Atom, LogOut, Menu, User, X } from "lucide-react";
import clsx from "clsx";

interface LayoutProps {
  children: React.ReactNode;
  activeSection: string;
  onNavigate: (section: string) => void;
}

const navItems = [
  { id: "dashboard", label: "Dashboard", icon: Activity },
  { id: "jobs", label: "Jobs", icon: Atom },
  { id: "new-job", label: "New Job", icon: Atom },
  { id: "keys", label: "Keys", icon: Atom },
  { id: "settings", label: "Settings", icon: Atom },
];

export function Layout({ children, activeSection, onNavigate }: LayoutProps) {
  const { user, logout } = useAuthStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gray-950">
      <aside
        className={clsx(
          "fixed inset-y-0 left-0 z-50 w-64 bg-gray-900 border-r border-gray-800 transform transition-transform duration-200 lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center justify-between h-16 px-4 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <span className="text-2xl">⚛</span>
            <span className="font-bold text-lg">
              QS<span className="text-primary-500">O</span>P
            </span>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden p-1 hover:bg-gray-800 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="p-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                onClick={() => {
                  onNavigate(item.id);
                  setSidebarOpen(false);
                }}
                className={clsx(
                  "w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors",
                  activeSection === item.id
                    ? "bg-primary-600 text-white"
                    : "text-gray-400 hover:text-white hover:bg-gray-800",
                )}
              >
                <Icon className="w-5 h-5" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-800">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-gray-800 flex items-center justify-center">
              <User className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{user?.username}</p>
              <p className="text-xs text-gray-500 truncate">{user?.email}</p>
            </div>
          </div>
          <button
            onClick={logout}
            className="w-full flex items-center gap-2 px-3 py-2 text-gray-400 hover:text-red-400 hover:bg-gray-800 rounded-lg transition-colors"
          >
            <LogOut className="w-4 h-4" />
            <span>Logout</span>
          </button>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="h-16 border-b border-gray-800 flex items-center px-4 lg:px-6">
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden p-1 hover:bg-gray-800 rounded"
          >
            <Menu className="w-5 h-5" />
          </button>
        </header>

        <main className="p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
