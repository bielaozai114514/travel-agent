"""
TripIntentAgent - 行程规划意图识别与参数提取

负责：
1. 识别用户意图：trip_planning / chat / trip_modification
2. 提取行程规划参数
3. 检测缺失参数并生成追问问题
"""
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

from settings import settings
from core.logger import logger
from core.EsAgent import EsAgentLLM, SimpleAgent
from core.context_manager import get_context_manager
from core.agent_stability import RobustJSONParser


class IntentType(str, Enum):
    """意图类型"""
    TRIP_PLANNING = "trip_planning"      # 新建行程规划
    TRIP_MODIFICATION = "trip_modification"  # 修改已有行程
    CHAT = "chat"                        # 普通聊天


class IntentAnalysisResult(BaseModel):
    """意图分析结果"""
    intent_type: IntentType = Field(..., description="意图类型")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="提取的参数")
    missing_params: List[str] = Field(default_factory=list, description="缺失的必要参数")
    clarification_question: Optional[str] = Field(None, description="追问问题（如果有）")
    confidence: float = Field(0.8, description="置信度")
    modification_summary: Optional[str] = Field(None, description="修改需求总结（仅trip_modification类型）")
    free_text_input: Optional[str] = Field(default="", description="额外要求/自由文本输入")


class TripIntentAgent:
    """行程规划意图识别 Agent"""

    # 必要参数列表
    REQUIRED_PARAMS = ["city"]

    # 可选参数列表
    OPTIONAL_PARAMS = [
        "start_date", "end_date", "travel_days",
        "transportation", "accommodation", "preferences"
    ]

    # 参数中文名称
    PARAM_NAMES = {
        "city": "目的地城市",
        "start_date": "开始日期",
        "end_date": "结束日期",
        "travel_days": "旅行天数",
        "transportation": "交通方式",
        "accommodation": "住宿偏好",
        "preferences": "景点偏好类型"
    }

    CITY_CANDIDATES = (
        "北京", "上海", "天津", "重庆", "广州", "深圳", "杭州", "南京", "苏州", "成都",
        "西安", "武汉", "长沙", "厦门", "青岛", "大连", "三亚", "海口", "昆明", "丽江",
        "大理", "桂林", "阳朔", "张家界", "黄山", "婺源", "景德镇", "南昌", "福州", "泉州",
        "宁波", "绍兴", "嘉兴", "无锡", "扬州", "镇江", "常州", "合肥", "郑州", "洛阳",
        "开封", "济南", "泰安", "烟台", "威海", "哈尔滨", "长春", "沈阳", "呼和浩特",
        "太原", "石家庄", "兰州", "西宁", "银川", "乌鲁木齐", "拉萨", "贵阳", "南宁",
        "北海", "珠海", "佛山", "东莞", "中山", "香港", "澳门", "台北", "高雄",
        "新疆", "西藏", "内蒙古", "海南", "云南", "贵州", "四川", "青海", "甘肃"
    )

    PLANNING_KEYWORDS = (
        "规划", "安排", "行程", "路线", "计划", "怎么玩", "怎么安排", "游玩",
        "自由行", "跟团", "一日游", "两日游", "三日游", "两天一夜", "三天两晚"
    )
    PLANNING_VERBS = ("想去", "打算去", "准备去", "计划去", "周末去", "五一去", "国庆去", "明天去", "后天去")
    INFO_QUERY_KEYWORDS = (
        "天气", "美食", "小吃", "景点", "门票", "开放时间", "怎么去", "交通", "地铁",
        "特色", "特产", "酒店", "住宿", "多少钱", "价格", "值得去吗", "有哪些", "有什么"
    )
    MODIFICATION_KEYWORDS = (
        "修改", "调整", "改成", "换成", "替换", "删掉", "删除", "取消", "加一天",
        "再加", "少一天", "多一天"
    )

    def __init__(self):
        config = settings.get_agent_config("intent")
        intent_temperature = (
            settings.INTENT_AGENT_TEMPERATURE
            if settings.INTENT_AGENT_TEMPERATURE is not None
            else 0.2
        )
        self.llm = EsAgentLLM(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=intent_temperature,  # 意图识别用较低温度，避免 JSON 飘格式
            timeout=config.timeout,
        )
        self.agent = self._create_agent()
        # 初始化上下文管理器（意图识别用较小的Token限制）
        self.context_manager = get_context_manager(max_tokens=6000)
        logger.info("TripIntentAgent 初始化完成")

    def _create_agent(self) -> SimpleAgent:
        """创建支持工具调用的 SimpleAgent"""
        system_prompt = """你是旅行意图识别助手。分析对话历史，判断用户最新输入的意图并提取参数。

## 意图分类（仔细区分！）
- trip_planning: 用户**需要行程安排帮助**，包括但不限于：
  • 明确要求规划/安排/做计划："帮我规划北京3天行程"、"安排杭州五一游"
  • 表达想去某地旅游并需要建议："我想去杭州玩几天"、"周末去苏州怎么安排"、"打算去上海旅游"
  • 询问旅行相关的安排建议："去西安3天怎么玩"、"厦门两天一夜推荐"
- trip_modification: 用户要**修改已有行程**
  例: "把第二天景点换成故宫"、"再加一天"、"调整一下行程"
- chat: 用户只是**询问信息、聊天咨询**，不需要生成完整行程安排
  例: "杭州有什么小众景点"、"北京天气怎么样"、"推荐一些美食"、"西湖怎么去"、"上海有什么特色"

## 关键区分规则（非常重要！）
→ 用户表达"想去某地旅游/玩"，或者询问"怎么玩/怎么安排" → trip_planning（需要进一步追问详细信息）
→ 用户只询问单一信息（景点/天气/美食/交通），没有表达要安排行程的需求 → chat

## 参数提取规则（尽可能从用户输入提取！）
- city: 目的地城市名称，必须提取（如"杭州"、"北京"、"西安"）
- travel_days: 旅行天数，整数（如"3天"→3，"两天"→2，"几天"→null，"一个星期"→7）
- start_date/end_date: 日期，必须输出YYYY-MM-DD；如果用户说了相对时间（明天/下周/五一），根据用户消息里提供的current_date推算
- transportation: 交通方式（如"自驾"、"高铁"、"飞机"）
- accommodation: 住宿偏好（如"经济型"、"舒适型"、"五星级"）
- preferences: 景点偏好（如"历史文化"、"自然景观"、"美食"）
- free_text_input: 其他所有额外要求、特殊说明、偏好描述，如果没有可以不填
  例如："希望多安排一些博物馆"、"想去看升旗"、"对海鲜过敏"、"需要无障碍设施"、"带老人孩子慢节奏"等
  → 把结构化参数提取后，剩下的用户需求内容都放这里！

## 规则
1. 累积参数：结合对话历史提取所有已提及的参数
2. 只判断用户最新输入；历史只用于补全已经提到的城市、天数、日期等参数
3. trip_modification必须生成modification_summary（简洁总结修改内容）
4. trip_planning缺少city，或者有city但没有任何日期/天数信息时，填入missing_params并生成clarification_question
5. chat类型不提取参数，missing_params和clarification_question留空
6. 必须只输出JSON，不要输出Markdown代码块、解释文字或工具调用

## 输出JSON
{
  "intent_type": "trip_planning|trip_modification|chat",
  "parameters": {},
  "missing_params": [],
  "clarification_question": null,
  "confidence": 0.8,
  "modification_summary": null,
  "free_text_input": ""
}"""

        agent = SimpleAgent(
            name="TripIntentAgent",
            llm=self.llm,
            system_prompt=system_prompt,
            tool_registry=None,
            enable_tool_calling=False
        )

        return agent

    async def analyze_intent(self, message: str, history_messages: Optional[List[Dict[str, str]]] = None) -> IntentAnalysisResult:
        """
        分析用户消息的意图（使用上下文管理器确保稳定性）

        Args:
            message: 用户消息内容
            history_messages: 历史消息列表，格式为 [{"role": "user/assistant", "content": "..."}]

        Returns:
            IntentAnalysisResult: 意图分析结果
        """
        try:
            logger.debug(f"开始分析意图: {message[:50]}..., 历史消息数: {len(history_messages) if history_messages else 0}")

            # 预处理历史消息
            processed_history = self._preprocess_history(history_messages or [])
            processed_history = self._remove_current_message_from_history(processed_history, message)

            # 调用 Agent 分析（纯 JSON 分类，不启用工具调用）
            intent_message = self._build_intent_message(message)
            response = self.agent.run(
                intent_message,
                external_history=processed_history,
                save_to_history=False,
                max_tool_iterations=1,
                max_tokens=700,
                temperature=0.2,
            )

            # 解析响应
            result = self._parse_response(response, message, processed_history)
            logger.info(f"意图分析完成: type={result.intent_type}, "
                       f"params={list(result.parameters.keys())}, "
                       f"missing={result.missing_params}")

            return result

        except Exception as e:
            logger.error(f"意图分析失败: {e}", exc_info=True)
            return self._heuristic_analyze_intent(message, history_messages or [], confidence=0.55)

    def _build_intent_message(self, message: str) -> str:
        """构造给意图识别模型的最新输入。"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        return (
            f"current_date: {current_date}\n"
            f"用户最新输入: {message}\n"
            "请结合历史消息补全参数，并只输出JSON。"
        )

    def _remove_current_message_from_history(
        self,
        history_messages: List[Dict[str, str]],
        current_message: str
    ) -> List[Dict[str, str]]:
        """避免当前用户输入在历史和最新消息里重复出现。"""
        if not history_messages:
            return []

        cleaned = list(history_messages)
        current_text = (current_message or "").strip()
        while cleaned:
            last = cleaned[-1]
            if last.get("role") == "user" and last.get("content", "").strip() == current_text:
                cleaned.pop()
                continue
            break

        return cleaned

    def _preprocess_history(self, history_messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        预处理历史消息，确保格式正确并进行安全截断

        Args:
            history_messages: 原始历史消息列表

        Returns:
            处理后的历史消息列表
        """
        if not history_messages:
            return []

        # 验证和清洗消息
        cleaned = []
        issues = []
        warnings = []

        last_role = None
        for i, msg in enumerate(history_messages):
            role = msg.get("role", "")
            content = msg.get("content", "")

            # 验证角色
            if role not in ["user", "assistant", "system"]:
                issues.append(f"消息{i}: 无效角色 '{role}'")
                continue

            # 验证内容
            if not content or not content.strip():
                warnings.append(f"消息{i}: 空内容")
                continue

            # 检查角色交替
            if role == last_role and role != "system":
                warnings.append(f"消息{i}: 连续 {role} 消息")

            # 截断过长消息
            if len(content) > 5000:
                content = content[:5000] + "...[内容已截断]"
                warnings.append(f"消息{i}: 内容过长已截断")

            cleaned.append({
                "role": role,
                "content": content.strip()
            })
            last_role = role

        if issues:
            logger.warning(f"意图识别历史消息问题: {issues}")
        if warnings:
            logger.debug(f"意图识别历史消息警告: {warnings}")

        # 安全截断（保留最近消息）
        max_tokens = 4000  # 意图识别用较小的限制
        total_tokens = 0
        selected = []

        for msg in reversed(cleaned):
            msg_tokens = self.context_manager._estimate_tokens(msg["content"])
            if total_tokens + msg_tokens > max_tokens:
                if not selected:
                    # 至少保留最后一条
                    truncated_content = self.context_manager._truncate_content(
                        msg["content"], max_tokens
                    )
                    selected.append({
                        "role": msg["role"],
                        "content": truncated_content
                    })
                logger.info(f"意图识别历史消息已截断: 保留{len(selected)}/{len(cleaned)}条")
                break
            selected.append(msg)
            total_tokens += msg_tokens

        selected.reverse()
        return selected

    def _parse_response(
        self,
        response: str,
        message: str = "",
        history_messages: Optional[List[Dict[str, str]]] = None
    ) -> IntentAnalysisResult:
        """解析 Agent 的响应（使用RobustJSONParser增强容错）"""
        response = response or ""
        history_messages = history_messages or []
        logger.debug(f"[IntentAgent] 开始解析响应，长度: {len(response)}")

        # 使用鲁棒JSON解析器
        parse_result = RobustJSONParser.parse(response)

        if not parse_result.success:
            logger.warning(f"[IntentAgent] JSON解析失败，使用本地规则兜底。方法: {parse_result.parse_method}")
            return self._heuristic_analyze_intent(message, history_messages, confidence=0.55)

        logger.debug(f"[IntentAgent] JSON解析成功，使用方法: {parse_result.parse_method}")
        data = parse_result.data
        if not isinstance(data, dict):
            logger.warning("[IntentAgent] JSON根节点不是对象，使用本地规则兜底")
            return self._heuristic_analyze_intent(message, history_messages, confidence=0.55)

        # 解析意图类型
        intent_type_str = data.get("intent_type") or data.get("intent") or data.get("type") or "chat"
        intent_type = self._normalize_intent_type(intent_type_str)
        if intent_type is None:
            logger.warning(f"[IntentAgent] 未知意图类型 '{intent_type_str}'，使用本地规则兜底")
            return self._heuristic_analyze_intent(message, history_messages, confidence=0.55)

        # 确保parameters是dict
        parameters = data.get("parameters", {})
        if not isinstance(parameters, dict):
            logger.warning(f"[IntentAgent] parameters类型不对，修复为空dict")
            parameters = {}
        parameters = dict(parameters)

        # 兼容模型把参数平铺到顶层的情况
        for key in self.REQUIRED_PARAMS + self.OPTIONAL_PARAMS:
            if key in data and key not in parameters:
                parameters[key] = data[key]
        parameters = self._normalize_parameters(parameters)

        # 确保missing_params是list
        missing_params = data.get("missing_params", [])
        if not isinstance(missing_params, list):
            missing_params = []

        # 构建结果
        result = IntentAnalysisResult(
            intent_type=intent_type,
            parameters=parameters,
            missing_params=missing_params,
            clarification_question=data.get("clarification_question"),
            confidence=self._normalize_confidence(data.get("confidence", 0.8)),
            modification_summary=data.get("modification_summary"),
            free_text_input=data.get("free_text_input", "")
        )
        result = self._repair_result_with_heuristics(result, message, history_messages)

        # 验证必要参数
        if result.intent_type == IntentType.TRIP_PLANNING:
            self._validate_required_params(result)
        elif result.intent_type == IntentType.CHAT:
            result.parameters = {}
            result.missing_params = []
            result.clarification_question = None

        logger.info(f"[IntentAgent] 解析完成: type={result.intent_type}")
        return result

    def _normalize_intent_type(self, intent_type: Any) -> Optional[IntentType]:
        """兼容模型输出的各种意图命名。"""
        value = str(intent_type or "").strip()
        normalized = value.lower().replace("-", "_").replace(" ", "_")

        mapping = {
            "trip_planning": IntentType.TRIP_PLANNING,
            "travel_planning": IntentType.TRIP_PLANNING,
            "trip_plan": IntentType.TRIP_PLANNING,
            "plan_trip": IntentType.TRIP_PLANNING,
            "planning": IntentType.TRIP_PLANNING,
            "travel_plan": IntentType.TRIP_PLANNING,
            "行程规划": IntentType.TRIP_PLANNING,
            "旅行规划": IntentType.TRIP_PLANNING,
            "旅游规划": IntentType.TRIP_PLANNING,
            "trip_modification": IntentType.TRIP_MODIFICATION,
            "trip_modify": IntentType.TRIP_MODIFICATION,
            "modify_trip": IntentType.TRIP_MODIFICATION,
            "trip_change": IntentType.TRIP_MODIFICATION,
            "modification": IntentType.TRIP_MODIFICATION,
            "行程修改": IntentType.TRIP_MODIFICATION,
            "修改行程": IntentType.TRIP_MODIFICATION,
            "chat": IntentType.CHAT,
            "qa": IntentType.CHAT,
            "question": IntentType.CHAT,
            "normal_chat": IntentType.CHAT,
            "咨询": IntentType.CHAT,
            "问答": IntentType.CHAT,
            "聊天": IntentType.CHAT,
        }
        return mapping.get(normalized)

    def _normalize_confidence(self, value: Any) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.8
        return max(0.0, min(1.0, confidence))

    def _normalize_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """清洗模型提取的参数，避免空值和类型飘移影响后续路由。"""
        normalized: Dict[str, Any] = {}
        for key, value in parameters.items():
            if value in (None, "", [], {}):
                continue

            if key == "city":
                city = self._clean_city(str(value))
                if city:
                    normalized[key] = city
            elif key == "travel_days":
                days = self._normalize_days_value(value)
                if days:
                    normalized[key] = days
            elif key in ("start_date", "end_date"):
                date_value = self._normalize_date_value(value)
                if date_value:
                    normalized[key] = date_value
            elif key == "preferences":
                if isinstance(value, list):
                    prefs = [str(item).strip() for item in value if str(item).strip()]
                else:
                    prefs = [item.strip() for item in re.split(r"[,，、/ ]+", str(value)) if item.strip()]
                if prefs:
                    normalized[key] = prefs
            else:
                normalized[key] = value

        return normalized

    def _repair_result_with_heuristics(
        self,
        result: IntentAnalysisResult,
        message: str,
        history_messages: List[Dict[str, str]]
    ) -> IntentAnalysisResult:
        """用本地规则修复模型漏识别、参数漏提取或明显误判。"""
        heuristic = self._heuristic_analyze_intent(
            message,
            history_messages,
            confidence=0.6,
            validate=False,
        )

        if (
            result.intent_type == IntentType.TRIP_PLANNING
            and heuristic.intent_type == IntentType.CHAT
            and self._is_single_info_query(message)
        ):
            return heuristic

        if heuristic.intent_type != IntentType.CHAT:
            if result.intent_type == IntentType.CHAT and result.confidence >= 0.65:
                # LLM 较确信是 chat，且不是单一信息查询，尊重 LLM 判断
                pass
            elif result.intent_type == IntentType.CHAT or result.confidence < 0.65:
                return heuristic
            if result.intent_type == heuristic.intent_type:
                for key, value in heuristic.parameters.items():
                    if not result.parameters.get(key):
                        result.parameters[key] = value
                if heuristic.modification_summary and not result.modification_summary:
                    result.modification_summary = heuristic.modification_summary

        return result

    def _heuristic_analyze_intent(
        self,
        message: str,
        history_messages: Optional[List[Dict[str, str]]] = None,
        confidence: float = 0.6,
        validate: bool = True,
    ) -> IntentAnalysisResult:
        """本地规则兜底：覆盖常见旅游规划、追问补参和行程修改场景。"""
        history_messages = self._remove_current_message_from_history(history_messages or [], message)
        current_text = (message or "").strip()
        recent_user_text = " ".join(
            msg.get("content", "")
            for msg in history_messages[-6:]
            if msg.get("role") == "user"
        )
        combined_text = f"{recent_user_text} {current_text}".strip()

        if not current_text:
            return IntentAnalysisResult(intent_type=IntentType.CHAT, confidence=confidence)

        if self._is_modification_request(current_text):
            return IntentAnalysisResult(
                intent_type=IntentType.TRIP_MODIFICATION,
                parameters={},
                missing_params=[],
                clarification_question=None,
                confidence=max(confidence, 0.75),
                modification_summary=current_text,
                free_text_input="",
            )

        if self._is_planning_request(current_text) or self._is_planning_followup(current_text, history_messages):
            params = self._extract_parameters(current_text, combined_text)
            free_text = self._extract_free_text_input(current_text)
            result = IntentAnalysisResult(
                intent_type=IntentType.TRIP_PLANNING,
                parameters=params,
                missing_params=[],
                clarification_question=None,
                confidence=max(confidence, 0.72),
                free_text_input=free_text,
            )
            if validate:
                self._validate_required_params(result)
            return result

        return IntentAnalysisResult(intent_type=IntentType.CHAT, confidence=confidence)

    def _is_modification_request(self, text: str) -> bool:
        if any(keyword in text for keyword in self.MODIFICATION_KEYWORDS):
            return True
        return bool(
            re.search(r"第[一二三四五六七八九十\d]+天.*(改|换|删|加|调整)", text)
            or re.search(r"(不要去|不想去).*(改|换|替|删|取消|调整)", text)
        )

    def _is_planning_request(self, text: str) -> bool:
        if self._is_single_info_query(text):
            return False
        if any(keyword in text for keyword in self.PLANNING_KEYWORDS):
            return True
        if any(verb in text for verb in self.PLANNING_VERBS):
            return True
        if self._extract_city(text) and self._extract_travel_days(text):
            return True
        return bool(re.search(r"(去|到).{0,12}(玩|旅游|旅行|度假)", text))

    def _is_single_info_query(self, text: str) -> bool:
        if not text:
            return False
        has_info_keyword = any(keyword in text for keyword in self.INFO_QUERY_KEYWORDS)
        if not has_info_keyword:
            return False
        has_planning_keyword = any(keyword in text for keyword in self.PLANNING_KEYWORDS)
        has_trip_days = self._extract_travel_days(text) is not None
        return not has_planning_keyword and not has_trip_days

    def _is_planning_followup(self, text: str, history_messages: List[Dict[str, str]]) -> bool:
        if not self._is_parameter_only_message(text):
            return False

        for msg in reversed(history_messages[-6:]):
            content = msg.get("content", "")
            if msg.get("role") == "assistant" and any(word in content for word in ("玩几天", "什么时候", "哪个城市", "目的地")):
                return True
            if msg.get("role") == "user" and self._is_planning_request(content):
                return True
        return False

    def _is_parameter_only_message(self, text: str) -> bool:
        compact = re.sub(r"[\s，。,.！!？?~～]", "", text or "")
        if not compact or len(compact) > 20 or self._is_single_info_query(compact):
            return False
        return bool(
            self._extract_city(compact)
            or self._extract_travel_days(compact)
            or self._extract_dates(compact)
            or self._extract_transportation(compact)
            or self._extract_accommodation(compact)
        )

    def _extract_parameters(self, current_text: str, combined_text: str) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        city = self._extract_city(current_text) or self._extract_city(combined_text)
        if city:
            params["city"] = city

        days = self._extract_travel_days(current_text)
        if days is None:
            days = self._extract_travel_days(combined_text)
        if days:
            params["travel_days"] = days

        dates = self._extract_dates(current_text) or self._extract_dates(combined_text)
        params.update(dates)

        if params.get("start_date") and params.get("travel_days") and not params.get("end_date"):
            try:
                start = datetime.strptime(params["start_date"], "%Y-%m-%d")
                end = start + timedelta(days=int(params["travel_days"]) - 1)
                params["end_date"] = end.strftime("%Y-%m-%d")
            except (TypeError, ValueError):
                pass

        transportation = self._extract_transportation(combined_text)
        if transportation:
            params["transportation"] = transportation

        accommodation = self._extract_accommodation(combined_text)
        if accommodation:
            params["accommodation"] = accommodation

        preferences = self._extract_preferences(combined_text)
        if preferences:
            params["preferences"] = preferences

        return params

    def _extract_free_text_input(self, text: str) -> str:
        """从用户输入中提取额外要求（去除结构化参数部分后的剩余内容）"""
        if not text:
            return ""

        # 要移除的关键词和模式
        patterns_to_remove = [
            # 规划相关关键词
            r"(?:帮我|请|帮|给我)?(?:规划|安排|做|弄|设计)?(?:一个|一份)?(?:行程|旅游计划|旅行计划|攻略)",
            r"(?:我想去|我打算去|我准备去|我计划去|我想|打算|准备|计划)?:?",
            r"(?:去|到)(?:玩|旅游|旅行|度假|自由行)",
            r"(?:多少|几|)(?:天|日|晚)(?:行程|旅游|旅行|度假|)?",
            r"(?:出发|到达|开始|结束|去|回)日期?",
            r"(?:住|住宿)(?:经济型|舒适型|五星级|豪华型|民宿|青年旅舍|酒店)?",
            r"(?:交通|出行)(?:方式)?(?:自驾|高铁|飞机|火车|公共交通)?",
            r"(?:景点|景色|风景)(?:偏好|喜欢|想要)?",
            r"(?:希望|想要|最好|想|要求|需要)",
            # 标点和空格
            r"^[，。,.！!？?\s]+",
            r"[，。,.！!？?\s]+$",
        ]

        result = text
        for pattern in patterns_to_remove:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)

        # 移除提取过的城市名
        city = self._extract_city(text)
        if city:
            result = result.replace(city, "")

        # 移除天数相关
        days = self._extract_travel_days(text)
        if days:
            result = re.sub(rf"{days}\s*(?:天|日)", "", result)
            result = re.sub(r"(?:三|两|二|一|四|五|六|七|八|九|十)\s*(?:天|日)", "", result)

        # 移除日期相关
        result = re.sub(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}(?:日|号)?", "", result)
        result = re.sub(r"\d{1,2}月\d{1,2}(?:日|号)?", "", result)
        result = re.sub(r"(?:明天|后天|大后天|下周|下下周|五一|国庆|春节)", "", result)

        # 清理多余空格
        result = re.sub(r"\s+", " ", result).strip()

        # 如果剩下的内容太短，可能只是语气词，返回空
        if len(result) < 2:
            return ""

        return result

    def _extract_city(self, text: str) -> Optional[str]:
        if not text:
            return None

        for city in sorted(self.CITY_CANDIDATES, key=len, reverse=True):
            if city in text:
                return city

        patterns = [
            r"(?:想去|打算去|准备去|计划去|去|到)([\u4e00-\u9fa5]{2,8}?)(?:玩|旅游|旅行|自由行|度假|怎么|如何|[一二两三四五六七八九十几半\d]+天|[，。,.！!？?\s]|$)",
            r"([\u4e00-\u9fa5]{2,8}?)(?:怎么玩|怎么安排|旅游攻略|旅行攻略|自由行|行程|[一二两三四五六七八九十\d]+日游)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                city = self._clean_city(match.group(1))
                if city:
                    return city
        return None

    def _clean_city(self, city: str) -> Optional[str]:
        city = re.sub(r"(旅游|旅行|自由行|攻略|行程|路线|玩|游)$", "", city.strip())
        invalid = {"帮我", "我想", "打算", "准备", "计划", "周末", "五一", "国庆", "明天", "后天"}
        if len(city) < 2 or city in invalid:
            return None
        return city

    def _extract_travel_days(self, text: str) -> Optional[int]:
        if not text or "几天" in text:
            return None
        if "半天" in text:
            return 1
        if "周末" in text:
            return 2
        if any(word in text for word in ("一周", "一星期", "一个星期")):
            return 7

        arabic_match = re.search(r"(\d{1,2})\s*(?:天|日)", text)
        if arabic_match:
            return int(arabic_match.group(1))

        chinese_match = re.search(r"([一二两三四五六七八九十]{1,3})\s*(?:天|日)", text)
        if chinese_match:
            return self._parse_chinese_number(chinese_match.group(1))

        return None

    def _normalize_days_value(self, value: Any) -> Optional[int]:
        if isinstance(value, int):
            return value if value > 0 else None
        if isinstance(value, float):
            return int(value) if value > 0 else None
        return self._extract_travel_days(str(value))

    def _parse_chinese_number(self, value: str) -> Optional[int]:
        digits = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
        if value == "十":
            return 10
        if "十" in value:
            left, _, right = value.partition("十")
            tens = digits.get(left, 1) if left else 1
            ones = digits.get(right, 0) if right else 0
            return tens * 10 + ones
        return digits.get(value)

    def _extract_dates(self, text: str) -> Dict[str, str]:
        if not text:
            return {}

        today = datetime.now()
        start_date: Optional[datetime] = None

        iso_match = re.search(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})", text)
        if iso_match:
            year, month, day = map(int, iso_match.groups())
            start_date = datetime(year, month, day)

        month_day_match = re.search(r"(?<!\d)(\d{1,2})月(\d{1,2})[日号]?", text)
        if not start_date and month_day_match:
            month, day = map(int, month_day_match.groups())
            year = today.year
            candidate = datetime(year, month, day)
            if candidate.date() < today.date():
                candidate = datetime(year + 1, month, day)
            start_date = candidate

        relative_days = [("大后天", 3), ("后天", 2), ("明天", 1), ("今天", 0)]
        for keyword, offset in relative_days:
            if not start_date and keyword in text:
                start_date = today + timedelta(days=offset)
                break

        if not start_date and "下周末" in text:
            next_monday = today + timedelta(days=7 - today.weekday())
            start_date = next_monday + timedelta(days=5)
        elif not start_date and "周末" in text:
            start_date = self._next_weekday(today, 5, include_today=True)
        elif not start_date and "下周" in text:
            start_date = today + timedelta(days=7 - today.weekday())

        holiday_map = {"五一": (5, 1), "劳动节": (5, 1), "国庆": (10, 1)}
        for keyword, (month, day) in holiday_map.items():
            if not start_date and keyword in text:
                candidate = datetime(today.year, month, day)
                if candidate.date() < today.date():
                    candidate = datetime(today.year + 1, month, day)
                start_date = candidate
                break

        return {"start_date": start_date.strftime("%Y-%m-%d")} if start_date else {}

    def _normalize_date_value(self, value: Any) -> Optional[str]:
        text = str(value).strip()
        if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", text):
            return text
        return self._extract_dates(text).get("start_date")

    def _next_weekday(self, start: datetime, weekday: int, include_today: bool) -> datetime:
        days_ahead = weekday - start.weekday()
        if days_ahead < 0 or (days_ahead == 0 and not include_today):
            days_ahead += 7
        return start + timedelta(days=days_ahead)

    def _extract_transportation(self, text: str) -> Optional[str]:
        mapping = {
            "自驾": "自驾",
            "开车": "自驾",
            "高铁": "高铁",
            "动车": "高铁",
            "飞机": "飞机",
            "火车": "火车",
            "公共交通": "公共交通",
            "地铁": "公共交通",
        }
        for keyword, value in mapping.items():
            if keyword in text:
                return value
        return None

    def _extract_accommodation(self, text: str) -> Optional[str]:
        mapping = {
            "五星": "五星级",
            "豪华": "豪华型",
            "舒适": "舒适型",
            "经济": "经济型",
            "青旅": "青年旅舍",
            "民宿": "民宿",
            "酒店": "酒店",
        }
        for keyword, value in mapping.items():
            if keyword in text:
                return value
        return None

    def _extract_preferences(self, text: str) -> List[str]:
        preferences = []
        mapping = [
            (("历史", "文化", "博物馆", "古镇"), "历史文化"),
            (("自然", "山水", "爬山", "森林", "海边"), "自然景观"),
            (("美食", "小吃", "吃"), "美食"),
            (("亲子", "孩子", "儿童"), "亲子"),
            (("小众", "人少"), "小众"),
            (("夜景", "夜市"), "夜游"),
        ]
        for keywords, value in mapping:
            if any(keyword in text for keyword in keywords) and value not in preferences:
                preferences.append(value)
        return preferences

    def _validate_required_params(self, result: IntentAnalysisResult):
        """验证必要参数，更新缺失列表和追问问题"""
        # 检查 city
        if not result.parameters.get("city"):
            if "city" not in result.missing_params:
                result.missing_params.insert(0, "city")
            if not result.clarification_question:
                result.clarification_question = "你想去哪个城市旅游呢？"
            logger.info(f"_validate_required_params: 缺少 city，设置追问")
            return

        # 如果有 city，检查天数或完整日期范围
        has_start_date = result.parameters.get("start_date")
        has_end_date = result.parameters.get("end_date")
        has_date_range = has_start_date and has_end_date
        has_days = result.parameters.get("travel_days")

        logger.info(
            f"_validate_required_params: city={result.parameters.get('city')}, "
            f"has_start_date={has_start_date}, has_end_date={has_end_date}, has_days={has_days}"
        )

        if not has_days and not has_date_range:
            # 缺少日期或天数，需要追问
            if not result.missing_params:
                result.missing_params = ["travel_days", "start_date"]
            if not result.clarification_question:
                # 更自然的追问
                city = result.parameters['city']
                result.clarification_question = f"好的！{city}是个很棒的目的地～你打算去玩几天，或者计划什么时候出发呢？"
            logger.info(f"_validate_required_params: 缺少日期/天数，设置追问: {result.clarification_question}")
        else:
            # 已有必要参数，清空缺失列表和追问问题
            result.missing_params = []
            result.clarification_question = None
            logger.info(f"_validate_required_params: 参数完整")


# 单例实例
_trip_intent_agent_instance: Optional[TripIntentAgent] = None


def get_trip_intent_agent() -> TripIntentAgent:
    """获取 TripIntentAgent 单例"""
    global _trip_intent_agent_instance
    if _trip_intent_agent_instance is None:
        _trip_intent_agent_instance = TripIntentAgent()
    return _trip_intent_agent_instance
