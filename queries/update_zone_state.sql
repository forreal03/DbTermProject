-- Zone 상태 업데이트
-- Parameters: food_type, quantity, busy_until, zone_id
UPDATE ZoneRealtimeState
SET
    current_food_type = ?,
    current_quantity = ?,
    busy_until = ?
WHERE zone_id = ?;
