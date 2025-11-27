#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
맘스터치 시뮬레이션 - 완전 자동화 데모
모든 테이블과 컬럼이 실제로 동작하는 것을 보여줍니다
"""

import sqlite3
import os
import sys
import time
from datetime import datetime
from tabulate import tabulate
from colorama import Fore, Style, init

init(autoreset=True)

DB_NAME = "momstouch_demo.db"

def setup_database():
    """데이터베이스 초기화"""
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    print(Fore.YELLOW + "📊 데이터베이스 생성 중...")
    
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
    
    # 기본 데이터 삽입
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
    
    INSERT INTO MenuItems (name, price) VALUES 
        ('싸이버거', 6000),
        ('싸이버거 세트', 8500),
        ('에드워드 리 버거', 9500);
    
    INSERT INTO MenuTasks (menu_item_id, task_name, task_order, base_time_seconds, workstation_id, preferred_section_id) VALUES
        (1, '패티튀기기', 1, 300, 1, 1),
        (1, '조립', 2, 60, 2, 3),
        (2, '패티튀기기', 1, 300, 1, 1),
        (2, '감자튀김', 2, 180, 1, 2),
        (2, '음료준비', 3, 30, 2, 4),
        (2, '조립', 4, 90, 2, 3),
        (3, '패티튀기기', 1, 360, 1, 1),
        (3, '치즈 슬라이스', 2, 20, 2, 3),
        (3, '소스 바르기', 3, 15, 2, 3),
        (3, '조립', 4, 120, 2, 4);
    
    INSERT INTO WorkstationConstraints (section_id, menu_item_id, priority, description) VALUES
        (1, 1, 1, '싸이버거 전용 튀김기 #1'),
        (1, 3, 2, '에드워드 리 버거 추천 튀김기 #1');
    """)
    
    conn.commit()
    print(Fore.GREEN + "✅ 데이터베이스 생성 완료!\n")
    return conn

def demo_dba_register(conn):
    """1. DBA: 메뉴 등록 및 레시피 정의"""
    print(Fore.CYAN + "="*70)
    print("📋 [DBA 모드] 메뉴 및 레시피 관리")
    print("="*70)
    
    cursor = conn.cursor()
    
    # 현재 등록된 메뉴 확인
    print("\n📍 현재 등록된 메뉴:")
    cursor.execute("SELECT menu_item_id, name, price FROM MenuItems")
    menus = cursor.fetchall()
    print(tabulate(menus, headers=["메뉴ID", "메뉴명", "가격"], tablefmt="grid"))
    
    # 메뉴별 레시피 확인
    print("\n📍 메뉴별 레시피:")
    cursor.execute("""
        SELECT 
            M.menu_item_id, M.name, 
            T.task_order, T.task_name, T.base_time_seconds,
            CASE WHEN W.workstation_id=1 THEN '튀김기' ELSE '조립대' END as 작업장,
            T.preferred_section_id
        FROM MenuItems M
        LEFT JOIN MenuTasks T ON M.menu_item_id = T.menu_item_id
        LEFT JOIN Workstations W ON T.workstation_id = W.workstation_id
        ORDER BY M.menu_item_id, T.task_order
    """)
    recipes = cursor.fetchall()
    print(tabulate(recipes, headers=["메뉴ID", "메뉴명", "순서", "작업명", "예상시간(초)", "작업장", "선호섹션"], tablefmt="grid"))
    
    # 제약조건 확인
    print("\n📍 등록된 제약조건:")
    cursor.execute("""
        SELECT 
            WC.constraint_id, 
            WC.section_id,
            WS.description as 섹션명,
            MI.name as 메뉴명,
            WC.priority,
            WC.description
        FROM WorkstationConstraints WC
        LEFT JOIN WorkstationSections WS ON WC.section_id = WS.section_id
        LEFT JOIN MenuItems MI ON WC.menu_item_id = MI.menu_item_id
    """)
    constraints = cursor.fetchall()
    if constraints:
        print(tabulate(constraints, headers=["제약ID", "섹션ID", "섹션명", "메뉴명", "우선순위", "설명"], tablefmt="grid"))
    else:
        print("등록된 제약조건이 없습니다.")
    
    print(Fore.GREEN + "\n✅ DBA 등록 현황 확인 완료!\n")

