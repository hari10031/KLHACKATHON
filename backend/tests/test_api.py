"""
API integration tests.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["service"] == "GST Reconciliation Engine"

    @patch("app.main.Neo4jConnection")
    def test_health(self, mock_conn, client):
        mock_conn.verify_connectivity.return_value = None
        response = client.get("/health")
        assert response.status_code == 200


class TestReconciliationAPI:
    @patch("app.engine.reconciliation.ReconciliationEngine.get_all_gstins")
    def test_list_gstins(self, mock_fn, client):
        mock_fn.return_value = ["27AADCB2230M1ZT"]
        response = client.get("/api/v1/reconciliation/gstins")
        assert response.status_code == 200
        assert "gstins" in response.json()

    @patch("app.engine.reconciliation.ReconciliationEngine.get_return_periods")
    def test_list_periods(self, mock_fn, client):
        mock_fn.return_value = ["032025"]
        response = client.get("/api/v1/reconciliation/periods")
        assert response.status_code == 200
        assert "periods" in response.json()


class TestDashboardAPI:
    @patch("app.database.execute_query")
    def test_trends(self, mock_eq, client):
        mock_eq.return_value = []
        response = client.get("/api/v1/dashboard/trends?gstin=27AADCB2230M1ZT")
        assert response.status_code == 200
        assert "trends" in response.json()


class TestRiskAPI:
    @patch("app.database.execute_query")
    def test_heatmap(self, mock_eq, client):
        mock_eq.return_value = []
        response = client.get("/api/v1/risk/heatmap")
        assert response.status_code == 200
        assert "vendors" in response.json()

    @patch("app.database.execute_query")
    def test_communities(self, mock_eq, client):
        mock_eq.return_value = []
        response = client.get("/api/v1/risk/communities")
        assert response.status_code == 200

    @patch("app.database.execute_query")
    def test_vendor_not_found(self, mock_eq, client):
        mock_eq.return_value = []
        response = client.get("/api/v1/risk/vendor/INVALID")
        assert response.status_code == 404
