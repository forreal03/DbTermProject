-- 사용 가능한 직원 조회 (중복 할당 방지)
-- Parameters: workstation_id
SELECT SA.staff_id
FROM StaffAssignment SA
JOIN Staff S ON SA.staff_id = S.staff_id
WHERE SA.workstation_id = ?
AND S.status = 'ACTIVE'
AND SA.staff_id NOT IN (
    SELECT assigned_staff_id
    FROM KitchenTaskQueue
    WHERE status IN ('WAITING_RESOURCE', 'IN_PROGRESS')
    AND assigned_staff_id IS NOT NULL
)
LIMIT 1;