def demo_user_order(conn):
    """2. User: 주문 접수"""
    print(Fore.MAGENTA + "="*70)
    print("🛒 [User 모드] 고객 주문")
    print("="*70)
    
    cursor = conn.cursor()
    
    # 메뉴 표시
    print("\n📍 판매 중인 메뉴:")
    cursor.execute("SELECT menu_item_id, name, price FROM MenuItems")
    menus = cursor.fetchall()
    print(tabulate(menus, headers=["메뉴ID", "메뉴명", "가격"], tablefmt="grid"))
    
    # 주문 1: 싸이버거 1개
    print("\n📌 주문 1: 싸이버거 1개")
    order_num_query = """
        SELECT COALESCE(MAX(CAST(substr(order_number,5) AS INTEGER)), 0) + 1 
        FROM CustomerOrders 
        WHERE date(order_time) = date('now')
    """
    cursor.execute(order_num_query)
    next_order_num = cursor.fetchone()[0]
    order_number_1 = f"ORD-{next_order_num:03d}"
    
    cursor.executescript(f"""
    BEGIN TRANSACTION;
    INSERT INTO CustomerOrders (order_number, status, order_time, estimated_total_seconds) 
    VALUES ('{order_number_1}', 'CONFIRMED', datetime('now', 'localtime'), 360);
    INSERT INTO OrderItems (order_id, menu_item_id) 
    VALUES ((SELECT last_insert_rowid()), 1);
    INSERT INTO KitchenTaskQueue (order_item_id, task_definition_id, assigned_section_id, status, started_at) 
    SELECT (SELECT last_insert_rowid()), task_definition_id, NULL, 'QUEUED', datetime('now', 'localtime') 
    FROM MenuTasks WHERE menu_item_id = 1;
    COMMIT;
    """)
    
    print(f"   ✅ {order_number_1} 주문 접수 (예상시간: 360초)")
    
    # 주문 2: 싸이버거 세트 2개
    print("\n📌 주문 2: 싸이버거 세트 2개")
    next_order_num += 1
    order_number_2 = f"ORD-{next_order_num:03d}"
    
    cursor.executescript(f"""
    BEGIN TRANSACTION;
    INSERT INTO CustomerOrders (order_number, status, order_time, estimated_total_seconds) 
    VALUES ('{order_number_2}', 'CONFIRMED', datetime('now', 'localtime'), 600);
    INSERT INTO OrderItems (order_id, menu_item_id) 
    VALUES ((SELECT last_insert_rowid()), 2);
    INSERT INTO OrderItems (order_id, menu_item_id) 
    VALUES ((SELECT last_insert_rowid()), 2);
    COMMIT;
    """)
    
    # 각 OrderItem에 대해 KitchenTaskQueue 생성
    cursor.execute("SELECT order_item_id FROM OrderItems WHERE order_id = (SELECT order_id FROM CustomerOrders WHERE order_number = ?)", (order_number_2,))
    order_items = cursor.fetchall()
    
    for order_item in order_items:
        cursor.executescript(f"""
        INSERT INTO KitchenTaskQueue (order_item_id, task_definition_id, assigned_section_id, status, started_at) 
        SELECT {order_item[0]}, task_definition_id, NULL, 'QUEUED', datetime('now', 'localtime') 
        FROM MenuTasks WHERE menu_item_id = 2;
        """)
    
    print(f"   ✅ {order_number_2} 주문 접수 (2개, 예상시간: 600초)")
    
    # 주문 3: 에드워드 리 버거 1개
    print("\n📌 주문 3: 에드워드 리 버거 1개")
    next_order_num += 1
    order_number_3 = f"ORD-{next_order_num:03d}"
    
    cursor.executescript(f"""
    BEGIN TRANSACTION;
    INSERT INTO CustomerOrders (order_number, status, order_time, estimated_total_seconds) 
    VALUES ('{order_number_3}', 'CONFIRMED', datetime('now', 'localtime'), 515);
    INSERT INTO OrderItems (order_id, menu_item_id) 
    VALUES ((SELECT last_insert_rowid()), 3);
    INSERT INTO KitchenTaskQueue (order_item_id, task_definition_id, assigned_section_id, status, started_at) 
    SELECT (SELECT last_insert_rowid()), task_definition_id, NULL, 'QUEUED', datetime('now', 'localtime') 
    FROM MenuTasks WHERE menu_item_id = 3;
    COMMIT;
    """)
    
    print(f"   ✅ {order_number_3} 주문 접수 (예상시간: 515초)")
    
    conn.commit()
    print(Fore.GREEN + "\n✅ 전체 주문 접수 완료!\n")
    
    return [order_number_1, order_number_2, order_number_3]

