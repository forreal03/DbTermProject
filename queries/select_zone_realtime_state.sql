-- Zone 실시간 상태 조회
SELECT
    ZRS.zone_id,
    WZ.zone_name,
    COALESCE(ZRS.current_food_type, 'IDLE') as food_type,
    ZRS.current_quantity,
    COALESCE(ZRS.busy_until, 'N/A') as busy_until
FROM ZoneRealtimeState ZRS
JOIN WorkstationZones WZ ON ZRS.zone_id = WZ.zone_id
ORDER BY ZRS.zone_id;
