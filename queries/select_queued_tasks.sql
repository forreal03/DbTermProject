-- 대기 중인 작업 조회
SELECT
    KTQ.queue_task_id,
    KTQ.task_definition_id,
    MT.workstation_id,
    OI.menu_item_id
FROM KitchenTaskQueue KTQ
JOIN MenuTasks MT ON KTQ.task_definition_id = MT.task_definition_id
JOIN OrderItems OI ON KTQ.order_item_id = OI.order_item_id
WHERE KTQ.status = 'QUEUED'
ORDER BY KTQ.created_at;
