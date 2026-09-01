"""Maps raw Ergast/Jolpica race-result `status` strings into broad categories
used by the Elo engine's crash/driver-error penalty (see PLAN.md section 3.3).

Known limitation: Ergast cannot distinguish a self-caused single-car accident
from being crashed into by someone else — both often show as "Accident" or
"Collision". We discount the penalty for "Collision" (contact, ambiguous
fault) relative to "Accident"/"Spun off" (much more likely self-inflicted)
rather than pretending we can fully resolve fault from this data source.
"""

DRIVER_FAULT = "driver_fault"
MECHANICAL = "mechanical"
FINISHED = "finished"
DISQUALIFIED = "disqualified"
OTHER = "other"

# Sub-classification of driver_fault used by penalty.py to discount ambiguous-fault
# contact incidents relative to clear single-car incidents.
SINGLE_CAR_FAULT_STATUSES = {"accident", "spun off"}
CONTACT_FAULT_STATUSES = {"collision", "collision damage"}

_DRIVER_FAULT_STATUSES = SINGLE_CAR_FAULT_STATUSES | CONTACT_FAULT_STATUSES

_OTHER_STATUSES = {
    "did not qualify",
    "did not prequalify",
    "did not start",
    "withdrew",
    "not classified",
}

_FINISHED_STATUSES = {"finished", "lapped"}


def classify(status: str) -> str:
    s = (status or "").strip().lower()
    if s in _FINISHED_STATUSES or s.startswith("+"):
        return FINISHED
    if s in _DRIVER_FAULT_STATUSES:
        return DRIVER_FAULT
    if s == "disqualified":
        return DISQUALIFIED
    if s in _OTHER_STATUSES:
        return OTHER
    # Everything else (Engine, Gearbox, Hydraulics, Electrical, Brakes,
    # Suspension, Transmission, Turbo, Puncture, Wheel, Fuel system,
    # generic "Retired", etc.) is treated as mechanical/unknown and not
    # penalized, since Ergast doesn't disambiguate driver fault here.
    return MECHANICAL
