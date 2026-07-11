# 统一意图识别模块 — RAG 知识库测试报告

**测试时间**: 2026-07-11 11:21:19
**数据来源**: 知识库测试结果.xlsx → 08服务器rag
**问题数**: 41
**总耗时**: 76.0 秒

## 1. 概要

| 总问题数 | 41 |
| 成功提取 | 41 |
| 成功率 | 100.0% |

## 2. 调度结果分布

| 调度结果 | 数量 | 占比 |
|----------|------|------|
| 纯 Text2SQL | 14 | 34.1% |
| 纯 RAG | 1 | 2.4% |
| 混合（Text2SQL + RAG） | 7 | 17.1% |
| 追问补槽位 | 18 | 43.9% |

## 3. 详细输出

### #1 — 纯 Text2SQL
**问题**: 2018年，全省一般公共预算收入完成多少

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算执行 |
| account_book | 一般公共预算 |
| flow_type | 收入 |
| region_level | 全省 |
| time_text | 2018年 |
| time_start | 201801 |
| time_end | 201812 |
| time_grain | year |
| query_type | detail |
| data_stage | 执行数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 一般公共预算收入 |
| metrics | 总计 |
| regions | 全省 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 纯 Text2SQL | text2sql=True | rag=False

---

### #2 — 纯 Text2SQL
**问题**: 2018年，全省一般公共预算收入完成预算的百分之多少

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算执行 |
| account_book | 一般公共预算 |
| flow_type | 收入 |
| region_level | 全省 |
| time_text | 2018年 |
| time_start | 201801 |
| time_end | 201812 |
| time_grain | year |
| query_type | proportion |
| data_stage | 执行数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 一般公共预算收入 |
| metrics | 完成预算比例 |
| regions | 全省 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 纯 Text2SQL | text2sql=True | rag=False

---

### #3 — 追问补槽位
**问题**: 比上年提高多少个百分点

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | — |
| account_book | — |
| flow_type | — |
| region_level | — |
| time_text | 比上年 |
| time_start | — |
| time_end | — |
| time_grain | year |
| query_type | comparison |
| data_stage | — |
| compare_dimension | time |
| compare_operator | diff |
| chart_hint | auto |
| top_n | 0 |
| subjects | — |
| metrics | 百分点 |
| regions | — |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 追问补槽位 | text2sql=False | rag=False
 | 缺失: subject, flow_direction, region_level

---

### #4 — 纯 Text2SQL
**问题**: 2018年，省级一般公共预算收入完成多少

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算执行 |
| account_book | 一般公共预算 |
| flow_type | 收入 |
| region_level | 省本级 |
| time_text | 2018年 |
| time_start | 201801 |
| time_end | 201812 |
| time_grain | year |
| query_type | detail |
| data_stage | 执行数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 一般公共预算收入 |
| metrics | 总计 |
| regions | 省级 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 纯 Text2SQL | text2sql=True | rag=False

---

### #5 — 纯 Text2SQL
**问题**: 2018年，省级一般公共预算收入完成预算的多少

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算执行 |
| account_book | 一般公共预算 |
| flow_type | 收入 |
| region_level | 省本级 |
| time_text | 2018年 |
| time_start | 201801 |
| time_end | 201812 |
| time_grain | year |
| query_type | detail |
| data_stage | 执行数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 一般公共预算收入 |
| metrics | 总计 |
| regions | 省级 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 纯 Text2SQL | text2sql=True | rag=False

---

### #6 — 纯 Text2SQL
**问题**: 2019年全省一般公共预算收入预期目标多少

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算草案 |
| account_book | 一般公共预算 |
| flow_type | 收入 |
| region_level | 全省 |
| time_text | 2019年 |
| time_start | 201901 |
| time_end | 201912 |
| time_grain | year |
| query_type | detail |
| data_stage | 预算数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 一般公共预算收入 |
| metrics | 总计 |
| regions | 全省 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 纯 Text2SQL | text2sql=True | rag=False

---

