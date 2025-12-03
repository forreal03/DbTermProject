-- 작업에 자원 할당
-- Parameters: workstation_id, zone_id, staff_id, queue_task_id
UPDATE KitchenTaskQueue
SET
    status = 'WAITING_RESOURCE',
    assigned_workstation_id = ?,
    assigned_zone_id = ?,
    assigned_staff_id = ?
WHERE queue_task_id = ?;
