-- 주문의 정확한 예상 대기 시간 계산
-- Parameters: order_id

-- 1. 이 주문보다 먼저 들어온 주문들의 남은 작업 시간 합계
-- 2. 이 주문 자체의 총 작업 시간
-- 결과: 총 예상 대기 시간 (초)

WITH OrderTotalTime AS (
    -- 각 주문의 총 작업 시간 계산
    SELECT
        CO.order_id,
        CO.order_time,
        CO.order_number,
        COALESCE(SUM(MT.base_time_seconds * OI.quantity), 0) as total_seconds
    FROM CustomerOrders CO
    LEFT JOIN OrderItems OI ON CO.order_id = OI.order_id
    LEFT JOIN MenuTasks MT ON OI.menu_item_id = MT.menu_item_id
    WHERE CO.status IN ('PENDING', 'CONFIRMED')
    GROUP BY CO.order_id, CO.order_time, CO.order_number
),
QueuePosition AS (
    -- 이 주문보다 앞선 주문들의 남은 시간
    SELECT
        SUM(total_seconds) as queue_time
    FROM OrderTotalTime
    WHERE order_time < (SELECT order_time FROM CustomerOrders WHERE order_id = ?)
)
SELECT
    COALESCE((SELECT queue_time FROM QueuePosition), 0) +
    COALESCE((SELECT total_seconds FROM OrderTotalTime WHERE order_id = ?), 0) as estimated_wait_seconds;
