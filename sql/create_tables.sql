CREATE DATABASE IF NOT EXISTS llm_arena
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE llm_arena;

CREATE TABLE IF NOT EXISTS arena_battle (
    record_id INT PRIMARY KEY,
    question_id VARCHAR(100),
    model_a VARCHAR(120) NOT NULL,
    model_b VARCHAR(120) NOT NULL,
    winner VARCHAR(20) NOT NULL,
    language VARCHAR(50),
    tstamp DATETIME,
    battle_date DATE,
    battle_hour INT,
    battle_month VARCHAR(20),
    prompt_text TEXT,
    response_a_text MEDIUMTEXT,
    response_b_text MEDIUMTEXT,
    prompt_len INT,
    response_a_len INT,
    response_b_len INT,
    len_diff INT,
    abs_len_diff INT,
    topic_name VARCHAR(50),
    topic_cluster INT,
    INDEX idx_model_a (model_a),
    INDEX idx_model_b (model_b),
    INDEX idx_winner (winner),
    INDEX idx_language (language),
    INDEX idx_topic (topic_name),
    INDEX idx_date (battle_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS model_statistics (
    id INT PRIMARY KEY AUTO_INCREMENT,
    model_name VARCHAR(120) NOT NULL UNIQUE,
    battle_count INT NOT NULL,
    win_count INT NOT NULL,
    lose_count INT NOT NULL,
    tie_count INT NOT NULL,
    win_rate DOUBLE,
    tie_rate DOUBLE,
    score DOUBLE,
    score_rate DOUBLE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS topic_statistics (
    id INT PRIMARY KEY AUTO_INCREMENT,
    topic_name VARCHAR(50) NOT NULL UNIQUE,
    count INT NOT NULL,
    proportion DOUBLE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
