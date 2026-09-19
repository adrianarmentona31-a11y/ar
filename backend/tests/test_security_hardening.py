"""
ARMENTA OS - Iteration 4: Security hardening regression tests.
Covers: RBAC (viewer read-only + staff writes), settings redaction,
finance guard, file tokens, brute-force, google session error handling,
team CRUD, deactivated users, AI quota (not exhausted - just guard).
"""
import os
import uuid
import time
import io

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://armenta-hub.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"identifier": "admin", "password": "armenta123"}
VIEWER = {"identifier": "viewer", "password": "viewer123"}


# -------------------- fixtures --------------------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def viewer_token():
    r = requests.post(f"{API}/auth/login", json=VIEWER, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def ah(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


# -------------------- Viewer read-only --------------------
class TestViewerRBAC:
    def test_viewer_can_read(self, viewer_token):
        h = ah(viewer_token)
        for path in ("/clients", "/services", "/notes", "/payments"):
            r = requests.get(f"{API}{path}", headers=h, timeout=15)
            assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:150]}"

    def test_viewer_write_forbidden(self, viewer_token):
        h = ah(viewer_token)
        # POST clients
        r = requests.post(f"{API}/clients", headers=h, json={"nombre": "X", "tipo": "particular"}, timeout=10)
        assert r.status_code == 403, r.text
        r = requests.post(f"{API}/services", headers=h, json={}, timeout=10)
        assert r.status_code == 403
        r = requests.post(f"{API}/notes", headers=h, json={"cliente_nombre": "x", "descripcion": "y", "precio_total": 10}, timeout=10)
        assert r.status_code == 403
        r = requests.post(f"{API}/payments", headers=h, json={"service_id": "x", "amount": 1, "method": "cash"}, timeout=10)
        assert r.status_code == 403
        r = requests.patch(f"{API}/clients/nonexistent", headers=h, json={"nombre": "z"}, timeout=10)
        assert r.status_code == 403
        r = requests.post(f"{API}/ai/images/generate", headers=h, json={"prompt": "x", "model": "gemini-2.5-flash-image-preview"}, timeout=10)
        assert r.status_code == 403

    def test_viewer_finance_forbidden(self, viewer_token):
        r = requests.get(f"{API}/finance/summary", headers=ah(viewer_token), timeout=10)
        assert r.status_code == 403

    def test_viewer_settings_hides_bank(self, viewer_token):
        r = requests.get(f"{API}/settings", headers=ah(viewer_token), timeout=10)
        assert r.status_code == 200
        j = r.json()
        assert "bank_card" not in j
        assert "bank_clabe" not in j

    def test_viewer_team_forbidden(self, viewer_token):
        r = requests.get(f"{API}/team", headers=ah(viewer_token), timeout=10)
        assert r.status_code == 403

    def test_viewer_patch_settings_forbidden(self, viewer_token):
        r = requests.patch(f"{API}/settings", headers=ah(viewer_token), json={"bank_holder": "hack"}, timeout=10)
        assert r.status_code == 403


# -------------------- Admin --------------------
class TestAdminAccess:
    def test_settings_has_bank(self, admin_token):
        r = requests.get(f"{API}/settings", headers=ah(admin_token), timeout=10)
        assert r.status_code == 200
        j = r.json()
        assert "bank_card" in j and "bank_clabe" in j

    def test_finance_summary_ok(self, admin_token):
        r = requests.get(f"{API}/finance/summary", headers=ah(admin_token), timeout=15)
        assert r.status_code == 200

    def test_team_list(self, admin_token):
        r = requests.get(f"{API}/team", headers=ah(admin_token), timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json().get("items"), list)


# -------------------- Team CRUD --------------------
class TestTeam:
    @pytest.fixture(scope="class")
    def invited(self, admin_token):
        email = f"TEST_invite_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/team", headers=ah(admin_token),
                          json={"email": email, "name": "Tester", "role": "technician"}, timeout=10)
        assert r.status_code == 201, r.text
        yield r.json()
        # cleanup
        requests.delete(f"{API}/team/{r.json()['id']}", headers=ah(admin_token), timeout=10)

    def test_invite_created(self, invited):
        assert invited["role"] == "technician"
        assert invited["active"] is True

    def test_duplicate_invite_409(self, admin_token, invited):
        r = requests.post(f"{API}/team", headers=ah(admin_token),
                          json={"email": invited["email"], "role": "viewer"}, timeout=10)
        assert r.status_code == 409

    def test_patch_role_and_active(self, admin_token, invited):
        uid = invited["id"]
        r = requests.patch(f"{API}/team/{uid}", headers=ah(admin_token), json={"role": "viewer"}, timeout=10)
        assert r.status_code == 200
        assert r.json()["role"] == "viewer"
        r = requests.patch(f"{API}/team/{uid}", headers=ah(admin_token), json={"active": False}, timeout=10)
        assert r.status_code == 200
        assert r.json()["active"] is False

    def test_cannot_demote_self(self, admin_token):
        me = requests.get(f"{API}/auth/me", headers=ah(admin_token), timeout=10).json()
        r = requests.patch(f"{API}/team/{me['id']}", headers=ah(admin_token), json={"role": "viewer"}, timeout=10)
        assert r.status_code == 400

    def test_cannot_deactivate_self(self, admin_token):
        me = requests.get(f"{API}/auth/me", headers=ah(admin_token), timeout=10).json()
        r = requests.patch(f"{API}/team/{me['id']}", headers=ah(admin_token), json={"active": False}, timeout=10)
        assert r.status_code == 400

    def test_cannot_delete_self(self, admin_token):
        me = requests.get(f"{API}/auth/me", headers=ah(admin_token), timeout=10).json()
        r = requests.delete(f"{API}/team/{me['id']}", headers=ah(admin_token), timeout=10)
        assert r.status_code == 400

    def test_delete_invited(self, admin_token):
        # create a fresh one and delete
        email = f"TEST_del_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/team", headers=ah(admin_token),
                          json={"email": email, "role": "technician"}, timeout=10)
        assert r.status_code == 201
        uid = r.json()["id"]
        r = requests.delete(f"{API}/team/{uid}", headers=ah(admin_token), timeout=10)
        assert r.status_code == 200


