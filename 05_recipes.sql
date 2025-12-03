-- ==========================================
-- 레시피 정의 (MenuTasks + TaskDependencies)
-- ==========================================

-- [8] MenuTasks (작업 순서 정의)

-- 싸이버거 (메뉴_id=1)
INSERT INTO MenuTasks (menu_item_id, workstation_id, task_name, task_order, base_time_seconds, task_type) VALUES
    (1, 1, '싸이패티 튀기기', 1, 300, 'ACTIVE'),
    (1, 3, '버거 조립', 2, 60, 'ACTIVE');

-- 싸이버거 세트 (메뉴_id=2)
INSERT INTO MenuTasks (menu_item_id, workstation_id, task_name, task_order, base_time_seconds, task_type) VALUES
    (2, 1, '싸이패티 튀기기', 1, 300, 'ACTIVE'),
    (2, 2, '감자튀김', 2, 180, 'PASSIVE'),
    (2, 4, '음료 준비', 3, 30, 'ACTIVE'),
    (2, 3, '버거 조립', 4, 90, 'ACTIVE');

-- 에드워드리 버거 (메뉴_id=3)
INSERT INTO MenuTasks (menu_item_id, workstation_id, task_name, task_order, base_time_seconds, task_type) VALUES
    (3, 1, '싸이패티 튀기기', 1, 360, 'ACTIVE'),
    (3, 3, '치즈 슬라이스', 2, 20, 'ACTIVE'),
    (3, 3, '소스 바르기', 3, 15, 'ACTIVE'),
    (3, 3, '조립 완성', 4, 120, 'ACTIVE');

-- 에드워드리 버거 세트 (메뉴_id=4)
INSERT INTO MenuTasks (menu_item_id, workstation_id, task_name, task_order, base_time_seconds, task_type) VALUES
    (4, 1, '싸이패티 튀기기', 1, 360, 'ACTIVE'),
    (4, 2, '감자튀김', 2, 180, 'PASSIVE'),
    (4, 4, '음료 준비', 3, 30, 'ACTIVE'),
    (4, 3, '치즈 슬라이스', 4, 20, 'ACTIVE'),
    (4, 3, '소스 바르기', 5, 15, 'ACTIVE'),
    (4, 3, '조립 완성', 6, 120, 'ACTIVE');

-- 텐더 5개 (메뉴_id=5)
INSERT INTO MenuTasks (menu_item_id, workstation_id, task_name, task_order, base_time_seconds, task_type) VALUES
    (5, 1, '텐더 튀기기', 1, 240, 'ACTIVE'),
    (5, 3, '포장 완성', 2, 30, 'ACTIVE');

-- [9] TaskDependencies (작업 의존성)

-- 싸이버거: 패티튀김 -> 조립
-- Task IDs: 1 (패티), 2 (조립)
INSERT INTO TaskDependencies (task_id, depends_on_task_id) VALUES
    (2, 1);

-- 싸이버거 세트: 패티 완료 후 조립, 음료 완료 후 조립
-- Task IDs: 3 (패티), 4 (감자), 5 (음료), 6 (조립)
INSERT INTO TaskDependencies (task_id, depends_on_task_id) VALUES
    (6, 3),
    (6, 5);

-- 에드워드리: 패티 -> 치즈 -> 소스 -> 완성
-- Task IDs: 7 (패티), 8 (치즈), 9 (소스), 10 (완성)
INSERT INTO TaskDependencies (task_id, depends_on_task_id) VALUES
    (8, 7),
    (9, 8),
    (10, 9);

-- 에드워드리 세트: 패티 -> 치즈/음료 -> 소스 -> 완성
-- Task IDs: 11 (패티), 12 (감자), 13 (음료), 14 (치즈), 15 (소스), 16 (완성)
INSERT INTO TaskDependencies (task_id, depends_on_task_id) VALUES
    (14, 11),
    (14, 13),
    (15, 14),
    (16, 15);

-- 텐더: 튀기기 -> 포장
-- Task IDs: 17 (튀기기), 18 (포장)
INSERT INTO TaskDependencies (task_id, depends_on_task_id) VALUES
    (18, 17);
