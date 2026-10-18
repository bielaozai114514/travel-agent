"""
攻略知识抽取器 - 将非结构化攻略文本转换为结构化知识图谱
这是反思型多智能体协作框架（RMCAF）的核心组件之一
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from core.logger import logger
from settings import settings


class GuideKnowledgeExtractor:
    """
    攻略知识抽取器

    负责将非结构化的旅游攻略文本，转换为结构化的"决策知识图谱"。
    这是理论创新点之一：从"文本检索"升级到"决策知识检索"。
    """

    def __init__(self, llm=None):
        self.llm = llm
        logger.info("[GuideKnowledgeExtractor] 攻略知识抽取器初始化完成")

    def extract_knowledge_sync(self, guide_content: str, city: str = "") -> Dict[str, Any]:
        """
        同步抽取攻略知识（简化版，用于演示）

        Args:
            guide_content: 攻略文本内容
            city: 城市名称

        Returns:
            结构化的知识图谱
        """
        logger.info(f"[GuideKnowledgeExtractor] 开始抽取攻略知识，城市: {city}")

        # 简化版：使用启发式规则抽取知识（演示用）
        # 实际生产环境应该使用LLM进行抽取

        knowledge = {
            "city": city,
            "extraction_time": datetime.now().isoformat(),
            "version": "1.0",
            "attractions": self._extract_attractions_heuristic(guide_content, city),
            "itinerary_patterns": self._extract_patterns_heuristic(guide_content, city),
            "common_mistakes": self._extract_mistakes_heuristic(guide_content),
            "tips": self._extract_tips_heuristic(guide_content),
        }

        logger.info(f"[GuideKnowledgeExtractor] 知识抽取完成，景点数: {len(knowledge['attractions'])}")
        return knowledge

    def _extract_attractions_heuristic(self, content: str, city: str) -> List[Dict]:
        """启发式抽取景点信息（演示用）"""
        attractions = []

        # 常见景点库（简化版）
        city_attractions = {
            "杭州": [
                {"name": "西湖", "category": "自然景观", "ticket_price": "0元", "best_time": "08:00-10:00"},
                {"name": "灵隐寺", "category": "历史文化", "ticket_price": "75元", "best_time": "07:30-09:00"},
                {"name": "西溪湿地", "category": "自然景观", "ticket_price": "80元", "best_time": "全天"},
                {"name": "宋城", "category": "娱乐", "ticket_price": "310元", "best_time": "下午+晚上"},
            ],
            "北京": [
                {"name": "故宫", "category": "历史文化", "ticket_price": "60元", "best_time": "08:30-10:00"},
                {"name": "长城", "category": "历史文化", "ticket_price": "45元", "best_time": "上午"},
                {"name": "颐和园", "category": "园林", "ticket_price": "30元", "best_time": "全天"},
            ],
            "上海": [
                {"name": "外滩", "category": "城市景观", "ticket_price": "0元", "best_time": "晚上"},
                {"name": "迪士尼", "category": "主题乐园", "ticket_price": "475元", "best_time": "全天"},
                {"name": "豫园", "category": "历史文化", "ticket_price": "40元", "best_time": "上午"},
            ]
        }

        # 根据城市返回预设景点（演示用）
        if city in city_attractions:
            for attr in city_attractions[city]:
                # 添加一些通用的反思提示
                attr["tips"] = [
                    f"建议早上去，人少景美",
                    f"周末人流量大，建议错峰出行"
                ]
                attr["common_mistakes"] = [
                    f"不要在景点周边吃饭，价格贵且不正宗",
                    f"建议提前查看开放时间"
                ]
                attractions.append(attr)

        return attractions

    def _extract_patterns_heuristic(self, content: str, city: str) -> List[Dict]:
        """启发式抽取出行模式（演示用）"""
        patterns = []

        # 预设的经典行程模式
        city_patterns = {
            "杭州": [
                {
                    "days": 3,
                    "pattern": "D1: 西湖周边（断桥、白堤、苏堤、雷峰塔）→ D2: 灵隐寺+宋城 → D3: 西溪湿地",
                    "suitable_for": "亲子游、情侣游、家庭游"
                }
            ],
            "北京": [
                {
                    "days": 3,
                    "pattern": "D1: 天安门+故宫+景山 → D2: 长城+鸟巢水立方 → D3: 颐和园+圆明园",
                    "suitable_for": "首次来京、历史文化爱好者"
                }
            ]
        }

        if city in city_patterns:
            patterns.extend(city_patterns[city])

        return patterns

    def _extract_mistakes_heuristic(self, content: str) -> List[str]:
        """启发式抽取常见错误（演示用）"""
        mistakes = []

        # 查找常见的警告词
        mistake_keywords = [
            ("不要", "不建议"),
            ("别去", "避免"),
            ("坑", "雷"),
            ("注意", "提醒"),
            ("提前", "务必"),
        ]

        # 预设的通用常见错误
        common_mistakes = [
            "周末热门景点人流量大，建议工作日或早上前往",
            "不要在景区周边的餐馆吃饭，价格贵且不正宗",
            "热门景点建议提前在网上预约购票",
            "注意查看景区的开放时间，有些景点周一闭馆",
            "出行前查看天气预报，合理安排行程"
        ]

        return common_mistakes

    def _extract_tips_heuristic(self, content: str) -> List[str]:
        """启发式抽取建议（演示用）"""
        tips = []

        # 预设的通用建议
        common_tips = [
            "早上是游览热门景点的最佳时间，人少景美",
            "地铁是城市内出行的首选方式，方便快捷不堵车",
            "建议穿着舒适的鞋子，旅行需要走很多路",
            "带上充电宝，拍照导航很费电",
            "准备一些常用药品，以备不时之需"
        ]

        return common_tips

    async def extract_knowledge_with_llm(self, guide_content: str, city: str = "") -> Dict[str, Any]:
        """
        使用LLM抽取攻略知识（完整版）

        Args:
            guide_content: 攻略文本内容
            city: 城市名称

        Returns:
            结构化的知识图谱
        """
        if not self.llm:
            logger.warning("[GuideKnowledgeExtractor] 未配置LLM，使用启发式抽取")
            return self.extract_knowledge_sync(guide_content, city)

        logger.info(f"[GuideKnowledgeExtractor] 使用LLM抽取攻略知识，城市: {city}")

        extraction_prompt = self._build_extraction_prompt(guide_content, city)

        try:
            response = await self.llm.ainvoke([
                {"role": "system", "content": "你是专业的旅游知识抽取专家。请从给定的旅游攻略中抽取出结构化的知识图谱。输出格式：严格按照JSON格式输出，不要有其他文本。"},
                {"role": "user", "content": extraction_prompt}
            ])

            # 解析LLM返回的JSON
            knowledge = self._parse_llm_response(response)
            knowledge["city"] = city
            knowledge["extraction_time"] = datetime.now().isoformat()

            logger.info(f"[GuideKnowledgeExtractor] LLM知识抽取完成")
            return knowledge

        except Exception as e:
            logger.error(f"[GuideKnowledgeExtractor] LLM抽取失败: {e}，使用启发式抽取")
            return self.extract_knowledge_sync(guide_content, city)

    def _build_extraction_prompt(self, content: str, city: str) -> str:
        """构建知识抽取的提示词"""
        return f"""
