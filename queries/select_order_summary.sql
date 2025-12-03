-- 주문 현황 조회
SELECT CO.order_id, CO.order_number, CO.status, COUNT(*) as items_count
FROM CustomerOrders CO
LEFT JOIN OrderItems OI ON CO.order_id = OI.order_id
GROUP BY CO.order_id;