### #7 — 纯 Text2SQL
**问题**: 2019年省级一般公共预算收入预期目标多少

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算草案 |
| account_book | 一般公共预算 |
| flow_type | 收入 |
| region_level | 省本级 |
| time_text | 2019年 |
| time_start | 201901 |
| time_end | 201912 |
| time_grain | year |
| query_type | detail |
| data_stage | 预算数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 一般公共预算收入 |
| metrics | 总计 |
| regions | 省级 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 纯 Text2SQL | text2sql=True | rag=False

---

### #8 — 纯 Text2SQL
**问题**: 2019年全省一般公共预算收入增长安排多少

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算草案 |
| account_book | 一般公共预算 |
| flow_type | 收入 |
| region_level | 全省 |
| time_text | 2019年 |
| time_start | 201901 |
| time_end | 201912 |
| time_grain | year |
| query_type | detail |
| data_stage | 预算数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 一般公共预算收入 |
| metrics | 总计 |
| regions | 全省 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 纯 Text2SQL | text2sql=True | rag=False

---

### #9 — 纯 Text2SQL
**问题**: 2019年全省一般公共预算支出多少

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | — |
| account_book | 一般公共预算 |
| flow_type | 支出 |
| region_level | 全省 |
| time_text | 2019年 |
| time_start | 201901 |
| time_end | 201912 |
| time_grain | year |
| query_type | detail |
| data_stage | — |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 一般公共预算支出 |
| metrics | 总计 |
| regions | 全省 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 纯 Text2SQL | text2sql=True | rag=False

---

### #10 — 追问补槽位
**问题**: 比上年初预算增长多少

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算执行 |
| account_book | — |
| flow_type | — |
| region_level | — |
| time_text | 上年初 |
| time_start | — |
| time_end | — |
| time_grain | year |
| query_type | comparison |
| data_stage | 执行数 |
| compare_dimension | time |
| compare_operator | diff |
| chart_hint | auto |
| top_n | 0 |
| subjects | — |
| metrics | 总计 |
| regions | — |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 追问补槽位 | text2sql=False | rag=False
 | 缺失: subject, flow_direction, region_level

---

### #11 — 纯 Text2SQL
**问题**: 2019年全省一般公共预算支出中科学技术支出增长多少

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算执行 |
| account_book | 一般公共预算 |
| flow_type | 支出 |
| region_level | 全省 |
| time_text | 2019年 |
| time_start | 201901 |
| time_end | 201912 |
| time_grain | year |
| query_type | trend |
| data_stage | 执行数 |
| compare_dimension | time |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 一般公共预算支出, 科学技术支出 |
| metrics | 同比增幅 |
| regions | 全省 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 纯 Text2SQL | text2sql=True | rag=False

---

### #12 — 混合（Text2SQL + RAG）
**问题**: 2019年全省一般公共预算收入总计多少，由哪几部分构成

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | — |
| account_book | 一般公共预算 |
| flow_type | 收入 |
| region_level | 全省 |
| time_text | 2019年 |
| time_start | 201901 |
| time_end | 201912 |
| time_grain | year |
| query_type | proportion |
| data_stage | 执行数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | pie |
| top_n | 0 |
| subjects | 一般公共预算收入 |
| metrics | 总计 |
| regions | 全省 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | True |
| need_data_value | True |

**调度**: 混合（Text2SQL + RAG） | text2sql=True | rag=True

---

### #13 — 混合（Text2SQL + RAG）
**问题**: 2019年省级一般公共预算收入总计多少，由哪几部分构成

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | — |
| account_book | 一般公共预算 |
| flow_type | 收入 |
| region_level | 省本级 |
| time_text | 2019年 |
| time_start | 201901 |
| time_end | 201912 |
| time_grain | year |
| query_type | proportion |
| data_stage | 执行数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | pie |
| top_n | 0 |
| subjects | 一般公共预算收入 |
| metrics | 总计 |
| regions | 省级 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | True |
| need_data_value | True |

**调度**: 混合（Text2SQL + RAG） | text2sql=True | rag=True

---

### #14 — 追问补槽位
**问题**: 2018年政府性基金预算收入完成多少

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算执行 |
| account_book | 政府性基金 |
| flow_type | 收入 |
| region_level | — |
| time_text | 2018年 |
| time_start | 201801 |
| time_end | 201812 |
| time_grain | year |
| query_type | detail |
| data_stage | 完成情况 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 政府性基金预算收入 |
| metrics | 总计 |
| regions | — |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 追问补槽位 | text2sql=False | rag=False
 | 缺失: region_level

