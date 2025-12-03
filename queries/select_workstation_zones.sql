-- 작업장의 구역 조회
-- Parameters: workstation_id
SELECT zone_id
FROM WorkstationZones
WHERE workstation_id = ?
LIMIT 1;
