-- agent_trader_schema.sql
--
-- 说明：
-- 1. 这份脚本面向当前仓库的 domain model，优先覆盖 `Opportunity` 与 `ResearchTask`
--    的真实持久化需求。
-- 2. 任务回答和 skill 版本表一并提供，为后续 agent 运行审计做准备。
-- 3. 当前项目中 `candles` / `signals` 更适合 InfluxDB，因此这里不在 MySQL 建表。

CREATE DATABASE IF NOT EXISTS agent_trader
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE agent_trader;

CREATE TABLE opportunities (
    id CHAR(36) PRIMARY KEY COMMENT '机会唯一ID，UUID',
    symbol VARCHAR(32) NOT NULL COMMENT '标的代码',
    trigger_kind VARCHAR(32) NOT NULL COMMENT '触发类型',
    summary TEXT NULL COMMENT '机会摘要',
    confidence DECIMAL(5,4) NOT NULL COMMENT '机会置信度，对齐 domain.Opportunity.confidence',
    source_ref VARCHAR(255) NOT NULL COMMENT '上游 trigger/event 的来源引用',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE research_tasks (
    id CHAR(36) PRIMARY KEY COMMENT '研究任务ID，UUID',
    opportunity_id CHAR(36) NOT NULL COMMENT '关联机会ID',
    trigger_kind VARCHAR(32) NOT NULL COMMENT '保留任务触发类型，便于直接查询',
    payload JSON NOT NULL COMMENT '任务上下文，对齐 domain.ResearchTask.payload',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
);

CREATE TABLE agent_definitions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    agent_code VARCHAR(64) NOT NULL UNIQUE,
    agent_name VARCHAR(128) NOT NULL,
    agent_type VARCHAR(64) NOT NULL,
    description TEXT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE agent_skill_definitions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    skill_code VARCHAR(64) NOT NULL UNIQUE,
    skill_name VARCHAR(128) NOT NULL,
    description TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE agent_skill_versions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    skill_id BIGINT NOT NULL,
    version VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    implementation_ref VARCHAR(255) NULL,
    prompt_template TEXT NULL,
    input_schema JSON NULL,
    output_schema JSON NULL,
    config JSON NULL,
    change_log TEXT NULL,
    is_current TINYINT(1) NOT NULL DEFAULT 0,
    created_by VARCHAR(64) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at DATETIME NULL,
    FOREIGN KEY (skill_id) REFERENCES agent_skill_definitions(id),
    UNIQUE (skill_id, version)
);

CREATE TABLE agent_task_runs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    run_id CHAR(36) NOT NULL UNIQUE,
    research_task_id CHAR(36) NOT NULL,
    opportunity_id CHAR(36) NOT NULL,
    agent_id BIGINT NOT NULL,
    trigger_kind VARCHAR(32) NOT NULL,
    symbol VARCHAR(32) NULL,
    run_status VARCHAR(32) NOT NULL DEFAULT 'queued',
    input_payload JSON NULL,
    context_payload JSON NULL,
    result_summary TEXT NULL,
    error_message TEXT NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (research_task_id) REFERENCES research_tasks(id),
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id),
    FOREIGN KEY (agent_id) REFERENCES agent_definitions(id)
);

CREATE TABLE agent_task_run_steps (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_run_id BIGINT NOT NULL,
    research_task_id CHAR(36) NOT NULL,
    opportunity_id CHAR(36) NOT NULL,
    step_code VARCHAR(64) NOT NULL,
    step_name VARCHAR(128) NOT NULL,
    agent_id BIGINT NULL,
    skill_version_id BIGINT NULL,
    step_order INT NOT NULL,
    step_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    input_payload JSON NULL,
    output_payload JSON NULL,
    error_message TEXT NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_run_id) REFERENCES agent_task_runs(id),
    FOREIGN KEY (research_task_id) REFERENCES research_tasks(id),
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id),
    FOREIGN KEY (agent_id) REFERENCES agent_definitions(id),
    FOREIGN KEY (skill_version_id) REFERENCES agent_skill_versions(id)
);

CREATE TABLE agent_task_answers (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_run_id BIGINT NOT NULL,
    step_id BIGINT NULL,
    research_task_id CHAR(36) NOT NULL,
    opportunity_id CHAR(36) NOT NULL,
    agent_id BIGINT NOT NULL,
    skill_version_id BIGINT NULL,
    answer_type VARCHAR(32) NOT NULL DEFAULT 'final',
    answer_format VARCHAR(32) NOT NULL DEFAULT 'markdown',
    title VARCHAR(255) NULL,
    content LONGTEXT NOT NULL,
    structured_content JSON NULL,
    confidence DECIMAL(5,4) NULL,
    model_name VARCHAR(128) NULL,
    token_input INT NULL,
    token_output INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_run_id) REFERENCES agent_task_runs(id),
    FOREIGN KEY (step_id) REFERENCES agent_task_run_steps(id),
    FOREIGN KEY (research_task_id) REFERENCES research_tasks(id),
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id),
    FOREIGN KEY (agent_id) REFERENCES agent_definitions(id),
    FOREIGN KEY (skill_version_id) REFERENCES agent_skill_versions(id)
);
