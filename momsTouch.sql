-- =====================================
-- 맘스터치형 주방 워크플로우 시스템 (Revised)
-- =====================================

-- [1] 작업장 및 구역 관리 (정적 정의)
-- -------------------------------------

CREATE TABLE Workstations (
    workstation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE, 
    -- 예: '메인 튀김기', '서브 튀김기', '버거 조립대', '카운터/포장'
    -- '그릴' 삭제됨 (맘스터치 스타일 반영)
    
    type VARCHAR(20) NOT NULL DEFAULT 'STATION' 
        CHECK(type IN ('STATION', 'ZONED_FRYER')),
    
    max_staff INT NOT NULL DEFAULT 1
);

-- 작업장 내 구역 정의 (물리적 공간)
CREATE TABLE WorkstationZones (
    zone_id INTEGER PRIMARY KEY AUTOINCREMENT,
    workstation_id INT NOT NULL,
    zone_name VARCHAR(50) NOT NULL, -- 예: '튀김기_좌측', '튀김기_우측'
    
    FOREIGN KEY (workstation_id) REFERENCES Workstations(workstation_id),
    UNIQUE(workstation_id, zone_name)
);

-- [3NF 적용] 구역별 용량 규칙 (변하지 않는 기준값)
CREATE TABLE ZoneCapacityRules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id INT NOT NULL,
    food_type VARCHAR(50) NOT NULL, -- '싸이패티', '텐더', '감자튀김'
    max_quantity INT NOT NULL,      -- 한 번에 튀길 수 있는 최대 양
    
    FOREIGN KEY (zone_id) REFERENCES WorkstationZones(zone_id),
    UNIQUE(zone_id, food_type)
);

-- [2] 작업장 실시간 상태 (동적 데이터 - 분리됨)
-- -------------------------------------

CREATE TABLE ZoneRealtimeState (
    state_id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id INT NOT NULL UNIQUE,
    
    current_food_type VARCHAR(50) NULL, -- 현재 튀기고 있는 종류 (NULL이면 비어있음)
    current_quantity INT DEFAULT 0,     -- 현재 튀겨지는 개수
    
    -- 이 시간까지는 해당 구역 사용 불가 (기름 온도 복구 시간 등 포함)
    busy_until TIMESTAMP NULL,
    
    FOREIGN KEY (zone_id) REFERENCES WorkstationZones(zone_id)
);

-- =====================================
-- [3] 스태프 및 숙련도 관리
-- =====================================

CREATE TABLE Staff (
    staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    
    -- 숙련도 레벨 (1: 초보, 2: 숙련, 3: 마스터)
    -- hire_date 대신 직접 입력 방식으로 변경
    skill_level INT NOT NULL DEFAULT 1 
        CHECK(skill_level BETWEEN 1 AND 3),
        
    status VARCHAR(20) DEFAULT 'ACTIVE'
        CHECK(status IN ('ACTIVE', 'BREAK', 'OFF_WORK'))
);

-- 스태프 현재 배치 상태
CREATE TABLE StaffAssignment (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INT NOT NULL,
    workstation_id INT NOT NULL,
    
    -- 현재 맡고 있는 역할의 난이도 (스태프 레벨과 매칭 권장)
    assigned_difficulty INT DEFAULT 1, 
    
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (staff_id) REFERENCES Staff(staff_id),
    FOREIGN KEY (workstation_id) REFERENCES Workstations(workstation_id)
);

-- =====================================
-- [4] 메뉴 및 작업 정의 (Blueprint)
-- =====================================

CREATE TABLE MenuItems (
    menu_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE, -- '싸이버거 세트'
    price INT NOT NULL
);

