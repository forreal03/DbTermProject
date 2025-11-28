-- 맘스터치 레시피 (MenuTasks)

-- 작업장 ID: 1=튀김기, 2=조립대
-- 튀김기 섹션 ID: 1~6 (바스켓 3개 x 2슬롯)
-- 조립대 섹션 ID: 7~16 (10개 위치)

-- ===========================================
-- 버거 단품 (닭다리살 패티)
-- ===========================================

-- 싸이버거 (5300원)
INSERT INTO MenuTasks (menu_item_id, task_name, task_order, base_time_seconds, workstation_id, preferred_section_id) VALUES
((SELECT menu_item_id FROM MenuItems WHERE name='싸이버거'), '닭다리살패티 준비 및 튀기기', 1, 480, 1, 1);

-- 싸이플렉스버거 (8300원)
INSERT INTO MenuTasks (menu_item_id, task_name, task_order, base_time_seconds, workstation_id, preferred_section_id) VALUES
((SELECT menu_item_id FROM MenuItems WHERE name='싸이플렉스버거'), '닭다리살패티 준비 및 튀기기', 1, 480, 1, 1);

-- 불불불싸이버거 (6800원)
INSERT INTO MenuTasks (menu_item_id, task_name, task_order, base_time_seconds, workstation_id, preferred_section_id) VALUES
((SELECT menu_item_id FROM MenuItems WHERE name='불불불싸이버거'), '닭다리살패티 준비 및 튀기기', 1, 480, 1, 1);

-- 아라비아따치즈버거 (7400원)
INSERT INTO MenuTasks (menu_item_id, task_name, task_order, base_time_seconds, workstation_id, preferred_section_id) VALUES
((SELECT menu_item_id FROM MenuItems WHERE name='아라비아따치즈버거'), '닭다리살패티 준비 및 튀기기', 1, 480, 1, 1);

-- 텍사스바베큐치킨버거 (6600원)
INSERT INTO MenuTasks (menu_item_id, task_name, task_order, base_time_seconds, workstation_id, preferred_section_id) VALUES
((SELECT menu_item_id FROM MenuItems WHERE name='텍사스바베큐치킨버거'), '닭다리살패티 준비 및 튀기기', 1, 480, 1, 1);

-- ===========================================
-- 버거 세트 (패티 + 감자튀김 + 음료)
-- ===========================================

-- 싸이버거 세트 (8200원)
INSERT INTO MenuTasks (menu_item_id, task_name, task_order, base_time_seconds, workstation_id, preferred_section_id) VALUES
((SELECT menu_item_id FROM MenuItems WHERE name='싸이버거 세트'), '닭다리살패티 준비 및 튀기기', 1, 480, 1, 1),
((SELECT menu_item_id FROM MenuItems WHERE name='싸이버거 세트'), '감자튀김 튀기기', 2, 180, 1, 3),
((SELECT menu_item_id FROM MenuItems WHERE name='싸이버거 세트'), '음료 준비', 3, 15, 2, 7);

-- 싸이플렉스버거 세트 (10700원)
INSERT INTO MenuTasks (menu_item_id, task_name, task_order, base_time_seconds, workstation_id, preferred_section_id) VALUES
((SELECT menu_item_id FROM MenuItems WHERE name='싸이플렉스버거 세트'), '닭다리살패티 준비 및 튀기기', 1, 480, 1, 1),
((SELECT menu_item_id FROM MenuItems WHERE name='싸이플렉스버거 세트'), '감자튀김 튀기기', 2, 180, 1, 3),
((SELECT menu_item_id FROM MenuItems WHERE name='싸이플렉스버거 세트'), '음료 준비', 3, 15, 2, 8);

-- 불불불싸이버거 세트 (9200원)
INSERT INTO MenuTasks (menu_item_id, task_name, task_order, base_time_seconds, workstation_id, preferred_section_id) VALUES
((SELECT menu_item_id FROM MenuItems WHERE name='불불불싸이버거 세트'), '닭다리살패티 준비 및 튀기기', 1, 480, 1, 2),
((SELECT menu_item_id FROM MenuItems WHERE name='불불불싸이버거 세트'), '감자튀김 튀기기', 2, 180, 1, 4),
((SELECT menu_item_id FROM MenuItems WHERE name='불불불싸이버거 세트'), '음료 준비', 3, 15, 2, 9);

-- 아라비아따치즈버거 세트 (9800원)
INSERT INTO MenuTasks (menu_item_id, task_name, task_order, base_time_seconds, workstation_id, preferred_section_id) VALUES
((SELECT menu_item_id FROM MenuItems WHERE name='아라비아따치즈버거 세트'), '닭다리살패티 준비 및 튀기기', 1, 480, 1, 2),
((SELECT menu_item_id FROM MenuItems WHERE name='아라비아따치즈버거 세트'), '감자튀김 튀기기', 2, 180, 1, 4),
((SELECT menu_item_id FROM MenuItems WHERE name='아라비아따치즈버거 세트'), '음료 준비', 3, 15, 2, 10);

-- 텍사스바베큐치킨버거 세트 (9000원)
INSERT INTO MenuTasks (menu_item_id, task_name, task_order, base_time_seconds, workstation_id, preferred_section_id) VALUES
((SELECT menu_item_id FROM MenuItems WHERE name='텍사스바베큐치킨버거 세트'), '닭다리살패티 준비 및 튀기기', 1, 480, 1, 1),
((SELECT menu_item_id FROM MenuItems WHERE name='텍사스바베큐치킨버거 세트'), '감자튀김 튀기기', 2, 180, 1, 3),
((SELECT menu_item_id FROM MenuItems WHERE name='텍사스바베큐치킨버거 세트'), '음료 준비', 3, 15, 2, 11);

-- ===========================================
-- 치킨
-- ===========================================

-- 에드워드리 치킨 (뼈) - 12분
INSERT INTO MenuTasks (menu_item_id, task_name, task_order, base_time_seconds, workstation_id, preferred_section_id) VALUES
((SELECT menu_item_id FROM MenuItems WHERE name='에드워드리 치킨'), '치킨(뼈) 준비 및 튀기기', 1, 720, 1, 5);

-- 에드워드리 순살 - 7분
INSERT INTO MenuTasks (menu_item_id, task_name, task_order, base_time_seconds, workstation_id, preferred_section_id) VALUES
((SELECT menu_item_id FROM MenuItems WHERE name='에드워드리 순살'), '치킨(순살) 준비 및 튀기기', 1, 420, 1, 3);

-- ===========================================
-- 음료 (단품 주문 시)
-- ===========================================

INSERT INTO MenuTasks (menu_item_id, task_name, task_order, base_time_seconds, workstation_id, preferred_section_id) VALUES
((SELECT menu_item_id FROM MenuItems WHERE name='콜라 355ml'), '음료 준비', 1, 15, 2, 7),
((SELECT menu_item_id FROM MenuItems WHERE name='콜라 500ml'), '음료 준비', 1, 15, 2, 7),
((SELECT menu_item_id FROM MenuItems WHERE name='사이다 355ml'), '음료 준비', 1, 15, 2, 7),
((SELECT menu_item_id FROM MenuItems WHERE name='사이다 500ml'), '음료 준비', 1, 15, 2, 7),
((SELECT menu_item_id FROM MenuItems WHERE name='환타 355ml'), '음료 준비', 1, 15, 2, 7),
((SELECT menu_item_id FROM MenuItems WHERE name='환타 500ml'), '음료 준비', 1, 15, 2, 7);
