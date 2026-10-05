# Animated Command Centre UI

The UI upgrade lives in this repository, `emergency-corridor-recovery`. The separate extracted copy under `Desktop/Proctor/emergency` is not modified.

## Ten connected pages

| Page | Working interaction |
|---|---|
| Command Centre | 3D vehicle tracking, incident injection, recovery stages, controller evidence and event stream |
| Missions | Current ambulance, route, destination, ETA and backend event timeline |
| Route Planner | Select a calculated alternative to preview it in 3D; previewing does not activate it |
| Incident Centre | Network impact view, status filters, scheduling, individual resolution and cancellation |
| Controllers | Select one of eight controller cards to inspect phase, freshness, capability and generation evidence |
| Hospitals | 3D destination context with explicit unknown acceptance/capacity status |
| Scenarios | Configure simulation settings and save or reuse incident schedules |
| Experiments | Run matched recovery strategies with progress and measured results |
| Analytics | Generation-duration chart, recorded counters and event timeline |
| Run history | Save/export runs and play recorded frames with a scrubber and 0.5×–4× playback speed |

## Animation and display rules

- The city uses real Three.js geometry, including buildings, streets, vehicles, trees and a hospital. It is a synthetic simulation network, not an imported geographic map.
- Vehicle positions interpolate only between backend observations. Motion freezes on pause, replay frame selection, or stale telemetry. Vehicles are never animated along an invented journey.
- Follow, overview reset and top-down camera controls are available in every city view.
- A purple dashed route is an alternative preview; it does not confer signal authority. Physical signal lamps remain separate from generation and verification state.
- Recovery progress uses events and certificates belonging to the current generation, rather than a presentation timer.
- Page transitions, chart updates and panel motion support system reduced-motion preferences and the accessibility button in the top bar.
- Telemetry older than five seconds disables simulation mutation controls. Dialogs support Escape, focus containment and focus restoration.
- The hospital page does not invent admission, bed capacity or clinical data. The backend continues to model one ambulance.

## Build and run

From the project root:

```powershell
cd frontend
npm ci
npm run build
cd ..\research-service
$env:SIMULATION_MODE = "sumo"
$env:AGENT_MODE = "process"
..\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8020
```

Open **http://127.0.0.1:8020**. Using a different port avoids confusing this build with an older service on port 8000. For the explicitly labeled protocol model, set `SIMULATION_MODE` to `kinematic` before starting.

The existing Docker stack can use the same frontend through `docker compose up -d --build frontend`. The Python API is unchanged by this UI upgrade.

## Browser validation and animated tour

```powershell
cd frontend
npx playwright install ffmpeg
npm run test:ui
```

This uses installed Microsoft Edge (or `BROWSER_CHANNEL=chrome`) and starts an isolated SUMO service on port 8019. It records actual app interactions and tests all ten desktop/mobile pages, route previews, controller selection, replay, stale telemetry, camera controls and reduced motion.

Artifacts are saved under `.qa/ui-tour/`: a screenshot for each page, `command-centre-tour.webm`, and `report.json`. Test data is isolated from existing saved runs. These artifacts are ignored by Git.

Validated on this machine: production build passed; all ten pages fit desktop and mobile; SUMO incident recovery, stale-command rejection, route previews, controller selection, replay, stale telemetry and camera controls passed without browser exceptions. The Three.js bundle still produces Vite's size advisory and is loaded separately from the main UI.

The local preview started for this upgrade uses port 8020 and `.qa/ui-preview.db`, keeping its saved runs separate from other running copies.
