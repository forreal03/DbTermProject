import sqlite3
import os
import time
import google.generativeai as genai
from dotenv import load_dotenv
from tabulate import tabulate
from colorama import Fore, Style, init

# 1. 환경 설정
load_dotenv()
init(autoreset=True)

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    print(Fore.RED + "❌ 오류: .env 파일에 GOOGLE_API_KEY가 없습니다.")
    exit()

# 모델 설정 (Pro 모델 권장)
genai.configure(api_key=API_KEY)
DB_NAME = "momstouch_v2.db"

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
    """주방 작업에 섹션 자동 할당"""
    cursor = conn.cursor()
    
    # assigned_section_id가 NULL인 작업들 찾기
    cursor.execute("""
        SELECT KTQ.queue_task_id, MT.task_definition_id, MT.preferred_section_id, MT.menu_item_id
        FROM KitchenTaskQueue KTQ
        JOIN MenuTasks MT ON KTQ.task_definition_id = MT.task_definition_id
        WHERE KTQ.assigned_section_id IS NULL
    """)
    
    unassigned_tasks = cursor.fetchall()
    
    for queue_id, task_def_id, preferred_section, menu_item_id in unassigned_tasks:
        # 1. 제약조건에 지정된 섹션이 있으면 그것을 사용
        cursor.execute("""
            SELECT section_id FROM WorkstationConstraints 
            WHERE menu_item_id = ? LIMIT 1
        """, (menu_item_id,))
        
        constraint_result = cursor.fetchone()
        assigned_section = constraint_result[0] if constraint_result else preferred_section
        
        if assigned_section:
            cursor.execute("""
                UPDATE KitchenTaskQueue 
                SET assigned_section_id = ?, started_at = datetime('now', 'localtime')
                WHERE queue_task_id = ?
            """, (assigned_section, queue_id))
    
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
    print(Fore.CYAN + "\n👔 [Manager 모드] 주방 관리 (주문 접수/완료 처리)")
    print("명령: '주문받기', '완료', '상태', '최적화', 'exit'")
    
    while True:
        # 현재 큐 상태 보여주기
        cursor = conn.cursor()
        cursor.execute("""
            SELECT o.order_number, m.name, t.task_name, q.queue_task_id, q.status, q.assigned_section_id, 
                   CASE WHEN q.completed_at IS NOT NULL THEN 'O' ELSE 'X' END as 완료여부,
                   strftime('%M:%S', CASE WHEN q.started_at IS NOT NULL THEN q.started_at ELSE '기록없음' END) as 시작시간
            FROM KitchenTaskQueue q
            JOIN MenuTasks t ON q.task_definition_id = t.task_definition_id
            JOIN OrderItems oi ON q.order_item_id = oi.order_item_id
            JOIN MenuItems m ON oi.menu_item_id = m.menu_item_id
            JOIN CustomerOrders o ON oi.order_id = o.order_id
            WHERE q.status IN ('QUEUED', 'IN_PROGRESS')
            ORDER BY o.order_time, t.task_order
        """)
        tasks = cursor.fetchall()
        print(Fore.CYAN + "\n[현재 주방 작업 큐]")
        if tasks:
            print(tabulate(tasks, headers=["주문번호", "메뉴", "현재작업", "Task ID", "상태", "섹션", "완료", "시작시간"], tablefmt="simple"))
        else:
            print("대기 중인 작업 없음.")

        user_input = input("\nManager Command (주문받기/완료/상태/최적화/exit) > ").strip()
        if user_input == 'exit': 
            break
        
        # 주문 접수
        if '주문' in user_input or '받' in user_input:
            menu_input = input("주문 내용 입력 (예: '싸이버거 1개') > ").strip()
            sql = ask_gemini(PROMPT_MANAGER, menu_input)
            execute_and_show(conn, sql)
        
        # 작업 완료 처리
        elif '완료' in user_input or '처리' in user_input:
            task_id = input("완료할 Task ID 입력 > ").strip()
            if task_id.isdigit():
                # 작업 완료 + 시간 기록
                cursor.execute("""
                    UPDATE KitchenTaskQueue 
                    SET status = 'COMPLETED', 
                        completed_at = datetime('now', 'localtime'),
                        started_at = CASE WHEN started_at IS NULL THEN datetime('now', 'localtime') ELSE started_at END
                    WHERE queue_task_id = ?
                """, (int(task_id),))
                
                # 해당 작업이 완료되면 다음 작업을 IN_PROGRESS로 변경
                cursor.execute("""
                    SELECT order_item_id FROM KitchenTaskQueue WHERE queue_task_id = ?
                """, (int(task_id),))
                
                order_item = cursor.fetchone()
                if order_item:
                    order_item_id = order_item[0]
                    cursor.execute("""
                        UPDATE KitchenTaskQueue 
                        SET status = 'IN_PROGRESS'
                        WHERE order_item_id = ? AND status = 'QUEUED'
                        LIMIT 1
                    """, (order_item_id,))
                
                # 주문 전체의 actual_total_seconds 계산 (모든 작업 완료 시간 - 주문 시간)
                cursor.execute("""
                    SELECT OI.order_id FROM OrderItems OI
                    WHERE OI.order_item_id = ?
                """, (order_item_id,))
                
                result = cursor.fetchone()
                if result:
                    order_id = result[0]
                    cursor.execute("""
                        SELECT CAST((julianday(MAX(KTQ.completed_at)) - julianday(CO.order_time)) * 86400 AS INTEGER) as actual_seconds
                        FROM CustomerOrders CO
                        JOIN OrderItems OI ON CO.order_id = OI.order_id
                        JOIN KitchenTaskQueue KTQ ON OI.order_item_id = KTQ.order_item_id
                        WHERE CO.order_id = ? AND KTQ.completed_at IS NOT NULL
                        GROUP BY CO.order_id
                    """, (order_id,))
                    
                    time_result = cursor.fetchone()
                    if time_result and time_result[0]:
                        actual_seconds = time_result[0]
                        cursor.execute("""
                            UPDATE CustomerOrders 
                            SET actual_total_seconds = ? 
                            WHERE order_id = ?
                        """, (actual_seconds, order_id))
                
                conn.commit()
                print(Fore.GREEN + "✅ 작업 완료 처리 및 시간 기록 완료!")
        
        # 상태 조회
        elif '상태' in user_input:
            sql = ask_gemini(PROMPT_MANAGER, "현재 진행 상황 보여줘")
            execute_and_show(conn, sql, show_result=True)
        
        # AI 최적화 제안
        elif '최적' in user_input:
            print(Fore.MAGENTA + "\n🤖 [AI 작업대 최적화 제안]")
            # 각 섹션별 현재 로드 조회
            cursor.execute("""
                SELECT 
                    WS.section_id, 
                    WS.description,
                    COUNT(CASE WHEN KTQ.status='IN_PROGRESS' THEN 1 END) as 진행중,
                    COUNT(CASE WHEN KTQ.status='QUEUED' THEN 1 END) as 대기중
                FROM WorkstationSections WS
                LEFT JOIN KitchenTaskQueue KTQ ON KTQ.assigned_section_id = WS.section_id AND KTQ.status IN ('QUEUED', 'IN_PROGRESS')
                GROUP BY WS.section_id
                ORDER BY WS.section_id
            """)
            ws_status = cursor.fetchall()
            if ws_status:
                print(tabulate(ws_status, headers=["섹션ID", "섹션명", "진행중", "대기중"], tablefmt="simple"))
                
                # AI에게 최적화 제안 요청
                status_text = "\n".join([f"{row[1]}: 진행중 {row[2]}개, 대기중 {row[3]}개" for row in ws_status])
                ai_suggestion = ask_gemini(PROMPT_MANAGER_OPTIMIZE, status_text)
                print(Fore.YELLOW + f"\n💡 제안:\n{ai_suggestion[:500]}")
        
        # 기타 명령
        else:
            sql = ask_gemini(PROMPT_MANAGER, user_input)
            execute_and_show(conn, sql)

