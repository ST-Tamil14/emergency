# Corridor Emergency Traffic Recovery

A runnable research application for state-coupled recovery of a simulated emergency traffic corridor. Includes a connected 3D city, SUMO traffic simulation, independent controller processes, signed state-transfer authorization, stale-command rejection, fault injection, saved scenarios, experiment comparisons, and run replay.

**Status:** implementation v0.2, simulation prototype. It is not a roadside controller product, a safety-certified system, or proof of patent novelty. It does not reproduce the unverified numerical results in the supplied invention draft.

## Advanced incidents

Use **Incident control** to add accidents, directional road closures, congestion or signal faults while the ambulance moves. Schedule incidents by simulation time or junction approach, resolve them individually, and inspect repeated E2/E3 transfers, estimated route alternatives and decision explanations. The network now has eight junctions with additional bypasses. See [Advanced incident guide](docs/ADVANCED-INCIDENTS.md) for the J3 accident walkthrough, reusable schedules, validation, and deployment limits.

## Start here on Windows

### Easiest packaged start

Install Python 3.12, extract the ZIP, and double-click **START-WINDOWS.bat**. The launcher creates a Python environment, installs the simulation dependencies, and opens **http://127.0.0.1:8000**. It uses the included production frontend, so Node.js and Maven are not required just to run this mode. Internet access is needed for initial Python package installation. No administrator rights are needed. The batch file permits this local PowerShell setup script to run for that process only.

This single-service mode runs the real Python/SUMO engine and isolated controller processes with SQLite. Use the development instructions below to edit the interface, or Docker for the full Spring Boot/PostgreSQL stack.

### Option A — development mode

Requires Python 3.11 or 3.12 and Node.js 22 LTS. Open PowerShell in the extracted `emergency-corridor-recovery` directory. Do not use `C:\Windows\System32`.

First terminal:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r research-service\requirements.txt
cd research-service
$env:SIMULATION_MODE = "sumo"
$env:AGENT_MODE = "process"
..\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

If Python 3.11 is installed, use `py -3.11` in the first command. No environment activation is required. If the SUMO package does not provide a working binary on your machine, install Eclipse SUMO separately and add its `bin` directory to PATH, or set `SIMULATION_MODE` to `kinematic` for explicitly labelled protocol-model operation. Do not label kinematic output as SUMO output.

Second terminal, in the extracted project directory:

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open **http://127.0.0.1:5173**. Keep both terminals open. This mode uses SQLite, avoids PostgreSQL setup, and connects React directly to the Python API. Eight controller agents run as child Python processes when `AGENT_MODE=process`.

### Add the Spring Boot gateway locally

Requires Java 17. The package includes a compiled gateway, which can be started with `java -jar backend/target/corridor-backend-0.1.0.jar` from the project root. To rebuild or develop it, use Maven 3.9 in a third terminal:

```powershell
cd backend
mvn spring-boot:run
```

Restart the frontend terminal with:

```powershell
$env:VITE_API_TARGET = "http://127.0.0.1:8080"
npm run dev -- --host 127.0.0.1
```

REST requests now pass through Spring Boot; WebSocket telemetry connects directly to the research service. Spring Boot currently acts as the application API gateway. Scenario and result persistence are owned by the research service; account management is not implemented.

### Option B — full container stack

Requires Docker Desktop using Linux containers. From the project directory:

```powershell
Copy-Item .env.example .env
notepad .env
docker compose up --build
```

Set a long alphanumeric password in `.env`. Open **http://localhost:8088**. This deployment uses PostgreSQL, Spring Boot, the Python/SUMO service, process-isolated controllers, and the 3D frontend. The application binds only to localhost and has no authentication; do not expose it to a public network without adding access control.

The v0.2 Docker/PostgreSQL stack has been built and tested on Windows Docker Desktop, including repeated SUMO recovery, isolated controller processes, browser telemetry and saved scenarios. See `docs/VALIDATION.md` for measured results and limits.

Stop without deleting data:

```powershell
docker compose down
```

## First demonstration

1. Open **Live corridor** and press **Start simulation**.
2. Within the first several seconds, open **Incident control**.
3. Choose **Loss of phase readback**, controller **J3**, and inject the incident.
4. Watch the replacement route through J5. Successor capsules remain prepared while clearance predicates are pending.
5. Observe per-controller verification and the E2 release event.
6. Press **Replay stale command**. The inspector/event log reports rejection.
7. Inspect the signed certificates.
8. Save the run in **Run history**, then replay recorded frames.
9. Use **Experiments** to compare whole-network and partial recovery in SUMO or the explicitly labelled kinematic model.

