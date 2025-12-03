-- ==========================================
-- 맘스터치 주방 관리 시스템 - 스키마 정의
-- ==========================================

-- [1] Workstations
CREATE TABLE Workstations (
    workstation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    type VARCHAR(20) NOT NULL DEFAULT 'STATION' CHECK(type IN ('STATION', 'ZONED_FRYER')),
    max_staff INT NOT NULL DEFAULT 1
);

-- [2] WorkstationZones
CREATE TABLE WorkstationZones (
    zone_id INTEGER PRIMARY KEY AUTOINCREMENT,
    workstation_id INT NOT NULL,
    zone_name VARCHAR(50) NOT NULL,
    FOREIGN KEY (workstation_id) REFERENCES Workstations(workstation_id),
    UNIQUE(workstation_id, zone_name)
);

-- [3] ZoneCapacityRules
CREATE TABLE ZoneCapacityRules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id INT NOT NULL,
    food_type VARCHAR(50) NOT NULL,
    max_quantity INT NOT NULL,
    FOREIGN KEY (zone_id) REFERENCES WorkstationZones(zone_id),
    UNIQUE(zone_id, food_type)
);

-- [4] ZoneRealtimeState
CREATE TABLE ZoneRealtimeState (
    state_id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id INT NOT NULL UNIQUE,
    current_food_type VARCHAR(50) NULL,
    current_quantity INT DEFAULT 0,
    busy_until TIMESTAMP NULL,
    FOREIGN KEY (zone_id) REFERENCES WorkstationZones(zone_id)
);

-- [5] Staff
CREATE TABLE Staff (
    staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'BREAK', 'OFF_WORK'))
);

-- [6] StaffAssignment
CREATE TABLE StaffAssignment (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INT NOT NULL,
    workstation_id INT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (staff_id) REFERENCES Staff(staff_id),
    FOREIGN KEY (workstation_id) REFERENCES Workstations(workstation_id)
);

-- [7] MenuItems
CREATE TABLE MenuItems (
    menu_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    price INT NOT NULL
);

-- [8] MenuTasks
CREATE TABLE MenuTasks (
    task_definition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    menu_item_id INT NOT NULL,
    workstation_id INT NOT NULL,
    task_name VARCHAR(100) NOT NULL,
    task_order INT NOT NULL,
    base_time_seconds INT NOT NULL,
    task_type VARCHAR(10) NOT NULL DEFAULT 'ACTIVE' CHECK(task_type IN ('ACTIVE', 'PASSIVE')),
    FOREIGN KEY (menu_item_id) REFERENCES MenuItems(menu_item_id),
    FOREIGN KEY (workstation_id) REFERENCES Workstations(workstation_id)
);

-- [9] TaskDependencies
CREATE TABLE TaskDependencies (
    dependency_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INT NOT NULL,
    depends_on_task_id INT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES MenuTasks(task_definition_id),
    FOREIGN KEY (depends_on_task_id) REFERENCES MenuTasks(task_definition_id)
);

-- [10] CustomerOrders
CREATE TABLE CustomerOrders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number VARCHAR(20) UNIQUE,
    status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estimated_seconds_remaining INT NULL
);

-- [11] OrderItems
CREATE TABLE OrderItems (
    order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INT NOT NULL,
    menu_item_id INT NOT NULL,
    quantity INT DEFAULT 1,
    FOREIGN KEY (order_id) REFERENCES CustomerOrders(order_id),
    FOREIGN KEY (menu_item_id) REFERENCES MenuItems(menu_item_id)
);

-- [12] KitchenTaskQueue
CREATE TABLE KitchenTaskQueue (
    queue_task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_item_id INT NOT NULL,
    task_definition_id INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'WAITING_RESOURCE', 'IN_PROGRESS', 'COMPLETED')),
    assigned_workstation_id INT NULL,
    assigned_zone_id INT NULL,
    assigned_staff_id INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actual_start_time TIMESTAMP NULL,
    actual_end_time TIMESTAMP NULL,
    FOREIGN KEY (order_item_id) REFERENCES OrderItems(order_item_id),
    FOREIGN KEY (task_definition_id) REFERENCES MenuTasks(task_definition_id),
    FOREIGN KEY (assigned_staff_id) REFERENCES Staff(staff_id)
);

-- [13] BottleneckAnalysis
CREATE TABLE BottleneckAnalysis (
    analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_task_id INT NOT NULL,
    bottleneck_type VARCHAR(50) NOT NULL CHECK (bottleneck_type IN ('NO_STAFF', 'NO_FRYER_ZONE', 'FRYER_TEMP_RECOVERY', 'DEPENDENCY_WAIT')),
    wait_duration_seconds INT NOT NULL,
    problematic_workstation_id INT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (queue_task_id) REFERENCES KitchenTaskQueue(queue_task_id),
    FOREIGN KEY (problematic_workstation_id) REFERENCES Workstations(workstation_id)
);

-- 인덱스
CREATE INDEX idx_queue_priority ON KitchenTaskQueue(status, created_at);
CREATE INDEX idx_zone_state ON ZoneRealtimeState(zone_id, busy_until);
CREATE INDEX idx_bottleneck_type ON BottleneckAnalysis(bottleneck_type);
