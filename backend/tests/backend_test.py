"""
ARMENTA OS - Backend regression tests (Phase 2+).
Covers auth, clients, vehicles, technicians, companies, quotes, services,
payments (with recalc), settings, dashboard/finance summaries.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://armenta-hub.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"identifier": "admin", "password": "armenta123"}


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# --- health / auth
def test_health():
    r = requests.get(f"{API}/health", timeout=10)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_me(h):
    r = requests.get(f"{API}/auth/me", headers=h, timeout=10)
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


# --- clients
@pytest.fixture(scope="session")
def client_id(h):
    r = requests.post(f"{API}/clients", headers=h, json={"nombre": f"TEST_Client_{uuid.uuid4().hex[:6]}", "telefono": "555-1234", "tipo": "particular"}, timeout=10)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    yield cid
    requests.delete(f"{API}/clients/{cid}", headers=h, timeout=10)


def test_client_get_after_create(h, client_id):
    r = requests.get(f"{API}/clients/{client_id}", headers=h, timeout=10)
    assert r.status_code == 200
    assert r.json()["id"] == client_id


# --- vehicles
@pytest.fixture(scope="session")
def vehicle_id(h, client_id):
    payload = {"client_id": client_id, "make": "toyota", "model": "corolla", "year": 2020, "vin": "abc123vin", "plates": "xyz-999"}
    r = requests.post(f"{API}/vehicles", headers=h, json=payload, timeout=10)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["vin"] == "ABC123VIN"
    assert data["plates"] == "XYZ-999"
    vid = data["id"]
    yield vid
    requests.delete(f"{API}/vehicles/{vid}", headers=h, timeout=10)


def test_vehicle_requires_valid_client(h):
    r = requests.post(f"{API}/vehicles", headers=h, json={"client_id": "not-a-real-id", "make": "ford", "model": "focus"}, timeout=10)
    assert r.status_code == 400


def test_vehicle_list_enriched_with_client_name(h, vehicle_id, client_id):
    r = requests.get(f"{API}/vehicles", headers=h, timeout=10)
    assert r.status_code == 200
    items = r.json()["items"]
    found = [v for v in items if v["id"] == vehicle_id]
    assert found and "client_name" in found[0] and found[0]["client_name"]


# --- technicians
@pytest.fixture(scope="session")
def tech_id(h):
    r = requests.post(f"{API}/technicians", headers=h, json={"name": "TEST_Tech", "commission_type": "percentage", "commission_value": 10}, timeout=10)
    assert r.status_code == 201
    tid = r.json()["id"]
    yield tid
    requests.delete(f"{API}/technicians/{tid}", headers=h, timeout=10)


def test_tech_update(h, tech_id):
    r = requests.patch(f"{API}/technicians/{tech_id}", headers=h, json={"commission_type": "fixed", "commission_value": 500}, timeout=10)
    assert r.status_code == 200
    assert r.json()["commission_type"] == "fixed"


# --- companies
def test_company_crud(h):
    r = requests.post(f"{API}/companies", headers=h, json={"name": "TEST_CoMx", "rfc": "XAXX010101000", "payment_terms_days": 30, "credit_limit": 50000}, timeout=10)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["rfc"] == "XAXX010101000"
    assert r.json()["payment_terms_days"] == 30
    p = requests.patch(f"{API}/companies/{cid}", headers=h, json={"credit_limit": 75000}, timeout=10)
    assert p.status_code == 200 and p.json()["credit_limit"] == 75000
    d = requests.delete(f"{API}/companies/{cid}", headers=h, timeout=10)
    assert d.status_code == 200


# --- services (folio + totals + enrichment)
@pytest.fixture(scope="session")
def service_id(h, client_id, vehicle_id, tech_id):
    items = [
        {"description": "Aceite 5W30", "quantity": 5, "unit_price": 250.0, "cost": 150.0},
        {"description": "Mano de obra", "quantity": 1, "unit_price": 680.0, "cost": 0.0, "is_labor": True},
    ]
    r = requests.post(f"{API}/services", headers=h, json={
        "client_id": client_id, "vehicle_id": vehicle_id, "technician_id": tech_id,
        "items": items, "tax_rate": 0.16, "type": "mantenimiento",
    }, timeout=10)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["folio"].startswith("OS-")
    # subtotal = 5*250 + 680 = 1930 ; tax = 308.8 ; total = 2238.8 ; cost=750 ; profit=1180
    assert d["subtotal"] == 1930.0
    assert d["tax"] == 308.8
    assert d["total"] == 2238.8
    assert d["balance"] == 2238.8
    assert d["paid"] == 0.0
    sid = d["id"]
    yield sid
    requests.delete(f"{API}/services/{sid}", headers=h, timeout=10)


def test_service_get_enriched(h, service_id):
    r = requests.get(f"{API}/services/{service_id}", headers=h, timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert "client" in d and d["client"]["nombre"]
    assert "vehicle" in d and d["vehicle"]["make"] == "TOYOTA" or d["vehicle"]["make"] == "toyota"
    assert "technician" in d


def test_service_patch_recalcs(h, service_id):
    new_items = [{"description": "Filtro", "quantity": 2, "unit_price": 100.0, "cost": 40.0}]
    r = requests.patch(f"{API}/services/{service_id}", headers=h, json={"items": new_items, "tax_rate": 0.16}, timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["subtotal"] == 200.0
    assert d["tax"] == 32.0
    assert d["total"] == 232.0
    # restore items back
    orig = [
        {"description": "Aceite 5W30", "quantity": 5, "unit_price": 250.0, "cost": 150.0},
        {"description": "Mano de obra", "quantity": 1, "unit_price": 680.0, "cost": 0.0, "is_labor": True},
    ]
    requests.patch(f"{API}/services/{service_id}", headers=h, json={"items": orig, "tax_rate": 0.16}, timeout=10)


# --- payments (recalc)
def test_payment_recalcs_service(h, service_id):
    r = requests.post(f"{API}/payments", headers=h, json={"service_id": service_id, "amount": 1000.0, "method": "cash"}, timeout=10)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    s = requests.get(f"{API}/services/{service_id}", headers=h, timeout=10).json()
    assert s["paid"] == 1000.0
    assert round(s["balance"], 2) == round(s["total"] - 1000.0, 2)
    # delete payment -> balance back
    requests.delete(f"{API}/payments/{pid}", headers=h, timeout=10)
    s2 = requests.get(f"{API}/services/{service_id}", headers=h, timeout=10).json()
    assert s2["paid"] == 0.0
    assert s2["balance"] == s2["total"]


# --- quotes
def test_quote_create_and_get(h, client_id, vehicle_id):
    r = requests.post(f"{API}/quotes", headers=h, json={
        "client_id": client_id, "vehicle_id": vehicle_id,
        "items": [{"description": "X", "quantity": 1, "unit_price": 100, "cost": 40}],
        "tax_rate": 0.16, "valid_days": 10,
    }, timeout=10)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["folio"].startswith("COT-")
    assert d["expires_at"]
    qid = d["id"]
    g = requests.get(f"{API}/quotes/{qid}", headers=h, timeout=10).json()
    assert g.get("client") and g.get("vehicle")
    requests.delete(f"{API}/quotes/{qid}", headers=h, timeout=10)


# --- settings singleton
def test_settings_singleton(h):
    r = requests.get(f"{API}/settings", headers=h, timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert "company_name" in d
    assert d.get("currency") == "MXN" or "currency" in d
    p = requests.patch(f"{API}/settings", headers=h, json={"tax_rate": 0.16}, timeout=10)
    assert p.status_code == 200
    assert p.json()["tax_rate"] == 0.16


# --- dashboard + finance
def test_dashboard_summary(h):
    r = requests.get(f"{API}/dashboard/summary", headers=h, timeout=10)
    assert r.status_code == 200
    d = r.json()
    for k in ("clients_total", "vehicles_total", "receivable_total_mxn", "quotes_pending", "services_today", "system_status"):
        assert k in d, f"missing {k}"
    assert d["system_status"] == "operativo"


def test_finance_summary(h):
    r = requests.get(f"{API}/finance/summary", headers=h, timeout=10)
    assert r.status_code == 200
    d = r.json()
    for k in ("revenue", "cost", "profit", "collected", "receivable", "services_by_status"):
        assert k in d


# --- Phase 3: Notes / receipts / relaxed validation / bank settings / emails ---

def test_notes_crud_and_folio(h):
    """POST /api/notes computes totals and status; folio NR-YYYY-####; PATCH recalcs; DELETE removes."""
    payload = {
        "client_name": "TEST_NoteClient",
        "client_phone": "555-0000",
        "client_email": "delivered@resend.dev",
        "items": [{"description": "Item A", "quantity": 2, "unit_price": 100.0, "cost": 40.0},
                  {"description": "Item B", "quantity": 1, "unit_price": 50.0, "cost": 20.0}],
        "tax_rate": 0.16,
        "paid_amount": 100.0,
    }
    r = requests.post(f"{API}/notes", headers=h, json=payload, timeout=15)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["folio"].startswith("NR-")
    assert d["subtotal"] == 250.0
    assert d["tax"] == 40.0
    assert d["total"] == 290.0
    assert d["paid_amount"] == 100.0
    assert d["balance"] == 190.0
    assert d["status"] == "pendiente"
    nid = d["id"]

    # list
    r = requests.get(f"{API}/notes", headers=h, timeout=10)
    assert r.status_code == 200 and any(n["id"] == nid for n in r.json()["items"])

    # get enriched
    r = requests.get(f"{API}/notes/{nid}", headers=h, timeout=10)
    assert r.status_code == 200
    assert r.json().get("client", {}).get("nombre") == "TEST_NoteClient"

    # patch pay full -> pagada
    r = requests.patch(f"{API}/notes/{nid}", headers=h, json={"paid_amount": 290.0}, timeout=10)
    assert r.status_code == 200
    assert r.json()["status"] == "pagada"
    assert r.json()["balance"] == 0.0

    # PDF endpoints
    for path in (f"/receipts/nota/{nid}/pdf",):
        r = requests.get(f"{API}{path}", headers=h, timeout=20)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    # send-email note (delivered@resend.dev) - may take time
    r = requests.post(f"{API}/notes/{nid}/send-email", headers=h, timeout=30)
    assert r.status_code in (200, 502), r.text
    if r.status_code == 200:
        j = r.json()
        assert j.get("ok") is True
        assert j.get("email_id")

    # delete
    r = requests.delete(f"{API}/notes/{nid}", headers=h, timeout=10)
    assert r.status_code == 200
    r = requests.get(f"{API}/notes/{nid}", headers=h, timeout=10)
    assert r.status_code == 404