---

### #15 — 追问补槽位
**问题**: 2018年政府性基金预算收入完成预算的多少，增长了多少

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算执行 |
| account_book | 政府性基金 |
| flow_type | 收入 |
| region_level | — |
| time_text | 2018年 |
| time_start | 201801 |
| time_end | 201812 |
| time_grain | year |
| query_type | detail |
| data_stage | 完成情况 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 政府性基金预算收入 |
| metrics | 总计, 执行金额, 同比增幅 |
| regions | — |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 追问补槽位 | text2sql=False | rag=False
 | 缺失: region_level

---

### #16 — 追问补槽位
**问题**: 2019年政府性基金预算支出安排多少

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算草案 |
| account_book | 政府性基金 |
| flow_type | 支出 |
| region_level | — |
| time_text | 2019年 |
| time_start | 201901 |
| time_end | 201912 |
| time_grain | year |
| query_type | detail |
| data_stage | 预算数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 政府性基金预算支出 |
| metrics | 总计 |
| regions | — |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 追问补槽位 | text2sql=False | rag=False
 | 缺失: region_level

---

### #17 — 混合（Text2SQL + RAG）
**问题**: 2019年省级政府性基金预算收入总计多少，由哪几部分组成

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算执行 |
| account_book | 政府性基金 |
| flow_type | 收入 |
| region_level | 省本级 |
| time_text | 2019年 |
| time_start | 201901 |
| time_end | 201912 |
| time_grain | year |
| query_type | proportion |
| data_stage | 执行数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | pie |
| top_n | 0 |
| subjects | 政府性基金预算收入 |
| metrics | 总计 |
| regions | 省级 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | True |
| need_data_value | True |

**调度**: 混合（Text2SQL + RAG） | text2sql=True | rag=True

---

### #18 — 混合（Text2SQL + RAG）
**问题**: 2019年省级政府性基金预算支出总计多少，由哪几部分组成

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算执行 |
| account_book | 政府性基金 |
| flow_type | 支出 |
| region_level | 省本级 |
| time_text | 2019年 |
| time_start | 201901 |
| time_end | 201912 |
| time_grain | year |
| query_type | summary |
| data_stage | 执行数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 政府性基金预算支出 |
| metrics | 总计 |
| regions | 省级 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | True |
| need_data_value | True |

**调度**: 混合（Text2SQL + RAG） | text2sql=True | rag=True

---

### #19 — 纯 Text2SQL
**问题**: 2019年,全省国有资本经营预算收入

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | — |
| account_book | 国有资本经营预算 |
| flow_type | 收入 |
| region_level | 全省 |
| time_text | 2019年 |
| time_start | 201901 |
| time_end | 201912 |
| time_grain | year |
| query_type | detail |
| data_stage | — |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 国有资本经营预算收入 |
| metrics | 总计 |
| regions | 全省 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 纯 Text2SQL | text2sql=True | rag=False

---

### #20 — 纯 Text2SQL
**问题**: 2019年省级国有资本经营预算收入

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算草案 |
| account_book | 国有资本经营预算 |
| flow_type | 收入 |
| region_level | 省本级 |
| time_text | 2019年 |
| time_start | 201901 |
| time_end | 201912 |
| time_grain | year |
| query_type | detail |
| data_stage | 预算数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 国有资本经营预算收入 |
| metrics | 总计 |
| regions | 省级 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 纯 Text2SQL | text2sql=True | rag=False

---

### #21 — 混合（Text2SQL + RAG）
**问题**: 2019年全省国有资本经营预算支出总计多少，由哪些组成

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算执行 |
| account_book | 国有资本经营预算 |
| flow_type | 支出 |
| region_level | 全省 |
| time_text | 2019年 |
| time_start | 201901 |
| time_end | 201912 |
| time_grain | year |
| query_type | proportion |
| data_stage | 执行数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | pie |
| top_n | 0 |
| subjects | 国有资本经营预算支出 |
| metrics | 总计 |
| regions | 全省 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | True |
| need_data_value | True |

