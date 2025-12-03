-- 작업을 COMPLETED 상태로 변경
-- Parameters: queue_task_id
UPDATE KitchenTaskQueue
SET
    status = 'COMPLETED',
    actual_end_time = datetime('now', 'localtime')
WHERE queue_task_id = ?;
