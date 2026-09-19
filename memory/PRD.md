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

### Encuestas de satisfacción (COMPLETED · 2026-09-19)
Botón "Enviar encuesta" en el formulario de un servicio existente → crea encuesta (1 por servicio, token único), copia la liga pública `/encuesta/:token` y abre WhatsApp con mensaje prellenado al teléfono del cliente. Página pública sin login: estrellas 1-5, NPS 0-10, aspectos destacados (puntualidad, calidad, precio, comunicación, limpieza), comentario; bloquea doble respuesta (409). Módulo admin `/encuestas`: KPIs (enviadas, tasa de respuesta, calificación promedio, NPS con promotores/detractores), filtros y tarjetas con respuestas; copiar liga / WhatsApp / eliminar para pendientes. Endpoints: `POST/GET /api/surveys`, `DELETE /api/surveys/{id}`, `GET /api/public/surveys/{token}`, `POST /api/public/surveys/{token}/respond`. Archivos: `pages/Encuestas.jsx`, `pages/EncuestaPublica.jsx`, `lib/surveyLink.js`.

## Backend Endpoints
Auth: `/api/auth/{login,me,logout}`. Clients, Companies, Vehicles, Technicians, Quotes, Services, Payments — all with POST/GET list/GET one/PATCH/DELETE. Dashboard: `/api/dashboard/summary`. Finance: `/api/finance/summary`. Settings: `/api/settings`.

DB: MongoDB with unique `id` indexes across every collection + folio counters collection.

## Verified End-to-End via curl
✅ Seed client → seed vehicle → seed technician → create service (auto folio OS-2026-0001, total $2,238.80 with IVA, profit $1,235) → register payment (auto-updates balance) → recibo endpoint returns enriched client + vehicle + technician data → finance summary aggregates correctly → dashboard summary counts clients/vehicles/receivable.

## Next Backlog (P2/P3)
- P1 Compresión de fotos (máx 1600px) al subir evidencias.
- P1 Envío de recibo PDF por email (Resend vía integration playbook).
- P2 Recordatorios de kilometraje (cron 6 meses / 10,000 km) + WhatsApp automatizado.
- P2 Envío automático de encuesta al marcar servicio como "entregado".
- RFC-grouped fleet consolidation view.
- Splash screen with hex animation.

## Credentials
See `/app/memory/test_credentials.md` — `admin` / `armenta123`.
