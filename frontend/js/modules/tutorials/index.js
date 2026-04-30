/**
 * Interactive Tutorial System
 * Guided walkthroughs for platform features
 */

import { showToast } from "../toast.js";

const TUTORIAL_STORAGE_KEY = "qsop_tutorials";

const tutorials = {
  "getting-started": {
    id: "getting-started",
    title: "Getting Started with QSOP",
    description: "Learn the basics of the Quantum-Safe Optimization Platform",
    duration: "5 min",
    steps: [
      {
        target: "#nav-dashboard",
        title: "Dashboard",
        content:
          "Welcome to QSOP! The dashboard shows your optimization jobs, metrics, and quick actions. Let's explore the key features.",
        position: "bottom",
      },
      {
        target: "#quick-submit-section",
        title: "Submit Your First Job",
        content:
          "Use this form to submit quantum optimization jobs. Select an algorithm, configure parameters, and click Submit.",
        position: "top",
      },
      {
        target: "#algorithm-select",
        title: "Algorithm Selection",
        content:
          "Choose from VQE, QAOA, Grover, and other quantum algorithms. Each has different use cases and parameter requirements.",
        position: "right",
      },
      {
        target: "#jobs-table",
        title: "Job Management",
        content:
          "View all your jobs here. Track status, view results, and manage your optimization workflows.",
        position: "top",
      },
      {
        target: "#nav-security",
        title: "Security Features",
        content:
          "Explore quantum-safe cryptography, key management, and audit logging in the Security section.",
        position: "right",
      },
    ],
  },
  "vqe-optimization": {
    id: "vqe-optimization",
    title: "VQE Optimization Workflow",
    description: "Complete guide to Variational Quantum Eigensolver",
    duration: "10 min",
    steps: [
      {
        target: "#algorithm-select",
        title: "Select VQE",
        content:
          "Select VQE (Variational Quantum Eigensolver) from the algorithm dropdown. VQE is ideal for finding ground state energies.",
        position: "right",
      },
      {
        target: "#hamiltonian-section",
        title: "Hamiltonian Configuration",
        content:
          "Define your molecular Hamiltonian. You can use preset molecules or custom Pauli operators.",
        position: "bottom",
      },
      {
        target: "#ansatz-section",
        title: "Ansatz Selection",
        content:
          "Choose your variational ansatz: Hardware Efficient, UCCSD, or custom circuits. Simpler ansatzes converge faster.",
        position: "bottom",
      },
      {
        target: "#optimizer-section",
        title: "Classical Optimizer",
        content:
          "Select COBYLA, SPSA, or Adam optimizer. SPSA works well for noisy quantum hardware.",
        position: "bottom",
      },
      {
        target: "#shots-config",
        title: "Shot Count",
        content:
          "Set measurement shots. More shots = better statistics but longer runtime. Start with 1000-4000.",
        position: "left",
      },
      {
        target: "#submit-btn",
        title: "Submit and Monitor",
        content:
          "Submit your job and monitor progress in real-time. Results include energy estimates and convergence plots.",
        position: "top",
      },
    ],
  },
  "key-management": {
    id: "key-management",
    title: "Quantum-Safe Key Management",
    description: "Manage your post-quantum cryptographic keys",
    duration: "7 min",
    steps: [
      {
        target: "#nav-security",
        title: "Security Section",
        content:
          "Navigate to Security to access key management, encryption, and audit features.",
        position: "right",
      },
      {
        target: "#key-list",
        title: "Key Inventory",
        content:
          "View all your quantum-safe keys. Each key uses post-quantum algorithms like Kyber or Dilithium.",
        position: "bottom",
      },
      {
        target: "#generate-key-btn",
        title: "Generate New Key",
        content:
          "Create new keys with ML-KEM (Kyber) for key encapsulation or ML-DSA (Dilithium) for signatures.",
        position: "bottom",
      },
      {
        target: "#key-rotation-section",
        title: "Key Rotation",
        content:
          "Schedule automatic key rotation. Best practice: rotate keys every 90 days.",
        position: "top",
      },
      {
        target: "#key-audit-log",
        title: "Audit Trail",
        content:
          "All key operations are logged. Review usage patterns and detect anomalies.",
        position: "top",
      },
    ],
  },
  "api-integration": {
    id: "api-integration",
    title: "API Integration Guide",
    description: "Connect your applications to QSOP",
    duration: "8 min",
    steps: [
      {
        target: "#nav-settings",
        title: "Settings & API",
        content:
          "Access API keys and integration settings from the Settings menu.",
        position: "right",
      },
      {
        target: "#api-keys-section",
        title: "API Keys",
        content:
          "Create and manage API keys for programmatic access. Keep keys secure!",
        position: "bottom",
      },
      {
        target: "#api-docs-link",
        title: "API Documentation",
        content:
          "Full API reference with examples for all endpoints. OpenAPI/Swagger format available.",
        position: "bottom",
      },
      {
        target: "#webhook-section",
        title: "Webhooks",
        content:
          "Configure webhooks to receive real-time notifications when jobs complete.",
        position: "top",
      },
      {
        target: "#sdk-download",
        title: "SDK & Libraries",
        content:
          "Download official SDKs for Python, JavaScript, and other languages.",
        position: "top",
      },
    ],
  },
  "dashboard-features": {
    id: "dashboard-features",
    title: "Dashboard Deep Dive",
    description: "Master all dashboard features",
    duration: "6 min",
    steps: [
      {
        target: "#metrics-cards",
        title: "Key Metrics",
        content:
          "Monitor active jobs, success rate, total optimizations, and resource utilization at a glance.",
        position: "bottom",
      },
      {
        target: "#quick-actions",
        title: "Quick Actions",
        content:
          "One-click access to common tasks: submit job, generate key, view reports.",
        position: "left",
      },
      {
        target: "#recent-jobs",
        title: "Recent Activity",
        content:
          "Your latest jobs with status indicators. Click any job for detailed results.",
        position: "top",
      },
      {
        target: "#charts-section",
        title: "Analytics Charts",
        content:
          "Visualize optimization trends, algorithm performance, and resource usage over time.",
        position: "top",
      },
      {
        target: "#notifications-bell",
        title: "Notifications",
        content:
          "Stay informed with real-time notifications for job completions, alerts, and system updates.",
        position: "bottom",
      },
    ],
  },
};

