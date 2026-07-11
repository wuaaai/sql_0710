# 数据处理中心模块设计文档

## 1. 模块定位

数据处理中心是财政智能助手的数据底座模块，负责把分散在不同财政业务系统中的结构化数据、元数据、字典信息、表关系和语义信息整理成可被系统稳定消费的数据资产。

它不直接面向最终问答结果，而是向以下两个核心能力提供底层支撑：
- 向 `Text2SQL` 提供候选表、候选字段、Join 关系、候选 Schema、示例 SQL 和字段语义
- 向 `RAG` 提供财政术语、库表说明、字段释义、指标口径、业务关系和知识增强材料

## 2. 模块目标

- 统一接入财政相关数据源
- 沉淀元数据资产和财政语义资产
- 构建可用于智能选表的结构化检索底座
- 建立向量化索引和候选 Schema 生成能力
- 对数据质量、Schema 变化、同步状态进行持续监控
- 为 `Text2SQL` 和 `RAG` 提供稳定接口

## 3. 功能拆分

### 3.1 数据源管理 — 管理 MySQL/Oracle/PostgreSQL/SQL Server/ClickHouse/Hive 等数据源，连接测试、权限校验
### 3.2 数据同步 — 定时同步库表元数据、增量同步字段和注释变化、全量刷新
### 3.3 数据清洗 — 空值处理、重复值识别、异常值识别、格式标准化、金额单位转换
### 3.4 数据质量评估 — 完整性/唯一性/一致性/准确性/时效性多维度评估
### 3.5 元数据管理 — 数据库/Schema/Table/Column/主外键/索引/Comment 管理
### 3.6 表结构理解 — 识别表说明和字段含义、理解主外键和 Join 关系、形成 Schema 语义资产
### 3.7 向量数据维护 — 为表/字段/术语/示例SQL生成 Embedding、增量/全量重建
### 3.8 定时维护任务 — 新表检测、字段变更检测、向量重建、质量定期重评估
### 3.9 智能选表支撑 — 表召回、字段召回、Join 推荐、候选 Schema 生成、Rerank 重排
### 3.10 数据监控 — 同步状态、更新频率、质量评分变化、向量索引状态、异常告警

## 4. 目录结构建议

```
src/data_processing_center/
├── facade.py
├── datasource/registry.py, connection_manager.py, source_health_checker.py
├── sync/metadata_sync_service.py, incremental_sync_service.py, full_sync_service.py
├── cleaning/null_value_cleaner.py, duplicate_detector.py, anomaly_detector.py, field_normalizer.py, unit_converter.py
├── quality/quality_rule_engine.py, quality_evaluator.py, quality_report_builder.py
├── metadata/catalog_manager.py, dictionary_manager.py, lineage_manager.py, schema_snapshot_manager.py
├── semantics/table_structure_analyzer.py, business_term_mapper.py, join_path_builder.py, query_pattern_builder.py
├── vectorization/embedding_builder.py, schema_vector_indexer.py, vector_refresh_service.py
├── retrieval_support/table_retriever.py, field_retriever.py, join_recommender.py, schema_candidate_builder.py, rerank_service.py
├── scheduling/maintenance_scheduler.py, change_detection_job.py, quality_recheck_job.py
├── monitoring/sync_monitor.py, schema_change_monitor.py, vector_index_monitor.py, alert_dispatcher.py
└── dto/datasource_dto.py, metadata_dto.py, quality_dto.py, schema_candidate_dto.py
```

## 5. 核心服务类

- `DataProcessingCenterFacade` — 统一入口，对外屏蔽内部复杂子模块
- `DataSourceRegistry` — 数据源注册、修改、禁用、标签和业务域管理
- `MetadataSyncService` — 拉取库表字段元数据并生成标准化快照
- `IncrementalSyncService` — 检测字段/注释/索引/Schema 变化并增量更新
- `DataCleaningPipeline` — 组织空值处理、格式统一、金额单位转换、异常值识别
- `DataQualityEvaluator` — 执行质量评分和质量报告输出
- `MetadataCatalogManager` — 维护数据库目录/Schema目录/表目录/字段目录
- `BusinessTermMapper` — 将财政业务术语映射到库表字段和口径定义
- `TableStructureAnalyzer` — 分析表结构、字段含义、Join 关系和常见查询模式
- `EmbeddingBuilder` — 构建表/字段/术语/示例SQL的 Embedding
- `SchemaCandidateBuilder` — 面向 Text2SQL 输出候选表/候选字段/候选 Join
- `DataMaintenanceScheduler` — 调度各类维护任务
- `DataMonitoringCenter` — 收集状态、告警和趋势

