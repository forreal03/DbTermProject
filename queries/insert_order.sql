-- 고객 주문 생성
-- Parameters: order_number, status, created_at
INSERT INTO CustomerOrders (order_number, status, created_at)
VALUES (?, 'PENDING', datetime('now', 'localtime'));
