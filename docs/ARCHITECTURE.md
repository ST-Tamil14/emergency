# Architecture and safety boundaries

The UI submits scenario-level requests through REST and renders snapshots streamed over WebSockets. It does not authorize signal changes. Spring Boot proxies REST requests to the single-worker FastAPI orchestrator. A serialized simulation loop calls process-isolated controller agents over local RPC pipes. Each agent owns its capsule, observed state, local generation and last accepted sequence. Only the SUMO adapter performs TraCI operations.

## Transition sequence

ACTIVE -> capability invalidation -> FROZEN scope -> PREPARED successor -> local COMMITTED -> corridor release -> ACTIVE.

A prepared capsule carries no authority. A signed certificate binds run identity, controller identity, successor generation, capsule digest, capability digest, frontier, route and local state evidence. The local verifier checks its own fresh evidence, not merely the signature. Generation advancement is atomically replaced on disk and flushed before actuation is allowed. Commands are rejected when their run, generation, sequence or capsule binding is invalid. The implementation serializes agent calls; future concurrent transports must preserve that property.

This is a bounded implementation, not a complete formalization of every invention claim. In particular, the frontier is conservatively restricted to the entered edge, controller interfaces are emulated, and physical observation sources are simulated. See README limits.

## Run identity versus generation

A generation is local to a run. The retained prefix can remain at E1 while a successor uses E2. A command from another run is never authorized solely because its numeric generation is larger. Within a run, the watermark cannot move backward. On restart an agent enters RECOVERING rather than resuming old executable authority.

## State, time and movement

The engine advances simulated time in 0.2-second increments. Certificate freshness is one simulated second. A green-to-red transition passes through a modeled yellow interval. The emergency vehicle is held during recovery; all required successor controllers must verify before release. Actual stopping-distance design is outside this prototype. The code is not suitable for direct connection to public traffic signals.

In SUMO mode position data are taken from SUMO using the same non-normalized coordinate system as the 3D map. The browser interpolates positions for rendering only. Commanded signal states are applied to SUMO. The next observation reads the actual SUMO signal state separately from the command and combines it with observed vehicle occupancy before validating cutover. A failed sensor is represented by refusing to refresh the controller's observation timestamp.

## Storage

PostgreSQL in Compose; SQLite in quick-start mode. Both use SQLAlchemy. A saved run includes snapshots and events. Replay displays recorded states without commanding the live simulation. Certificates have per-run ephemeral signing keys. Exports include the public key for offline verification; private keys are not archived. Verification establishes consistency with that included key, not an independently trusted signer identity. Protocol canonical encoding normalizes integral JSON numbers so browser export preserves signatures. The export is evidence of what the simulator recorded, not a safety certificate.

## Threat model

Included: stale/duplicate sequence, wrong run, forged/modified certificate, wrong capsule, capability drift, missing readback, modeled partition, expired evidence and local restart.

Excluded: compromised operating system, malicious simulator, vendor firmware bypass, physical actuation bypass, Byzantine consensus, production key management, clock synchronization attacks and externally exposed multi-user operation.
