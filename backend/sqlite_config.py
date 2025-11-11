# backend/sqlite_config.py

import sqlite3
from contextlib import contextmanager
from logger import get_logger

logger = get_logger(__name__)

SQLITE_DB_PATH = "building_schedules.db"

@contextmanager
def get_sqlite_connection():
    """Context manager for SQLite database connections."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        logger.error(f"SQLite transaction error: {e}")
        raise
    else:
        conn.commit()
    finally:
        conn.close()

# --- Building Schedule Functions ---

def get_building_time(building_id: int) -> dict | None:
    with get_sqlite_connection() as conn:
        cursor = conn.execute(
            "SELECT start_time FROM building_times WHERE building_id = ?",
            (building_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

def set_building_time(building_id: int, start_time: str) -> bool:
    """
    Sets only the start time for a building schedule.
    """
    try:
        with get_sqlite_connection() as conn:
            cursor = conn.execute("SELECT building_id FROM building_times WHERE building_id = ?", (building_id,))
            exists = cursor.fetchone()

            if exists:
                conn.execute("""
                    UPDATE building_times
                    SET start_time = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE building_id = ?
                """, (start_time, building_id))
                logger.info(f"Updated schedule for building {building_id} to start at {start_time}")
            else:
                conn.execute("""
                    INSERT INTO building_times (building_id, start_time)
                    VALUES (?, ?)
                """, (building_id, start_time))
                logger.info(f"Inserted new schedule for building {building_id}: start at {start_time}")
        return True
    except Exception as e:
        logger.error(f"Error setting building time for ID {building_id}: {e}")
        return False


def get_all_building_times() -> dict:
    """
    Returns all building schedules.
    """
    with get_sqlite_connection() as conn:
        cursor = conn.execute("SELECT building_id, start_time FROM building_times")
        rows = cursor.fetchall()
        return {row["building_id"]: {"start_time": row["start_time"]} for row in rows} if rows else {}

# --- Ignored ProEvent Functions ---

def get_ignored_proevents() -> dict:
    """
    Fetches all ignored proevents with their building associations.
    """
    with get_sqlite_connection() as conn:
        cursor = conn.execute("""
            SELECT proevent_id, building_frk, ignore_on_arm, ignore_on_disarm 
            FROM ignored_proevents
        """)
        rows = cursor.fetchall()
        if not rows:
            return {}
            
        return {
            row["proevent_id"]: {
                "building_frk": row["building_frk"],
                "ignore_on_arm": bool(row["ignore_on_arm"]), 
                "ignore_on_disarm": bool(row["ignore_on_disarm"])
            } 
            for row in rows
        }

def set_proevent_ignore_status(proevent_id: int, building_frk: int, device_prk: int, ignore_on_arm: bool, ignore_on_disarm: bool) -> bool:
    """Set the ignore status for a specific proevent."""
    try:
        with get_sqlite_connection() as conn:
            conn.execute("""
                INSERT INTO ignored_proevents (proevent_id, building_frk, device_prk, ignore_on_arm, ignore_on_disarm)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(proevent_id) DO UPDATE SET
                    building_frk = excluded.building_frk,
                    device_prk = excluded.device_prk,
                    ignore_on_arm = excluded.ignore_on_arm,
                    ignore_on_disarm = excluded.ignore_on_disarm
            """, (proevent_id, building_frk, device_prk, ignore_on_arm, ignore_on_disarm))
        logger.info(f"Updated ignore status for ProEvent {proevent_id}")
        return True
    except Exception as e:
        logger.error(f"Error setting ignore status for ProEvent ID {proevent_id}: {e}")
        return False

# --- ProEvent History Logging ---

def log_proevent_state(proevent_id: int, building_frk: int, state: str) -> bool:
    """Log a ProEvent's state change to the history table."""
    try:
        with get_sqlite_connection() as conn:
            conn.execute(
                "INSERT INTO proevent_state_history (proevent_id, building_frk, state) VALUES (?, ?, ?)",
                (proevent_id, building_frk, state)
            )
        logger.info(f"Logged state '{state}' for ProEvent {proevent_id}")
        return True
    except Exception as e:
        logger.error(f"Error logging ProEvent state for ID {proevent_id}: {e}")
        return False

# --- Device State Snapshot Functions ---

def save_snapshot(building_id: int, device_states: list[dict]) -> bool:
    """
    Saves a snapshot of device states for a building.
    """
    try:
        with get_sqlite_connection() as conn:
            conn.execute("DELETE FROM device_state_snapshot WHERE building_id = ?", (building_id,))
            
            snapshot_data = [
                (building_id, device['id'], device['state'])
                for device in device_states
            ]
            
            conn.executemany("""
                INSERT INTO device_state_snapshot (building_id, device_id, original_state)
                VALUES (?, ?, ?)
            """, snapshot_data)
        logger.info(f"Successfully saved snapshot for {len(snapshot_data)} devices in building {building_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving snapshot for building {building_id}: {e}")
        return False

def get_snapshot(building_id: int) -> list[dict] | None:
    """
    Retrieves the device state snapshot for a given building.
    """
    try:
        with get_sqlite_connection() as conn:
            cursor = conn.execute(
                "SELECT device_id, original_state FROM device_state_snapshot WHERE building_id = ?",
                (building_id,)
            )
            rows = cursor.fetchall()
            if not rows:
                return None
            return [{"id": row["device_id"], "state": row["original_state"]} for row in rows]
    except Exception as e:
        logger.error(f"Error retrieving snapshot for building {building_id}: {e}")
        return None

def clear_snapshot(building_id: int) -> bool:
    """Clears the device state snapshot for a building."""
    try:
        with get_sqlite_connection() as conn:
            conn.execute("DELETE FROM device_state_snapshot WHERE building_id = ?", (building_id,))
        logger.info(f"Cleared snapshot for building {building_id}")
        return True
    except Exception as e:
        logger.error(f"Error clearing snapshot for building {building_id}: {e}")
        return False