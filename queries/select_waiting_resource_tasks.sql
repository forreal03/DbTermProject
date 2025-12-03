-- WAITING_RESOURCE 상태의 작업 조회
SELECT queue_task_id
FROM KitchenTaskQueue
WHERE status = 'WAITING_RESOURCE'
ORDER BY created_at
LIMIT 6;
