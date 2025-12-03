-- 병목 분석 데이터 삽입
-- Parameters: queue_task_id, bottleneck_type, wait_duration_seconds, problematic_workstation_id
INSERT INTO BottleneckAnalysis (
    queue_task_id, bottleneck_type, wait_duration_seconds,
    problematic_workstation_id, recorded_at
) VALUES (?, ?, ?, ?, datetime('now', 'localtime'));
