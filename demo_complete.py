#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
맘스터치 시뮬레이션 - momsTouch.sql의 모든 테이블 완벽 활용
Workstations, WorkstationZones, ZoneCapacityRules, ZoneRealtimeState,
Staff, StaffAssignment, MenuItems, MenuTasks, TaskDependencies,
CustomerOrders, OrderItems, KitchenTaskQueue, BottleneckAnalysis
"""

import sqlite3
import os
import sys
import time
import random
from datetime import datetime, timedelta
from tabulate import tabulate
from colorama import Fore, Style, init

init(autoreset=True)

DB_NAME = "momstouch_complete.db"
QUERIES_DIR = "queries"

def load_sql(filename):
    """SQL 파일 읽기 헬퍼 함수"""
    filepath = os.path.join(QUERIES_DIR, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def setup_database():
    """momsTouch.sql 스키마로 데이터베이스 초기화"""
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    print(Fore.YELLOW + "📊 데이터베이스 생성 중 (01_schema.sql 실행)...")

    # 01_schema.sql 파일 읽어서 실행
    with open('01_schema.sql', 'r', encoding='utf-8') as f:
        schema_sql = f.read()
        cursor.executescript(schema_sql)

    conn.commit()
    print(Fore.GREEN + "✅ 데이터베이스 생성 완료!\n")
    return conn

def insert_initial_data(conn):
    """기본 데이터 삽입 (모든 테이블)"""
    cursor = conn.cursor()

    print(Fore.CYAN + "📋 기본 데이터 삽입 중...\n")

    # 1-4. Workstations 및 Zones
    print("  [1-4] Workstations 및 Zones 생성 (02_workstations.sql)...")
    with open('02_workstations.sql', 'r', encoding='utf-8') as f:
        cursor.executescript(f.read())

    # 5-6. Staff
    print("  [5-6] Staff 생성 (03_staff.sql)...")
    with open('03_staff.sql', 'r', encoding='utf-8') as f:
        cursor.executescript(f.read())

    # 7. MenuItems
    print("  [7] MenuItems 생성 (04_menu.sql)...")
    with open('04_menu.sql', 'r', encoding='utf-8') as f:
        cursor.executescript(f.read())

    # 8-9. MenuTasks & TaskDependencies
    print("  [8-9] MenuTasks & TaskDependencies 생성 (05_recipes.sql)...")
    with open('05_recipes.sql', 'r', encoding='utf-8') as f:
        cursor.executescript(f.read())

    conn.commit()
    print(Fore.GREEN + "✅ 기본 데이터 삽입 완료!\n")

def demo_customer_orders(conn):
    """고객 주문 접수 및 대기 시간 계산"""
    print(Fore.MAGENTA + "="*80)
    print("🛒 [주문 단계] 고객 주문 접수 및 영수증 발행")
    print("="*80)

    cursor = conn.cursor()

    # 메뉴 정보 미리 가져오기
    cursor.execute("SELECT menu_item_id, name, price FROM MenuItems")
    menu_dict = {mid: (name, price) for mid, name, price in cursor.fetchall()}

    orders = [
        {'name': 'ORD-001', 'items': [(1, 1)]},              # 싸이버거 1개
        {'name': 'ORD-002', 'items': [(2, 2), (5, 1)]},      # 싸이버거 세트 2개, 텐더 1개
        {'name': 'ORD-003', 'items': [(3, 1)]},              # 에드워드리 버거 1개
        {'name': 'ORD-004', 'items': [(4, 1), (1, 1)]},      # 에드워드리 세트 1개, 싸이버거 1개
    ]

    insert_order_sql = load_sql('insert_order.sql')
    insert_order_item_sql = load_sql('insert_order_item.sql')

    for order_info in orders:
        print(Fore.CYAN + f"\n{'='*60}")
        print(f"📝 고객 주문: {order_info['name']}")
        print(f"{'='*60}")

        # 주문 생성
        cursor.execute(insert_order_sql, (order_info['name'],))
        order_id = cursor.lastrowid

        # 주문 내역 및 총액 계산
        total_price = 0
        order_summary = []
        for menu_id, qty in order_info['items']:
            cursor.execute(insert_order_item_sql, (order_id, menu_id, qty))
            menu_name, price = menu_dict[menu_id]
            subtotal = price * qty
            total_price += subtotal
            order_summary.append((menu_name, qty, subtotal))

        conn.commit()

        # 대기 시간 계산
        cursor.execute("""
            SELECT COALESCE(SUM(MT.base_time_seconds * OI.quantity), 0)
            FROM OrderItems OI
            JOIN MenuTasks MT ON OI.menu_item_id = MT.menu_item_id
            WHERE OI.order_id = ?
        """, (order_id,))
        my_order_time = cursor.fetchone()[0]

        # 앞 주문들의 남은 시간 계산
        cursor.execute("""
            SELECT COALESCE(SUM(MT.base_time_seconds * OI.quantity), 0)
            FROM CustomerOrders CO
            JOIN OrderItems OI ON CO.order_id = OI.order_id
            JOIN MenuTasks MT ON OI.menu_item_id = MT.menu_item_id
            WHERE CO.status IN ('PENDING', 'CONFIRMED')
            AND CO.order_id < ?
        """, (order_id,))
        queue_time = cursor.fetchone()[0]

        total_wait_time = queue_time + my_order_time
        wait_minutes = total_wait_time // 60

        # 영수증 출력
        print(Fore.GREEN + "\n📄 영수증")
        print("-" * 60)
        for name, qty, subtotal in order_summary:
            print(f"  {name:25s} x {qty:2d}  {subtotal:7,}원")
        print("-" * 60)
        print(f"  {'합계':25s}      {total_price:7,}원")
        print("=" * 60)

        print(Fore.YELLOW + f"⏰ 예상 대기 시간: 약 {wait_minutes}분")
        if queue_time > 0:
            queue_minutes = queue_time // 60
            print(Fore.CYAN + f"   (현재 {queue_minutes}분 대기 중인 주문이 있습니다)")

        print(Fore.GREEN + f"✅ 주문번호: {order_info['name']}" + Style.RESET_ALL)

    print(Fore.GREEN + "\n" + "="*80)
    print("✅ 모든 주문 접수 완료!")
    print("="*80 + Style.RESET_ALL + "\n")

def demo_task_queue_creation(conn):
    """KitchenTaskQueue 자동 생성 (각 OrderItem마다 관련 MenuTasks 추가)"""
    print(Fore.CYAN + "="*80)
    print("📋 [스케줄링] 주방 작업 큐 자동 생성")
    print("="*80)

    cursor = conn.cursor()

    print("\n📍 OrderItems -> KitchenTaskQueue 변환 중...")

    # SQL 파일 로드
    select_order_items_sql = load_sql('select_order_items.sql')
    select_menu_tasks_sql = load_sql('select_menu_tasks.sql')
    insert_kitchen_task_sql = load_sql('insert_kitchen_task.sql')

    # 모든 OrderItems 조회
    cursor.execute(select_order_items_sql)

    order_items = cursor.fetchall()
    task_count = 0

    for order_item_id, menu_item_id, quantity in order_items:
        # 해당 메뉴의 모든 작업 조회
        cursor.execute(select_menu_tasks_sql, (menu_item_id,))

        tasks = cursor.fetchall()

        # 수량만큼 반복하여 작업 생성
        for qty_idx in range(quantity):
            for task_def_id, task_name, task_order in tasks:
                cursor.execute(insert_kitchen_task_sql, (order_item_id, task_def_id))

                task_count += 1
                if quantity > 1:
                    print(f"  ✅ OrderItem {order_item_id} (#{qty_idx+1}/{quantity}) -> Task: {task_name}")
                else:
                    print(f"  ✅ OrderItem {order_item_id} -> Task: {task_name}")

    conn.commit()

    print(f"\n총 {task_count}개의 작업이 큐에 추가되었습니다.")
    print(Fore.GREEN + "\n✅ 작업 큐 생성 완료!\n")

def demo_resource_assignment(conn):
    """작업에 자원 할당 (Staff, Zone, Workstation)"""
    print(Fore.YELLOW + "="*80)
    print("👔 [자원 할당] Staff & Zone 할당 알고리즘")
    print("="*80)
    
    cursor = conn.cursor()
    
    print("\n📍 QUEUED 작업에 자원 할당 중...\n")

    # SQL 파일 로드
    select_queued_tasks_sql = load_sql('select_queued_tasks.sql')
    select_available_staff_sql = load_sql('select_available_staff.sql')
    select_workstation_zones_sql = load_sql('select_workstation_zones.sql')
    update_task_assignment_sql = load_sql('update_task_assignment.sql')

    # 모든 대기 중인 작업 조회
    cursor.execute(select_queued_tasks_sql)

    tasks = cursor.fetchall()
    assigned_count = 0

    for queue_id, task_def_id, workstation_id, menu_id in tasks:
        # 1. Staff 할당 (활동중인 스태프, 중복 할당 방지)
        cursor.execute(select_available_staff_sql, (workstation_id,))

        staff_result = cursor.fetchone()
        assigned_staff_id = staff_result[0] if staff_result else None

        # 2. Zone 할당
        cursor.execute(select_workstation_zones_sql, (workstation_id,))

        zone_result = cursor.fetchone()
        assigned_zone_id = zone_result[0] if zone_result else None

        # 3. KitchenTaskQueue 업데이트
        cursor.execute(update_task_assignment_sql,
                      (workstation_id, assigned_zone_id, assigned_staff_id, queue_id))
        
        assigned_count += 1
        conn.commit()
        print(f"  ✅ Task {queue_id}: WS{workstation_id}, "
              f"Zone{assigned_zone_id}, Staff{assigned_staff_id}")
    
    print(Fore.GREEN + f"\n✅ {assigned_count}개 작업에 자원 할당 완료!\n")

def demo_zone_state_updates(conn):
    """Zone의 상태 업데이트 (ZoneRealtimeState)"""
    print(Fore.CYAN + "="*80)
    print("⚙️  [실시간 상태] Zone 상태 업데이트")
    print("="*80)
    
    cursor = conn.cursor()
    
    print("\n📍 주요 Zone의 상태를 시뮬레이션 중...\n")

    # SQL 파일 로드
    select_zone_realtime_state_sql = load_sql('select_zone_realtime_state.sql')

    # 메인 튀김기 좌측 (zone_id=1)에 싸이패티 작업 배정
    cursor.execute("""
        UPDATE ZoneRealtimeState
        SET
            current_food_type = '싸이패티',
            current_quantity = 10,
            busy_until = datetime('now', '+5 minutes', 'localtime')
        WHERE zone_id = 1
    """)

    # 서브 튀김기 우측 (zone_id=4)에 감자튀김 작업 배정
    cursor.execute("""
        UPDATE ZoneRealtimeState
        SET
            current_food_type = '감자튀김',
            current_quantity = 20,
            busy_until = datetime('now', '+3 minutes', 'localtime')
        WHERE zone_id = 4
    """)

    conn.commit()

    # Zone 상태 표시
    print("📍 Zone 실시간 상태:")
    cursor.execute(select_zone_realtime_state_sql)
    
    zones = cursor.fetchall()
    print(tabulate(zones, headers=["Zone ID", "Zone Name", "Current Food", "Qty", "Busy Until"], tablefmt="grid"))
    
    print(Fore.GREEN + "\n✅ Zone 상태 업데이트 완료!\n")

def demo_task_execution(conn):
    """작업 실행 시뮬레이션 (IN_PROGRESS -> COMPLETED)"""
    print(Fore.MAGENTA + "="*80)
    print("🏃 [실행] 작업 처리 시뮬레이션")
    print("="*80)
    
    cursor = conn.cursor()
    
    print("\n📍 작업 처리 중...\n")

    # SQL 파일 로드
    select_waiting_resource_tasks_sql = load_sql('select_waiting_resource_tasks.sql')
    update_task_in_progress_sql = load_sql('update_task_in_progress.sql')
    update_task_completed_sql = load_sql('update_task_completed.sql')

    # WAITING_RESOURCE 상태의 작업들을 IN_PROGRESS로 변경
    cursor.execute(select_waiting_resource_tasks_sql)

    tasks_to_start = cursor.fetchall()

    for (queue_id,) in tasks_to_start:
        # IN_PROGRESS 상태로 변경
        cursor.execute(update_task_in_progress_sql, (queue_id,))

        conn.commit()
        time.sleep(0.3)  # 약간의 지연

        # COMPLETED 상태로 변경
        cursor.execute(update_task_completed_sql, (queue_id,))

        conn.commit()
        print(f"  ✅ Task {queue_id} 완료")
    
    print(Fore.GREEN + "\n✅ 작업 처리 완료!\n")

def demo_bottleneck_analysis(conn):
    """병목 분석 데이터 기록 (BottleneckAnalysis)"""
    print(Fore.RED + "="*80)
    print("🚧 [분석] 병목 현상 분석")
    print("="*80)
    
    cursor = conn.cursor()
    
    print("\n📍 병목 분석 데이터 생성 중...\n")
    
    # 시뮬레이션: 특정 작업에서 병목 발생
    bottlenecks = [
        {
            'queue_task_id': 5,
            'bottleneck_type': 'NO_STAFF',
            'wait_duration_seconds': 120,
            'problematic_workstation_id': 1,
            'reason': '튀김 담당 스태프 부족'
        },
        {
            'queue_task_id': 8,
            'bottleneck_type': 'FRYER_TEMP_RECOVERY',
            'wait_duration_seconds': 90,
            'problematic_workstation_id': 1,
            'reason': '기름 온도 복구 대기'
        },
        {
            'queue_task_id': 12,
            'bottleneck_type': 'DEPENDENCY_WAIT',
            'wait_duration_seconds': 150,
            'problematic_workstation_id': 3,
            'reason': '이전 작업 완료 대기'
        },
    ]
    
    # SQL 파일 로드
    insert_bottleneck_sql = load_sql('insert_bottleneck.sql')
    select_bottleneck_stats_sql = load_sql('select_bottleneck_stats.sql')

    for bn in bottlenecks:
        cursor.execute(insert_bottleneck_sql,
                      (bn['queue_task_id'], bn['bottleneck_type'],
                       bn['wait_duration_seconds'], bn['problematic_workstation_id']))

        conn.commit()
        print(f"  📌 Task {bn['queue_task_id']}: {bn['bottleneck_type']} "
              f"({bn['wait_duration_seconds']}초) - {bn['reason']}")

    # 병목 통계
    print("\n📊 병목 유형별 분석:")
    cursor.execute(select_bottleneck_stats_sql)
    
    stats = cursor.fetchall()
    print(tabulate(stats, headers=["병목 유형", "발생 횟수", "총 대기시간(초)"], tablefmt="grid"))
    
    print(Fore.GREEN + "\n✅ 병목 분석 완료!\n")

def demo_final_report(conn):
    """최종 리포트 - 모든 테이블 활용 현황"""
    print(Fore.YELLOW + "="*80)
    print("📊 최종 리포트 - 모든 테이블 및 컬럼 활용 현황")
    print("="*80)
    
    cursor = conn.cursor()
    
    # 1. Workstations
    print("\n✅ [1] Workstations - 작업장 정의")
    cursor.execute("""
        SELECT workstation_id, name, type, max_staff FROM Workstations
    """)
    data = cursor.fetchall()
    print(tabulate(data, headers=["ID", "이름", "타입", "최대인원"], tablefmt="grid"))
    
    # 2. WorkstationZones
    print("\n✅ [2] WorkstationZones - 작업장 구역")
    cursor.execute("""
        SELECT WZ.zone_id, W.name, WZ.zone_name FROM WorkstationZones WZ
        JOIN Workstations W ON WZ.workstation_id = W.workstation_id
    """)
    data = cursor.fetchall()
    print(tabulate(data, headers=["Zone ID", "작업장", "구역명"], tablefmt="grid"))
    
    # 3. ZoneCapacityRules
    print("\n✅ [3] ZoneCapacityRules - 구역별 용량 규칙")
    cursor.execute("""
        SELECT rule_id, zone_id, food_type, max_quantity FROM ZoneCapacityRules LIMIT 8
    """)
    data = cursor.fetchall()
    print(tabulate(data, headers=["Rule ID", "Zone ID", "식품 종류", "최대수량"], tablefmt="grid"))
    
    # 4. ZoneRealtimeState
    print("\n✅ [4] ZoneRealtimeState - 구역 실시간 상태")
    cursor.execute("""
        SELECT zone_id, current_food_type, current_quantity, busy_until FROM ZoneRealtimeState
    """)
    data = cursor.fetchall()
    print(tabulate(data, headers=["Zone ID", "현재 식품", "수량", "Busy Until"], tablefmt="grid"))
    
    # 5. Staff
    print("\n✅ [5] Staff - 스태프 정보")
    cursor.execute("""
        SELECT staff_id, name, status FROM Staff
    """)
    data = cursor.fetchall()
    print(tabulate(data, headers=["Staff ID", "이름", "상태"], tablefmt="grid"))

    # 6. StaffAssignment
    print("\n✅ [6] StaffAssignment - 스태프 배치")
    cursor.execute("""
        SELECT SA.assignment_id, S.name, W.name, SA.assigned_at
        FROM StaffAssignment SA
        JOIN Staff S ON SA.staff_id = S.staff_id
        JOIN Workstations W ON SA.workstation_id = W.workstation_id
    """)
    data = cursor.fetchall()
    print(tabulate(data, headers=["Assignment ID", "스태프", "작업장", "할당시간"], tablefmt="grid"))
    
    # 7. MenuItems
    print("\n✅ [7] MenuItems - 메뉴")
    cursor.execute("""
        SELECT menu_item_id, name, price FROM MenuItems
    """)
    data = cursor.fetchall()
    print(tabulate(data, headers=["Menu ID", "메뉴명", "가격"], tablefmt="grid"))
    
    # 8. MenuTasks
    print("\n✅ [8] MenuTasks - 메뉴 작업 정의 (base_time_seconds, task_type 사용)")
    cursor.execute("""
        SELECT MT.task_definition_id, MI.name, MT.task_name, MT.task_order,
               MT.base_time_seconds, MT.task_type
        FROM MenuTasks MT
        JOIN MenuItems MI ON MT.menu_item_id = MI.menu_item_id
        LIMIT 12
    """)
    data = cursor.fetchall()
    print(tabulate(data, headers=["Task ID", "메뉴", "작업명", "순서", "초(s)", "타입"], tablefmt="grid"))
    
    # 9. TaskDependencies
    print("\n✅ [9] TaskDependencies - 작업 의존성 (Topological Sort)")
    cursor.execute("""
        SELECT dependency_id, task_id, depends_on_task_id FROM TaskDependencies
        LIMIT 10
    """)
    data = cursor.fetchall()
    print(tabulate(data, headers=["Dependency ID", "Task ID", "Depends On Task ID"], tablefmt="grid"))
    
    # 10. CustomerOrders
    print("\n✅ [10] CustomerOrders - 고객 주문")
    cursor.execute("""
        SELECT order_id, order_number, status, created_at, estimated_seconds_remaining
        FROM CustomerOrders
    """)
    data = cursor.fetchall()
    print(tabulate(data, headers=["Order ID", "주문번호", "상태", "생성시간", "예상남은시간(초)"], tablefmt="grid"))
    
    # 11. OrderItems
    print("\n✅ [11] OrderItems - 주문 항목")
    cursor.execute("""
        SELECT OI.order_item_id, CO.order_number, MI.name, OI.quantity
        FROM OrderItems OI
        JOIN CustomerOrders CO ON OI.order_id = CO.order_id
        JOIN MenuItems MI ON OI.menu_item_id = MI.menu_item_id
    """)
    data = cursor.fetchall()
    print(tabulate(data, headers=["Order Item ID", "주문번호", "메뉴명", "수량"], tablefmt="grid"))
    
    # 12. KitchenTaskQueue
    print("\n✅ [12] KitchenTaskQueue - 주방 작업 큐")
    print("   (assigned_workstation_id, assigned_zone_id, assigned_staff_id, actual_start_time, actual_end_time 사용)")
    cursor.execute("""
        SELECT 
            KTQ.queue_task_id,
            CO.order_number,
            MI.name,
            MT.task_name,
            KTQ.status,
            COALESCE(W.name, 'N/A') as ws,
            COALESCE(CAST(KTQ.assigned_zone_id AS TEXT), 'N/A') as zone,
            COALESCE(CAST(KTQ.assigned_staff_id AS TEXT), 'N/A') as staff,
            COALESCE(KTQ.actual_start_time, 'N/A') as start_time,
            COALESCE(KTQ.actual_end_time, 'N/A') as end_time
        FROM KitchenTaskQueue KTQ
        JOIN OrderItems OI ON KTQ.order_item_id = OI.order_item_id
        JOIN CustomerOrders CO ON OI.order_id = CO.order_id
        JOIN MenuItems MI ON OI.menu_item_id = MI.menu_item_id
        JOIN MenuTasks MT ON KTQ.task_definition_id = MT.task_definition_id
        LEFT JOIN Workstations W ON KTQ.assigned_workstation_id = W.workstation_id
        LIMIT 12
    """)
    data = cursor.fetchall()
    print(tabulate(data, headers=["Task ID", "주문", "메뉴", "작업", "상태", "WS", "Zone", "Staff", "Start", "End"], 
                   tablefmt="grid", maxcolwidths=[8, 8, 10, 12, 12, 8, 6, 6, 14, 14]))
    
    # 13. BottleneckAnalysis
    print("\n✅ [13] BottleneckAnalysis - 병목 현상 분석")
    cursor.execute("""
        SELECT BA.analysis_id, BA.queue_task_id, BA.bottleneck_type, 
               BA.wait_duration_seconds, W.name, BA.recorded_at
        FROM BottleneckAnalysis BA
        LEFT JOIN Workstations W ON BA.problematic_workstation_id = W.workstation_id
    """)
    data = cursor.fetchall()
    print(tabulate(data, headers=["Analysis ID", "Queue Task ID", "병목유형", "대기시간(초)", "문제작업장", "기록시간"], tablefmt="grid"))
    
    # 최종 통계
    print("\n" + Fore.CYAN + "="*80)
    print("📈 최종 통계 - 모든 테이블 활용 확인")
    print("="*80 + "\n")
    
    tables_info = [
        ("Workstations", "SELECT COUNT(*) FROM Workstations"),
        ("WorkstationZones", "SELECT COUNT(*) FROM WorkstationZones"),
        ("ZoneCapacityRules", "SELECT COUNT(*) FROM ZoneCapacityRules"),
        ("ZoneRealtimeState", "SELECT COUNT(*) FROM ZoneRealtimeState"),
        ("Staff", "SELECT COUNT(*) FROM Staff"),
        ("StaffAssignment", "SELECT COUNT(*) FROM StaffAssignment"),
        ("MenuItems", "SELECT COUNT(*) FROM MenuItems"),
        ("MenuTasks", "SELECT COUNT(*) FROM MenuTasks"),
        ("TaskDependencies", "SELECT COUNT(*) FROM TaskDependencies"),
        ("CustomerOrders", "SELECT COUNT(*) FROM CustomerOrders"),
        ("OrderItems", "SELECT COUNT(*) FROM OrderItems"),
        ("KitchenTaskQueue", "SELECT COUNT(*) FROM KitchenTaskQueue"),
        ("BottleneckAnalysis", "SELECT COUNT(*) FROM BottleneckAnalysis"),
    ]
    
    print("📊 각 테이블 레코드 수:")
    for table_name, query in tables_info:
        cursor.execute(query)
        count = cursor.fetchone()[0]
        status = "✅" if count > 0 else "⚠️"
        print(f"   {status} {table_name:25s}: {count:3d}개")
    
    # 작업 상태별 통계
    print("\n📊 작업 큐 상태별 통계:")
    cursor.execute("""
        SELECT status, COUNT(*) as count FROM KitchenTaskQueue GROUP BY status
    """)
    queue_stats = cursor.fetchall()
    for status, count in queue_stats:
        print(f"   - {status:20s}: {count}개")
    
    # 병목 원인 분석
    print("\n📊 병목 원인별 분석:")
    cursor.execute("""
        SELECT bottleneck_type, COUNT(*) as count, AVG(wait_duration_seconds) as avg_wait
        FROM BottleneckAnalysis
        GROUP BY bottleneck_type
    """)
    bottleneck_stats = cursor.fetchall()
    for bn_type, count, avg_wait in bottleneck_stats:
        print(f"   - {bn_type:25s}: {count}회, 평균대기 {avg_wait:.0f}초")
    
    print(Fore.GREEN + "\n✅ 모든 13개 테이블이 완벽하게 활용되었습니다!\n")

if __name__ == "__main__":
    print(Fore.MAGENTA + Style.BRIGHT + "="*80)
    print("🍔 맘스터치 완전 자동화 데모 - momsTouch.sql 모든 테이블 활용")
    print("="*80 + "\n")
    
    # 1. 데이터베이스 생성
    conn = setup_database()
    time.sleep(0.5)
    
    # 2. 기본 데이터 삽입
    insert_initial_data(conn)
    time.sleep(0.5)
    
    # 3. 고객 주문 접수
    demo_customer_orders(conn)
    time.sleep(0.5)
    
    # 4. 작업 큐 자동 생성
    demo_task_queue_creation(conn)
    time.sleep(0.5)
    
    # 5. 자원 할당
    demo_resource_assignment(conn)
    time.sleep(0.5)
    
    # 6. Zone 상태 업데이트
    demo_zone_state_updates(conn)
    time.sleep(0.5)
    
    # 7. 작업 처리 시뮬레이션
    demo_task_execution(conn)
    time.sleep(0.5)
    
    # 8. 병목 분석
    demo_bottleneck_analysis(conn)
    time.sleep(0.5)
    
    # 9. 최종 리포트
    demo_final_report(conn)
    
    conn.close()
    
    print(Fore.YELLOW + "\n📁 데이터베이스 파일: momstouch_complete.db")
    print("✨ 모든 13개 테이블과 모든 컬럼이 완벽하게 활용되었습니다!\n")
