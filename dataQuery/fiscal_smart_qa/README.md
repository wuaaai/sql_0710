# Fiscal Smart QA

一个面向财政数据场景的智能问数示例项目。

## 项目能力

- 接收自然语言问题
- 调用 DeepSeek 提取槽位和问题类型
- 基于 pgvector 向量库做选表、科目匹配、指标匹配
- 生成达梦 SQL 模板并填充槽位
- 执行 SQL
- 调用模型生成分析结论
- 返回表格和图表配置

## 目录结构

- [main.py](D:/pythonPro/dataQuery/fiscal_smart_qa/main.py:1): FastAPI 入口
- [config.py](D:/pythonPro/dataQuery/fiscal_smart_qa/config.py:1): 配置加载，支持 `.env`
- [metadata.py](D:/pythonPro/dataQuery/fiscal_smart_qa/metadata.py:1): 读取 schema 和 table_info
- [llm_client.py](D:/pythonPro/dataQuery/fiscal_smart_qa/llm_client.py:1): DeepSeek 调用
- [embedding_client.py](D:/pythonPro/dataQuery/fiscal_smart_qa/embedding_client.py:1): embedding 调用
- [vector_retriever.py](D:/pythonPro/dataQuery/fiscal_smart_qa/vector_retriever.py:1): pgvector 检索
- [intent.py](D:/pythonPro/dataQuery/fiscal_smart_qa/intent.py:1): 槽位抽取
- [selector.py](D:/pythonPro/dataQuery/fiscal_smart_qa/selector.py:1): 选表和候选匹配
- [sql_builder.py](D:/pythonPro/dataQuery/fiscal_smart_qa/sql_builder.py:1): SQL 模板生成
- [dameng_executor.py](D:/pythonPro/dataQuery/fiscal_smart_qa/dameng_executor.py:1): 达梦执行
- [analysis.py](D:/pythonPro/dataQuery/fiscal_smart_qa/analysis.py:1): 结果分析
- [charting.py](D:/pythonPro/dataQuery/fiscal_smart_qa/charting.py:1): 图表配置
- [quick_check.py](D:/pythonPro/dataQuery/fiscal_smart_qa/quick_check.py:1): 启动前检查
- [DEBUG_EXAMPLES.md](D:/pythonPro/dataQuery/fiscal_smart_qa/DEBUG_EXAMPLES.md:1): 3 个联调示例
- [templates/index.html](D:/pythonPro/dataQuery/fiscal_smart_qa/templates/index.html:1): 简单前端页面

## 运行前准备

1. 确保已经构建好向量表：

```bash
python D:\pythonPro\dataQuery\table_vector_rebuild\run_rebuild.py build-all --version v1
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 复制环境变量模板：

```bash
copy .env.example .env
```

4. 编辑 `.env`，至少填好：

- `DEEPSEEK_API_KEY`
- `DM_USER`
- `DM_PASSWORD`
- `DM_SCHEMA`

## 推荐启动顺序

1. 先做启动检查：

```bash
python quick_check.py
```

2. 启动服务：

```bash
python main.py
```

或者在 PowerShell 里：

```bash
.\start.ps1
```

3. 打开页面：

[http://127.0.0.1:8000](http://127.0.0.1:8000)

## 默认依赖路径

项目默认读取以下元数据：

- `D:\pythonPro\dataQuery\table_vector_rebuild\metadata\RDYS_PUBLIC_TBS.json`
- `D:\pythonPro\dataQuery\table_vector_rebuild\metadata\table_info.json`

如果你改了位置，可以通过 `.env` 里的这两个变量覆盖：

- `QA_SCHEMA_META_PATH`
- `QA_TABLE_INFO_PATH`

## 3 个推荐联调问题

1. `2025年10月一般公共预算收入中税收收入合计是多少？`
2. `2025年1月到10月全省教育支出每月变化趋势怎么样？`
3. `2025年10月省本级政府性基金收入各科目占比情况是什么？`

更详细的联调说明见：

[DEBUG_EXAMPLES.md](D:/pythonPro/dataQuery/fiscal_smart_qa/DEBUG_EXAMPLES.md:1)
