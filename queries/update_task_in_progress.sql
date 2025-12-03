-- 작업을 IN_PROGRESS 상태로 변경
-- Parameters: queue_task_id
UPDATE KitchenTaskQueue
SET
    status = 'IN_PROGRESS',
    actual_start_time = datetime('now', 'localtime')
WHERE queue_task_id = ?;
