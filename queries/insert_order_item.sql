-- 주문 항목 추가
-- Parameters: order_id, menu_item_id, quantity
INSERT INTO OrderItems (order_id, menu_item_id, quantity)
VALUES (?, ?, ?);
