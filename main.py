import sqlite3
import os
import time
import threading
from datetime import datetime, timedelta
import google.generativeai as genai
from dotenv import load_dotenv
from tabulate import tabulate
from colorama import Fore, Style, init

# 1. 환경 설정
load_dotenv()
init(autoreset=True)

# 가상 시간 설정 (2초 = 1분)
VIRTUAL_TIME_START = datetime.now()
VIRTUAL_TIME_OFFSET = timedelta(0)  # 경과한 가상 시간
TIMER_RUNNING = False
TIMER_THREAD = None

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    print(Fore.RED + "❌ 오류: .env 파일에 GOOGLE_API_KEY가 없습니다.")
    exit()

# 모델 설정 (Pro 모델 권장)
genai.configure(api_key=API_KEY)
DB_NAME = "momstouch_v2.db"

# ==========================================
# 가상 시간 및 작업 모니터링 함수
# ==========================================

def get_virtual_time():
    """현재 가상 시간 반환 (2초 = 1분)"""
    global VIRTUAL_TIME_OFFSET
    return VIRTUAL_TIME_START + VIRTUAL_TIME_OFFSET

def virtual_timer_loop():
    """백그라운드에서 2초마다 1분씩 시간 증가 및 작업 완료 체크"""
    global VIRTUAL_TIME_OFFSET, TIMER_RUNNING

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    while TIMER_RUNNING:
        time.sleep(2)  # 2초 대기
        VIRTUAL_TIME_OFFSET += timedelta(minutes=1)  # 가상으로 1분 경과

        current_virtual_time = get_virtual_time()

        # 완료된 작업 자동 업데이트 (화면 출력 없음)
        cursor.execute("""
            UPDATE KitchenTaskQueue
            SET status = 'COMPLETED', completed_at = ?
            WHERE status = 'IN_PROGRESS'
            AND datetime(started_at, '+' || (
                SELECT base_time_seconds FROM MenuTasks
                WHERE task_definition_id = KitchenTaskQueue.task_definition_id
            ) || ' seconds') <= ?
        """, (current_virtual_time.strftime('%Y-%m-%d %H:%M:%S'),
              current_virtual_time.strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()

        # 대기 중인 작업을 빈 섹션에 할당 (섹션이 비면 자동으로 다음 작업 시작)
        _auto_assign_sections(conn)

        # 화면 출력 없음 - Manager 모드에서만 현황판 표시

    conn.close()

def start_virtual_timer():
    """가상 타이머 시작"""
    global TIMER_RUNNING, TIMER_THREAD

    if not TIMER_RUNNING:
        TIMER_RUNNING = True
        TIMER_THREAD = threading.Thread(target=virtual_timer_loop, daemon=True)
        TIMER_THREAD.start()
        print(f"{Fore.GREEN}⏰ 주방 타이머 시작! (현재 시간: {get_virtual_time().strftime('%H:%M')}){Style.RESET_ALL}")

def stop_virtual_timer():
    """가상 타이머 중지"""
    global TIMER_RUNNING
    TIMER_RUNNING = False
    print(f"{Fore.YELLOW}⏸ 주방 타이머 중지{Style.RESET_ALL}")

# ==========================================
# [프롬프트 센터] 각 모드별 페르소나 정의
# ==========================================

# 1. DBA 모드: 메뉴, 레시피, 작업대 구성 등록 전문가
PROMPT_DBA = """
당신은 'DBA(데이터베이스 관리자)'입니다. 
사용자의 자연어 설명을 듣고 SQL을 작성하세요.

[주의: 작업대와 구역은 이미 기본 설정되어 있습니다]
- 튀김기: 2개 구역 (튀김기 #1, 튀김기 #2)
- 조립대: 3개 구역 (조립대 #1, 조립대 #2, 조립대 #3)

[데이터베이스 스키마]
- MenuItems: menu_item_id(PK), name(TEXT), price(INT)
- MenuTasks: task_definition_id(PK), menu_item_id(FK), task_name, task_order, base_time_seconds, workstation_id
- WorkstationSections: section_id(PK), description (튀김기 #1=1, 튀김기 #2=2, 조립대 #1=3, 조립대 #2=4, 조립대 #3=5)
- Workstations: workstation_id (1=튀김기, 2=조립대)

[요청 종류]
1. **메뉴만 추가** (예: "싸이버거 6000원 추가")
   - MenuItems에만 INSERT

2. **메뉴 + 레시피 추가** (예: "싸이버거. 레시피: 패티튀기기(300초, 튀김기), 조립(60초, 조립대)")
   - MenuItems에 INSERT
   - MenuTasks에 순서대로 INSERT
   - workstation_id: 1=튀김기, 2=조립대

3. **제약조건 설정** (예: "싸이버거는 튀김기 1번에서만 튀겨")
   - WorkstationConstraints에 INSERT

[절대 규칙]
- 반드시 유효한 SQL 코드만 출력하세요
- 마지막 쉼표가 없어야 합니다
- 한글 설명이나 주석은 절대 포함하지 마세요
- 작업대 구성(Workstations, WorkstationSections) 설정은 하지 마세요 (이미 설정됨)
- 이미 등록된 메뉴를 다시 INSERT하지 마세요

[예시 1 - 메뉴 + 레시피 추가]
User: "싸이버거 6000원. 패티튀기기 300초 튀김기, 조립 60초 조립대"
Output:
INSERT INTO MenuItems (name, price) VALUES ('싸이버거', 6000);
INSERT INTO MenuTasks (menu_item_id, task_name, task_order, base_time_seconds, workstation_id) VALUES
((SELECT menu_item_id FROM MenuItems WHERE name='싸이버거'), '패티튀기기', 1, 300, 1),
((SELECT menu_item_id FROM MenuItems WHERE name='싸이버거'), '조립', 2, 60, 2)

[예시 2 - 여러 메뉴 추가]
User: "싸이버거 세트 8500원. 레시피: 패티튀기기 300초 튀김기, 감자튀김 180초 튀김기, 음료준비 30초 조립대, 조립 90초 조립대"
Output:
INSERT INTO MenuItems (name, price) VALUES ('싸이버거 세트', 8500);
INSERT INTO MenuTasks (menu_item_id, task_name, task_order, base_time_seconds, workstation_id, preferred_section_id) VALUES
((SELECT menu_item_id FROM MenuItems WHERE name='싸이버거 세트'), '패티튀기기', 1, 300, 1, 1),
((SELECT menu_item_id FROM MenuItems WHERE name='싸이버거 세트'), '감자튀김', 2, 180, 1, 2),
((SELECT menu_item_id FROM MenuItems WHERE name='싸이버거 세트'), '음료준비', 3, 30, 2, 3),
((SELECT menu_item_id FROM MenuItems WHERE name='싸이버거 세트'), '조립', 4, 90, 2, 4)

[예시 3 - 제약조건 설정]
User: "싸이버거는 튀김기 #1에서만 튀겨"
Output:
INSERT INTO WorkstationConstraints (section_id, menu_item_id, priority, description) VALUES
(1, (SELECT menu_item_id FROM MenuItems WHERE name='싸이버거'), 1, '튀김기 #1 전용')
"""

# 2. Manager 모드: 주문 접수 및 작업 할당 관리자
PROMPT_MANAGER = """
당신은 '매장 매니저'입니다.
사용자의 명령을 해석하여 적절한 SQL을 생성하세요.

[데이터베이스 스키마]
- MenuItems: menu_item_id(PK), name(TEXT), price(INT)
- MenuTasks: task_definition_id(PK), menu_item_id(FK), task_name, task_order, base_time_seconds, workstation_id, preferred_section_id
- WorkstationConstraints: constraint_id(PK), section_id, menu_item_id, priority, description
- CustomerOrders: order_id(PK), order_number(TEXT), status(TEXT), order_time(DATETIME), estimated_total_seconds(INT)
- OrderItems: order_item_id(PK), order_id(FK), menu_item_id(FK)
- KitchenTaskQueue: queue_task_id(PK), order_item_id(FK), task_definition_id(FK), assigned_section_id, status, started_at, completed_at

[절대 규칙]
- 반드시 유효한 SQL 코드만 출력하세요
- 마지막 쉼표가 없어야 합니다
- 한글 설명이나 주석은 절대 포함하지 마세요
- 한글 인사말은 포함하면 안 됩니다
- SELECT 구문에서 쉼표 뒤에 바로 FROM이 오지 않도록 주의하세요
- FROM 뒤에는 반드시 테이블명이 와야 합니다 (예: FROM MenuItems, FROM KitchenTaskQueue)
- WHERE 조건이 필요한 경우 반드시 완전한 WHERE 절을 작성하세요

[주문번호 형식]
- 새로운 주문: SELECT COALESCE(MAX(CAST(substr(order_number,5) AS INTEGER)), 0) + 1 FROM CustomerOrders WHERE date(order_time) = date('now') 로 오늘의 순번 조회
- 순번을 3자리로 포맷팅 ('ORD-' || printf('%03d', 순번))
- 예: ORD-001, ORD-002, ORD-003
- 자정 이후면 자동으로 001부터 시작

[작업 할당 전략]
- 제약조건 확인: WorkstationConstraints에서 해당 메뉴에 지정된 섹션 확인
- 섹션 할당: preferred_section_id 또는 constraint의 section_id 사용
- assigned_section_id에 자동으로 값 할당

[요청 종류]
1. **주문 접수** (예: "싸이버거 2개 주문")
   - BEGIN TRANSACTION으로 시작
   - `CustomerOrders` 생성 (주문번호: 'ORD-' + 3자리 순번)
   - `OrderItems` 생성 (같은 메뉴 n개면 n개의 OrderItem 생성)
   - `KitchenTaskQueue` 생성 (MenuTasks를 SELECT로 복사)
   - 각 작업의 assigned_section_id를 자동으로 할당
   - started_at 초기값 설정, estimated_total_seconds 계산
   - COMMIT으로 종료

2. **메뉴 조회** (예: "싸이버거 들어왔지 않나?" / "현재 메뉴 있어?")
   - MenuItems에서 모든 상품 조회: SELECT menu_item_id, name, price FROM MenuItems

3. **주방 큐 상태** (예: "지금 주방 작업 어떻게 되나?")
   - KitchenTaskQueue에서 QUEUED/IN_PROGRESS 상태인 작업 조회
   - 할당된 섹션 정보 포함

4. **작업 삭제** (예: "싸이버거 세트 3개는 기존에 있는거 주면 되니깐 큐에서 없애")
   - KitchenTaskQueue에서 특정 메뉴의 작업 DELETE

5. **작업 완료** (예: "Task 5 완료")
   - KitchenTaskQueue의 해당 작업 상태를 'COMPLETED'로 UPDATE
   - completed_at 자동 설정

[예시 - 메뉴 조회]
User: "싸이버거 들어왔지 않나?"
Output:
SELECT menu_item_id, name, price FROM MenuItems

[예시 - 특정 메뉴 작업 삭제]
User: "싸이버거 세트 3개는 기존에 있는거 주면 되니깐 큐에서 없애"
Output:
DELETE FROM KitchenTaskQueue
WHERE order_item_id IN (
    SELECT OI.order_item_id
    FROM OrderItems AS OI
    JOIN MenuItems AS MI ON OI.menu_item_id = MI.menu_item_id
    WHERE MI.name = '싸이버거 세트'
    ORDER BY OI.order_item_id DESC
    LIMIT 3
)

[예시 - 작업 상태 조회]
User: "지금 상태 어떻게 되지?"
Output:
SELECT
    KTQ.queue_task_id,
    CO.order_number,
    MI.name AS menu_item_name,
    MT.task_name,
    KTQ.assigned_section_id,
    KTQ.status,
    KTQ.started_at,
    KTQ.completed_at
FROM
    KitchenTaskQueue AS KTQ
JOIN
    OrderItems AS OI ON KTQ.order_item_id = OI.order_item_id
JOIN
    CustomerOrders AS CO ON OI.order_id = CO.order_id
JOIN
    MenuTasks AS MT ON KTQ.task_definition_id = MT.task_definition_id
JOIN
    MenuItems AS MI ON MT.menu_item_id = MI.menu_item_id
WHERE
    KTQ.status IN ('QUEUED', 'IN_PROGRESS')
ORDER BY
    CO.order_time, MT.task_order

[예시 4 - 작업 완료]
User: "Task 5 완료"
Output:
UPDATE KitchenTaskQueue SET status = 'COMPLETED', completed_at = datetime('now', 'localtime'), started_at = CASE WHEN started_at IS NULL THEN datetime('now', 'localtime') ELSE started_at END WHERE queue_task_id = 5
"""

# 3. User 모드: 고객 응대 및 시간 조회
PROMPT_USER = """
당신은 '키오스크 안내원'입니다.
사용자의 요청을 해석하여 적절한 SELECT SQL을 생성하세요.

[데이터베이스 스키마]
- CustomerOrders: order_id(PK), order_number(TEXT), status(TEXT), order_time(DATETIME)
- OrderItems: order_item_id(PK), order_id(FK), menu_item_id(FK)
- KitchenTaskQueue: queue_task_id(PK), order_item_id(FK), task_definition_id(FK), status
- MenuTasks: task_definition_id(PK), menu_item_id(FK), task_name, base_time_seconds
- MenuItems: menu_item_id(PK), name(TEXT), price(INT)

[요청 종류]
1. **주문 번호로 조회** (예: "ORD-001 상태")
   - 해당 주문의 상태와 남은 시간 조회

2. **메뉴 조회** (예: "메뉴를 보여주세요", "현재 팔고있는 상품")
   - MenuItems에서 모든 상품 조회

3. **최근 주문 조회** (예: "내 최근 주문은?")
   - 가장 최근의 주문을 조회

[절대 규칙]
- 반드시 SELECT 쿼리만 생성하세요
- 유효한 SQL 문법만 사용하세요
- 마지막 쉼표가 없어야 합니다
- 한글 설명이나 주석은 절대 포함하지 마세요
- SELECT 구문에서 쉼표 뒤에 바로 FROM이 오지 않도록 주의하세요

[예시 1 - 주문 상태 + ETA]
User: "ORD-001 상태"
Output:
SELECT 
  o.order_number, 
  o.status,
  IFNULL(SUM(t.base_time_seconds), 0) as remaining_seconds,
  datetime('now', 'localtime', '+' || printf('%d', IFNULL(SUM(t.base_time_seconds), 0)/60) || ' minutes') as estimated_pickup_time
FROM CustomerOrders o
LEFT JOIN OrderItems oi ON o.order_id = oi.order_id
LEFT JOIN KitchenTaskQueue q ON oi.order_item_id = q.order_item_id AND q.status != 'COMPLETED'
LEFT JOIN MenuTasks t ON q.task_definition_id = t.task_definition_id
WHERE o.order_number = 'ORD-001'
GROUP BY o.order_id

[예시 2 - 메뉴 전체 조회]
User: "메뉴를 보여주세요"
Output:
SELECT menu_item_id, name, price FROM MenuItems

[예시 3 - 최근 주문]
User: "내 최근 주문은?"
Output:
SELECT 
  o.order_number, 
  o.status,
  IFNULL(SUM(t.base_time_seconds), 0) as remaining_seconds,
  datetime('now', 'localtime', '+' || printf('%d', IFNULL(SUM(t.base_time_seconds), 0)/60) || ' minutes') as estimated_pickup_time
FROM CustomerOrders o
LEFT JOIN OrderItems oi ON o.order_id = oi.order_id
LEFT JOIN KitchenTaskQueue q ON oi.order_item_id = q.order_item_id AND q.status != 'COMPLETED'
LEFT JOIN MenuTasks t ON q.task_definition_id = t.task_definition_id
WHERE o.order_id = (SELECT order_id FROM CustomerOrders ORDER BY order_time DESC LIMIT 1)
GROUP BY o.order_id
"""

# 3-1. User 모드: 주문하기
PROMPT_USER_ORDER = """
당신은 '키오스크 주문 담당자'입니다.
고객이 메뉴를 선택하여 주문할 때, 다음 SQL을 생성하세요:
1. CustomerOrders에 새 주문 생성
2. OrderItems에 메뉴 추가
3. KitchenTaskQueue에 작업 추가 (assigned_section_id는 NULL, 이후 자동 할당됨)

[데이터베이스 스키마]
- MenuItems: menu_item_id(PK), name(TEXT), price(INT)
- MenuTasks: task_definition_id(PK), menu_item_id(FK), task_name, base_time_seconds, workstation_id, preferred_section_id
- CustomerOrders: order_id(PK), order_number(TEXT), status(TEXT), order_time(DATETIME), estimated_total_seconds(INT)
- OrderItems: order_item_id(PK), order_id(FK), menu_item_id(FK)
- KitchenTaskQueue: queue_task_id(PK), order_item_id(FK), task_definition_id(FK), assigned_section_id, status(TEXT), started_at, completed_at

[요청 형식]
- "싸이버거 1개" → 싸이버거 메뉴 이름으로 주문
- "1번 2개" → 1번 메뉴 ID로 주문 (숫자는 menu_item_id)
- "싸이버거 1개, 감자튀김 2개" → 여러 메뉴 주문

[절대 규칙]
- 반드시 유효한 SQL 코드만 출력하세요
- 마지막 쉼표가 없어야 합니다
- 한글은 절대 포함하지 마세요

[예시]
User: "싸이버거 1개"
Output:
BEGIN TRANSACTION;
INSERT INTO CustomerOrders (order_number, status, order_time, estimated_total_seconds) VALUES ('ORD-' || printf('%03d', COALESCE((SELECT MAX(CAST(substr(order_number,5) AS INTEGER)) FROM CustomerOrders WHERE date(order_time) = date('now')), 0) + 1), 'CONFIRMED', datetime('now', 'localtime'), (SELECT COALESCE(SUM(base_time_seconds), 0) FROM MenuTasks WHERE menu_item_id = (SELECT menu_item_id FROM MenuItems WHERE name='싸이버거')));
INSERT INTO OrderItems (order_id, menu_item_id) VALUES ((SELECT last_insert_rowid()), (SELECT menu_item_id FROM MenuItems WHERE name='싸이버거'));
INSERT INTO KitchenTaskQueue (order_item_id, task_definition_id, assigned_section_id, status, started_at) SELECT (SELECT last_insert_rowid()), task_definition_id, NULL, 'QUEUED', datetime('now', 'localtime') FROM MenuTasks WHERE menu_item_id = (SELECT menu_item_id FROM MenuItems WHERE name='싸이버거');
COMMIT
"""

# 3-2. User 모드: 주문 상태 조회
PROMPT_USER_STATUS = """
당신은 '키오스크 상태 조회 담당자'입니다.
고객이 주문번호를 입력하면, 그 주문의 상태와 예상 수령 시간을 조회하는 SQL을 생성하세요.

[절대 규칙]
- 반드시 SELECT 쿼리만 생성하세요
- 마지막 쉼표가 없어야 합니다
- 한글은 절대 포함하지 마세요

[예시]
User: "ORD-001"
Output:
SELECT 
  o.order_number, 
  o.status,
  IFNULL(SUM(t.base_time_seconds), 0) as remaining_seconds,
  datetime('now', 'localtime', '+' || printf('%d', IFNULL(SUM(t.base_time_seconds), 0)/60) || ' minutes') as estimated_pickup_time
FROM CustomerOrders o
LEFT JOIN OrderItems oi ON o.order_id = oi.order_id
LEFT JOIN KitchenTaskQueue q ON oi.order_item_id = q.order_item_id AND q.status != 'COMPLETED'
LEFT JOIN MenuTasks t ON q.task_definition_id = t.task_definition_id
WHERE o.order_number LIKE '%' || substr(사용자입력, -3)
GROUP BY o.order_id
"""

# 2-1. Manager 모드: 최적화 제안
PROMPT_MANAGER_OPTIMIZE = """
당신은 '주방 관리 AI'입니다.
현재 각 작업대의 상태를 보고 최적의 작업 분배를 제안하세요.

[역할]
- 각 작업대의 현재 작업량 분석
- 대기 중인 작업의 효율적 분배 방안 제시
- 예상 완료 시간 단축 방안 제안
- 작업자 배치 및 리소스 최적화

[제안 포맷]
구역별 권장사항과 예상 효과를 간단히 설명하세요.
한글로 자연스럽게 설명하되, 너무 길지 않게 (200자 이내)
"""

# ==========================================
# [공통 함수] DB 및 AI 통신
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # 확장된 스키마: 작업대 구성 및 제약조건 포함
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS Workstations (
        workstation_id INTEGER PRIMARY KEY, 
        name TEXT UNIQUE,
        total_units INTEGER DEFAULT 1
    );
    
    CREATE TABLE IF NOT EXISTS WorkstationSections (
        section_id INTEGER PRIMARY KEY,
        workstation_id INT,
        section_number INT,
        max_concurrent_tasks INT DEFAULT 1,
        description TEXT
    );
    
    CREATE TABLE IF NOT EXISTS WorkstationConstraints (
        constraint_id INTEGER PRIMARY KEY,
        section_id INT,
        menu_item_id INT,
        priority INT DEFAULT 0,
        description TEXT,
        UNIQUE(section_id, menu_item_id)
    );
    
    CREATE TABLE IF NOT EXISTS MenuItems (
        menu_item_id INTEGER PRIMARY KEY, 
        name TEXT UNIQUE, 
        price INT
    );
    
    CREATE TABLE IF NOT EXISTS MenuTasks (
        task_definition_id INTEGER PRIMARY KEY, 
        menu_item_id INT, 
        task_name TEXT, 
        task_order INT, 
        base_time_seconds INT,
        workstation_id INT,
        preferred_section_id INT
    );
    
    CREATE TABLE IF NOT EXISTS CustomerOrders (
        order_id INTEGER PRIMARY KEY, 
        order_number TEXT UNIQUE, 
        status TEXT,
        order_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        estimated_total_seconds INT DEFAULT 0,
        actual_total_seconds INT
    );
    
    CREATE TABLE IF NOT EXISTS OrderItems (
        order_item_id INTEGER PRIMARY KEY, 
        order_id INT, 
        menu_item_id INT
    );
    
    CREATE TABLE IF NOT EXISTS KitchenTaskQueue (
        queue_task_id INTEGER PRIMARY KEY, 
        order_item_id INT, 
        task_definition_id INT, 
        assigned_section_id INT,
        status TEXT DEFAULT 'QUEUED',
        started_at DATETIME,
        completed_at DATETIME
    );
    """)
    
    # 기본 작업장 시드 데이터만 한 번 확인 후 추가
    cursor.execute("SELECT COUNT(*) FROM Workstations")
    if cursor.fetchone()[0] == 0:
        cursor.executescript("""
        INSERT INTO Workstations (workstation_id, name, total_units) VALUES 
            (1, '튀김기', 2), 
            (2, '조립대', 3);
        
        INSERT INTO WorkstationSections (section_id, workstation_id, section_number, max_concurrent_tasks, description) VALUES
            (1, 1, 1, 1, '튀김기 #1'),
            (2, 1, 2, 1, '튀김기 #2'),
            (3, 2, 1, 2, '조립대 #1'),
            (4, 2, 2, 2, '조립대 #2'),
            (5, 2, 3, 2, '조립대 #3');
        """)
    
    conn.commit()
    return conn

def ask_gemini(system_prompt, user_input):
    model = genai.GenerativeModel('gemini-2.5-pro') # Pro 모델 사용
    full_prompt = f"{system_prompt}\n\nUser Input: \"{user_input}\"\n\n[중요] 반드시 유효한 SQL 코드만 출력하세요. 마지막 쉼표가 없어야 합니다. 설명이나 한글 텍스트는 절대 포함하지 마세요. SQL Query:"
    try:
        response = model.generate_content(full_prompt)
        text = response.text.replace("```sql", "").replace("```", "").strip()
        
        # SQL 문장 필터링: 한글/설명 제거
        sql_lines = []
        for line in text.split('\n'):
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith('--'):
                # 빈 줄 또는 주석
                if line_stripped:
                    sql_lines.append(line)
                continue
            
            line_upper = line_stripped.upper()
            # SQL 키워드로 시작하거나, SQL의 계속된 부분 (함수, 피연산자, 닫는 괄호)
            starts_with_sql = any(line_upper.startswith(kw) for kw in [
                'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'BEGIN', 'COMMIT', 
                'DECLARE', 'SET', 'FROM', 'VALUES', 'WHERE', 'JOIN', 
                'LEFT', 'RIGHT', 'INNER', 'OUTER', 'GROUP', 'ORDER', 'UNION',
                'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'AND', 'OR', '(', ')'
            ])
            
            # 괄호, 함수, 산술식 등 포함
            has_sql_content = any(c in line_stripped for c in ['(', ')', ',', ';']) or \
                             any(fn in line_upper for fn in ['COALESCE', 'MAX', 'MIN', 'SUM', 'COUNT', 
                                                               'PRINTF', 'SUBSTR', 'DATETIME', 'STRFTIME', 
                                                               'CAST', 'AS', 'LIKE', 'DESC', 'ASC', 'LIMIT',
                                                               'ON', 'ISNULL', 'IFNULL'])
            
            if starts_with_sql or has_sql_content:
                sql_lines.append(line)
        
        # SQL 문장 정리: trailing comma 제거, 문법 수정
        sql_text = '\n'.join(sql_lines).strip()
        
        # Trailing comma 제거 (FROM, WHERE, JOIN 등 키워드 앞의 쉼표)
        sql_text = sql_text.replace(',\nFROM', '\nFROM')
        sql_text = sql_text.replace(',\nWHERE', '\nWHERE')
        sql_text = sql_text.replace(',\nGROUP', '\nGROUP')
        sql_text = sql_text.replace(',\nORDER', '\nORDER')
        sql_text = sql_text.replace(',\nLEFT', '\nLEFT')
        sql_text = sql_text.replace(',\nRIGHT', '\nRIGHT')
        sql_text = sql_text.replace(',\nINNER', '\nINNER')
        sql_text = sql_text.replace(',\nJOIN', '\nJOIN')
        sql_text = sql_text.replace(',\nCOMMIT', '\nCOMMIT')
        sql_text = sql_text.replace(',\n;', '\n;')
        
        # 맨 마지막 줄에서 trailing comma 제거
        lines = sql_text.split('\n')
        cleaned_lines = []
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            # 마지막 줄이고 쉼표로 끝나는 경우
            if i == len(lines) - 1 and line_stripped.endswith(','):
                line = line.rstrip().rstrip(',')
            cleaned_lines.append(line)
        
        sql_text = '\n'.join(cleaned_lines).strip()
        
        # SQL 유효성 검증: FROM 다음에 WHERE가 바로 오는 경우 감지
        if 'FROM\nWHERE' in sql_text or 'FROM WHERE' in sql_text:
            print(Fore.YELLOW + "⚠️  경고: FROM 뒤에 테이블명이 없습니다. AI에게 다시 요청해주세요.")
            return ""
        
        # FROM 뒤에 공백만 있고 WHERE가 오는 경우
        import re
        if re.search(r'FROM\s+WHERE', sql_text, re.IGNORECASE):
            print(Fore.YELLOW + "⚠️  경고: FROM 뒤에 테이블명이 필요합니다.")
            return ""
        
        return sql_text
    except Exception as e:
        print(f"AI Error: {e}")
        return ""

def execute_and_show(conn, sql, show_result=False):
    if not sql or sql.strip() == '':
        print(Fore.RED + "❌ 오류: AI가 유효한 SQL을 생성하지 못했습니다.")
        return
    
    try:
        cursor = conn.cursor()
        print(Fore.BLUE + f"\n[AI Generated SQL]\n{sql}")
        
        # SELECT 문이면 결과 출력, 아니면 실행 후 커밋
        if sql.strip().upper().startswith("SELECT"):
            cursor.execute(sql)
            results = cursor.fetchall()
            if results:
                headers = [description[0] for description in cursor.description]
                print(Fore.GREEN + "\n[Query Result]")
                print(tabulate(results, headers=headers, tablefmt="fancy_grid"))
            else:
                print(Fore.YELLOW + "검색 결과가 없습니다.")
        else:
            # INSERT/UPDATE/DELETE 처리
            if ';' in sql or 'BEGIN' in sql.upper() or 'COMMIT' in sql.upper():
                cursor.executescript(sql)
            else:
                cursor.execute(sql)
            conn.commit()
            print(Fore.GREEN + "✅ DB 업데이트 완료!")
            
            # 주문 접수 후 자동으로 assigned_section_id 설정
            if 'INSERT INTO CustomerOrders' in sql and 'INSERT INTO KitchenTaskQueue' in sql:
                _auto_assign_sections(conn)
    except sqlite3.OperationalError as e:
        print(Fore.RED + f"❌ SQL 문법 오류: {e}")
        print(Fore.YELLOW + f"   생성된 SQL: {sql[:150]}...")
        print(Fore.YELLOW + f"   테이블/컬럼 존재 여부 확인")
    except Exception as e:
        print(Fore.RED + f"❌ 실행 오류: {e}")
        print(Fore.YELLOW + f"   생성된 SQL: {sql[:150]}...")

def _auto_assign_sections(conn):
    """주방 작업에 섹션 자동 할당 (주문 순서 보장, 용량 고려)"""
    cursor = conn.cursor()

    # assigned_section_id가 NULL인 작업들을 주문 시간 순서대로 찾기
    # 단, 같은 주문의 다른 아이템이 진행 중이면 대기 (배치 순차 처리)
    cursor.execute("""
        SELECT KTQ.queue_task_id, MT.task_definition_id, MT.preferred_section_id,
               MT.menu_item_id, MT.workstation_id, CO.order_time, MT.task_order,
               CO.order_id, OI.menu_item_id
        FROM KitchenTaskQueue KTQ
        JOIN MenuTasks MT ON KTQ.task_definition_id = MT.task_definition_id
        JOIN OrderItems OI ON KTQ.order_item_id = OI.order_item_id
        JOIN CustomerOrders CO ON OI.order_id = CO.order_id
        WHERE KTQ.assigned_section_id IS NULL AND KTQ.status = 'QUEUED'
        ORDER BY CO.order_time, MT.task_order, OI.order_item_id
    """)

    unassigned_tasks = cursor.fetchall()

    for queue_id, task_def_id, preferred_section, menu_item_id, workstation_id, order_time, task_order, order_id, order_menu_id in unassigned_tasks:
        # 1. 제약조건에 지정된 섹션이 있으면 그것을 사용
        cursor.execute("""
            SELECT section_id FROM WorkstationConstraints
            WHERE menu_item_id = ? LIMIT 1
        """, (menu_item_id,))

        constraint_result = cursor.fetchone()
        target_sections = [constraint_result[0]] if constraint_result else None

        # 2. 제약조건이 없으면 해당 작업장의 모든 섹션 중에서 선택
        if not target_sections:
            cursor.execute("""
                SELECT section_id FROM WorkstationSections
                WHERE workstation_id = ?
            """, (workstation_id,))
            target_sections = [row[0] for row in cursor.fetchall()]

        # 3. 각 섹션의 현재 사용 중인 작업 수 확인하고 빈 자리 찾기
        assigned_section = None
        for section_id in target_sections:
            # 해당 섹션에서 진행 중인 작업 수 확인
            cursor.execute("""
                SELECT COUNT(*) FROM KitchenTaskQueue
                WHERE assigned_section_id = ? AND status = 'IN_PROGRESS'
            """, (section_id,))
            in_progress_count = cursor.fetchone()[0]

            # 섹션의 최대 동시 작업 수 확인
            cursor.execute("""
                SELECT max_concurrent_tasks FROM WorkstationSections
                WHERE section_id = ?
            """, (section_id,))
            max_concurrent = cursor.fetchone()[0]

            # 빈 자리가 있으면 할당
            if in_progress_count < max_concurrent:
                assigned_section = section_id
                break

        # 4. 빈 자리가 있으면 섹션 할당하고 시작 (가상 시간 사용)
        if assigned_section:
            virtual_now = get_virtual_time().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                UPDATE KitchenTaskQueue
                SET assigned_section_id = ?, status = 'IN_PROGRESS', started_at = ?
                WHERE queue_task_id = ?
            """, (assigned_section, virtual_now, queue_id))
        # 빈 자리가 없으면 QUEUED 상태 유지 (다음 타이머 루프에서 다시 시도)

    conn.commit()

# ==========================================
# [모드별 실행 함수]
# ==========================================

def mode_dba(conn):
    print(Fore.YELLOW + "\n🔧 [DBA 모드] 메뉴 및 레시피 관리자")
    print("예: '불고기버거(4000원) 추가. 레시피: 1.패티굽기(200초), 2.조립(50초)'")
    
    while True:
        # 현재 메뉴 목록 보여주기
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM MenuItems")
        menus = [row[0] for row in cursor.fetchall()]
        print(f"현재 등록된 메뉴: {menus}")
        
        user_input = input("\nDBA Command (exit로 종료) > ")
        if user_input == 'exit': break
        
        sql = ask_gemini(PROMPT_DBA, user_input)
        execute_and_show(conn, sql)

def mode_manager(conn):
    cursor = conn.cursor()

    try:
        first_run = True
        while True:
            # 첫 실행이 아니면 2초 대기
            if not first_run:
                time.sleep(2)
            else:
                first_run = False

            # 화면 클리어
            os.system('cls' if os.name == 'nt' else 'clear')

            # 가상 시간
            current_virtual_time = get_virtual_time()

            # 오늘의 모든 주문 조회 (완료된 주문 포함)
            cursor.execute("""
                SELECT COUNT(*) FROM CustomerOrders
                WHERE date(order_time) = date('now')
            """)

            if cursor.fetchone()[0] == 0:
                print(f"\n{Fore.CYAN}👔 [Manager 모드] 실시간 주방 현황판{Style.RESET_ALL}")
                print(f"\n{Fore.YELLOW}⏰ [{current_virtual_time.strftime('%H:%M')}]{Style.RESET_ALL}\n")
                print(f"{Fore.GREEN}✅ 오늘 주문이 없습니다!{Style.RESET_ALL}")

                # 입력 대기 (Enter로 나가기)
                input(f"\n{Fore.CYAN}[메인 메뉴로 돌아가기: Enter]{Style.RESET_ALL}")
                return  # mode_manager 함수 종료

            # 주문별 현황 조회 (메뉴별로 묶어서, 완료된 주문 포함)
            cursor.execute("""
                SELECT
                    co.order_number,
                    mi.name as menu_name,
                    mi.menu_item_id,
                    COUNT(DISTINCT oi.order_item_id) as quantity,
                    co.order_time,
                    co.estimated_total_seconds
                FROM CustomerOrders co
                JOIN OrderItems oi ON co.order_id = oi.order_id
                JOIN MenuItems mi ON oi.menu_item_id = mi.menu_item_id
                WHERE date(co.order_time) = date('now')
                GROUP BY co.order_number, mi.name, mi.menu_item_id, co.order_time, co.estimated_total_seconds
                ORDER BY co.order_time, mi.menu_item_id
            """)

            order_menu_groups = cursor.fetchall()

            # 현황판 출력
            print(f"\n{Fore.CYAN}👔 [Manager 모드] 실시간 주방 현황판 (종료: Ctrl+C){Style.RESET_ALL}")
            print(f"\n{Fore.YELLOW}⏰ [{current_virtual_time.strftime('%H:%M')}]{Style.RESET_ALL}\n")

            # 주문별로 그룹화하여 표시
            table_data = []
            prev_order_num = None

            for order_num, menu_name, menu_item_id, quantity, order_time, estimated_seconds in order_menu_groups:
                # 예상 완료 시각 계산
                order_datetime = datetime.strptime(order_time, '%Y-%m-%d %H:%M:%S')
                estimated_finish = order_datetime + timedelta(seconds=estimated_seconds)
                estimated_finish_str = estimated_finish.strftime('%H:%M')
                # 이 주문의 이 메뉴에 대한 모든 order_item_id 가져오기
                cursor.execute("""
                    SELECT oi.order_item_id
                    FROM OrderItems oi
                    JOIN CustomerOrders co ON oi.order_id = co.order_id
                    WHERE co.order_number = ? AND oi.menu_item_id = ?
                """, (order_num, menu_item_id))

                order_item_ids = [row[0] for row in cursor.fetchall()]

                # 모든 항목의 작업을 가져와서 가장 늦게 끝나는 시간 기준으로 표시
                # all_completed: 모든 아이템이 완료되어야 1, 하나라도 미완료면 0
                cursor.execute("""
                    SELECT
                        mt.task_name,
                        CASE WHEN COUNT(*) = SUM(CASE WHEN ktq.status = 'COMPLETED' THEN 1 ELSE 0 END) THEN 1 ELSE 0 END as all_completed,
                        MAX(mt.base_time_seconds) as duration,
                        MAX(ktq.started_at) as latest_start,
                        MAX(ktq.status) as latest_status
                    FROM KitchenTaskQueue ktq
                    JOIN MenuTasks mt ON ktq.task_definition_id = mt.task_definition_id
                    WHERE ktq.order_item_id IN ({})
                    GROUP BY mt.task_name, mt.task_order
                    ORDER BY mt.task_order
                """.format(','.join('?' * len(order_item_ids))), order_item_ids)

                tasks = cursor.fetchall()

                # 전체 완료 여부 체크 (모든 항목이 완료되었는지)
                all_completed = True
                any_in_progress = False
                debug_early_completion = False

                for item_id in order_item_ids:
                    cursor.execute("""
                        SELECT COUNT(*) as total, SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed
                        FROM KitchenTaskQueue
                        WHERE order_item_id = ?
                    """, (item_id,))
                    total, completed = cursor.fetchone()
                    if completed < total:
                        all_completed = False
                    if completed > 0 and completed < total:
                        any_in_progress = True

                # 작업 진행 상황 문자열 생성
                # 전체 주문의 남은 시간 = 완료예정 시각 - 현재 시각
                total_remaining = (estimated_finish - current_virtual_time).total_seconds() / 60
                total_remaining = max(0, int(total_remaining))

                task_status_parts = []
                # 전체 주문이 완료되었는지에 따라 표시 (개별 작업이 아닌)
                for task_name, task_all_completed, duration, started_at, latest_status in tasks:
                    if all_completed:
                        # 전체 주문이 완료됨
                        if '패티' in task_name:
                            task_status_parts.append("✅패티")
                        elif '감자' in task_name:
                            task_status_parts.append("✅감자")
                        elif '치킨' in task_name:
                            task_status_parts.append("✅치킨")
                        elif '음료' in task_name:
                            task_status_parts.append("✅음료")
                        else:
                            task_status_parts.append("✅" + task_name[:4])
                    elif started_at is None or latest_status == 'QUEUED':
                        # 대기 중
                        if '패티' in task_name:
                            task_status_parts.append(f"⏳패티({total_remaining}분)")
                        elif '감자' in task_name:
                            task_status_parts.append(f"⏳감자({total_remaining}분)")
                        elif '치킨' in task_name:
                            task_status_parts.append(f"⏳치킨({total_remaining}분)")
                        elif '음료' in task_name:
                            task_status_parts.append(f"⏳음료({total_remaining}분)")
                        else:
                            task_status_parts.append(f"⏳{task_name[:4]}({total_remaining}분)")
                    else:
                        # 진행 중 - 전체 주문의 남은 시간 표시
                        if '패티' in task_name:
                            task_status_parts.append(f"⏳패티({total_remaining}분)")
                        elif '감자' in task_name:
                            task_status_parts.append(f"⏳감자({total_remaining}분)")
                        elif '치킨' in task_name:
                            task_status_parts.append(f"⏳치킨({total_remaining}분)")
                        elif '음료' in task_name:
                            task_status_parts.append(f"⏳음료({total_remaining}분)")
                        else:
                            task_status_parts.append(f"⏳{task_name[:4]}({total_remaining}분)")

                task_status_str = " ".join(task_status_parts)

                # 전체 상태 판단
                if all_completed:
                    overall_status = "완료"
                else:
                    overall_status = "조리중"

                # 수량 표시
                menu_display = f"{menu_name} x{quantity}" if quantity > 1 else menu_name

                # 주문번호, 시작시각, 예상완료시각 표시 (같은 주문번호면 빈칸)
                # 실제 조리 시작 시간 = 첫 번째 작업의 started_at
                cursor.execute("""
                    SELECT MIN(ktq.started_at)
                    FROM KitchenTaskQueue ktq
                    WHERE ktq.order_item_id IN ({})
                    AND ktq.started_at IS NOT NULL
                """.format(','.join('?' * len(order_item_ids))), order_item_ids)

                actual_start = cursor.fetchone()[0]
                if actual_start:
                    actual_start_dt = datetime.strptime(actual_start, '%Y-%m-%d %H:%M:%S')
                    order_start_str = actual_start_dt.strftime('%H:%M')
                else:
                    order_start_str = "-"  # 아직 시작 안 함
                if order_num != prev_order_num:
                    order_num_display = order_num
                    start_time_display = order_start_str
                    finish_time_display = estimated_finish_str
                    prev_order_num = order_num
                else:
                    order_num_display = ""
                    start_time_display = ""
                    finish_time_display = ""

                table_data.append([order_num_display, menu_display, task_status_str, overall_status, start_time_display, finish_time_display])

            # 한글 문자 너비 계산 함수
            def get_display_width(text):
                width = 0
                for char in str(text):
                    if ord(char) > 127:
                        width += 2
                    else:
                        width += 1
                return width

            def pad_string(text, target_width):
                current_width = get_display_width(text)
                padding_needed = target_width - current_width
                return text + ' ' * padding_needed

            # 각 열의 최대 너비 계산
            if table_data:
                header = ["주문번호", "메뉴", "작업 진행상황", "상태", "시작시간", "완료예정"]
                col_widths = [
                    max([get_display_width(row[i]) for row in table_data] + [get_display_width(header[i])])
                    for i in range(6)
                ]

                # 수동으로 테이블 그리기
                # 상단 경계
                print("┌─" + "─┬─".join(["─" * w for w in col_widths]) + "─┐")

                # 헤더
                header_row = "│ " + " │ ".join([pad_string(header[i], col_widths[i]) for i in range(6)]) + " │"
                print(header_row)

                # 헤더 구분선
                print("├─" + "─┼─".join(["─" * w for w in col_widths]) + "─┤")

                # 데이터 행
                for row in table_data:
                    data_row = "│ " + " │ ".join([pad_string(str(row[i]), col_widths[i]) for i in range(6)]) + " │"
                    print(data_row)

                # 하단 경계
                print("└─" + "─┴─".join(["─" * w for w in col_widths]) + "─┘")

    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}Manager 모드를 종료합니다.{Style.RESET_ALL}")
        time.sleep(1)


