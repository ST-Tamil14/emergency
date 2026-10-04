# Repeated incident recovery (v0.2)

The live simulation supports multiple independently resolved incidents, scheduled activation, and repeated signed generation transfers in a single journey. This is an advanced simulation platform; it is not an industrial traffic controller deployment.

## Try the accident near J3

1. Reset the live simulation, then open **Incident control**.
2. Choose **Accident / blocked lane**, road **J3 → J6**, and **When approaching junction**.
3. Select **J3**, distance **30 m**, and a duration such as **30 seconds**. Press **Schedule incident**.
4. Start the simulation. The accident activates as the ambulance approaches J3. The engine retains its entered road and evaluates legal exits, including the new bypass through J8.
5. Add another signal or road incident while moving or while a generation is being prepared. All active incidents constrain the new plan. The recovery history records committed and superseded generations.
6. Use the individual **Resolve** buttons. **Restore Jn** only clears that selected controller's incidents.

A blockage ahead in the ambulance's current lane holds it immediately in the model. Resolving or expiring the blockage triggers fresh verification. A fault at the current target signal also holds the ambulance. An accident behind the ambulance on its current edge does not force it to reverse. SUMO vehicles already inside an internal junction finish their entered movement before planning from the outgoing road; they cannot switch to a different exit mid-junction.

## Incident model

Kinds: accident, directional road closure, congestion, readback loss, write denial, communication partition, configuration drift, pedestrian clearance. The network has eight junctions, thirteen bidirectional road links, and **one lane per direction**. Lane 0 is the only supported lane. Accident position is a fraction of the directed road length, displayed as a percentage. There is no simulated crash physics or lane-change maneuver.

Triggers use simulation time: immediate, absolute simulation seconds, or remaining route distance before a junction. Pausing also pauses schedules and durations. Approach triggers stay scheduled if a reroute avoids that junction; they become `MISSED` when the journey finishes. Duration runs from activation, not scheduling. Cancellation affects only a scheduled incident; resolution affects only the selected active incident. Overlapping incidents combine, so resolving one cannot silently clear another.

SUMO lane permissions prevent entry to closed roads and lane speed limits apply congestion. The entered emergency lane is held conservatively when blocked ahead. The kinematic engine models the same routing/hold constraints without claiming microsimulation measurements.

## Route objective and verification

Planning runs on incident activation or resolution. It evaluates directed, simple downstream routes, excludes unavailable controllers and closed directions, and retains the entered road and travelled prefix. SUMO candidates must obey the generated network's actual turn connections. See SUMO's [route replacement requirements](https://sumo.dlr.de/pydoc/traci._vehicle.html) and [lane controls](https://sumo.dlr.de/pydoc/traci._lane.html).

The objective uses estimated remaining travel time, a modeled 3.4-second recovery allowance, and a 2-second route-change penalty. SUMO costs use road length, measured mean speed and stopped-vehicle count (1.5 seconds per queued vehicle); pedestrian clearance adds pending delay. Empty roads use free-flow speed. The kinematic model uses its modeled speed. These coefficients are explicit demonstration assumptions, not a calibrated traffic prediction model. Feasible routes must improve the objective by at least 3 seconds to replace a still-feasible current route. Blocked routes do not receive this hysteresis protection.

Up to three alternatives show remaining distance, ETA and reconfiguration scope. “Fastest estimated” and “Least reconfiguration” labels are calculated across the enumerated candidates. All candidates exclude unavailable controllers. This bounded network searches up to 100 paths; it is not an unrestricted city-scale optimizer. The estimates are refreshed each simulated second; displayed alternatives describe the last incident decision, rather than continuous optimization.

Each prepared generation binds the current incident revision into its signed capsule. A subsequent incident invalidates the pending plan, freezes its scope, and allocates a new generation even if some old candidates already committed locally. Release requires every successor controller at the exact intended generation. Prior committed fences remain monotonic. Configuration restoration requires a newly bound capsule if that controller is used again.

## Reproducibility and experiments

In **Scenarios**, **Use current incident schedule** copies the run's incident requests into a preset. Immediate injections become absolute-time triggers at their original creation time. Canceled incidents are excluded. Save and apply the preset to replay the initial schedule; manual resolution actions are retained in run history but are not automatically added to the preset.

**Experiments → Repeated disruptions** runs a J3 readback failure at 4 seconds, a J5 partition at 8 seconds, and 70% speed reduction on J8 → E at 12 seconds for 20 seconds. Both partial and whole-network strategies use the same seed and schedule. Results include committed recovery count, cumulative controller reconfiguration work, cumulative committed recovery duration, stale-command rejections, and final outcome. A controller counted in two recoveries contributes twice to cumulative work. Superseded preparation work contributes to reconfiguration count; its delay is visible in history but not counted as committed recovery duration.

Exports use schema version 2 / algorithm version 0.2.0. Saved frames contain incident state, route decisions and generation history. Existing v0.1 experiment data remains historical and should not be mixed with results from the expanded network.

## Persistence and operations

Live runs are checkpointed at incident changes and every five simulated seconds, and saved on graceful shutdown. Saved checkpoints are inspectable and replayable; restarting creates a **new journey** and signing authority. Active vehicle state is not restored into SUMO. Batch partial results are persisted after each run; a saved running batch is marked `INTERRUPTED` on service startup. Docker services restart unless stopped, and container logs rotate at 10 MB with three retained files. Existing PostgreSQL and controller volumes remain in use.

Still outside this upgrade: multi-ambulance coordination; multi-lane driving; calibrated pedestrian demand and city traffic; automatic live-journey/job resumption; authenticated operator roles and TLS termination; managed signing keys; validated vendor interfaces; alerting and automated backup policy; real-road trials and independent safety validation. The application remains bound to localhost.

## Validation commands

```powershell
cd research-service
$env:RUN_SUMO_TESTS = "1"
..\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm ci
npm run build
node tests/incidents.cjs
```

The browser test uses a separate local SUMO service on port 8017, a separate SQLite database under `.qa`, and installed Microsoft Edge in headless mode. Set `BROWSER_CHANNEL=chrome` to use installed Chrome. Reports and screenshots are written under `.qa`. SUMO tests exercise route continuity, repeated transfers, approaching-J3 incidents, internal-junction deferral, and expired current-road closures.

The running local Compose stack can also be checked with `node tests/docker-smoke.cjs` from `frontend`. This check creates one SUMO comparison and a saved J3-accident preset; it stages the preset only if the live run is still idle at time zero. See [validation record](VALIDATION.md) for recorded results.