-- 작업 단계 정의
CREATE TABLE MenuTasks (
    task_definition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    menu_item_id INT NOT NULL,
    workstation_id INT NOT NULL,
    
    task_name VARCHAR(100) NOT NULL, -- '패티 튀기기', '소스 바르기'
    task_order INT NOT NULL,
    
    -- 난이도 설정 (1~3)
    -- C++ 알고리즘은 이 난이도와 스태프의 skill_level을 비교하여 배정
    difficulty_level INT NOT NULL DEFAULT 1 
        CHECK(difficulty_level BETWEEN 1 AND 3),
    
    -- 표준 소요 시간 (초 단위)
    -- 실제 시간 = base_time * (숙련도 보정 계수) 로 C++에서 계산
    base_time_seconds INT NOT NULL,
    
    -- 기계 작업 여부 (Active: 사람 손 필요, Passive: 기계가 함)
    task_type VARCHAR(10) NOT NULL DEFAULT 'ACTIVE'
        CHECK(task_type IN ('ACTIVE', 'PASSIVE')),

    FOREIGN KEY (menu_item_id) REFERENCES MenuItems(menu_item_id),
    FOREIGN KEY (workstation_id) REFERENCES Workstations(workstation_id)
);

-- 작업 간 의존성 (Topological Sort용 그래프 데이터)
CREATE TABLE TaskDependencies (
    dependency_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INT NOT NULL,
    depends_on_task_id INT NOT NULL,
    
    FOREIGN KEY (task_id) REFERENCES MenuTasks(task_definition_id),
    FOREIGN KEY (depends_on_task_id) REFERENCES MenuTasks(task_definition_id)
);

-- =====================================
-- [5] 주문 및 실행 큐 (Execution)
-- =====================================

CREATE TABLE CustomerOrders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number VARCHAR(20) UNIQUE,
    status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    estimated_seconds_remaining INT NULL 
);

CREATE TABLE OrderItems (
    order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INT NOT NULL,
    menu_item_id INT NOT NULL,
    quantity INT DEFAULT 1,
    
    FOREIGN KEY (order_id) REFERENCES CustomerOrders(order_id),
    FOREIGN KEY (menu_item_id) REFERENCES MenuItems(menu_item_id)
);

-- 실제 작업 큐 테이블
CREATE TABLE KitchenTaskQueue (
    queue_task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_item_id INT NOT NULL,
    task_definition_id INT NOT NULL,
    
    -- 상태 관리
    status VARCHAR(20) NOT NULL DEFAULT 'QUEUED'
        CHECK (status IN ('QUEUED', 'WAITING_RESOURCE', 'IN_PROGRESS', 'COMPLETED')),
        
    -- C++ 알고리즘에 의해 할당된 자원
    assigned_workstation_id INT NULL,
    assigned_zone_id INT NULL,
    assigned_staff_id INT NULL,
    
    -- 시간 로그
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actual_start_time TIMESTAMP NULL,
    actual_end_time TIMESTAMP NULL,
    
    FOREIGN KEY (order_item_id) REFERENCES OrderItems(order_item_id),
    FOREIGN KEY (task_definition_id) REFERENCES MenuTasks(task_definition_id),
    FOREIGN KEY (assigned_staff_id) REFERENCES Staff(staff_id)
);

-- =====================================
-- [6] 병목 현상 분석 및 로깅 (New)
-- =====================================

-- "왜 늦어졌는가?"를 기록하여 추후 운영 최적화에 사용합니다.
CREATE TABLE BottleneckAnalysis (
    analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_task_id INT NOT NULL,
    
    -- 지연 원인 분류
    bottleneck_type VARCHAR(50) NOT NULL
        CHECK (bottleneck_type IN ('NO_STAFF', 'NO_FRYER_ZONE', 'FRYER_TEMP_RECOVERY', 'DEPENDENCY_WAIT')),
        
    -- 대기 시간 (초)
    wait_duration_seconds INT NOT NULL,
    
    -- 당시 상황 스냅샷 (어느 작업장이 문제였나)
    problematic_workstation_id INT NULL,
    
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (queue_task_id) REFERENCES KitchenTaskQueue(queue_task_id),
    FOREIGN KEY (problematic_workstation_id) REFERENCES Workstations(workstation_id)
);

-- =====================================
-- 인덱스 전략 (최적화)
-- =====================================

-- 알고리즘이 "대기 중인 작업"을 빠르게 가져오기 위함
CREATE INDEX idx_queue_priority ON KitchenTaskQueue(status, created_at);

-- 특정 구역의 현재 상태를 빠르게 조회 (Locking 최소화)
CREATE INDEX idx_zone_state ON ZoneRealtimeState(zone_id, busy_until);

-- 병목 분석 리포트 생성용
CREATE INDEX idx_bottleneck_type ON BottleneckAnalysis(bottleneck_type);