def test_relaxed_validation(h):
    """services/vehicles/clients/quotes can be created with minimal payloads."""
    # service without client_id
    r = requests.post(f"{API}/services", headers=h, json={}, timeout=10)
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    requests.delete(f"{API}/services/{sid}", headers=h, timeout=10)

    # vehicle with only year
    r = requests.post(f"{API}/vehicles", headers=h, json={"year": 2020}, timeout=10)
    assert r.status_code == 201, r.text
    vid = r.json()["id"]
    requests.delete(f"{API}/vehicles/{vid}", headers=h, timeout=10)

    # client with only tipo
    r = requests.post(f"{API}/clients", headers=h, json={"tipo": "particular"}, timeout=10)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["nombre"] == "Cliente sin nombre"
    requests.delete(f"{API}/clients/{d['id']}", headers=h, timeout=10)

    # quote with items=[]
    r = requests.post(f"{API}/quotes", headers=h, json={"items": []}, timeout=10)
    assert r.status_code == 201, r.text
    qid = r.json()["id"]
    requests.delete(f"{API}/quotes/{qid}", headers=h, timeout=10)


def test_settings_bank_and_survey(h):
    r = requests.patch(f"{API}/settings", headers=h, json={
        "bank_holder": "TEST_Holder", "bank_name": "TEST_Bank",
        "bank_card": "1234 5678 9012 3456", "bank_clabe": "012345678901234567",
        "survey_url": "https://forms.gle/testsurvey",
    }, timeout=10)
    assert r.status_code == 200
    r = requests.get(f"{API}/settings", headers=h, timeout=10)
    d = r.json()
    assert d["bank_holder"] == "TEST_Holder"
    assert d["bank_card"] == "1234 5678 9012 3456"
    assert d["bank_clabe"] == "012345678901234567"
    assert d["survey_url"] == "https://forms.gle/testsurvey"


