-- 맘스터치 메뉴 데이터 (2025년 기준)

-- 기존 데이터 모두 삭제
DELETE FROM KitchenTaskQueue;
DELETE FROM OrderItems;
DELETE FROM CustomerOrders;
DELETE FROM MenuTasks;
DELETE FROM WorkstationConstraints;
DELETE FROM MenuItems;

-- 버거 단품
INSERT INTO MenuItems (name, price) VALUES
('싸이버거', 5300),
('싸이플렉스버거', 8300),
('불불불싸이버거', 6800),
('아라비아따치즈버거', 7400),
('텍사스바베큐치킨버거', 6600);

-- 버거 세트
INSERT INTO MenuItems (name, price) VALUES
('싸이버거 세트', 8200),
('싸이플렉스버거 세트', 10700),
('불불불싸이버거 세트', 9200),
('아라비아따치즈버거 세트', 9800),
('텍사스바베큐치킨버거 세트', 9000);

-- 치킨
INSERT INTO MenuItems (name, price) VALUES
('에드워드리 치킨', 18900),
('에드워드리 순살', 19900);

-- 음료
INSERT INTO MenuItems (name, price) VALUES
('콜라 355ml', 1600),
('콜라 500ml', 2000),
('사이다 355ml', 1600),
('사이다 500ml', 2000),
('환타 355ml', 1600),
('환타 500ml', 2000);
