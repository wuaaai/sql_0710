from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import List

from langchain_core.messages import AIMessage

from text_smart_qa.src.agent.my_llm import llm
from text_smart_qa.src.agent.utils.log_utils import log
from text_smart_qa.src.unified.models import IntentTask, RoutingDecision


WORKSPACE_DIR = Path(__file__).resolve().parents[3]
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from fiscal_smart_qa.project_names import load_project_names


ROUTER_PROMPT = """
你是财政智能助手的路由器，需要先理解用户问题，再判断问题属于下面 4 类中的哪一种：
1. text_qa：主要问政策、文件、预算解读、名词解释、规定依据、原因说明、构成口径。
2. fiscal_sql：主要问财政数据，需要查数据库、做统计、做对比、看趋势、看金额。
3. hybrid：一个问题里同时包含财政数据查询和财政文档解释。
4. chitchat：闲聊、打招呼，或者与财政问答和财政问数无关。
请严格输出 JSON，不要输出其他内容：
{
  "route": "text_qa | fiscal_sql | hybrid | chitchat",
  "confidence": 0.0,
  "reason": "一句话说明原因",
  "text_question": "给智能问答系统的问题，没有就留空",
  "data_question": "给智能问数系统的问题，没有就留空"
}
"""


class RouterService:
    """先做主意图和子意图拆分，必要时再用大模型补判。"""

    def __init__(self):
        self._account_scope_keywords = [
            "一般公共预算",
            "政府性基金",
            "国有资本经营预算",
            "社会保险基金预算",
            "一般公共预算收入",
            "一般公共预算支出",
            "政府性基金收入",
            "政府性基金支出",
            "国有资本经营收入",
            "国有资本经营支出",
            "社会保险基金收入",
            "社会保险基金支出",
        ]
        self._subject_keywords = self._load_subject_keywords()
        self._metric_keywords = [
            "执行金额",
            "完成金额",
            "完成多少",
            "完成情况",
            "完成数",
            "预算数",
            "决算数",
            "收入金额",
            "支出金额",
            "总计",
            "合计",
            "同比",
            "环比",
            "增幅",
            "增速",
            "执行率",
            "完成率",
            "占比",
            "比重",
            "排名",
            "增长率",
        ]
        self._generic_subject_keywords = [
            "财政收入",
            "财政支出",
            "收入",
            "支出",
            "重点支出",
        ]
        self._generic_metric_keywords = [
            "情况",
            "规模",
            "水平",
        ]
        self._flow_direction_keywords = [
            "收入",
            "支出",
        ]
        self._region_level_keywords = [
            "全省",
            "省本级",
            "省级",
            "市级",
            "各市",
            "市本级",
            "县级",
            "区县",
            "全市",
            "本级",
        ]
        self._business_domain_keywords = [
            "预算执行",
            "决算",
            "预算调整",
            "预算草案",
            "预算审查",
        ]
        self._data_keywords = [
            "多少",
            "金额",
            "收入",
            "支出",
            "执行率",
            "同比",
            "环比",
            "趋势",
            "变化",
            "排名",
            "top",
            "TOP",
            "各市",
            "各区县",
            "各地",
            "每月",
            "分月",
            "占比",
            "比重",
            "预算执行",
            "完成多少",
            "总计多少",
            "增收",
            "增支",
        ]
        self._text_keywords = [
            "政策",
            "文件",
            "解读",
            "依据",
            "规定",
            "措施",
            "要求",
            "含义",
            "什么意思",
            "名词解释",
            "为什么",
            "原因",
            "背景",
            "如何理解",
            "怎么理解",
            "怎么说",
            "构成",
            "组成",
            "由哪几部分",
            "包括哪些",
            "口径",
            "分别指",
            "分类",
            "范围",
        ]
        self._chat_keywords = [
            "你好",
            "您好",
            "谢谢",
            "再见",
            "你是谁",
            "你能做什么",
            "天气",
            "讲个笑话",
            "早上好",
            "晚上好",
        ]
        self._split_patterns = [
            "？",
            "，",
            ";",
            "并且",
            "和",
            "以及",
            "同时",
        ]

    @staticmethod
    def _load_subject_keywords() -> List[str]:
        """从 fiscal_smart_qa/projectname.json 动态加载项目名称列表。"""
        subject_keywords = load_project_names()
        if subject_keywords:
            return subject_keywords
        return [
            "税收收入",
            "非税收入",
            "卫生健康支出",
            "教育支出",
            "社会保障和就业支出",
            "农林水支出",
            "科学技术支出",
            "住房保障支出",
            "交通运输支出",
        ]

    async def route_question(self, question: str, history_messages: List[dict] | None = None) -> RoutingDecision:
        """对外统一入口。"""
        decision = self.route_by_rules(question)
        if decision is not None:
            log.info(f"[Router] 规则命中，route={decision.route}, reason={decision.reason}")
            return decision

        log.info("[Router] 规则未命中，开始使用大模型补判")
        decision = await asyncio.to_thread(self.route_by_llm, question, history_messages or [])
        return self._finalize_fiscal_decision(decision, question)

    def route_by_rules(self, question: str) -> RoutingDecision | None:
        """先拆子意图，再按规则汇总主意图。"""
        normalized = self._normalize_question(question)
        if not normalized:
            return RoutingDecision(
                route="chitchat",
                confidence=1.0,
                reason="问题为空，按闲聊处理",
                source="rules",
                main_intent="chitchat",
            )

        if self._looks_like_chitchat(normalized):
            return RoutingDecision(
                route="chitchat",
                confidence=0.98,
                reason="命中闲聊关键词，且没有明显财政业务意图",
                source="rules",
                main_intent="chitchat",
            )

        sub_questions = self._split_into_sub_questions(normalized)
        sub_tasks = self._classify_sub_questions(sub_questions)
        if not sub_tasks:
            return None

        decision = self._build_decision_from_tasks(normalized, sub_tasks)
        return self._finalize_fiscal_decision(decision, normalized)

    def route_by_llm(self, question: str, history_messages: List[dict]) -> RoutingDecision:
        """规则无法确定时，使用大模型补充判断。"""
        history_text = self._build_history_text(history_messages)
        user_prompt = (
            f"历史对话摘要：\n{history_text}\n\n"
            f"当前问题：\n{question}\n"
        )
        content = llm.invoke(
            [
                {"role": "system", "content": ROUTER_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
        )
        if isinstance(content, AIMessage):
            raw_text = content.content
        else:
            raw_text = getattr(content, "content", str(content))

        payload = self._parse_json_text(raw_text)
        route = payload.get("route") or "text_qa"
        if route not in {"text_qa", "fiscal_sql", "hybrid", "chitchat"}:
            route = "text_qa"

        text_question = str(payload.get("text_question") or "")
        data_question = str(payload.get("data_question") or "")
        sub_tasks: List[IntentTask] = []
        if route in {"text_qa", "hybrid"} and text_question:
            sub_tasks.append(IntentTask(route="text_qa", question=text_question, reason="大模型识别为文档解释问题"))
        if route in {"fiscal_sql", "hybrid"} and data_question:
            fiscal_task = self._classify_single_sub_question(data_question)
            if fiscal_task is not None and fiscal_task.route == "fiscal_sql":
                sub_tasks.append(fiscal_task)
            elif data_question:
                sub_tasks.append(IntentTask(route="fiscal_sql", question=data_question, reason="大模型识别为数据查询问题"))

        if not sub_tasks and route == "text_qa":
            sub_tasks.append(IntentTask(route="text_qa", question=question, reason="大模型兜底归类为智能问答"))
        if not sub_tasks and route == "fiscal_sql":
            task = self._classify_single_sub_question(question)
            if task is not None:
                sub_tasks.append(task)
            else:
                sub_tasks.append(IntentTask(route="fiscal_sql", question=question, reason="大模型兜底归类为智能问数"))

        return RoutingDecision(
            route=route,
            confidence=float(payload.get("confidence") or 0.70),
            reason=str(payload.get("reason") or "大模型补充判断"),
            source="llm",
            text_question=text_question if route in {"text_qa", "hybrid"} else "",
            data_question=data_question if route in {"fiscal_sql", "hybrid"} else "",
            main_intent=route,
            sub_tasks=sub_tasks,
        )

    def _build_decision_from_tasks(self, original_question: str, tasks: List[IntentTask]) -> RoutingDecision:
        """根据子任务集合汇总主意图。"""
        text_tasks = [task for task in tasks if task.route == "text_qa"]
        data_tasks = [task for task in tasks if task.route == "fiscal_sql"]

        if text_tasks and data_tasks:
            return RoutingDecision(
                route="hybrid",
                confidence=0.93,
                reason="问题拆分后同时包含数据查询和文档解释子意图",
                source="rules",
                text_question="，".join(task.question for task in text_tasks),
                data_question="，".join(task.question for task in data_tasks),
                main_intent="hybrid",
                sub_tasks=tasks,
            )

        if data_tasks:
            primary = data_tasks[0].question if len(data_tasks) == 1 else original_question
            return RoutingDecision(
                route="fiscal_sql",
                confidence=0.92,
                reason="问题拆分后主要是财政数据查询",
                source="rules",
                data_question=primary,
                main_intent="fiscal_sql",
                sub_tasks=tasks,
            )

        if text_tasks:
            primary = text_tasks[0].question if len(text_tasks) == 1 else original_question
            return RoutingDecision(
                route="text_qa",
                confidence=0.90,
                reason="问题拆分后主要是财政文档解释",
                source="rules",
                text_question=primary,
                main_intent="text_qa",
                sub_tasks=tasks,
            )

        return RoutingDecision(
            route="text_qa",
            confidence=0.65,
            reason="未识别出明确数据意图，默认按财政问答处理",
            source="rules",
            text_question=original_question,
            main_intent="text_qa",
            sub_tasks=[IntentTask(route="text_qa", question=original_question, reason="默认兜底到智能问答")],
        )

    def _classify_sub_questions(self, sub_questions: List[str]) -> List[IntentTask]:
        """对子问题逐个分类。"""
        tasks: List[IntentTask] = []
        context_anchor = ""
        domain_anchor = ""
        for sub_question in sub_questions:
            if self._is_domain_anchor_text(sub_question):
                domain_anchor = sub_question
                context_anchor = self._build_context_anchor(context_anchor, sub_question)
                continue

            completed_question = self._attach_domain_anchor(sub_question, domain_anchor)
            completed_question = self._complete_sub_question(completed_question, context_anchor)
            task = self._classify_single_sub_question(completed_question)
            if task is not None:
                tasks.append(task)
                context_anchor = self._build_context_anchor(context_anchor, completed_question)
        return self._dedupe_tasks(tasks)

    def _classify_single_sub_question(self, question: str) -> IntentTask | None:
        """对单个子问题做规则分类。"""
        normalized = self._normalize_question(question)
        if not normalized:
            return None

        fiscal_slots = self._extract_fiscal_slots(normalized)
        data_score = self._count_keywords(normalized, self._data_keywords)
        text_score = self._count_keywords(normalized, self._text_keywords)

        has_year = bool(re.search(r"\d{4}年", normalized))
        has_month = bool(re.search(r"\d{1,2}月", normalized))
        has_compare = any(word in normalized for word in ["对比", "比较", "排名", "最高", "最低", "相差"])

        if (has_year or has_month or has_compare) and data_score == 0:
            data_score += 1

        if text_score > data_score and text_score > 0:
            return IntentTask(route="text_qa", question=normalized, reason="命中文档解释类关键词")

        if data_score > 0:
            if self._is_fiscal_query_ready(fiscal_slots):
                return IntentTask(
                    route="fiscal_sql",
                    question=normalized,
                    reason="已识别到明确科目、指标、收支方向和地区层级，可进入智能问数",
                    slot_status="ready",
                    slot_values=fiscal_slots,
                )
            missing_slots = self._find_missing_fiscal_slots(fiscal_slots)
            return IntentTask(
                route="fiscal_sql",
                question=normalized,
                reason="问数意图明显，但关键查询槽位还不完整，需要先补充条件",
                slot_status="clarify",
                missing_slots=missing_slots,
                slot_values=fiscal_slots,
            )

        if text_score > 0:
            return IntentTask(route="text_qa", question=normalized, reason="命中文档解释类关键词")

        if self._looks_like_definition_question(normalized):
            return IntentTask(route="text_qa", question=normalized, reason="更像概念解释或口径说明")

        return None

    def _extract_fiscal_slots(self, question: str) -> dict:
        """从问题中提取智能问数路由所需的关键要素。"""
        subject = self._extract_subject(question)
        metric = self._extract_metric(question)
        flow_direction = self._extract_flow_direction(question, subject)
        region_level = self._extract_region_level(question)
        return {
            "subject": subject,
            "metric": metric,
            "flow_direction": flow_direction,
            "region_level": region_level,
        }

    def _find_missing_fiscal_slots(self, slots: dict) -> List[str]:
        """找出当前问题里缺少的智能问数关键槽位。"""
        missing_slots: List[str] = []
        subject = slots.get("subject", "")
        metric = slots.get("metric", "")
        flow_direction = slots.get("flow_direction", "")
        region_level = slots.get("region_level", "")

        if not subject or self._is_generic_subject(subject):
            missing_slots.append("subject")
        if not metric or self._is_generic_metric(metric):
            missing_slots.append("metric")
        if flow_direction not in {"收入", "支出"}:
            missing_slots.append("flow_direction")
        if not region_level:
            missing_slots.append("region_level")
        return missing_slots

    @staticmethod
    def _is_fiscal_query_ready(slots: dict) -> bool:
        """只有关键要素齐全，才允许进入智能问数。"""
        return bool(
            slots.get("subject")
            and slots.get("metric")
            and slots.get("flow_direction")
            and slots.get("region_level")
        )

    def _extract_subject(self, question: str) -> str:
        """抽取明确科目。"""
        for keyword in self._subject_keywords:
            if keyword in question:
                return keyword

        match = re.search(r"([\u4e00-\u9fa5]{2,18}(收入|支出))", question)
        if match:
            candidate = match.group(1)
            if self._is_generic_account_scope(candidate):
                return ""
            if candidate not in {"重点支出", "财政支出", "财政收入"}:
                return candidate
        return ""

    def _extract_metric(self, question: str) -> str:
        """抽取明确指标。"""
        for keyword in self._metric_keywords:
            if keyword in question:
                return keyword

        if "完成多少" in question:
            return "完成多少"
        if "完成" in question and "多少" in question:
            return "完成多少"
        if "多少" in question and ("金额" in question or "总计" in question or "合计" in question):
            return "金额"
        if "多少" in question and ("收入" in question or "支出" in question):
            return "金额"
        return ""

    def _is_generic_account_scope(self, text: str) -> bool:
        """判断是否只是预算口径大类，而不是具体科目。"""
        return any(keyword in text for keyword in self._account_scope_keywords)

    def _is_generic_subject(self, subject: str) -> bool:
        """判断当前科目是不是过于宽泛，不能直接用于问数。"""
        if not subject:
            return True
        if self._is_generic_account_scope(subject):
            return True
        return subject in self._generic_subject_keywords

    def _is_generic_metric(self, metric: str) -> bool:
        """判断当前指标是不是泛指标。"""
        if not metric:
            return True
        return metric in self._generic_metric_keywords

    def _extract_flow_direction(self, question: str, subject: str) -> str:
        """抽取明确收支方向。"""
        if "收入" in question or (subject and "收入" in subject):
            return "收入"
        if "支出" in question or (subject and "支出" in subject):
            return "支出"
        return ""

    def _extract_region_level(self, question: str) -> str:
        """抽取明确地区层级。"""
        for keyword in self._region_level_keywords:
            if keyword in question:
                return keyword
        return ""

    def _split_into_sub_questions(self, question: str) -> List[str]:
        """把复合问题拆成多个子问题。"""
        working = question
        for splitter in self._split_patterns:
            working = working.replace(splitter, "|")

        parts = []
        for item in working.split("|"):
            text = self._normalize_question(item)
            if not text:
                continue
            parts.append(text)

        return parts or [question]

    def _is_domain_anchor_text(self, text: str) -> bool:
        """判断一段话是不是仅用于描述业务域的前缀。"""
        normalized = self._normalize_question(text)
        if not normalized:
            return False

        business_domain_patterns = [
            rf"^{keyword}业务域$"
            for keyword in self._business_domain_keywords
        ] + [
            rf"^{keyword}业务域中$"
            for keyword in self._business_domain_keywords
        ] + [
            rf"^{keyword}业务域里$"
            for keyword in self._business_domain_keywords
        ]
        return any(re.match(pattern, normalized) for pattern in business_domain_patterns)

    def _attach_domain_anchor(self, sub_question: str, domain_anchor: str) -> str:
        """把业务域前缀补到后续真正的问题前面。"""
        normalized_question = self._normalize_question(sub_question)
        normalized_anchor = self._normalize_question(domain_anchor)

        if not normalized_anchor:
            return normalized_question
        if not normalized_question:
            return normalized_question
        if any(keyword in normalized_question for keyword in self._business_domain_keywords):
            return normalized_question
        return f"{normalized_anchor}{normalized_question}"

    @staticmethod
    def _complete_sub_question(sub_question: str, context_anchor: str) -> str:
        """对子问题做简单补全，避免后半句缺主语。"""
        if not context_anchor:
            return sub_question

        if any(word in sub_question for word in ["由哪几部分", "构成", "包括哪些", "口径", "依据", "原因"]):
            if "预算" not in sub_question and "收入" not in sub_question and "支出" not in sub_question:
                return f"{context_anchor}{sub_question}"
        return sub_question

    @staticmethod
    def _build_context_anchor(existing_anchor: str, sub_question: str) -> str:
        """从前一个子问题提取简单上下文。"""
        important_words = [
            "预算执行",
            "决算",
            "预算调整",
            "预算草案",
            "预算审查",
            "一般公共预算",
            "政府性基金",
            "国有资本经营",
            "社会保险基金",
            "收入",
            "支出",
            "总计",
        ]
        for word in important_words:
            if word in sub_question and word not in existing_anchor:
                existing_anchor += word
        if re.search(r"\d{4}年", sub_question) and not re.search(r"\d{4}年", existing_anchor):
            year_match = re.search(r"\d{4}年", sub_question)
            if year_match:
                existing_anchor = year_match.group(0) + existing_anchor
        return existing_anchor

    @staticmethod
    def _dedupe_tasks(tasks: List[IntentTask]) -> List[IntentTask]:
        """对子任务去重，保留原顺序。"""
        deduped: List[IntentTask] = []
        seen = set()
        for task in tasks:
            key = (task.route, task.question, task.slot_status)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(task)
        return deduped

    def _finalize_fiscal_decision(self, decision: RoutingDecision, question: str) -> RoutingDecision:
        """把财政问数候选态整理成统一的路由结果。"""
        fiscal_tasks = [task for task in decision.sub_tasks if task.route == "fiscal_sql"]
        if not fiscal_tasks:
            return decision

        ready_tasks = [task for task in fiscal_tasks if task.slot_status == "ready"]
        clarify_tasks = [task for task in fiscal_tasks if task.slot_status == "clarify"]

        if ready_tasks and not clarify_tasks:
            decision.slot_status = "ready"
            decision.slot_values = dict(ready_tasks[0].slot_values)
            return decision

        if clarify_tasks:
            primary_task = clarify_tasks[0]
            decision.slot_status = "clarify"
            decision.missing_slots = list(primary_task.missing_slots)
            decision.slot_values = dict(primary_task.slot_values)
            decision.clarify_message = self._build_clarify_message(
                question=question,
                missing_slots=primary_task.missing_slots,
                slot_values=primary_task.slot_values,
            )
            if decision.route == "fiscal_sql":
                decision.reason = "问数意图明确，但关键槽位缺失，先返回补槽位引导"
            elif decision.route == "hybrid":
                decision.reason = "问题同时包含问数和问答，但问数部分还需要补充关键条件"
        return decision

    def _build_clarify_message(self, question: str, missing_slots: List[str], slot_values: dict) -> str:
        """生成缺槽位时给用户的补充提问文案。"""
        slot_label_map = {
            "subject": "科目",
            "metric": "指标",
            "flow_direction": "收支方向",
            "region_level": "地区层级",
        }
        missing_labels = [slot_label_map[item] for item in missing_slots if item in slot_label_map]

        current_lines = []
        if slot_values.get("subject"):
            current_lines.append(f"- 已识别科目：{slot_values['subject']}")
        if slot_values.get("metric"):
            current_lines.append(f"- 已识别指标：{slot_values['metric']}")
        if slot_values.get("flow_direction"):
            current_lines.append(f"- 已识别收支方向：{slot_values['flow_direction']}")
        if slot_values.get("region_level"):
            current_lines.append(f"- 已识别地区层级：{slot_values['region_level']}")

        example_question = "例如你可以这样问：“2025年省本级卫生健康支出的执行金额是多少”"
        lines = [
            "这个问题更像是财政数据查询，但当前还不具备直接执行 SQL 的条件。",
            f"还缺少的关键条件：{'、'.join(missing_labels) if missing_labels else '关键槽位'}。",
        ]
        if current_lines:
            lines.append("当前已经识别到的信息如下：")
            lines.extend(current_lines)
        lines.append("请补充缺少的条件后，我就可以继续帮你查询。")
        lines.append(example_question)
        return "\n".join(lines)

    def _looks_like_chitchat(self, question: str) -> bool:
        if any(word in question for word in self._chat_keywords):
            has_business_word = self._count_keywords(question, self._data_keywords + self._text_keywords) > 0
            return not has_business_word
        return False

    @staticmethod
    def _looks_like_definition_question(question: str) -> bool:
        keywords = ["是什么", "怎么理解", "含义", "构成", "组成", "口径", "依据"]
        return any(word in question for word in keywords)

    @staticmethod
    def _normalize_question(question: str) -> str:
        return re.sub(r"\s+", "", (question or "").strip())

    @staticmethod
    def _count_keywords(question: str, keywords: List[str]) -> int:
        return sum(1 for word in keywords if word in question)

    @staticmethod
    def _build_history_text(history_messages: List[dict]) -> str:
        parts: List[str] = []
        for item in history_messages[-6:]:
            role = item.get("role", "")
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            parts.append(f"{role}: {content}")
        return "\n".join(parts) or "无"

    @staticmethod
    def _parse_json_text(raw_text: str) -> dict:
        text = (raw_text or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.replace("json", "", 1).strip()

        try:
            return json.loads(text)
        except Exception:
            match = re.search(r"\{.*\}", text, re.S)
            if match:
                return json.loads(match.group(0))
        return {}