class TutorialManager {
  constructor() {
    this.currentTutorial = null;
    this.currentStepIndex = 0;
    this.overlay = null;
    this.highlight = null;
    this.tooltip = null;
    this.completedTutorials = this.loadCompletedTutorials();
  }

  loadCompletedTutorials() {
    try {
      const stored = localStorage.getItem(TUTORIAL_STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  }

  saveCompletedTutorials() {
    localStorage.setItem(
      TUTORIAL_STORAGE_KEY,
      JSON.stringify(this.completedTutorials),
    );
  }

  markCompleted(tutorialId) {
    if (!this.completedTutorials.includes(tutorialId)) {
      this.completedTutorials.push(tutorialId);
      this.saveCompletedTutorials();
    }
  }

  isCompleted(tutorialId) {
    return this.completedTutorials.includes(tutorialId);
  }

  getTutorials() {
    return Object.values(tutorials).map((t) => ({
      ...t,
      completed: this.isCompleted(t.id),
    }));
  }

  start(tutorialId) {
    const tutorial = tutorials[tutorialId];
    if (!tutorial) {
      showToast(
        "error",
        "Tutorial Not Found",
        `Tutorial "${tutorialId}" does not exist`,
      );
      return;
    }

    this.currentTutorial = tutorial;
    this.currentStepIndex = 0;
    this.createOverlay();
    this.showStep(0);
    showToast("success", "Tutorial Started", tutorial.title);
  }

  createOverlay() {
    this.removeOverlay();

    this.overlay = document.createElement("div");
    this.overlay.className = "tutorial-overlay";
    this.overlay.innerHTML = `
            <div class="tutorial-backdrop"></div>
            <div class="tutorial-highlight"></div>
            <div class="tutorial-tooltip">
                <div class="tutorial-tooltip-header">
                    <span class="tutorial-step-counter"></span>
                    <h4 class="tutorial-title"></h4>
                    <button class="tutorial-close" aria-label="Close tutorial">&times;</button>
                </div>
                <div class="tutorial-tooltip-body">
                    <p class="tutorial-content"></p>
                </div>
                <div class="tutorial-tooltip-footer">
                    <div class="tutorial-progress"></div>
                    <div class="tutorial-actions">
                        <button class="btn btn-ghost btn-sm tutorial-skip">Skip Tutorial</button>
                        <button class="btn btn-outline btn-sm tutorial-prev">Previous</button>
                        <button class="btn btn-primary btn-sm tutorial-next">Next</button>
                    </div>
                </div>
            </div>
        `;

    document.body.appendChild(this.overlay);

    this.highlight = this.overlay.querySelector(".tutorial-highlight");
    this.tooltip = this.overlay.querySelector(".tutorial-tooltip");

    this.overlay
      .querySelector(".tutorial-close")
      .addEventListener("click", () => this.end());
    this.overlay
      .querySelector(".tutorial-skip")
      .addEventListener("click", () => this.end());
    this.overlay
      .querySelector(".tutorial-prev")
      .addEventListener("click", () => this.prevStep());
    this.overlay
      .querySelector(".tutorial-next")
      .addEventListener("click", () => this.nextStep());
  }

  removeOverlay() {
    if (this.overlay) {
      this.overlay.remove();
      this.overlay = null;
      this.highlight = null;
      this.tooltip = null;
    }
  }

  showStep(index) {
    if (
      !this.currentTutorial ||
      index < 0 ||
      index >= this.currentTutorial.steps.length
    ) {
      return;
    }

    this.currentStepIndex = index;
    const step = this.currentTutorial.steps[index];
    const target = document.querySelector(step.target);

    const stepCounter = this.tooltip.querySelector(".tutorial-step-counter");
    const title = this.tooltip.querySelector(".tutorial-title");
    const content = this.tooltip.querySelector(".tutorial-content");
    const progress = this.tooltip.querySelector(".tutorial-progress");
    const prevBtn = this.tooltip.querySelector(".tutorial-prev");
    const nextBtn = this.tooltip.querySelector(".tutorial-next");

    stepCounter.textContent = `Step ${index + 1} of ${this.currentTutorial.steps.length}`;
    title.textContent = step.title;
    content.textContent = step.content;

    progress.innerHTML = this.currentTutorial.steps
      .map(
        (_, i) =>
          `<span class="progress-dot ${i === index ? "active" : ""} ${i < index ? "completed" : ""}"></span>`,
      )
      .join("");

    prevBtn.style.display = index === 0 ? "none" : "inline-block";
    nextBtn.textContent =
      index === this.currentTutorial.steps.length - 1 ? "Finish" : "Next";

    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "center" });

      setTimeout(() => {
        const rect = target.getBoundingClientRect();
        this.highlight.style.top = `${rect.top - 5}px`;
        this.highlight.style.left = `${rect.left - 5}px`;
        this.highlight.style.width = `${rect.width + 10}px`;
        this.highlight.style.height = `${rect.height + 10}px`;

        const tooltipRect = this.tooltip.getBoundingClientRect();
        let top, left;

        switch (step.position) {
          case "top":
            top = rect.top - tooltipRect.height - 15;
            left = rect.left + rect.width / 2 - tooltipRect.width / 2;
            break;
          case "bottom":
            top = rect.bottom + 15;
            left = rect.left + rect.width / 2 - tooltipRect.width / 2;
            break;
          case "left":
            top = rect.top + rect.height / 2 - tooltipRect.height / 2;
            left = rect.left - tooltipRect.width - 15;
            break;
          case "right":
            top = rect.top + rect.height / 2 - tooltipRect.height / 2;
            left = rect.right + 15;
            break;
          default:
            top = rect.bottom + 15;
            left = rect.left;
        }

        left = Math.max(
          10,
          Math.min(left, window.innerWidth - tooltipRect.width - 10),
        );
        top = Math.max(
          10,
          Math.min(top, window.innerHeight - tooltipRect.height - 10),
        );

        this.tooltip.style.top = `${top}px`;
        this.tooltip.style.left = `${left}px`;
      }, 100);
    } else {
      this.tooltip.style.top = "50%";
      this.tooltip.style.left = "50%";
      this.tooltip.style.transform = "translate(-50%, -50%)";
    }
  }

  nextStep() {
    if (this.currentStepIndex >= this.currentTutorial.steps.length - 1) {
      this.complete();
    } else {
      this.showStep(this.currentStepIndex + 1);
    }
  }

  prevStep() {
    if (this.currentStepIndex > 0) {
      this.showStep(this.currentStepIndex - 1);
    }
  }

  complete() {
    this.markCompleted(this.currentTutorial.id);
    this.removeOverlay();
    showToast(
      "success",
      "Tutorial Complete!",
      `You've completed "${this.currentTutorial.title}"`,
    );
    this.currentTutorial = null;
  }

  end() {
    this.removeOverlay();
    this.currentTutorial = null;
  }

  reset(tutorialId) {
    this.completedTutorials = this.completedTutorials.filter(
      (id) => id !== tutorialId,
    );
    this.saveCompletedTutorials();
  }

  resetAll() {
    this.completedTutorials = [];
    this.saveCompletedTutorials();
  }
}

