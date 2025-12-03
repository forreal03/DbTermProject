-- ==========================================
-- 작업장 및 구역 설정
-- ==========================================

-- [1] Workstations 생성
INSERT INTO Workstations (name, type, max_staff) VALUES
    ('메인 튀김기', 'ZONED_FRYER', 2),
    ('서브 튀김기', 'ZONED_FRYER', 2),
    ('버거 조립대', 'STATION', 3),
    ('음료/사이드', 'STATION', 1);

-- [2] WorkstationZones 생성
INSERT INTO WorkstationZones (workstation_id, zone_name) VALUES
    (1, '튀김기_좌측'),
    (1, '튀김기_우측'),
    (2, '튀김기_좌측'),
    (2, '튀김기_우측'),
    (3, '조립대_1번'),
    (3, '조립대_2번'),
    (3, '조립대_3번'),
    (4, '음료_준비');

-- [3] ZoneCapacityRules 생성 (수정됨: 튀김기 zone만 용량 규칙 적용)
INSERT INTO ZoneCapacityRules (zone_id, food_type, max_quantity) VALUES
    -- 메인 튀김기 좌측/우측 (zone 1-2)
    (1, '싸이패티', 10),
    (1, '텐더', 15),
    (1, '감자튀김', 20),
    (2, '싸이패티', 10),
    (2, '텐더', 15),
    (2, '감자튀김', 20),
    -- 서브 튀김기 좌측/우측 (zone 3-4)
    (3, '싸이패티', 10),
    (3, '텐더', 15),
    (3, '감자튀김', 20),
    (4, '싸이패티', 10),
    (4, '텐더', 15),
    (4, '감자튀김', 20);

-- [4] ZoneRealtimeState 초기화
INSERT INTO ZoneRealtimeState (zone_id, current_food_type, current_quantity, busy_until) VALUES
    (1, NULL, 0, NULL),
    (2, NULL, 0, NULL),
    (3, NULL, 0, NULL),
    (4, NULL, 0, NULL),
    (5, NULL, 0, NULL),
    (6, NULL, 0, NULL),
    (7, NULL, 0, NULL),
    (8, NULL, 0, NULL);
