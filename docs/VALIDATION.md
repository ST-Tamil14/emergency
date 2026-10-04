# Validation record

Validation applies to this bounded software research prototype, not physical traffic equipment.

## Current v0.2 validation ? 25 September 2026

- Final research Docker image: **45 tests passed**, including real SUMO, repeated/superseded generations, entered-road preservation, timed and approach triggers, individual resolution, no-route fallback, traffic-cost routing, API validation, persisted schedules, repeated experiments and eight isolated controller processes.
- Windows Python 3.11: 44-test full suite passed, followed by the added repeated-experiment test passing separately. Docker ran the complete 45-test suite on Python 3.12.
- TypeScript/Vite production build passed on Windows and in the frontend Docker image. Vite reports the existing large 3D bundle warning; this is not a build failure.
- Headless Microsoft Edge: repeated SUMO incidents through E3, stale-command rejection, approach scheduling/cancellation, individual resolution, saved incident presets, desktop/mobile rendering and no horizontal overflow. No browser page errors. See [advanced browser report](../experiments/advanced-browser-validation.json) and [dashboard screenshot](advanced-dashboard.png).
- Docker Compose deployment passed: Nginx frontend, Spring gateway, PostgreSQL, research service and eight controller processes. API health reports 0.2.0; the deployed browser receives WebSocket telemetry and persisted presets/runs. Existing saved data remains available. See [deployed-stack report](../experiments/advanced-docker-validation.json).
- A deployed SUMO repeated-disruption comparison (seed 0, density 0) completed for both strategies: 65 simulated seconds, two committed transfers, 6.8 seconds total committed recovery time, one rejected stale command and zero reported collisions per run. Partial recovery counted 11 controller reconfigurations versus 16 for whole-network rebuilding. These two runs do **not** establish a travel-time advantage or general safety.
- The expanded network and route objective change the experiment baseline. Historical v0.1 results below remain historical evidence, not measurements for v0.2.
- A dependency deprecation warning from Starlette's httpx TestClient is present; tests pass.

See [advanced incident guide](ADVANCED-INCIDENTS.md) for commands, assumptions and remaining deployment limits.

## Historical v0.1 automated checks

- Python unit/integration suite: **23 passed**. Includes invalid signatures, altered capabilities, expired/future evidence, stale generations, duplicate sequence numbers, wrong run identity, incompatible native commands, restart fencing, preparation gating, dependency gating, observed-versus-commanded phase distinction, browser numeric round-trip signature stability, isolated controller processes and API/WebSocket persistence flows.
- React/TypeScript production build: passed.
- Spring Boot Java 17 build: passed. Packaged gateway health and proxy response also checked during browser validation.
- Browser: packaged production UI, real SUMO telemetry, fault injection, recovery, stale rejection, certificate inspection, scenario saving, SUMO batch execution, saved-run replay and mobile layout. See `experiments/browser-validation.json` for the machine-readable result.
- Offline verification passed for all 4 certificates in the browser-exported `experiments/sample-run.json`. Recheck with `experiments/verify_export.py`. This verifies consistency with the exported public key; it does not authenticate an independently trusted signer.

## Historical v0.1 bounded simulation experiments

`experiments/validation-results.json` contains 16 measured runs:

- 3 seeds x 2 strategies x 2 engines = 12 runs.
- 4 additional SUMO runs for write denial, configuration drift, communication-partition modelling and pedestrian-clearance delay.

All 16 reached the destination and rejected the injected superseded command. No superseded command was accepted in these checks. No SUMO collision was reported in these sampled runs. These observations are not a proof of safety over all inputs.

For the recorded readback-failure scenarios, partial recovery reconfigured 5 controllers versus 6 for the whole-network baseline. Both strategies had equal ambulance travel time for the same seed. Do not claim a travel-time improvement from these experiments. The pedestrian scenario can have a different reconfiguration count because it does not require bypassing J3.

The `unsafe_acceptances` field counts the deliberately replayed stale-command acceptance test only; it is not a comprehensive physical safety metric. `collisions` is the SUMO-reported count and is null for the kinematic model.

## Historical v0.1 environment limits (superseded by v0.2 checks above)

- Windows launcher execution on an actual Windows machine. The commands are provided and the equivalent Python/application path was tested on Linux.
- Docker Compose/PostgreSQL deployment: Docker was unavailable. Configuration is included; SQLAlchemy supports the configured PostgreSQL driver, but the full container path still needs a deployment smoke test.
- Physical controllers, calibrated city demand, real pedestrian sensing, real communication partitions and roadside deployment.

## Reproduce

From project root after setup:

```powershell
cd research-service
..\.venv\Scripts\python.exe -m pytest -q
cd ..
.\.venv\Scripts\python.exe experiments\validate.py
.\.venv\Scripts\python.exe experiments\verify_export.py experiments\sample-run.json
```

To run browser checks, install frontend development dependencies, install the Playwright Chromium browser, and ensure Java 17 and the packaged gateway jar are available. Stop any already-running service on ports 8000 and 8080 before running the smoke script.

```powershell
cd frontend
npm ci
npx playwright install chromium
npm run build
npm run test:e2e
```

Browser checks initialize their own server and generate screenshots and a validation JSON file.
