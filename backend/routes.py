# backend/routes.py

from fastapi import APIRouter, HTTPException, Query
from services import device_service, proevent_service, cache_service
from models import (DeviceOut, DeviceActionRequest, DeviceActionSummaryResponse,
                   BuildingOut, BuildingTimeRequest, BuildingTimeResponse,
                   IgnoredItemRequest, IgnoredItemBulkRequest,
                   PanelStatus)
from sqlite_config import (get_building_time, set_building_time,
                           get_ignored_proevents, set_proevent_ignore_status,
                           get_all_building_times)
from logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

# --- Panel Status Endpoints ---

@router.get("/panel_status", response_model=PanelStatus)
def get_panel_status():
    status = cache_service.get_cache_value('panel_armed')
    if status is None:
        status = True
        cache_service.set_cache_value('panel_armed', status)
    return PanelStatus(armed=status)

@router.post("/panel_status", response_model=PanelStatus)
def set_panel_status(status: PanelStatus):
    cache_service.set_cache_value('panel_armed', status.armed)
    logger.info(f"Global panel status (dummy) set to: {'Armed' if status.armed else 'Disarmed'}")
    return status


# --- Building and Device Routes ---

@router.get("/buildings", response_model=list[BuildingOut])
def list_buildings():
    """
    Fetches real buildings from PROD DB and merges schedules from SQLite DB.
    """
    logger.info("API: Fetching all buildings...")
    buildings_from_db = device_service.get_distinct_buildings() 
    schedules_from_sqlite = get_all_building_times()
    
    buildings_out = []
    for b in buildings_from_db:
        building_id = b["id"]
        schedule = schedules_from_sqlite.get(building_id)
        start_time = schedule.get("start_time", "20:00") if schedule else "20:00"

        buildings_out.append(BuildingOut(
            id=building_id,
            name=b["name"],
            start_time=start_time
        ))
    return buildings_out


@router.get("/devices", response_model=list[DeviceOut])
def list_proevents(
    building: int | None = Query(default=None),
    search: str | None = Query(default=""),
    limit: int = Query(default=100, ge=1, le=10000),
    offset: int = Query(default=0, ge=0)
):
    """
    Fetches real devices (proevents) from PROD DB and merges
    ignore status from SQLite DB.
    """
    if building is None:
        raise HTTPException(status_code=400, detail="A building ID is required.")
        
    proevents = proevent_service.get_all_proevents_for_building(
        building_id=building, search=search, limit=limit, offset=offset
    )
    
    ignored_proevents = get_ignored_proevents()
    proevents_out = []
    
    for p in proevents:
        ignore_status = ignored_proevents.get(p["id"], {})
        state_str = "armed" if p["reactive_state"] == 0 else "disarmed"
        
        proevent_out = DeviceOut(
            id=p["id"],
            name=p["name"],
            state=state_str,
            building_name=p.get("building_name", ""),
            is_ignored=ignore_status.get("ignore_on_disarm", False)
        )
        proevents_out.append(proevent_out)

    return proevents_out


# --- Schedule and Ignore Endpoints ---

@router.get("/buildings/{building_id}/time")
def get_building_scheduled_time(building_id: int):
    times = get_building_time(building_id)
    return {
        "building_id": building_id,
        "start_time": times.get("start_time") if times else None
    }

@router.post("/buildings/{building_id}/time", response_model=BuildingTimeResponse)
def set_building_scheduled_time(building_id: int, request: BuildingTimeRequest):
    if request.building_id != building_id:
        raise HTTPException(400, "Building ID in path and body must match")
        
    success = set_building_time(building_id, request.start_time)
    if not success:
        raise HTTPException(500, "Failed to update building scheduled time")
    
    return BuildingTimeResponse(
        building_id=building_id,
        start_time=request.start_time,
        updated=True
    )

@router.post("/buildings/{building_id}/reevaluate")
def reevaluate_building(building_id: int):
    """
    Triggers scheduler logic for one building immediately.
    """
    try:
        proevent_service.reevaluate_building_state(building_id)
        return {"status": "success", "message": f"Building {building_id} re-evaluated."}
    except Exception as e:
        logger.error(f"Failed to re-evaluate building {building_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to re-evaluate building: {e}")


@router.post("/proevents/ignore/bulk")
def manage_ignored_proevents_bulk(req: IgnoredItemBulkRequest):
    """
    Saves the ignore list to the local SQLite DB.
    """
    try:
        for item in req.items:
            set_proevent_ignore_status(
                item.item_id, item.building_frk, item.device_prk, 
                ignore_on_arm=False,
                ignore_on_disarm=item.ignore
            )
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error saving ignore bulk: {e}")
        raise HTTPException(500, "Failed to save ignore status")


# --- Legacy Endpoint ---

@router.post("/devices/action", response_model=DeviceActionSummaryResponse)
def device_action(req: DeviceActionRequest):
    """
    Legacy endpoint - not used by frontend.
    """
    logger.warning(f"Legacy endpoint /devices/action called for building {req.building_id}")
    
    reactive_state = 1 if req.action.lower() == "disarm" else 0
    
    try:
        affected_rows = proevent_service.set_proevent_reactive_for_building(
            req.building_id, reactive_state, []
        )
        return DeviceActionSummaryResponse(
            success_count=affected_rows,
            failure_count=0,
            details=[]
        )
    except Exception as e:
        logger.error(f"Error during legacy bulk action for building {req.building_id}: {e}")
        raise HTTPException(500, str(e))