def mode_user(conn):
    print(Fore.GREEN + "\n🙋 [User 모드] 주문 키오스크")
    print("메뉴 보기 → 선택 → 주문 완료 → ETA 확인")
    
    while True:
        user_input = input("\nCustomer Input (메뉴/order/상태 확인/exit) > ").strip()
        if user_input == 'exit': 
            break
        
        # 메뉴 보기
        if '메뉴' in user_input or '상품' in user_input:
            cursor = conn.cursor()
            cursor.execute("SELECT menu_item_id, name, price FROM MenuItems")
            results = cursor.fetchall()
            if results:
                print(Fore.GREEN + "\n[현재 판매중인 메뉴]")
                print(tabulate(results, headers=["Menu ID", "메뉴명", "가격"], tablefmt="fancy_grid"))
            else:
                print(Fore.YELLOW + "등록된 메뉴가 없습니다.")
            continue
        
        # 주문하기 (예: "싸이버거 1개" 또는 "1번 1개")
        if '개' in user_input or '주문' in user_input:
            sql = ask_gemini(PROMPT_USER_ORDER, user_input)
            execute_and_show(conn, sql)
            
            # 주문 완료 후 예상 시간 표시
            cursor = conn.cursor()
            cursor.execute("""
                SELECT o.order_number, o.status, 
                       IFNULL(SUM(t.base_time_seconds), 0) as remaining_seconds,
                       datetime('now', 'localtime', '+' || printf('%d', IFNULL(SUM(t.base_time_seconds), 0)/60) || ' minutes') as estimated_pickup_time
                FROM CustomerOrders o
                LEFT JOIN OrderItems oi ON o.order_id = oi.order_id
                LEFT JOIN KitchenTaskQueue q ON oi.order_item_id = q.order_item_id AND q.status != 'COMPLETED'
                LEFT JOIN MenuTasks t ON q.task_definition_id = t.task_definition_id
                WHERE o.order_id = (SELECT MAX(order_id) FROM CustomerOrders)
                GROUP BY o.order_id
            """)
            result = cursor.fetchone()
            if result:
                order_num, status, remaining_sec, pickup_time = result
                minutes = remaining_sec // 60
                seconds = remaining_sec % 60
                print(Fore.CYAN + f"\n✅ 주문 완료!")
                print(f"   주문번호: {order_num}")
                print(f"   예상 시간: {minutes}분 {seconds}초")
                print(f"   수령 예정: {pickup_time}")
            continue
        
        # 주문 상태 확인
        if '상태' in user_input or 'ORD-' in user_input:
            sql = ask_gemini(PROMPT_USER_STATUS, user_input)
            execute_and_show(conn, sql, show_result=True)
            continue
        
        # 기타 요청은 일반 User 프롬프트로
        sql = ask_gemini(PROMPT_USER, user_input)
        execute_and_show(conn, sql, show_result=True)

# ==========================================
# [메인 진입점]
# ==========================================
def main():
    conn = init_db()
    
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(Fore.MAGENTA + Style.BRIGHT + "="*50)
        print("🍔 MOM'S TOUCH AI DATABASE SIMULATION 🍔")
        print("="*50)
        print("1. 🔧 DBA (메뉴/레시피 등록)")
        print("2. 👔 Manager (주문 접수/관리)")
        print("3. 🙋 User (주문 조회)")
        print("0. ❌ 종료")
        
        choice = input(Fore.WHITE + "\n모드를 선택하세요 > ")
        
        if choice == '1': mode_dba(conn)
        elif choice == '2': mode_manager(conn)
        elif choice == '3': mode_user(conn)
        elif choice == '0': 
            conn.close()
            print("시스템 종료.")
            break
        else:
            print("잘못된 입력입니다.")
            time.sleep(1)

if __name__ == "__main__":
    main()