def test_qr_endpoint():
    r = requests.get(f"{API}/qr?data=https://x.y", timeout=10)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")


def test_service_payment_receipt_pdfs_and_email(h, client_id, vehicle_id):
    """Full flow: create client with email + service + payment; test receipt PDFs and send-email."""
    # patch client with delivered@resend.dev email
    requests.patch(f"{API}/clients/{client_id}", headers=h, json={"email": "delivered@resend.dev"}, timeout=10)

    r = requests.post(f"{API}/services", headers=h, json={
        "client_id": client_id, "vehicle_id": vehicle_id,
        "items": [{"description": "Aceite", "quantity": 1, "unit_price": 500.0, "cost": 200.0}],
        "tax_rate": 0.16,
    }, timeout=10)
    assert r.status_code == 201
    sid = r.json()["id"]

    # servicio PDF
    r = requests.get(f"{API}/receipts/servicio/{sid}/pdf", headers=h, timeout=20)
    assert r.status_code == 200 and r.content[:4] == b"%PDF"

    # cotizacion PDF via quote
    rq = requests.post(f"{API}/quotes", headers=h, json={
        "client_id": client_id, "items": [{"description": "X", "quantity": 1, "unit_price": 100, "cost": 40}],
    }, timeout=10)
    qid = rq.json()["id"]
    r = requests.get(f"{API}/receipts/cotizacion/{qid}/pdf", headers=h, timeout=20)
    assert r.status_code == 200 and r.content[:4] == b"%PDF"

    # payment + pago PDF + email
    rp = requests.post(f"{API}/payments", headers=h, json={"service_id": sid, "amount": 300.0, "method": "cash"}, timeout=10)
    assert rp.status_code == 201
    pid = rp.json()["id"]
    r = requests.get(f"{API}/receipts/pago/{pid}/pdf", headers=h, timeout=20)
    assert r.status_code == 200 and r.content[:4] == b"%PDF"

    # payment email
    r = requests.post(f"{API}/payments/{pid}/send-email", headers=h, timeout=30)
    assert r.status_code in (200, 502), r.text
    if r.status_code == 200:
        j = r.json()
        assert j.get("ok") is True and j.get("email_id")

    # service send-receipt-email
    r = requests.post(f"{API}/services/{sid}/send-receipt-email", headers=h, timeout=30)
    assert r.status_code in (200, 502), r.text

    # cleanup
    requests.delete(f"{API}/payments/{pid}", headers=h, timeout=10)
    requests.delete(f"{API}/quotes/{qid}", headers=h, timeout=10)
    requests.delete(f"{API}/services/{sid}", headers=h, timeout=10)


def test_service_email_400_without_client_email(h):
    """When client has no email, POST /api/services/{id}/send-receipt-email returns 400."""
    # Create a fresh client with NO email
    rc = requests.post(f"{API}/clients", headers=h, json={"nombre": "TEST_NoEmail", "tipo": "particular"}, timeout=10)
    cid = rc.json()["id"]
    rs = requests.post(f"{API}/services", headers=h, json={"client_id": cid, "items": [{"description": "X", "quantity": 1, "unit_price": 10.0, "cost": 0}]}, timeout=10)
    sid = rs.json()["id"]
    r = requests.post(f"{API}/services/{sid}/send-receipt-email", headers=h, timeout=15)
    assert r.status_code == 400, r.text
    requests.delete(f"{API}/services/{sid}", headers=h, timeout=10)
    requests.delete(f"{API}/clients/{cid}", headers=h, timeout=10)
