-- 주방 작업 큐에 작업 추가
-- Parameters: order_item_id, task_definition_id
INSERT INTO KitchenTaskQueue (
    order_item_id, task_definition_id, status, created_at
) VALUES (?, ?, 'QUEUED', datetime('now', 'localtime'));