**调度**: 混合（Text2SQL + RAG） | text2sql=True | rag=True

---

### #22 — 追问补槽位
**问题**: 2019年社会保险基金预算被分类了多少类

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算草案 |
| account_book | 社会保险基金 |
| flow_type | — |
| region_level | — |
| time_text | 2019年 |
| time_start | 201901 |
| time_end | 201912 |
| time_grain | year |
| query_type | detail |
| data_stage | 预算数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | — |
| metrics | 总计 |
| regions | — |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | True |
| need_data_value | True |

**调度**: 追问补槽位 | text2sql=False | rag=False
 | 缺失: subject, flow_direction, region_level

---

### #23 — 纯 Text2SQL
**问题**: 2019年全省社会保险基金预算收入多少

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算草案 |
| account_book | 社会保险基金 |
| flow_type | 收入 |
| region_level | 全省 |
| time_text | 2019年 |
| time_start | 201901 |
| time_end | 201912 |
| time_grain | year |
| query_type | detail |
| data_stage | 预算数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 社会保险基金预算收入 |
| metrics | 总计 |
| regions | 全省 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 纯 Text2SQL | text2sql=True | rag=False

---

### #24 — 追问补槽位
**问题**: 2019年全省社会保险基金预算收入由哪些组成

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算草案 |
| account_book | 社会保险基金 |
| flow_type | 收入 |
| region_level | 全省 |
| time_text | 2019年 |
| time_start | 201901 |
| time_end | 201912 |
| time_grain | year |
| query_type | proportion |
| data_stage | 预算数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | pie |
| top_n | 0 |
| subjects | 社会保险基金预算收入 |
| metrics | — |
| regions | 全省 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | True |
| need_data_value | False |

**调度**: 追问补槽位 | text2sql=False | rag=False
 | 缺失: metric

---

### #25 — 混合（Text2SQL + RAG）
**问题**: 2019年全省社会保险基金预算支出多少，由哪些组成

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | — |
| account_book | 社会保险基金 |
| flow_type | 支出 |
| region_level | 全省 |
| time_text | 2019年 |
| time_start | 201901 |
| time_end | 201912 |
| time_grain | year |
| query_type | detail |
| data_stage | 执行数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 社会保险基金支出 |
| metrics | 总计 |
| regions | 全省 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | True |
| need_data_value | True |

**调度**: 混合（Text2SQL + RAG） | text2sql=True | rag=True

---

### #26 — 混合（Text2SQL + RAG）
**问题**: 2019年全省社会保险基金预算收入总计多少，由哪些组成

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算执行 |
| account_book | 社会保险基金 |
| flow_type | 收入 |
| region_level | 全省 |
| time_text | 2019年 |
| time_start | 201901 |
| time_end | 201912 |
| time_grain | year |
| query_type | proportion |
| data_stage | 执行数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | pie |
| top_n | 0 |
| subjects | 社会保险基金预算收入 |
| metrics | 总计 |
| regions | 全省 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | True |
| need_data_value | True |

**调度**: 混合（Text2SQL + RAG） | text2sql=True | rag=True

---

### #27 — 追问补槽位
**问题**: 请问2025年的预算是怎么安排的？

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算草案 |
| account_book | — |
| flow_type | — |
| region_level | — |
| time_text | 2025年 |
| time_start | 202501 |
| time_end | 202512 |
| time_grain | year |
| query_type | summary |
| data_stage | 预算数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 请问 预算是怎么安排 |
| metrics | — |
| regions | — |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | False |

**调度**: 追问补槽位 | text2sql=False | rag=False
 | 缺失: metric, flow_direction, region_level

---

### #28 — 追问补槽位
**问题**: 全社会研发经费投入近些年呈现什么趋势

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | — |
| account_book | — |
| flow_type | 支出 |
| region_level | — |
| time_text | 近些年 |
| time_start | 202001 |
| time_end | 202512 |
| time_grain | year |
| query_type | trend |
| data_stage | — |
| compare_dimension | time |
| compare_operator | none |
| chart_hint | line |
| top_n | 0 |
| subjects | 全社会研发经费投入 |
| metrics | 总计 |
| regions | — |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 追问补槽位 | text2sql=False | rag=False
 | 缺失: region_level

