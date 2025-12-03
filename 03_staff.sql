-- ==========================================
-- 직원 정보 및 배치
-- ==========================================

-- [5] Staff 생성
INSERT INTO Staff (name, status) VALUES
    ('김철수', 'ACTIVE'),
    ('이영희', 'ACTIVE'),
    ('박준호', 'ACTIVE'),
    ('최미라', 'ACTIVE'),
    ('손지훈', 'BREAK'),     -- 쉬는 중
    ('정수현', 'ACTIVE');

-- [6] StaffAssignment
INSERT INTO StaffAssignment (staff_id, workstation_id, assigned_at) VALUES
    (1, 1, datetime('now', 'localtime')),
    (2, 1, datetime('now', 'localtime')),
    (3, 3, datetime('now', 'localtime')),
    (4, 3, datetime('now', 'localtime')),
    (6, 4, datetime('now', 'localtime'));