## 6. 财政场景专用类

- `FiscalTermDictionaryManager` — 财政术语字典（预算指标、支付金额、功能分类、经济分类）
- `FiscalUnitNormalizer` — 统一金额单位、比例单位、数量单位
- `FiscalPeriodNormalizer` — 统一预算年度、执行期间、统计月份表达
- `FiscalOrgNormalizer` — 统一财政部门、预算单位、处室、项目单位等组织维度
- `FiscalSchemaSemanticTagger` — 对表和字段打财政业务标签（预算域/执行域/核算域/项目域）

## 7. 表结构与元数据对象设计

### 7.1 数据源对象 DataSource
source_id, source_name, source_type, business_domain, host, port, database_name, schema_name, auth_mode, owner, status, last_sync_time

### 7.2 表元数据对象 TableMetadata
table_id, source_id, database_name, schema_name, table_name, table_comment, business_domain, table_type, primary_key_columns, partition_columns, update_frequency, record_count, sample_sql, quality_score, semantic_tags

### 7.3 字段元数据对象 ColumnMetadata
column_id, table_id, column_name, column_comment, data_type, nullable, default_value, is_primary_key, is_foreign_key, enum_values, sample_values, business_meaning, metric_role, dimension_role, time_role, unit, sensitivity_level

### 7.4 关系对象 TableRelation
relation_id, source_table_id, target_table_id, relation_type, join_keys, relation_confidence, relation_description, business_relation_type

### 7.5 质量对象 DataQualityReport
report_id, source_id, table_id, completeness_score, uniqueness_score, consistency_score, accuracy_score, timeliness_score, overall_score, issue_count, issue_summary, generated_at

### 7.6 候选 Schema 对象 SchemaCandidate
candidate_id, query_text, candidate_tables, candidate_columns, candidate_joins, candidate_filters, ranking_score, retrieval_evidence, rerank_reason

## 8. 处理流程

### 8.1 元数据入库主流程
新增数据源 → 连接测试 → 拉取元数据 → 标准化快照 → 字段清洗与语义标准化 → 构建表关系与业务标签 → 写入元数据目录 → 生成 Embedding → 写入向量索引 → 更新监控状态

### 8.2 Schema 变化维护流程
定时任务触发 → 检测新表/删表/字段变化/Comment 变化 → 生成 Schema Diff → 更新元数据目录 → 触发受影响对象的 Embedding 重建 → 重算候选 Schema 索引 → 输出变更告警

### 8.3 智能选表支撑流程
接收用户问题 → 提取财政术语/指标/维度/时间 → 表召回 → 字段召回 → Join 路径推荐 → 候选 Schema 生成 → Rerank 重排 → 返回给 Text2SQL 链路

## 9. 与 Text2SQL 的接口

数据处理中心对 Text2SQL 的核心支撑是"让系统知道去哪张表、取哪个字段、怎么连表"：
- `search_candidate_tables(query_text, domain_scope)`
- `search_candidate_columns(query_text, candidate_tables)`
- `recommend_join_paths(candidate_tables, candidate_columns)`
- `build_schema_candidates(query_text, slots, top_k)`
- `get_table_semantics(table_id)` / `get_column_semantics(table_id, column_name)`
- `get_quality_score(table_id)`

## 10. 与 RAG 的接口

数据处理中心对 RAG 的核心支撑不是原始业务数据，而是"结构化知识解释层"：
- `retrieve_schema_knowledge(query_text, domain_scope)`
- `retrieve_business_term_definitions(query_text)`
- `retrieve_metric_caliber_explanations(metric_name)`
- `retrieve_table_relation_explanations(table_ids)`

## 11. 落地建议

按以下顺序推进：
1. 数据源管理 + 元数据管理 + 表结构理解
2. 智能选表支撑 + 候选 Schema 输出
3. 向量维护 + 财政语义增强
4. 质量评估 + 监控 + 定时维护
