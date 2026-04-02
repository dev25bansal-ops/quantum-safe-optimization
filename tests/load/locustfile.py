"""
Load Testing Configuration for CI Pipeline.

Provides locust-based load tests for the API.
"""

import os
import time
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner, WorkerRunner


class QuantumAPIUser(HttpUser):
    """Simulated API user for load testing."""

    wait_time = between(1, 5)

    def on_start(self):
        """Login and get auth token."""
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": os.getenv("ADMIN_PASSWORD", "changeme"),
            },
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.token = None
            self.headers = {}

    @task(10)
    def health_check(self):
        """Test health endpoint."""
        self.client.get("/health")

    @task(5)
    def get_jobs(self):
        """Test jobs listing."""
        self.client.get("/api/v1/jobs", headers=self.headers)

    @task(3)
    def submit_job(self):
        """Test job submission."""
        self.client.post(
            "/api/v1/jobs",
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1], [1, 2]]},
                "backend": "local_simulator",
            },
            headers=self.headers,
        )

    @task(2)
    def get_backends(self):
        """Test backends endpoint."""
        self.client.get("/api/v1/backends", headers=self.headers)

    @task(2)
    def get_billing_summary(self):
        """Test billing endpoint."""
        self.client.get("/api/v1/billing/usage/summary", headers=self.headers)

    @task(1)
    def get_marketplace(self):
        """Test marketplace endpoint."""
        self.client.get("/api/v1/marketplace/", headers=self.headers)

    @task(1)
    def get_federation_status(self):
        """Test federation endpoint."""
        self.client.get("/api/v1/federation/status", headers=self.headers)


class BillingLoadUser(HttpUser):
    """Simulated user focused on billing operations."""

    wait_time = between(2, 8)

    def on_start(self):
        """Login."""
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": os.getenv("ADMIN_PASSWORD", "changeme")},
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(5)
    def record_usage(self):
        """Record usage events."""
        self.client.post(
            "/api/v1/billing/usage",
            json={
                "resource_type": "api_call",
                "quantity": 10,
            },
            headers=self.headers,
        )

    @task(3)
    def get_pricing(self):
        """Get pricing info."""
        self.client.get("/api/v1/billing/pricing")

    @task(2)
    def estimate_cost(self):
        """Estimate job cost."""
        self.client.post(
            "/api/v1/billing/estimate",
            json={"shots": 10000, "jobs": 5, "compute_seconds": 60},
        )

    @task(1)
    def generate_invoice(self):
        """Generate invoice."""
        self.client.post("/api/v1/billing/invoices/generate", headers=self.headers)


class CircuitVisualizationUser(HttpUser):
    """Simulated user for circuit visualization."""

    wait_time = between(1, 3)

    def on_start(self):
        """Login."""
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": os.getenv("ADMIN_PASSWORD", "changeme")},
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(5)
    def generate_circuit(self):
        """Generate a circuit."""
        self.client.post(
            "/api/v1/circuits/circuits/generate?num_qubits=4&depth=3",
            headers=self.headers,
        )

    @task(3)
    def list_circuits(self):
        """List circuits."""
        self.client.get("/api/v1/circuits/circuits", headers=self.headers)

    @task(2)
    def get_styles(self):
        """Get visualization styles."""
        self.client.get("/api/v1/circuits/styles", headers=self.headers)


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Log test start."""
    print("Load test starting...")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Log test stop and print stats."""
    print("Load test complete.")
    if isinstance(environment.runner, (MasterRunner, WorkerRunner)):
        return

    stats = environment.stats
    print(f"\nTotal Requests: {stats.total.num_requests}")
    print(f"Total Failures: {stats.total.num_failures}")
    print(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")
    print(f"Requests/sec: {stats.total.total_rps:.2f}")


if __name__ == "__main__":
    import subprocess

    subprocess.run(
        [
            "locust",
            "-f",
            __file__,
            "--headless",
            "-u",
            "100",
            "-r",
            "10",
            "-t",
            "60s",
            "--host",
            os.getenv("API_URL", "http://localhost:8000"),
        ]
    )