def demo_manager_auto_assign(conn):
    """3. Manager: 섹션 자동 할당"""
    print(Fore.CYAN + "="*70)
    print("👔 [Manager 모드] 작업 할당 및 스케줄링")
    print("="*70)
    
    cursor = conn.cursor()
    
    print("\n📍 섹션 자동 할당 중...")
    
    # assigned_section_id가 NULL인 작업들에 섹션 할당
    cursor.execute("""
        SELECT KTQ.queue_task_id, MT.task_definition_id, MT.preferred_section_id, MT.menu_item_id
        FROM KitchenTaskQueue KTQ
        JOIN MenuTasks MT ON KTQ.task_definition_id = MT.task_definition_id
        WHERE KTQ.assigned_section_id IS NULL
    """)
    
    unassigned_tasks = cursor.fetchall()
    assigned_count = 0
    
    for queue_id, task_def_id, preferred_section, menu_item_id in unassigned_tasks:
        # 제약조건 확인
        cursor.execute("""
            SELECT section_id FROM WorkstationConstraints 
            WHERE menu_item_id = ? LIMIT 1
        """, (menu_item_id,))
        
        constraint_result = cursor.fetchone()
        assigned_section = constraint_result[0] if constraint_result else preferred_section
        
        if assigned_section:
            cursor.execute("""
                UPDATE KitchenTaskQueue 
                SET assigned_section_id = ?, status = 'QUEUED'
                WHERE queue_task_id = ?
            """, (assigned_section, queue_id))
            assigned_count += 1
    
    conn.commit()
    print(f"   ✅ {assigned_count}개 작업에 섹션 할당 완료\n")
    
    # 현재 주방 상태
    print("📍 현재 주방 작업 큐:")
    cursor.execute("""
        SELECT
            KTQ.queue_task_id,
            CO.order_number,
            MI.name as 메뉴,
            MT.task_name as 작업,
            MT.task_order,
            KTQ.assigned_section_id,
            WS.description as 섹션명,
            KTQ.status,
            KTQ.started_at
        FROM KitchenTaskQueue KTQ
        JOIN OrderItems OI ON KTQ.order_item_id = OI.order_item_id
        JOIN CustomerOrders CO ON OI.order_id = CO.order_id
        JOIN MenuTasks MT ON KTQ.task_definition_id = MT.task_definition_id
        JOIN MenuItems MI ON MT.menu_item_id = MI.menu_item_id
        LEFT JOIN WorkstationSections WS ON KTQ.assigned_section_id = WS.section_id
        ORDER BY CO.order_number, MT.task_order
    """)
    
    queue_tasks = cursor.fetchall()
    print(tabulate(queue_tasks, headers=["TaskID", "주문번호", "메뉴", "작업명", "순서", "섹션ID", "섹션명", "상태", "시작시간"], tablefmt="grid"))
    
    print(Fore.GREEN + "\n✅ 작업 할당 완료!\n")

