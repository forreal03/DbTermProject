-- 영수증 정보 조회
-- Parameters: order_number

SELECT
    CO.order_number,
    CO.created_at,
    CO.status,
    MI.name as menu_name,
    MI.price,
    OI.quantity,
    (MI.price * OI.quantity) as subtotal
FROM CustomerOrders CO
JOIN OrderItems OI ON CO.order_id = OI.order_id
JOIN MenuItems MI ON OI.menu_item_id = MI.menu_item_id
WHERE CO.order_number = ?
ORDER BY OI.order_item_id;
