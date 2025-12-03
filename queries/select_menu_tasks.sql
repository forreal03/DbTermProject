-- 특정 메뉴의 작업 조회
-- Parameters: menu_item_id
SELECT task_definition_id, task_name, task_order
FROM MenuTasks
WHERE menu_item_id = ?
ORDER BY task_order;