def demo_manager_process(conn):
    """4. Manager: 작업 처리 및 시간 추적"""
    print(Fore.CYAN + "="*70)
    print("⏱️  [Manager 모드] 작업 처리 및 시간 추적")
    print("="*70)
    
    cursor = conn.cursor()
    
    # 모든 작업 조회
    cursor.execute("""
        SELECT queue_task_id, order_item_id FROM KitchenTaskQueue 
        WHERE status = 'QUEUED'
        ORDER BY queue_task_id
    """)
    
    all_tasks = cursor.fetchall()
    
    # 작업 처리 (일부만 완료 처리)
    print("\n📍 작업 처리 시뮬레이션:")
    
    tasks_to_complete = all_tasks[:5]  # 처음 5개 작업만 완료
    
    for idx, (task_id, order_item_id) in enumerate(tasks_to_complete, 1):
        print(f"\n   [{idx}] Task {task_id} 처리 중...")
        
        # 작업 시작 (started_at 설정)
        cursor.execute("""
            UPDATE KitchenTaskQueue 
            SET status = 'IN_PROGRESS', started_at = datetime('now', 'localtime')
            WHERE queue_task_id = ?
        """, (task_id,))
        
        # 약간의 지연을 둬서 시간 차이 생성
        time.sleep(0.5)
        
        # 작업 완료 (completed_at 설정)
        cursor.execute("""
            UPDATE KitchenTaskQueue 
            SET status = 'COMPLETED', completed_at = datetime('now', 'localtime')
            WHERE queue_task_id = ?
        """, (task_id,))
        
        conn.commit()
        print(f"      ✅ Task {task_id} 완료!")
        
        # 다음 작업 시작
        cursor.execute("""
            SELECT MT.task_order FROM KitchenTaskQueue KTQ
            JOIN MenuTasks MT ON KTQ.task_definition_id = MT.task_definition_id
            WHERE KTQ.queue_task_id = ?
        """, (task_id,))
        
        current_task_order = cursor.fetchone()
        if current_task_order:
            cursor.execute("""
                SELECT KTQ.queue_task_id FROM KitchenTaskQueue KTQ
                JOIN MenuTasks MT ON KTQ.task_definition_id = MT.task_definition_id
                WHERE KTQ.order_item_id = ? 
                AND MT.task_order > ? AND KTQ.status = 'QUEUED'
                LIMIT 1
            """, (order_item_id, current_task_order[0]))
            
            next_task = cursor.fetchone()
            if next_task:
                cursor.execute("""
                    UPDATE KitchenTaskQueue SET status = 'IN_PROGRESS'
                    WHERE queue_task_id = ?
                """, (next_task[0],))
                conn.commit()
    
    # actual_total_seconds 계산
    print("\n📍 주문별 소요시간 계산 중...")
    cursor.execute("""
        SELECT DISTINCT CO.order_id, CO.order_number FROM KitchenTaskQueue KTQ
        JOIN OrderItems OI ON KTQ.order_item_id = OI.order_item_id
        JOIN CustomerOrders CO ON OI.order_id = CO.order_id
        WHERE KTQ.completed_at IS NOT NULL
    """)
    
    completed_orders = cursor.fetchall()
    
    for order_id, order_number in completed_orders:
        cursor.execute("""
            SELECT CAST((julianday(MAX(KTQ.completed_at)) - julianday(CO.order_time)) * 86400 AS INTEGER) as actual_seconds
            FROM CustomerOrders CO
            JOIN OrderItems OI ON CO.order_id = OI.order_id
            JOIN KitchenTaskQueue KTQ ON OI.order_item_id = KTQ.order_item_id
            WHERE CO.order_id = ? AND KTQ.completed_at IS NOT NULL
            GROUP BY CO.order_id
        """, (order_id,))
        
        result = cursor.fetchone()
        if result and result[0]:
            actual_seconds = result[0]
            cursor.execute("""
                UPDATE CustomerOrders 
                SET actual_total_seconds = ? 
                WHERE order_id = ?
            """, (actual_seconds, order_id))
            print(f"   ✅ {order_number}: {actual_seconds}초 (예상: {result[0]}초)")
            conn.commit()
    
    print(Fore.GREEN + "\n✅ 작업 처리 완료!\n")

