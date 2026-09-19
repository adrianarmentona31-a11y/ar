"""
Iteration 5 tests:
(A) Walk-in service creation (client_name/client_phone without client_id)
(B) PDFs one-page for servicio / cotizacion / nota / pago
(C) Share receipts public link (JWT-signed) with 401 on tamper
(D) Viewer read-only guardrails preserved
"""

import io
import os
import re
import pytest
import requests
from pypdf import PdfReader

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://armenta-hub.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


# ---------- fixtures ----------

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"identifier": "admin", "password": "armenta123"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def viewer_token():
    r = requests.post(f"{API}/auth/login", json={"identifier": "viewer", "password": "viewer123"}, timeout=30)
    if r.status_code != 200:
        pytest.skip("Viewer user not available")
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def viewer_h(viewer_token):
    return {"Authorization": f"Bearer {viewer_token}"}


def _pdf_pages(content: bytes) -> int:
    reader = PdfReader(io.BytesIO(content))
    return len(reader.pages)


def _pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


# ---------- (A) Walk-in service ----------

class TestWalkInService:
    service_id = None
    folio = None

    def test_create_walkin_service(self, admin_h):
        payload = {
            "client_name": "Donato Reyes",
            "client_phone": "6562033855",
            "items": [{"description": "Afinación", "quantity": 1, "unit_price": 1000}],
        }
        r = requests.post(f"{API}/services", json=payload, headers=admin_h, timeout=30)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["client_name"] == "Donato Reyes"
        assert data["client_phone"] == "6562033855"
        assert data.get("client_id") in (None, "")
        assert data["total"] > 0
        TestWalkInService.service_id = data["id"]
        TestWalkInService.folio = data["folio"]

    def test_get_service_builds_client_from_walkin_fields(self, admin_h):
        assert self.service_id
        r = requests.get(f"{API}/services/{self.service_id}", headers=admin_h, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        client = data.get("client") or {}
        assert client.get("nombre") == "Donato Reyes"
        assert client.get("telefono") == "6562033855"

    def test_patch_service_updates_walkin_name(self, admin_h):
        assert self.service_id
        r = requests.patch(f"{API}/services/{self.service_id}",
                           json={"client_name": "Otro Nombre"}, headers=admin_h, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["client_name"] == "Otro Nombre"

        r2 = requests.get(f"{API}/services/{self.service_id}", headers=admin_h, timeout=30)
        assert r2.status_code == 200
        assert (r2.json().get("client") or {}).get("nombre") == "Otro Nombre"

    def test_service_pdf_is_one_page_and_contains_updated_name(self, admin_h):
        assert self.service_id
        r = requests.get(f"{API}/receipts/servicio/{self.service_id}/pdf", headers=admin_h, timeout=60)
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/pdf")
        pages = _pdf_pages(r.content)
        assert pages == 1, f"Expected 1 page, got {pages}"
        text = _pdf_text(r.content)
        assert "Otro Nombre" in text, f"PDF text missing name. Text snippet: {text[:400]}"


# ---------- (B) All PDFs one page ----------

class TestReceiptPdfsSinglePage:
    quote_id = None
    note_id = None
    payment_id = None

    def test_cotizacion_pdf_one_page(self, admin_h):
        # create quote
        r = requests.post(f"{API}/quotes",
                          json={"client_name": "Cotiz Test", "client_phone": "5551112222",
                                "items": [{"description": "Diagnóstico", "quantity": 1, "unit_price": 500}]},
                          headers=admin_h, timeout=30)
        # quotes may need client_id — fallback: check by creating without walk-in
        if r.status_code != 201:
            # try alternate schema
            r = requests.post(f"{API}/quotes",
                              json={"items": [{"description": "Diag", "quantity": 1, "unit_price": 500}]},
                              headers=admin_h, timeout=30)
        assert r.status_code == 201, r.text
        qid = r.json()["id"]
        TestReceiptPdfsSinglePage.quote_id = qid
        p = requests.get(f"{API}/receipts/cotizacion/{qid}/pdf", headers=admin_h, timeout=60)
        assert p.status_code == 200, p.text
        assert _pdf_pages(p.content) == 1

    def test_nota_pdf_one_page(self, admin_h):
        r = requests.post(f"{API}/notes",
                          json={"client_name": "Nota Test", "client_phone": "5553334444",
                                "items": [{"description": "Aceite", "quantity": 1, "unit_price": 300}]},
                          headers=admin_h, timeout=30)
        assert r.status_code == 201, r.text
        nid = r.json()["id"]
        TestReceiptPdfsSinglePage.note_id = nid
        p = requests.get(f"{API}/receipts/nota/{nid}/pdf", headers=admin_h, timeout=60)
        assert p.status_code == 200, p.text
        assert _pdf_pages(p.content) == 1

    def test_pago_pdf_one_page(self, admin_h):
        # need a service to attach payment
        sr = requests.post(f"{API}/services",
                           json={"client_name": "Pago Test", "client_phone": "5559990000",
                                 "items": [{"description": "Servicio", "quantity": 1, "unit_price": 800}]},
                           headers=admin_h, timeout=30)
        assert sr.status_code == 201, sr.text
        sid = sr.json()["id"]
        pr = requests.post(f"{API}/payments",
                           json={"service_id": sid, "amount": 400, "method": "cash"},
                           headers=admin_h, timeout=30)
        assert pr.status_code == 201, pr.text
        pid = pr.json()["id"]
        TestReceiptPdfsSinglePage.payment_id = pid
        p = requests.get(f"{API}/receipts/pago/{pid}/pdf", headers=admin_h, timeout=60)
        assert p.status_code == 200, p.text
        assert _pdf_pages(p.content) == 1


# ---------- (C) Share links ----------

class TestShareLinks:
    def _make_service(self, headers):
        r = requests.post(f"{API}/services",
                          json={"client_name": "Share Test", "client_phone": "5551234567",
                                "items": [{"description": "X", "quantity": 1, "unit_price": 100}]},
                          headers=headers, timeout=30)
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def test_share_link_admin_and_public_pdf(self, admin_h):
        sid = self._make_service(admin_h)
        r = requests.get(f"{API}/receipts/servicio/{sid}/share-link", headers=admin_h, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "path" in data and "url" in data and "folio" in data and "expires_at" in data
        assert data["path"].startswith("/api/public/receipts/servicio/")
        assert "?t=" in data["path"]

        # public fetch (no auth)
        pub_url = f"{BASE_URL}{data['path']}"
        r2 = requests.get(pub_url, timeout=60)
        assert r2.status_code == 200, r2.text
        assert r2.headers.get("content-type", "").startswith("application/pdf")

    def test_tampered_token_401(self, admin_h):
        sid = self._make_service(admin_h)
        r = requests.get(f"{API}/receipts/servicio/{sid}/share-link", headers=admin_h, timeout=30)
        assert r.status_code == 200
        path = r.json()["path"]
        # tamper last chars of token
        tampered = re.sub(r"\?t=(.+)$", lambda m: "?t=" + m.group(1)[:-4] + "AAAA", path)
        r2 = requests.get(f"{BASE_URL}{tampered}", timeout=30)
        assert r2.status_code == 401

    def test_missing_token_errors(self, admin_h):
        sid = self._make_service(admin_h)
        r = requests.get(f"{API}/receipts/servicio/{sid}/share-link", headers=admin_h, timeout=30)
        assert r.status_code == 200
        # strip ?t=
        path_wo = r.json()["path"].split("?t=")[0]
        r2 = requests.get(f"{BASE_URL}{path_wo}", timeout=30)
        assert r2.status_code in (401, 422), r2.status_code

    def test_share_link_for_pago_and_nota(self, admin_h):
        # pago
        sr = requests.post(f"{API}/services",
                           json={"client_name": "Pago Share", "client_phone": "5550001111",
                                 "items": [{"description": "S", "quantity": 1, "unit_price": 200}]},
                           headers=admin_h, timeout=30)
        sid = sr.json()["id"]
        pr = requests.post(f"{API}/payments",
                           json={"service_id": sid, "amount": 100, "method": "cash"},
                           headers=admin_h, timeout=30)
        pid = pr.json()["id"]
        r = requests.get(f"{API}/receipts/pago/{pid}/share-link", headers=admin_h, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["path"].startswith("/api/public/receipts/pago/")
        # public fetch
        r2 = requests.get(f"{BASE_URL}{r.json()['path']}", timeout=60)
        assert r2.status_code == 200
        assert r2.headers.get("content-type", "").startswith("application/pdf")

        # nota
        nr = requests.post(f"{API}/notes",
                           json={"client_name": "Nota Share", "client_phone": "5552223333",
                                 "items": [{"description": "N", "quantity": 1, "unit_price": 50}]},
                           headers=admin_h, timeout=30)
        nid = nr.json()["id"]
        r = requests.get(f"{API}/receipts/nota/{nid}/share-link", headers=admin_h, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["path"].startswith("/api/public/receipts/nota/")

    def test_viewer_can_read_share_link(self, admin_h, viewer_h):
        sid = self._make_service(admin_h)
        r = requests.get(f"{API}/receipts/servicio/{sid}/share-link", headers=viewer_h, timeout=30)
        assert r.status_code == 200, r.text


# ---------- (D) Regression: viewer RBAC ----------

class TestViewerRBAC:
    def test_viewer_cannot_create_service(self, viewer_h):
        r = requests.post(f"{API}/services",
                          json={"client_name": "X", "items": [{"description": "y", "quantity": 1, "unit_price": 10}]},
                          headers=viewer_h, timeout=30)
        assert r.status_code == 403, r.status_code

    def test_viewer_cannot_read_finance_summary(self, viewer_h):
        r = requests.get(f"{API}/finance/summary", headers=viewer_h, timeout=30)
        assert r.status_code == 403, r.status_code