---

### #29 — 追问补槽位
**问题**: 2025年预算安排中是怎么样加大教育投入的？和前两年相比有什么区别

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算草案 |
| account_book | 一般公共预算 |
| flow_type | 支出 |
| region_level | — |
| time_text | 2025年 |
| time_start | 202501 |
| time_end | 202512 |
| time_grain | year |
| query_type | comparison |
| data_stage | 预算数 |
| compare_dimension | time |
| compare_operator | diff |
| chart_hint | bar |
| top_n | 0 |
| subjects | 教育投入 |
| metrics | 总计 |
| regions | — |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | True |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 追问补槽位 | text2sql=False | rag=False
 | 缺失: region_level

---

### #30 — 追问补槽位
**问题**: 2024年预算安排中是怎么样加大教育投入的，体现出什么？

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算草案 |
| account_book | 一般公共预算 |
| flow_type | 支出 |
| region_level | — |
| time_text | 2024年 |
| time_start | 202401 |
| time_end | 202412 |
| time_grain | year |
| query_type | detail |
| data_stage | 预算数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 教育投入 |
| metrics | — |
| regions | — |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | False |

**调度**: 追问补槽位 | text2sql=False | rag=False
 | 缺失: metric, region_level

---

### #31 — 追问补槽位
**问题**: 2025与2024年国家下达增发国债项目的数量变化

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | — |
| account_book | — |
| flow_type | — |
| region_level | — |
| time_text | 2025与2024年 |
| time_start | 202401 |
| time_end | 202512 |
| time_grain | year |
| query_type | trend |
| data_stage | — |
| compare_dimension | time |
| compare_operator | diff |
| chart_hint | bar |
| top_n | 0 |
| subjects | 增发国债项目 |
| metrics | 数量 |
| regions | 国家 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 追问补槽位 | text2sql=False | rag=False
 | 缺失: flow_direction, region_level

---

### #32 — 追问补槽位
**问题**: 2024年我省在新型城镇化方面取得了哪些成果，2025年如何巩固并发展的

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | — |
| account_book | — |
| flow_type | — |
| region_level | 全省 |
| time_text | 2024年、2025年 |
| time_start | 202401 |
| time_end | 202512 |
| time_grain | year |
| query_type | summary |
| data_stage | — |
| compare_dimension | time |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 我省在新型城镇化方面取得了哪些成果, 2025年如何巩固并发展 |
| metrics | — |
| regions | 我省 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | True |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | False |

**调度**: 追问补槽位 | text2sql=False | rag=False
 | 缺失: metric, flow_direction

---

### #33 — 纯 Text2SQL
**问题**: 2025年，省级安排资金多少，主要用于补助企业职工基本养老保险、城乡居民基本养老保险和医疗保险。

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | 预算执行 |
| account_book | 一般公共预算 |
| flow_type | 支出 |
| region_level | 省本级 |
| time_text | 2025年 |
| time_start | 202501 |
| time_end | 202512 |
| time_grain | year |
| query_type | detail |
| data_stage | 执行数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 企业职工基本养老保险, 城乡居民基本养老保险, 医疗保险 |
| metrics | 总计 |
| regions | 省级 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 纯 Text2SQL | text2sql=True | rag=False

---

### #34 — 追问补槽位
**问题**: 近几年城乡居民基本养老保险安排补助资金的变化体现出了什么，还有什么不足

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | — |
| account_book | 一般公共预算 |
| flow_type | 支出 |
| region_level | — |
| time_text | 近几年 |
| time_start | 202101 |
| time_end | 202512 |
| time_grain | year |
| query_type | trend |
| data_stage | 执行数 |
| compare_dimension | time |
| compare_operator | none |
| chart_hint | line |
| top_n | 0 |
| subjects | 城乡居民基本养老保险, 补助资金 |
| metrics | 总计 |
| regions | — |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 追问补槽位 | text2sql=False | rag=False
 | 缺失: region_level

---