const tutorialManager = new TutorialManager();

export function initTutorials() {
  const container = document.getElementById("tutorials-section");
  if (!container) return;

  renderTutorialList(container);
}

function renderTutorialList(container) {
  const tutorialList = tutorialManager.getTutorials();

  container.innerHTML = `
        <div class="tutorials-header">
            <h2><i class="fas fa-graduation-cap"></i> Interactive Tutorials</h2>
            <p>Learn the platform with step-by-step guides</p>
        </div>
        <div class="tutorials-grid">
            ${tutorialList
              .map(
                (t) => `
                <div class="tutorial-card ${t.completed ? "completed" : ""}" data-tutorial-id="${t.id}">
                    <div class="tutorial-icon">
                        <i class="fas ${t.completed ? "fa-check-circle" : "fa-play-circle"}"></i>
                    </div>
                    <div class="tutorial-info">
                        <h3>${t.title}</h3>
                        <p>${t.description}</p>
                        <div class="tutorial-meta">
                            <span class="duration"><i class="fas fa-clock"></i> ${t.duration}</span>
                            <span class="steps"><i class="fas fa-list-ol"></i> ${t.steps.length} steps</span>
                        </div>
                    </div>
                    <div class="tutorial-actions">
                        <button class="btn btn-primary btn-sm start-tutorial" data-id="${t.id}">
                            ${t.completed ? "Restart" : "Start"}
                        </button>
                        ${t.completed ? '<span class="completed-badge"><i class="fas fa-check"></i> Completed</span>' : ""}
                    </div>
                </div>
            `,
              )
              .join("")}
        </div>
        <div class="tutorials-footer">
            <button class="btn btn-ghost" onclick="window.resetAllTutorials()">
                <i class="fas fa-redo"></i> Reset All Progress
            </button>
        </div>
    `;

  container.querySelectorAll(".start-tutorial").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const id = e.target.dataset.id;
      tutorialManager.start(id);
    });
  });
}

window.startTutorial = (id) => tutorialManager.start(id);
window.resetAllTutorials = () => {
  tutorialManager.resetAll();
  initTutorials();
  showToast(
    "success",
    "Progress Reset",
    "All tutorial progress has been cleared",
  );
};

export { tutorialManager, tutorials };
