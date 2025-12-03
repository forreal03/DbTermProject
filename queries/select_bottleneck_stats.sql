-- 병목 유형별 통계
SELECT bottleneck_type, COUNT(*) as count, SUM(wait_duration_seconds) as total_wait
FROM BottleneckAnalysis
GROUP BY bottleneck_type;