### #35 — 追问补槽位
**问题**: 近两年，社会救助的变化

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | — |
| account_book | — |
| flow_type | — |
| region_level | — |
| time_text | 近两年 |
| time_start | 202301 |
| time_end | 202412 |
| time_grain | year |
| query_type | trend |
| data_stage | — |
| compare_dimension | time |
| compare_operator | none |
| chart_hint | line |
| top_n | 0 |
| subjects | 社会救助 |
| metrics | — |
| regions | — |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | False |

**调度**: 追问补槽位 | text2sql=False | rag=False
 | 缺失: metric, flow_direction, region_level

---

### #36 — 闲聊兜底
**问题**: 产生这些变化的原因是什么

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | — |
| account_book | — |
| flow_type | — |
| region_level | — |
| time_text | — |
| time_start | 0 |
| time_end | 0 |
| time_grain | year |
| query_type | summary |
| data_stage | — |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | — |
| metrics | — |
| regions | — |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | False |

**调度**: 闲聊兜底 | text2sql=False | rag=False

---

### #37 — 追问补槽位
**问题**: 2025年，如何落实公共卫生服务工作，为经济贡献体现在哪里

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | — |
| account_book | 一般公共预算 |
| flow_type | 支出 |
| region_level | — |
| time_text | 2025年 |
| time_start | 202501 |
| time_end | 202512 |
| time_grain | year |
| query_type | mixed |
| data_stage | — |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 公共卫生服务 |
| metrics | — |
| regions | — |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | True |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | False |

**调度**: 追问补槽位 | text2sql=False | rag=False
 | 缺失: metric, region_level

---

### #38 — 纯 Text2SQL
**问题**: 2024年我省公办幼儿园生均公用经费标准由每生每年多少元提高至每生每年多少元。

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | — |
| account_book | 一般公共预算 |
| flow_type | 支出 |
| region_level | 全省 |
| time_text | 2024年 |
| time_start | 202401 |
| time_end | 202412 |
| time_grain | year |
| query_type | detail |
| data_stage | 预算数 |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | none |
| top_n | 0 |
| subjects | 公办幼儿园生均公用经费 |
| metrics | 标准 |
| regions | 我省 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | False |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | True |

**调度**: 纯 Text2SQL | text2sql=True | rag=False

---

### #39 — 追问补槽位
**问题**: 2025年以及2024年的社会事业发展的重点工作有哪些,工作主线是什么

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | — |
| account_book | — |
| flow_type | — |
| region_level | — |
| time_text | 2025年以及2024年 |
| time_start | 202401 |
| time_end | 202512 |
| time_grain | year |
| query_type | summary |
| data_stage | — |
| compare_dimension | time |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 社会事业发展 |
| metrics | — |
| regions | — |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | True |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | False |

**调度**: 追问补槽位 | text2sql=False | rag=False
 | 缺失: metric, flow_direction, region_level

---

### #40 — 追问补槽位
**问题**: 在乡村振兴工作中，我省做了哪些工作，取得了什么成果

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | — |
| account_book | — |
| flow_type | — |
| region_level | 全省 |
| time_text | — |
| time_start | 0 |
| time_end | 0 |
| time_grain | year |
| query_type | summary |
| data_stage | — |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | 在乡村振兴工作中, 我省做了哪些工作, 取得了什么成果 |
| metrics | — |
| regions | 我省 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | True |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | False |

**调度**: 追问补槽位 | text2sql=False | rag=False
 | 缺失: metric, flow_direction, time

---

### #41 — 纯 RAG
**问题**: 我省的退税政策是什么

**text2sql 子集**:
| 字段 | 值 |
|------|----|
| business_module | — |
| account_book | — |
| flow_type | — |
| region_level | 全省 |
| time_text | — |
| time_start | 0 |
| time_end | 0 |
| time_grain | year |
| query_type | summary |
| data_stage | — |
| compare_dimension | none |
| compare_operator | none |
| chart_hint | auto |
| top_n | 0 |
| subjects | — |
| metrics | — |
| regions | 我省 |

**rag 子集**:
| 字段 | 值 |
|------|----|
| need_policy_basis | True |
| need_caliber_explanation | False |
| need_composition | False |
| need_data_value | False |

**调度**: 纯 RAG | text2sql=False | rag=True

---

*报告生成于 2026-07-11 11:21:19*