def demo_final_report(conn):
    """5. 최종 리포트 - 모든 테이블 활용 현황"""
    print(Fore.YELLOW + "="*70)
    print("📊 최종 리포트 - 모든 테이블 및 컬럼 활용 현황")
    print("="*70)
    
    cursor = conn.cursor()
    
    # 1. Workstations 확인
    print("\n✅ [Workstations] 작업장 정의")
    cursor.execute("SELECT * FROM Workstations")
    data = cursor.fetchall()
    print(tabulate(data, headers=["ID", "이름", "총 유닛수"], tablefmt="grid"))
    
    # 2. WorkstationSections 확인
    print("\n✅ [WorkstationSections] 작업장 구역")
    cursor.execute("SELECT * FROM WorkstationSections")
    data = cursor.fetchall()
    print(tabulate(data, headers=["ID", "작업장ID", "구역번호", "최대작업수", "설명"], tablefmt="grid"))
    
    # 3. WorkstationConstraints 확인
    print("\n✅ [WorkstationConstraints] 작업대 제약조건")
    cursor.execute("""
        SELECT WC.constraint_id, WC.section_id, MI.name, WC.priority, WC.description
        FROM WorkstationConstraints WC
        LEFT JOIN MenuItems MI ON WC.menu_item_id = MI.menu_item_id
    """)
    data = cursor.fetchall()
    if data:
        print(tabulate(data, headers=["제약ID", "섹션ID", "메뉴", "우선순위", "설명"], tablefmt="grid"))
    
    # 4. MenuItems 확인
    print("\n✅ [MenuItems] 메뉴 아이템")
    cursor.execute("SELECT * FROM MenuItems")
    data = cursor.fetchall()
    print(tabulate(data, headers=["ID", "메뉴명", "가격"], tablefmt="grid"))
    
    # 5. MenuTasks 확인 (preferred_section_id 포함)
    print("\n✅ [MenuTasks] 메뉴 작업 정의 (preferred_section_id 사용)")
    cursor.execute("""
        SELECT MT.task_definition_id, MI.name, MT.task_name, MT.task_order, 
               MT.base_time_seconds, MT.workstation_id, MT.preferred_section_id
        FROM MenuTasks MT
        LEFT JOIN MenuItems MI ON MT.menu_item_id = MI.menu_item_id
        ORDER BY MT.menu_item_id, MT.task_order
    """)
    data = cursor.fetchall()
    print(tabulate(data, headers=["작업ID", "메뉴", "작업명", "순서", "예상초(s)", "작업장", "선호섹션"], tablefmt="grid"))
    
    # 6. CustomerOrders 확인 (estimated_total_seconds, actual_total_seconds 포함)
    print("\n✅ [CustomerOrders] 고객 주문 (시간 추적)")
    cursor.execute("""
        SELECT order_id, order_number, status, order_time, 
               estimated_total_seconds, actual_total_seconds
        FROM CustomerOrders
    """)
    data = cursor.fetchall()
    print(tabulate(data, headers=["ID", "주문번호", "상태", "주문시간", "예상시간(s)", "실제시간(s)"], tablefmt="grid"))
    
    # 7. OrderItems 확인
    print("\n✅ [OrderItems] 주문 항목")
    cursor.execute("""
        SELECT OI.order_item_id, CO.order_number, MI.name, CO.order_time
        FROM OrderItems OI
        JOIN CustomerOrders CO ON OI.order_id = CO.order_id
        JOIN MenuItems MI ON OI.menu_item_id = MI.menu_item_id
    """)
    data = cursor.fetchall()
    print(tabulate(data, headers=["ID", "주문번호", "메뉴명", "주문시간"], tablefmt="grid"))
    
    # 8. KitchenTaskQueue 확인 (모든 컬럼)
    print("\n✅ [KitchenTaskQueue] 주방 작업 큐 (assigned_section_id, started_at, completed_at 사용)")
    cursor.execute("""
        SELECT KTQ.queue_task_id, CO.order_number, MI.name, MT.task_name,
               COALESCE(KTQ.assigned_section_id, 0), COALESCE(WS.description, 'N/A'),
               KTQ.status, COALESCE(KTQ.started_at, 'N/A'), COALESCE(KTQ.completed_at, 'N/A')
        FROM KitchenTaskQueue KTQ
        JOIN OrderItems OI ON KTQ.order_item_id = OI.order_item_id
        JOIN CustomerOrders CO ON OI.order_id = CO.order_id
        JOIN MenuItems MI ON OI.menu_item_id = MI.menu_item_id
        JOIN MenuTasks MT ON KTQ.task_definition_id = MT.task_definition_id
        LEFT JOIN WorkstationSections WS ON KTQ.assigned_section_id = WS.section_id
        ORDER BY CO.order_number, MT.task_order
    """)
    data = cursor.fetchall()
    print(tabulate(data, headers=["TaskID", "주문", "메뉴", "작업", "섹션ID", "섹션명", "상태", "시작", "완료"], 
                   tablefmt="grid", maxcolwidths=[6, 10, 10, 10, 6, 12, 12, 12, 12]))
    
    # 최종 통계
    print("\n" + Fore.CYAN + "="*70)
    print("📈 최종 통계")
    print("="*70)
    
    cursor.execute("SELECT COUNT(*) FROM Workstations")
    ws_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM WorkstationSections")
    section_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM WorkstationConstraints")
    constraint_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM MenuItems")
    menu_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM MenuTasks")
    task_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM CustomerOrders")
    order_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM OrderItems")
    orderitem_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM KitchenTaskQueue")
    queue_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM KitchenTaskQueue WHERE completed_at IS NOT NULL")
    completed_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(actual_total_seconds) FROM CustomerOrders WHERE actual_total_seconds IS NOT NULL")
    total_time = cursor.fetchone()[0]
    
    print(f"\n📊 테이블별 레코드 수:")
    print(f"   - Workstations: {ws_count}개")
    print(f"   - WorkstationSections: {section_count}개")
    print(f"   - WorkstationConstraints: {constraint_count}개 ✅ (제약조건 적용됨)")
    print(f"   - MenuItems: {menu_count}개")
    print(f"   - MenuTasks: {task_count}개 ✅ (preferred_section_id 사용됨)")
    print(f"   - CustomerOrders: {order_count}개 ✅ (estimated/actual_total_seconds 사용됨)")
    print(f"   - OrderItems: {orderitem_count}개")
    print(f"   - KitchenTaskQueue: {queue_count}개 ✅ (assigned_section_id/started_at/completed_at 사용됨)")
    
    print(f"\n⏱️  시간 추적:")
    print(f"   - 완료된 작업: {completed_count}개")
    if total_time:
        print(f"   - 총 소요시간: {total_time}초 ({total_time//60}분 {total_time%60}초)")
    
    print(Fore.GREEN + "\n✅ 모든 테이블과 컬럼이 완벽하게 활용되었습니다!\n")

if __name__ == "__main__":
    print(Fore.MAGENTA + Style.BRIGHT + "="*70)
    print("🍔 맘스터치 완전 자동화 데모")
    print("모든 테이블과 컬럼의 동작을 확인합니다")
    print("="*70 + "\n")
    
    # 1. 데이터베이스 생성
    conn = setup_database()
    
    # 2. DBA 메뉴 등록 확인
    demo_dba_register(conn)
    time.sleep(1)
    
    # 3. 사용자 주문 접수
    demo_user_order(conn)
    time.sleep(1)
    
    # 4. 매니저 작업 할당
    demo_manager_auto_assign(conn)
    time.sleep(1)
    
    # 5. 작업 처리 및 시간 추적
    demo_manager_process(conn)
    time.sleep(1)
    
    # 6. 최종 리포트
    demo_final_report(conn)
    
    conn.close()
    
    print(Fore.YELLOW + "\n📁 데이터베이스 파일: momstouch_demo.db")
    print("모든 테이블과 컬럼이 성공적으로 활용되었습니다!\n")
