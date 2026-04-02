import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User, AuthTokens } from "@/types";
import { apiClient } from "@/api/client";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const tokens = await apiClient.login(username, password);
          apiClient.setTokens(tokens);
          const user = await apiClient.getCurrentUser();
          set({ user, isAuthenticated: true, isLoading: false });
        } catch (err) {
          const message = err instanceof Error ? err.message : "Login failed";
          set({ error: message, isLoading: false });
          throw err;
        }
      },

      logout: async () => {
        try {
          await apiClient.logout();
        } finally {
          set({ user: null, isAuthenticated: false });
        }
      },

      checkAuth: async () => {
        if (!get().isAuthenticated) return;
        try {
          const user = await apiClient.getCurrentUser();
          set({ user });
        } catch {
          set({ user: null, isAuthenticated: false });
        }
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: "qsop-auth",
      partialize: (state) => ({ isAuthenticated: state.isAuthenticated }),
    },
  ),
);
