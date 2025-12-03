-- ==========================================
-- 직원 정보 및 배치
-- ==========================================

-- [5] Staff 생성
INSERT INTO Staff (name, skill_level, status) VALUES
    ('김철수', 3, 'ACTIVE'),    -- 마스터
    ('이영희', 2, 'ACTIVE'),    -- 숙련
    ('박준호', 2, 'ACTIVE'),    -- 숙련
    ('최미라', 1, 'ACTIVE'),    -- 초보
    ('손지훈', 2, 'BREAK'),     -- 쉬는 중
    ('정수현', 1, 'ACTIVE');    -- 초보

-- [6] StaffAssignment
INSERT INTO StaffAssignment (staff_id, workstation_id, assigned_difficulty, assigned_at) VALUES
    (1, 1, 3, datetime('now', 'localtime')),
    (2, 1, 2, datetime('now', 'localtime')),
    (3, 3, 2, datetime('now', 'localtime')),
    (4, 3, 1, datetime('now', 'localtime')),
    (6, 4, 1, datetime('now', 'localtime'));