To demonstrate fallback, reset, start, and fail **J1** before the ambulance leaves its current approach. That already-entered edge cannot be reassigned; the model holds the vehicle. Restore capability or reset to continue. For delayed local commitment, inject the pedestrian-clearance fault; this is a synthetic 8-second clearance obligation, not generated pedestrian demand.

## What is implemented

- React/TypeScript and Three.js city, vehicle interpolation, flashing ambulance beacon, signal indicators, orbit/follow cameras, responsive views.
- SUMO network generation, traffic-light actuation, vehicle states and rerouting through TraCI.
- A separately labelled deterministic kinematic model for fast protocol experiments.
- Eight process-isolated controllers (or in-process unit-test mode), configurable readback/write/connection faults.
- Runtime capability digests and explicit movement-obligation records.
- Conservative frontier at the destination of the already-entered edge; no teleporting or retrospective reassignment of that edge.
- Suffix replacement, non-actuating capsule storage, Ed25519-signed certificates, local evidence and freshness checks, durable generation fencing.
- A corridor release barrier: all required successor controllers must commit before the ambulance resumes. This is local commitment plus dependency gating, **not a globally atomic distributed transaction**.
- Three-second modeled yellow clearance and an additional 0.4-second all-red hold. These demonstration parameters are not jurisdiction-approved timings.
- Failure injection, old-command replay, capability restoration, save/export and recorded playback.
- PostgreSQL/SQLite-compatible persistence, seeded batch jobs with cancellation and measured outputs.
- Spring Boot API gateway and Docker Compose packaging.

## Deliberate limits

1. Controller profiles emulate three different command interfaces: phase hold, program selection and gateway permission. The compiler produces profile-specific commands and the local verifier rejects incompatible native commands. They are not validated NTCIP or vendor-native implementations. Profile names do not establish heterogeneous protocol interoperability.
2. The authority generates a signing key per run. Certificates are not accepted for actuation across application restarts. Exported public keys allow offline signature verification of archived certificates. A controller-agent restart reloads its durable generation watermark but withholds actuation until new verification; orchestrator restart starts a new experiment.
3. Local process pipes are a trusted emulator transport. Communication-partition faults model lost observations and unavailable command authority; the simulator retains an idealized out-of-band interlock. Real disconnected equipment cannot be assumed to accept a freeze command.
4. Conflict occupancy is observed from SUMO internal-lane occupancy. This is simulated evidence, not an independently verified physical sensor.
5. Background traffic is a bounded single route. This is not a calibrated city demand model. Pedestrian clearance is an injected timer; SUMO pedestrians, multiple emergencies and calibrated driver behaviour are not implemented.
6. Frontier selection is conservative and does not claim to solve the full general minimum-rebindable-suffix problem in the patent specification.
7. Old-generation rejection is tested locally. No formal proof covering arbitrary failures, Byzantine controllers, unbounded message delays or real-road safety is claimed.
8. The application supports repeated incidents and recoveries in one journey. Incident schedules, decisions, and replay frames persist; automatic active-journey or job resumption after restart is not implemented.
9. Experimental batch comparisons support SUMO and the kinematic model, with the selected engine recorded in each result.

## Tests

```powershell
cd research-service
..\.venv\Scripts\python.exe -m pytest -q
```

Frontend production build:

```powershell
cd frontend
npm run build
```

Python service API: http://127.0.0.1:8000/docs
Spring health: http://127.0.0.1:8080/actuator/health

## Project layout

- `frontend/` — connected React 3D application.
- `research-service/` — engine, controller protocol, agent processes, simulator adapters, API and persistence.
- `backend/` — Java 17 Spring Boot gateway.
- `experiments/` — generated validation artifacts and reproducibility scripts.
- `docs/` — implementation boundaries, validation and screenshots.
- `compose.yaml` — full local deployment.

## Reproducibility

Exports contain the seed, traffic mode, configuration, algorithm version, events, certificates and sampled replay frames. The event log records simulated timestamps; wall time is reported separately. Repeatability depends on the same dependency versions and engine configuration. `requirements-lock.txt` and the frontend lockfile record the tested environment. Never substitute the draft's numerical claims for measured results.
