# Demonstration guide

## Before presenting

Run START-WINDOWS.bat after installing Python 3.12. Allow package installation to finish. Open http://127.0.0.1:8000. Confirm the page says "Service connected" and "SUMO microsimulation".

## Three-minute demonstration

1. Explain: "This is a distributed traffic-control research simulator. It recovers only the affected execution scope and checks state before changing command ownership."
2. Show the 3D city. Drag to orbit and scroll to zoom. Select a junction to view its generation, readback and write authority.
3. Start the simulation. The ambulance moves according to SUMO position updates.
4. Within the first few seconds, inject a J3 readback failure. Select J3 in the inspector.
5. Point out the failed capability, frozen old scope and prepared alternate route.
6. Observe the verification events. A certificate is created and verified per successor controller. Generation E2 activates after the release barrier is satisfied.
7. Press Replay stale command. The delayed E1 command is rejected locally.
8. Inspect a certificate to show the capsule digest, state evidence and freshness interval.
9. Save the run in Run history. Replay it and move the timeline slider.
10. Export the run. Its settings, measurements, events, signed tokens, public verification key and replay frames are included.

## Second demonstration: withholding

Reset. Inject a J3 pedestrian-clearance fault. During its modeled eight-second clearance interval, the affected controller does not commit even if other controllers have already verified. The ambulance remains held until all required successor dependencies are ready. This is a synthetic clearance obligation; do not describe it as a real pedestrian sensor.

## Third demonstration: fallback

Reset and fail J1 while the ambulance is on its initial approach. The model cannot reassign the already-entered edge. It enters fallback. Restore capability or reset.

## Experiments

Select SUMO and 3 seeds, then Run comparison. The app runs both strategies for the same conditions. Compare reconfigured-controller counts, recovery time, and stale-command rejection. A smaller scope does not automatically produce faster ambulance arrival: report equal outcomes when the measured values are equal.

## Honest presentation statements

- Controller processes are isolated software emulations, not physical NTCIP devices.
- The local commitment protocol is not simultaneous global commitment.
- No collisions in sampled runs does not prove safety for every possible traffic condition.
- The general patent claim and the bounded demonstrator are different scopes; consult README for implementation limits.