请从以下旅游攻略中抽取出结构化的知识图谱。

城市：{city}

攻略内容：
{content[:8000]}

请提取以下信息：

1. 景点列表（attractions）：
   - 景点名称
   - 类别（自然景观/历史文化/娱乐/美食等）
   - 门票价格
   - 最佳游玩时间
   - 建议（tips）
   - 常见错误（common_mistakes）- 这是最重要的反思依据！

2. 行程模式（itinerary_patterns）：
   - 天数
   - 具体安排（每天去哪）
   - 适合人群

3. 常见错误（common_mistakes）：
   - 攻略中提到的"不要做"、"注意"、"雷区"等

4. 实用建议（tips）：
   - 交通建议
   - 住宿建议
   - 美食建议
   - 其他

输出格式：严格按照JSON格式输出，不要有其他解释文字。
"""

    def _parse_llm_response(self, response: str) -> Dict:
        """解析LLM返回的JSON"""
        try:
            # 尝试直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            # 尝试提取JSON部分
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
                return json.loads(json_str)
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                json_str = response[start:end].strip()
                return json.loads(json_str)
            else:
                # 尝试找到第一个{和最后一个}
                start = response.find("{")
                end = response.rfind("}") + 1
                json_str = response[start:end]
                return json.loads(json_str)


# 单例
_extractor_instance: Optional[GuideKnowledgeExtractor] = None


def get_guide_knowledge_extractor(llm=None) -> GuideKnowledgeExtractor:
    """获取攻略知识抽取器单例"""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = GuideKnowledgeExtractor(llm)
    return _extractor_instance
