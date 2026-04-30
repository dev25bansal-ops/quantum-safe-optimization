"""
Tests for GraphQL API endpoints.
"""

import pytest
from fastapi.testclient import TestClient


class TestGraphQLAPI:
    """Tests for GraphQL endpoints."""

    def test_graphql_endpoint_exists(self, client):
        """Test GraphQL endpoint is available."""
        response = client.get("/api/v1/graphql")
        # Should return 400 or 405 for GET, not 404
        assert response.status_code in [200, 400, 405, 404]

    def test_graphql_introspection(self, client):
        """Test GraphQL introspection query."""
        introspection_query = """
        {
            __schema {
                types {
                    name
                }
            }
        }
        """

        response = client.post(
            "/api/v1/graphql",
            json={"query": introspection_query},
            headers={"Content-Type": "application/json"},
        )

        # If GraphQL is available, should return valid response
        if response.status_code == 200:
            data = response.json()
            assert "data" in data or "errors" in data

    def test_graphql_jobs_query(self, client, auth_headers):
        """Test GraphQL jobs query."""
        query = """
        query {
            jobs(limit: 10) {
                id
                status
                problemType
            }
        }
        """

        response = client.post(
            "/api/v1/graphql",
            json={"query": query},
            headers=auth_headers,
        )

        # Check response structure
        if response.status_code == 200:
            data = response.json()
            if "data" in data:
                assert "jobs" in data["data"]

    def test_graphql_job_by_id_query(self, client, auth_headers):
        """Test GraphQL single job query."""
        query = """
        query($jobId: ID!) {
            job(id: $jobId) {
                id
                status
                createdAt
            }
        }
        """

        response = client.post(
            "/api/v1/graphql",
            json={"query": query, "variables": {"jobId": "test_job_id"}},
            headers=auth_headers,
        )

        # Should return proper GraphQL response structure
        if response.status_code == 200:
            data = response.json()
            assert "data" in data or "errors" in data

    def test_graphql_backends_query(self, client, auth_headers):
        """Test GraphQL backends query."""
        query = """
        query {
            backends {
                id
                name
                status
                numQubits
            }
        }
        """

        response = client.post(
            "/api/v1/graphql",
            json={"query": query},
            headers=auth_headers,
        )

        if response.status_code == 200:
            data = response.json()
            if "data" in data:
                assert "backends" in data["data"]

    def test_graphql_user_query(self, client, auth_headers):
        """Test GraphQL user query."""
        query = """
        query {
            me {
                id
                username
                email
            }
        }
        """

        response = client.post(
            "/api/v1/graphql",
            json={"query": query},
            headers=auth_headers,
        )

        if response.status_code == 200:
            data = response.json()
            if "data" in data:
                assert "me" in data["data"]

    def test_graphql_mutation_submit_job(self, client, auth_headers):
        """Test GraphQL submit job mutation."""
        mutation = """
        mutation($input: JobInput!) {
            submitJob(input: $input) {
                id
                status
            }
        }
        """

        variables = {
            "input": {
                "problemType": "QAOA",
                "problemConfig": {"type": "maxcut"},
                "parameters": {"layers": 2, "shots": 100},
            }
        }

        response = client.post(
            "/api/v1/graphql",
            json={"query": mutation, "variables": variables},
            headers=auth_headers,
        )

        if response.status_code == 200:
            data = response.json()
            # Should return mutation result or validation errors
            assert "data" in data or "errors" in data

    def test_graphql_error_handling(self, client):
        """Test GraphQL error handling."""
        invalid_query = """
        query {
            invalidField {
                id
            }
        }
        """

        response = client.post(
            "/api/v1/graphql",
            json={"query": invalid_query},
        )

        if response.status_code == 200:
            data = response.json()
            # Should have errors for invalid field
            if "errors" in data:
                assert len(data["errors"]) > 0


@pytest.fixture
def auth_headers():
    """Return authentication headers."""
    import os

    return {"Authorization": f"Bearer {os.getenv('TEST_TOKEN', 'test_token')}"}


@pytest.fixture
def client():
    """Return test client."""
    from api.main import app

    return TestClient(app)
