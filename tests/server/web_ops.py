"""The update_object ops the web installation editor sends for a 2D move / turn (web/src/install/deviceOps.ts)."""

MOVE_REASON = "dipindah di editor"
TURN_REASON = "diputar di editor"


def moved(oid: str, position: list) -> dict:
    return {"op": "update_object", "id": oid, "position": position, "reason": MOVE_REASON}
