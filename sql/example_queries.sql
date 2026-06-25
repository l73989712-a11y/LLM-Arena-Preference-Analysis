USE llm_arena;

-- 1. 投票结果分布
SELECT winner, COUNT(*) AS count
FROM arena_battle
GROUP BY winner
ORDER BY count DESC;

-- 2. 模型综合表现排名
SELECT model_name, battle_count, win_count, tie_count, score_rate
FROM model_statistics
WHERE battle_count >= 100
ORDER BY score_rate DESC
LIMIT 10;

-- 3. 语言分布
SELECT language, COUNT(*) AS count
FROM arena_battle
GROUP BY language
ORDER BY count DESC;

-- 4. 用户问题主题分布
SELECT topic_name, COUNT(*) AS count
FROM arena_battle
GROUP BY topic_name
ORDER BY count DESC;

-- 5. 每日对话量
SELECT battle_date, COUNT(*) AS count
FROM arena_battle
WHERE battle_date IS NOT NULL
GROUP BY battle_date
ORDER BY battle_date;