def mode_user(conn):
    cursor = conn.cursor()
    cart = []  # 장바구니: [(menu_id, menu_name, price, quantity), ...]

    while True:
        # 메뉴 자동 표시
        cursor.execute("SELECT menu_item_id, name, price FROM MenuItems ORDER BY menu_item_id")
        menu_results = cursor.fetchall()

        if menu_results:
            # 카테고리별 분류
            burgers = []
            sets = []
            chickens = []
            drinks = []

            for menu_id, name, price in menu_results:
                if '세트' in name:
                    sets.append((menu_id, name, price))
                elif ('치킨' in name or '순살' in name) and '버거' not in name:
                    chickens.append((menu_id, name, price))
                elif '콜라' in name or '사이다' in name or '환타' in name:
                    drinks.append((menu_id, name, price))
                else:
                    burgers.append((menu_id, name, price))

            # 한글 문자 너비 계산
            def get_display_width(text):
                width = 0
                for char in str(text):
                    if ord(char) > 127:
                        width += 2
                    else:
                        width += 1
                return width

            def pad_string(text, target_width):
                current_width = get_display_width(text)
                padding = target_width - current_width
                return str(text) + ' ' * max(0, padding)

            print(Fore.GREEN + "\n" + "="*70)
            print("🍔 맘스터치 메뉴판")
            print("="*70)

            # 버거 단품 (2열)
            if burgers:
                print(Fore.YELLOW + "\n[ 버거 단품 ]")
                for i in range(0, len(burgers), 2):
                    left = burgers[i]
                    right = burgers[i+1] if i+1 < len(burgers) else None

                    left_str = f"{left[0]:2d}. {pad_string(left[1], 20)} {left[2]:>6,}원"
                    if right:
                        right_str = f"{right[0]:2d}. {pad_string(right[1], 20)} {right[2]:>6,}원"
                        print(f"{left_str}  |  {right_str}")
                    else:
                        print(left_str)

            # 세트 메뉴 (2열)
            if sets:
                print(Fore.YELLOW + "\n[ 세트 메뉴 ]")
                for i in range(0, len(sets), 2):
                    left = sets[i]
                    right = sets[i+1] if i+1 < len(sets) else None

                    left_str = f"{left[0]:2d}. {pad_string(left[1], 20)} {left[2]:>6,}원"
                    if right:
                        right_str = f"{right[0]:2d}. {pad_string(right[1], 20)} {right[2]:>6,}원"
                        print(f"{left_str}  |  {right_str}")
                    else:
                        print(left_str)

            # 치킨 (1열)
            if chickens:
                print(Fore.YELLOW + "\n[ 치킨 ]")
                for menu_id, name, price in chickens:
                    print(f"{menu_id:2d}. {pad_string(name, 20)} {price:>6,}원")

            # 음료 (3열)
            if drinks:
                print(Fore.YELLOW + "\n[ 음료 ]")
                for i in range(0, len(drinks), 3):
                    items = drinks[i:i+3]
                    line_parts = []
                    for menu_id, name, price in items:
                        line_parts.append(f"{menu_id:2d}. {pad_string(name, 12)} {price:>5,}원")
                    print("  |  ".join(line_parts))

            print(Fore.GREEN + "\n" + "="*70)

        # 장바구니 표시
        if cart:
            print(Fore.CYAN + "\n[ 장바구니 ]")
            total_cart_price = 0
            for i, (mid, mname, mprice, qty) in enumerate(cart, 1):
                item_total = mprice * qty
                total_cart_price += item_total
                print(f"{i}. {mname} x {qty}개 = {item_total:,}원")
            print(Fore.CYAN + f"총 금액: {total_cart_price:,}원")

        # 메뉴 입력
        print(Fore.WHITE + "\n명령: 메뉴번호 수량 (예: 1 2) | 주문완료(0) | 메인으로(c)")
        user_input = input("입력 > ").strip()

        # 주문 완료
        if user_input == '0':
            if not cart:
                print(Fore.RED + "장바구니가 비어있습니다.")
                continue

            # 최종 확인
            total_cart_price = sum(mprice * qty for _, _, mprice, qty in cart)
            print(Fore.YELLOW + f"\n최종 주문 확인:")
            for mname, mprice, qty in [(n, p, q) for _, n, p, q in cart]:
                print(f"  - {mname} x {qty}개")
            print(Fore.YELLOW + f"총 금액: {total_cart_price:,}원")

            confirm = input("\n주문하시겠습니까? (y/n) > ").strip().lower()
            if confirm != 'y':
                print("주문이 취소되었습니다.")
                cart.clear()
                continue
            break  # 주문 처리로 진행

        # 메인 메뉴로 돌아가기
        if user_input.lower() == 'c':
            print(Fore.YELLOW + "주문을 취소하고 메인 메뉴로 돌아갑니다.")
            time.sleep(1)
            return  # mode_user 함수 종료 -> 메인 메뉴로

        # 메뉴 추가
        parts = user_input.split()
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            print(Fore.RED + "잘못된 입력입니다. (예: 1 2)")
            continue

        menu_id = int(parts[0])
        quantity = int(parts[1])

        if quantity <= 0:
            print(Fore.RED + "수량은 1개 이상이어야 합니다.")
            continue

        # 메뉴 확인
        cursor.execute("SELECT name, price FROM MenuItems WHERE menu_item_id = ?", (menu_id,))
        menu_info = cursor.fetchone()
        if not menu_info:
            print(Fore.RED + "존재하지 않는 메뉴 번호입니다.")
            continue

        menu_name, menu_price = menu_info

        # 장바구니에 추가 (같은 메뉴면 수량 누적)
        found = False
        for i, (mid, mname, mprice, qty) in enumerate(cart):
            if mid == menu_id:
                cart[i] = (mid, mname, mprice, qty + quantity)
                found = True
                break

        if not found:
            cart.append((menu_id, menu_name, menu_price, quantity))

        print(Fore.GREEN + f"✓ {menu_name} x {quantity}개 추가됨")
        continue

    # 여기부터 주문 처리
    if not cart:
        return

    # 주문 처리
    try:
        # 주문번호 생성
        cursor.execute("""
            SELECT COALESCE(MAX(CAST(substr(order_number,5) AS INTEGER)), 0) + 1
            FROM CustomerOrders
            WHERE date(order_time) = date('now')
        """)
        order_seq = cursor.fetchone()[0]
        order_number = f"ORD-{order_seq:03d}"

        # 예상 시간 계산 (섹션 용량 + 대기 시간 고려)
        # 1. 현재 진행 중인 모든 주문의 남은 작업 개수 계산
        cursor.execute("""
            SELECT mt.workstation_id, mt.task_name, mt.base_time_seconds, COUNT(*) as pending_count,
                   MAX(datetime(ktq.started_at, '+' || mt.base_time_seconds || ' seconds')) as latest_finish
            FROM KitchenTaskQueue ktq
            JOIN MenuTasks mt ON ktq.task_definition_id = mt.task_definition_id
            WHERE ktq.status IN ('IN_PROGRESS', 'QUEUED')
            GROUP BY mt.workstation_id, mt.task_name, mt.base_time_seconds
        """)

        ongoing_results = cursor.fetchall()
        ongoing_tasks = {}  # {(workstation_id, task_name): (pending_count, base_time, latest_finish)}
        ongoing_tasks_display = {}  # 표시용 (주문 전 상태)
        current_virtual_time = get_virtual_time()

        for ws_id, task_name, base_time, pending_count, latest_finish in ongoing_results:
            task_key = (ws_id, task_name)
            # 남은 시간 계산
            if latest_finish:
                finish_time = datetime.strptime(latest_finish, '%Y-%m-%d %H:%M:%S')
                remaining = (finish_time - current_virtual_time).total_seconds()
                remaining = max(0, remaining)
            else:
                remaining = 0
            ongoing_tasks[task_key] = (pending_count, base_time, remaining)

        # 2. 새 주문의 작업 개수 세기
        task_counts = {}  # {(workstation_id, task_name): (count, base_time)}

        for menu_id, _, _, quantity in cart:
            cursor.execute("""
                SELECT workstation_id, task_name, base_time_seconds
                FROM MenuTasks
                WHERE menu_item_id = ?
                ORDER BY task_order
            """, (menu_id,))

            tasks = cursor.fetchall()

            for workstation_id, task_name, base_time in tasks:
                task_key = (workstation_id, task_name)
                if task_key not in task_counts:
                    task_counts[task_key] = [0, base_time]
                task_counts[task_key][0] += quantity

        # 3. 대기 시간 + 실행 시간 계산
        task_times = []
        for (workstation_id, task_name), (count, base_time) in task_counts.items():
            task_key = (workstation_id, task_name)

            # 섹션 용량의 합계 조회 (섹션 개수 x 각 섹션의 max_concurrent_tasks)
            cursor.execute("""
                SELECT SUM(max_concurrent_tasks) FROM WorkstationSections
                WHERE workstation_id = ?
            """, (workstation_id,))
            max_concurrent = cursor.fetchone()[0] or 0

            # 진행 중인 작업이 있으면 대기 시간 추가
            wait_time = 0
            if task_key in ongoing_tasks:
                pending_count, _, remaining = ongoing_tasks[task_key]
                # 현재 진행중인 작업의 남은 시간을 대기 시간으로
                wait_time = remaining

            # 새 주문의 배치 수 계산
            if max_concurrent > 0:
                batches = (count + max_concurrent - 1) // max_concurrent
            else:
                batches = count

            # 총 시간 = 대기 시간 + (배치 수 × 작업 시간)
            total_time = wait_time + (batches * base_time)
            task_times.append(total_time)

        # 모든 작업 중 가장 긴 시간
        total_estimated_time = max(task_times) if task_times else 0

        # 트랜잭션 시작
        cursor.execute("BEGIN TRANSACTION")

        # CustomerOrders 생성 (가상 시간 사용)
        virtual_now = get_virtual_time().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            INSERT INTO CustomerOrders (order_number, status, order_time, estimated_total_seconds)
            VALUES (?, 'CONFIRMED', ?, ?)
        """, (order_number, virtual_now, total_estimated_time))

        order_id = cursor.lastrowid

        # 장바구니의 각 항목 처리
        for menu_id, menu_name, menu_price, quantity in cart:
            # OrderItems 생성 (수량만큼)
            for _ in range(quantity):
                cursor.execute("""
                    INSERT INTO OrderItems (order_id, menu_item_id)
                    VALUES (?, ?)
                """, (order_id, menu_id))

                order_item_id = cursor.lastrowid

                # KitchenTaskQueue 생성 (QUEUED 상태로, 나중에 _auto_assign_sections에서 시작)
                cursor.execute("""
                    INSERT INTO KitchenTaskQueue (order_item_id, task_definition_id, assigned_section_id, status, started_at)
                    SELECT ?, task_definition_id, NULL, 'QUEUED', NULL
                    FROM MenuTasks
                    WHERE menu_item_id = ?
                    ORDER BY task_order
                """, (order_item_id, menu_id))

        cursor.execute("COMMIT")

        # 섹션 자동 할당
        _auto_assign_sections(conn)

        print(Fore.GREEN + f"\n✅ 주문 완료! 주문번호: {order_number}")
        print(Fore.CYAN + f"   예상 시간: {total_estimated_time // 60}분 {total_estimated_time % 60}초")

        # 작업 시작 메시지 출력 (배치 정보 포함)
        print(f"\n{Fore.YELLOW}🔥 [{get_virtual_time().strftime('%H:%M')}] 주문 접수 완료!")

        for menu_id, menu_name, _, quantity in cart:
            cursor.execute("""
                SELECT task_name, base_time_seconds, workstation_id
                FROM MenuTasks
                WHERE menu_item_id = ?
                ORDER BY task_order
            """, (menu_id,))
            tasks = cursor.fetchall()

            # 메뉴의 가장 긴 작업 시간을 찾기 (병렬 처리 가정)
            max_task_time = 0
            max_wait_time = 0
            task_details = []

            for task_name, duration, workstation_id in tasks:
                # 해당 작업장의 용량 확인
                cursor.execute("""
                    SELECT SUM(max_concurrent_tasks)
                    FROM WorkstationSections
                    WHERE workstation_id = ?
                """, (workstation_id,))
                total_capacity = cursor.fetchone()[0] or 1

                # 배치 수 계산
                batches = (quantity + total_capacity - 1) // total_capacity
                cook_minutes = batches * (duration // 60)

                # 대기 시간 계산 - 현재 진행 중인 작업의 완료 시각까지 대기
                key = (workstation_id, task_name)
                wait_minutes = 0
                if key in ongoing_tasks:
                    ongoing = ongoing_tasks[key]
                    # latest_finish가 있으면 그 시각까지 대기
                    if ongoing['finish']:
                        current_time = get_virtual_time()
                        finish_time = datetime.strptime(ongoing['finish'], '%Y-%m-%d %H:%M:%S')
                        wait_seconds = (finish_time - current_time).total_seconds()
                        wait_minutes = max(0, int(wait_seconds // 60))

                # 이 작업의 총 시간
                total_task_time = wait_minutes + cook_minutes

                if total_task_time > max_task_time:
                    max_task_time = total_task_time
                    max_wait_time = wait_minutes

                # 작업 정보 저장 - 간단하고 명확하게
                if '패티' in task_name:
                    label = "패티"
                elif '감자' in task_name:
                    label = "감자"
                elif '치킨' in task_name:
                    if '뼈' in task_name:
                        label = "치킨(뼈)"
                    elif '순살' in task_name:
                        label = "순살"
                    else:
                        label = "치킨"
                elif '음료' in task_name:
                    label = "음료"
                else:
                    label = task_name[:6]

                if batches > 1:
                    task_details.append(f"{label}×{batches}배치")
                else:
                    task_details.append(f"{label}")

            # 메뉴당 한 줄로 표시
            task_summary = ", ".join(task_details)
            print(f"{Fore.CYAN}   • {menu_name} x{quantity}: {task_summary}")

            if max_wait_time > 0:
                print(f"{Fore.YELLOW}     ↳ 대기 {max_wait_time}분 + 조리 {max_task_time - max_wait_time}분 = 총 {max_task_time}분")

        # 타이머 시작 (아직 안 돌고 있으면)
        if not TIMER_RUNNING:
            start_virtual_timer()

        # 장바구니 비우기
        cart.clear()

        # 사용자가 Enter 누를 때까지 대기
        input(f"\n{Fore.CYAN}[Enter 키를 눌러 계속하기]{Style.RESET_ALL}")
        # continue로 while 루프 계속

    except Exception as e:
        cursor.execute("ROLLBACK")
        print(Fore.RED + f"❌ 주문 실패: {e}")

# ==========================================
# [메인 진입점]
# ==========================================
def main():
    conn = init_db()

    # 프로그램 시작 시 이전 세션의 미완료 작업 및 오늘 주문 정리
    cursor = conn.cursor()

    # 미완료 작업 완료 처리
    cursor.execute("""
        UPDATE KitchenTaskQueue
        SET status = 'COMPLETED', completed_at = datetime('now', 'localtime')
        WHERE status IN ('IN_PROGRESS', 'QUEUED')
    """)

    # 오늘 날짜의 모든 주문 삭제 (깨끗하게 시작)
    cursor.execute("""
        DELETE FROM KitchenTaskQueue
        WHERE order_item_id IN (
            SELECT oi.order_item_id
            FROM OrderItems oi
            JOIN CustomerOrders co ON oi.order_id = co.order_id
            WHERE date(co.order_time) = date('now')
        )
    """)

    cursor.execute("""
        DELETE FROM OrderItems
        WHERE order_id IN (
            SELECT order_id FROM CustomerOrders
            WHERE date(order_time) = date('now')
        )
    """)

    cursor.execute("""
        DELETE FROM CustomerOrders
        WHERE date(order_time) = date('now')
    """)

    conn.commit()
    print(f"{Fore.YELLOW}🧹 이전 세션 정리 완료 (오늘 주문 초기화){Style.RESET_ALL}")
    time.sleep(1)

    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(Fore.MAGENTA + Style.BRIGHT + "="*50)
        print("🍔 MOM'S TOUCH DATABASE SYSTEM 🍔")
        print("="*50)
        print("1. 🔧 DBA (메뉴/레시피 관리)")
        print("2. 🍔 주문하기")
        print("3. 👔 Manager (주방 관리)")
        print("0. ❌ 종료")
        
        choice = input(Fore.WHITE + "\n모드를 선택하세요 > ")
        
        if choice == '1': mode_dba(conn)
        elif choice == '2': mode_user(conn)
        elif choice == '3': mode_manager(conn)
        elif choice == '0': 
            conn.close()
            print("시스템 종료.")
            break
        else:
            print("잘못된 입력입니다.")
            time.sleep(1)

if __name__ == "__main__":
    main()