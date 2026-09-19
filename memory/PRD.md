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

### Encuestas de satisfacción (COMPLETED · 2026-09-19 · v2 Google Forms)
El usuario ya tiene un Google Form; se REEMPLAZÓ el módulo interno. `settings.survey_url` (default = liga del Google Form del usuario, editable en Configuración). Botón "Enviar encuesta" en un servicio existente abre WhatsApp al teléfono del cliente con la liga y copia la liga. QR de la encuesta impreso en el recibo PDF (junto a firmas) y en la vista web del recibo (`GET /api/qr?data=` genera PNG con `qrcode`). Archivos: `lib/surveyLink.js`, `pages/Servicios.jsx` (SurveyButton), `pages/Recibo.jsx`, `pdf_receipt.py`.

### Fase 3 (COMPLETED · 2026-09-19)
- **Email con PDF adjunto** (Emergent email proxy, `email_service.py`, `EMAIL_FROM_NAME` en .env): `POST /api/services/{id}/send-receipt-email`, `POST /api/payments/{id}/send-email`, `POST /api/notes/{id}/send-email`. Requiere email del cliente; solo `delivered@resend.dev` sirve para pruebas.
- **Encuesta automática**: al guardar un servicio que pasa a "Entregado" se abre WhatsApp con la liga de Google Forms (Servicios.jsx submit).
- **Notas de remisión** (`/notas`, colección `notes`, folio NR-YYYY-####): ticket rápido sin orden; cliente libre o existente; pagado/saldo/estatus; PDF `/api/receipts/nota/{id}/pdf`; recibo web `/recibo/nota/:id`; WhatsApp resumen; email.
- **Recibo de pago**: `GET /api/receipts/pago/{id}/pdf` + email + WhatsApp desde tabla Cobros (`PaymentActions`).
- **Validación relajada**: services/quotes/vehicles sin `client_id`; vehicles sin make/model; clients sin nombre → "Cliente sin nombre". Botones "Nuevo" siempre habilitados.
- **Nuevo diseño PDF** (`pdf_receipt.py`, estilo sencillo solicitado por el usuario: logo en caja negra, título, tabla de datos, DETALLE DE SERVICIOS, totales con TOTAL en negro, CONDICIONES Y GARANTÍA, QR encuesta al pie, paginación automática). Recibo web (`Recibo.jsx`) replica el encabezado.
- **Datos de transferencia** (`/transferencia`, `Transferencia.jsx` + `transferencia.css`): tarjeta oscura premium con titular, tarjeta, CLABE (settings `bank_holder/bank_name/bank_card/bank_clabe`, editables en Configuración), copiar y enviar por WhatsApp. Acceso desde Cobros.
- **Logos**: `public/armenta_logo.png` (hex + wordmark, bordes difuminados) en Login; `armenta_hex.png` recortado del nuevo logo; `armenta_wordmark.png` (óvalo) sin fondo rectangular, usado en PDF/recibo/transferencia.

## Backend Endpoints
Auth: `/api/auth/{login,me,logout}`. Clients, Companies, Vehicles, Technicians, Quotes, Services, Payments — all with POST/GET list/GET one/PATCH/DELETE. Dashboard: `/api/dashboard/summary`. Finance: `/api/finance/summary`. Settings: `/api/settings`.

DB: MongoDB with unique `id` indexes across every collection + folio counters collection.

## Verified End-to-End via curl
✅ Seed client → seed vehicle → seed technician → create service (auto folio OS-2026-0001, total $2,238.80 with IVA, profit $1,235) → register payment (auto-updates balance) → recibo endpoint returns enriched client + vehicle + technician data → finance summary aggregates correctly → dashboard summary counts clients/vehicles/receivable.

## Next Backlog (P2/P3)
- P1 Compresión de fotos (máx 1600px) al subir evidencias.
- P2 Recordatorios de kilometraje (cron 6 meses / 10,000 km) + WhatsApp automatizado.
- P2 Cartera vencida (saldos por cliente con días de atraso).
- P2 QR de encuesta en cotizaciones aprobadas / alerta de detractores.
- RFC-grouped fleet consolidation view.
- Splash screen with hex animation.

## Credentials
See `/app/memory/test_credentials.md` — `admin` / `armenta123`.
