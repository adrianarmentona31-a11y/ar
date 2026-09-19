# ARMENTA OS — Product Requirements Document

## Business Context
ARMENTA'S MOTORS is a Mexican mobile automotive service company (Ciudad Juárez). Field technicians drive an equipped mobile unit to clients (individuals, companies, fleets, auction lots).

## Brand System (implemented)
- **Brand Mark**: hexagonal SVG with red outer rim, obsidian body, chrome-silver "A" monogram — `components/BrandMark.jsx`
- **Wordmark**: SVG faithful to the identity system — chrome oval with red sports car silhouette, "ARMENTA'S" in chrome + "MOTORS" in red — `components/ArmentaWordmark.jsx`
- **Palette**: obsidian #070707/#101010, red #DC2626/#EF4444, silver #E5E7EB, status greens/ambers

## Phases Implemented (2026-02)

### Phase 1 — Núcleo (COMPLETED)
JWT auth, admin seed, protected routes, i18n ES/EN, mobile-first shell, session persistence.

### Phase 2 — Clientes (COMPLETED)
Full CRUD (particular/empresa/lote), search, filters.

### Phase 3 — Vehículos (COMPLETED)
Bound to client, VIN/plates uppercase, mileage, next-service reminder fields.

### Phase 4 — Servicios (COMPLETED)
Work orders with folio auto-generation (OS-YYYY-####), 9-state machine (lead → delivered), items editor with cost tracking + profit, status filters, quick access to receipt.

### Phase 5 — Cotizaciones (COMPLETED)
Folio auto (COT-YYYY-####), items with cost, subtotal/IVA/total auto-compute, valid-days expiry, 5 statuses (draft/sent/approved/rejected/expired), receipt preview.

### Phase 6 — Cobros / Pagos (COMPLETED)
Folio auto (PAG-YYYY-####), 4 payment methods, auto-recalculates service balance, tabular listing.

### Phase 7 — Finanzas (COMPLETED)
Revenue, cost, profit, margin %, collected, receivable, services-by-status histogram.

### Phase 8 — Técnicos (COMPLETED)
CRUD with commission model (percentage/fixed/none) and active flag.

### Phase 9 — Empresas (COMPLETED)
Corporate accounts with RFC, payment terms, credit limit for fleet consolidation.

### Configuración (COMPLETED)
Editable company info, tax rate, currency, footer note — feeds the receipt.

### Recibo de venta (COMPLETED)
Route `/recibo/:kind/:id` (kind = cotizacion | servicio). Renders professional printable receipt on white paper with brand mark + wordmark, folio pill, client/vehicle grid, items table, totals block (subtotal, IVA, TOTAL, pagado, saldo), notes + recommendations, signature lines, footer. `@media print` rules hide chrome. Fully bilingual.

## Backend Endpoints
Auth: `/api/auth/{login,me,logout}`. Clients, Companies, Vehicles, Technicians, Quotes, Services, Payments — all with POST/GET list/GET one/PATCH/DELETE. Dashboard: `/api/dashboard/summary`. Finance: `/api/finance/summary`. Settings: `/api/settings`.

DB: MongoDB with unique `id` indexes across every collection + folio counters collection.

## Verified End-to-End via curl
✅ Seed client → seed vehicle → seed technician → create service (auto folio OS-2026-0001, total $2,238.80 with IVA, profit $1,235) → register payment (auto-updates balance) → recibo endpoint returns enriched client + vehicle + technician data → finance summary aggregates correctly → dashboard summary counts clients/vehicles/receivable.

## Next Backlog (P2/P3)
- Phase 10 · Automatización: WhatsApp recordatorios (Twilio/Emergent), predictive kilometraje alerts, campaigns, AI insights.
- Evidence photos on service (fal.ai or object storage).
- PDF export of the receipt using server-side rendering (currently uses browser print).
- RFC-grouped fleet consolidation view.
- Splash screen with hex animation.

## Credentials
See `/app/memory/test_credentials.md` — `admin` / `armenta123`.