# -------------------- Deactivated users --------------------
class TestDeactivated:
    def test_deactivated_flow(self, admin_token):
        # find viewer id
        me = requests.post(f"{API}/auth/login", json=VIEWER, timeout=10).json()
        viewer_id = me["user"]["id"]
        viewer_jwt = me["token"]
        # deactivate via team endpoint
        r = requests.patch(f"{API}/team/{viewer_id}", headers=ah(admin_token), json={"active": False}, timeout=10)
        assert r.status_code == 200
        try:
            # login now 403
            r = requests.post(f"{API}/auth/login", json=VIEWER, timeout=10)
            assert r.status_code == 403, r.text
            # existing token 401 on business route
            r = requests.get(f"{API}/clients", headers=ah(viewer_jwt), timeout=10)
            assert r.status_code == 401
        finally:
            # always reactivate
            r = requests.patch(f"{API}/team/{viewer_id}", headers=ah(admin_token), json={"active": True}, timeout=10)
            assert r.status_code == 200
        # verify login works again
        r = requests.post(f"{API}/auth/login", json=VIEWER, timeout=10)
        assert r.status_code == 200


# -------------------- File tokens --------------------
class TestFileTokens:
    @pytest.fixture(scope="class")
    def file_id(self, admin_token):
        # tiny PNG (1x1)
        png = bytes.fromhex(
            "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489"
            "0000000D49444154789C6300010000000500010D0A2DB40000000049454E44AE426082"
        )
        files = {"file": ("t.png", io.BytesIO(png), "image/png")}
        r = requests.post(f"{API}/files/upload",
                          headers={"Authorization": f"Bearer {admin_token}"},
                          files=files, timeout=20)
        assert r.status_code == 201, r.text
        fid = r.json()["id"]
        yield fid
        requests.delete(f"{API}/files/{fid}", headers=ah(admin_token), timeout=10)

    def test_view_token_and_download(self, admin_token, file_id):
        r = requests.get(f"{API}/files/{file_id}/view-token", headers=ah(admin_token), timeout=10)
        assert r.status_code == 200
        tok = r.json()["token"]
        r = requests.get(f"{API}/files/{file_id}/download", params={"auth": tok}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("image/")

    def test_access_jwt_rejected_in_query(self, admin_token, file_id):
        r = requests.get(f"{API}/files/{file_id}/download", params={"auth": admin_token}, timeout=15)
        assert r.status_code == 401, f"expected 401 got {r.status_code}"

    def test_bearer_header_works(self, admin_token, file_id):
        r = requests.get(f"{API}/files/{file_id}/download", headers=ah(admin_token), timeout=15)
        assert r.status_code == 200


# -------------------- Google session error handling --------------------
class TestGoogleSession:
    def test_bogus_session_id(self):
        r = requests.post(f"{API}/auth/session", json={"session_id": "bogus-xyz-123"}, timeout=20)
        assert r.status_code in (400, 401), f"expected 400/401, got {r.status_code} {r.text[:200]}"

    def test_missing_session_id(self):
        r = requests.post(f"{API}/auth/session", json={}, timeout=10)
        assert r.status_code == 400


# -------------------- Brute force --------------------
class TestBruteForce:
    def test_brute_force_locks(self):
        ident = f"bruteforce_user_{uuid.uuid4().hex[:6]}"
        codes = []
        for _ in range(11):
            r = requests.post(f"{API}/auth/login", json={"identifier": ident, "password": "wrong"}, timeout=10)
            codes.append(r.status_code)
        # first 10 401, 11th 429
        assert codes[:10] == [401] * 10, codes
        assert codes[10] == 429, codes


# -------------------- CORS --------------------
def test_cors_no_wildcard():
    r = requests.options(f"{API}/auth/login",
                         headers={"Origin": "https://evil.example.com",
                                  "Access-Control-Request-Method": "POST"},
                         timeout=10)
    # should NOT echo * or evil origin
    aco = r.headers.get("access-control-allow-origin", "")
    assert aco != "*"
    assert "evil.example.com" not in aco
