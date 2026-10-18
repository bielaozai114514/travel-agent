from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Dict, Any
from functools import lru_cache


class AgentConfig:
    """Agent 配置封装，支持 fallback 到默认配置"""

    def __init__(
        self,
        settings: "Settings",
        agent_type: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        timeout: Optional[int] = None,
    ):
        self._settings = settings
        self._agent_type = agent_type
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._temperature = temperature
        self._timeout = timeout

    @property
    def api_key(self) -> str:
        return self._api_key or self._settings.MODEL_API_KEY

    @property
    def base_url(self) -> str:
        return self._base_url or self._settings.MODEL_BASE_URL

    @property
    def model(self) -> str:
        return self._model or self._settings.MODEL_NAME

    @property
    def temperature(self) -> float:
        return self._temperature if self._temperature is not None else 0.7

    @property
    def timeout(self) -> int:
        return self._timeout or 120

    def to_dict(self) -> Dict[str, Any]:
        return {
            "api_key": self.api_key,
            "base_url": self.base_url,
            "model": self.model,
            "temperature": self.temperature,
            "timeout": self.timeout,
        }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,  # 环境变量大小写敏感
        extra="ignore"  # 忽略多余环境变量, 主要是与EsAgent需要的环境变量分离
    )

    # uvicorn 
    BACKEND_HOST: str
    BACKEND_PORT: int
    RELOAD: bool = True
    WORKERS: int = 3
    LIMIT_CONCURRENCY: int = 100
    BACKLOG: int = 2048
    TIMEOUT_KEEP_ALIVE: int = 5

    # MySQL
    MYSQL_URL: str

    # 是否为测试环境
    TEST_ENV: bool
    MYSQL_TEST_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 360

    # 高德地图 API
    AMAP_API_KEY: str = ""

    # Qdrant 向量数据库配置
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_URL: str = ""  # 如果设置了，优先用这个
    QDRANT_BASIC_COLLECTION_NAME: str = "travel_guides_basic_chunks"  # 基础向量 collection（仅 chunk.content）

    # RAG 配置
    RAG_SEARCH_MODE: str = "adaptive_tcr"  # RAG 搜索策略: adaptive_tcr | tcr | enhanced_vector | basic_vector | llm_rag
    RAG_USE_LLM_OPTIMIZATION: bool = True
    RAG_LLM_TEMPERATURE: float = 0.3
    RAG_QUERY_REWRITE_ENABLED: bool = True
    RAG_KEYWORD_EXTRACTION_ENABLED: bool = True
    RAG_CACHE_ENABLED: bool = True
    RAG_CACHE_TTL_SECONDS: int = 3600  # 缓存1小时

    # ========== TCR-RAG 配置 ==========
    TCR_ENABLED: bool = True  # 启用TCR-RAG算法（False则回退到旧逻辑）
    TCR_CANDIDATE_K: int = 25  # 每路查询召回的候选数量
    TCR_RERANKER_ENABLED: bool = False  # 是否启用reranker精排
    TCR_RERANKER_MODEL_PATH: str = "models/bge-reranker-base"  # reranker本地模型路径
    TCR_SCORE_WEIGHTS: str = "0.50,0.15,0.12,0.10,0.08,0.03,0.02"
    # 权重顺序: vector, city, tag, keyword, hit, section, official
    TCR_SCORE_WEIGHTS_RERANK: str = "0.55,0.20,0.10,0.06,0.04,0.03,0.02"
    # 权重顺序: rerank, vector, city, tag, keyword, hit, official
    TCR_MIN_VECTOR_SCORE: float = 0.3  # 最低向量相似度阈值
    TCR_MAX_CHUNKS_PER_GUIDE: int = 2  # 同一攻略最多返回chunk数
    TCR_CONTENT_TRUNCATE_LENGTH: int = 500  # 返回内容截断长度
    TCR_STORE_EMBED_CONTENT: bool = False  # 是否在metadata中保存完整的embed_content

    # ========== Planner prompt 各区域字符上限 ==========
    PLANNER_RAG_MAX_CHARS: int = 6000       # 攻略检索依据（信息密度最高）
    PLANNER_ATTRACTION_MAX_CHARS: int = 3000  # 候选景点（紧凑格式化后够用）
    PLANNER_HOTEL_MAX_CHARS: int = 2000       # 候选酒店/区域
    PLANNER_WEATHER_MAX_CHARS: int = 1500     # 天气信息
    PLANNER_KEY_FACTS_MAX_CHARS: int = 1500   # RAG 提取的关键事实（票价/避坑）

    # ========== 上下文管理器配置 ==========
    # 最大Token数（根据使用的模型调整）
    CONTEXT_MAX_TOKENS: int = 8000
    # 预留给System Prompt的Token数
    CONTEXT_RESERVED_TOKENS: int = 1500
    # 安全边际Token数（防止接近上限）
    CONTEXT_SAFETY_MARGIN: int = 500

    # ========== 默认 LLM 配置 ==========
    MODEL_API_KEY: str
    MODEL_BASE_URL: str = "https://api.siliconflow.cn/v1"
    MODEL_NAME: str = "Qwen/Qwen3-8B"
    MODEL_TEMPERATURE: float = 0.7
    MODEL_TIMEOUT: int = 120

    # ========== 各 Agent 特定配置（可选，不设置则用默认） ==========
    # 聊天助手 Agent
    CHAT_AGENT_API_KEY: Optional[str] = None
    CHAT_AGENT_BASE_URL: Optional[str] = None
    CHAT_AGENT_MODEL: Optional[str] = None
    CHAT_AGENT_TEMPERATURE: Optional[float] = None
    CHAT_AGENT_TIMEOUT: Optional[int] = None

    # 景点搜索 Agent
    ATTRACTION_AGENT_API_KEY: Optional[str] = None
    ATTRACTION_AGENT_BASE_URL: Optional[str] = None
    ATTRACTION_AGENT_MODEL: Optional[str] = None
    ATTRACTION_AGENT_TEMPERATURE: Optional[float] = None
    ATTRACTION_AGENT_TIMEOUT: Optional[int] = None

    # 天气查询 Agent
    WEATHER_AGENT_API_KEY: Optional[str] = None
    WEATHER_AGENT_BASE_URL: Optional[str] = None
    WEATHER_AGENT_MODEL: Optional[str] = None
    WEATHER_AGENT_TEMPERATURE: Optional[float] = None
    WEATHER_AGENT_TIMEOUT: Optional[int] = None

    # 酒店推荐 Agent
    HOTEL_AGENT_API_KEY: Optional[str] = None
    HOTEL_AGENT_BASE_URL: Optional[str] = None
    HOTEL_AGENT_MODEL: Optional[str] = None
    HOTEL_AGENT_TEMPERATURE: Optional[float] = None
    HOTEL_AGENT_TIMEOUT: Optional[int] = None

    # 攻略专家 Agent
    GUIDE_EXPERT_AGENT_API_KEY: Optional[str] = None
    GUIDE_EXPERT_AGENT_BASE_URL: Optional[str] = None
    GUIDE_EXPERT_AGENT_MODEL: Optional[str] = None
    GUIDE_EXPERT_AGENT_TEMPERATURE: Optional[float] = None
    GUIDE_EXPERT_AGENT_TIMEOUT: Optional[int] = None

    # 行程规划 Agent
    PLANNER_AGENT_API_KEY: Optional[str] = None
    PLANNER_AGENT_BASE_URL: Optional[str] = None
    PLANNER_AGENT_MODEL: Optional[str] = None
    PLANNER_AGENT_TEMPERATURE: Optional[float] = None
    PLANNER_AGENT_TIMEOUT: Optional[int] = None

    # 意图识别 Agent
    INTENT_AGENT_API_KEY: Optional[str] = None
    INTENT_AGENT_BASE_URL: Optional[str] = None
    INTENT_AGENT_MODEL: Optional[str] = None
    INTENT_AGENT_TEMPERATURE: Optional[float] = None
    INTENT_AGENT_TIMEOUT: Optional[int] = None

    def get_agent_config(self, agent_type: str) -> AgentConfig:
        """
        获取指定类型 Agent 的配置

        Args:
            agent_type: Agent 类型，如 "chat", "attraction", "weather", "hotel", "guide_expert", "planner"

        Returns:
            AgentConfig 实例
        """
        config_map = {
            "chat": (
                self.CHAT_AGENT_API_KEY,
                self.CHAT_AGENT_BASE_URL,
                self.CHAT_AGENT_MODEL,
                self.CHAT_AGENT_TEMPERATURE,
                self.CHAT_AGENT_TIMEOUT,
            ),
            "attraction": (
                self.ATTRACTION_AGENT_API_KEY,
                self.ATTRACTION_AGENT_BASE_URL,
                self.ATTRACTION_AGENT_MODEL,
                self.ATTRACTION_AGENT_TEMPERATURE,
                self.ATTRACTION_AGENT_TIMEOUT,
            ),
            "weather": (
                self.WEATHER_AGENT_API_KEY,
                self.WEATHER_AGENT_BASE_URL,
                self.WEATHER_AGENT_MODEL,
                self.WEATHER_AGENT_TEMPERATURE,
                self.WEATHER_AGENT_TIMEOUT,
            ),
            "hotel": (
                self.HOTEL_AGENT_API_KEY,
                self.HOTEL_AGENT_BASE_URL,
                self.HOTEL_AGENT_MODEL,
                self.HOTEL_AGENT_TEMPERATURE,
                self.HOTEL_AGENT_TIMEOUT,
            ),
            "guide_expert": (
                self.GUIDE_EXPERT_AGENT_API_KEY,
                self.GUIDE_EXPERT_AGENT_BASE_URL,
                self.GUIDE_EXPERT_AGENT_MODEL,
                self.GUIDE_EXPERT_AGENT_TEMPERATURE,
                self.GUIDE_EXPERT_AGENT_TIMEOUT,
            ),
            "planner": (
                self.PLANNER_AGENT_API_KEY,
                self.PLANNER_AGENT_BASE_URL,
                self.PLANNER_AGENT_MODEL,
                self.PLANNER_AGENT_TEMPERATURE,
                self.PLANNER_AGENT_TIMEOUT,
            ),
            "intent": (
                self.INTENT_AGENT_API_KEY,
                self.INTENT_AGENT_BASE_URL,
                self.INTENT_AGENT_MODEL,
                self.INTENT_AGENT_TEMPERATURE,
                self.INTENT_AGENT_TIMEOUT,
            ),
        }

        api_key, base_url, model, temperature, timeout = config_map.get(
            agent_type, (None, None, None, None, None)
        )

        return AgentConfig(
            settings=self,
            agent_type=agent_type,
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            timeout=timeout,
        )


@lru_cache()
def get_settings() -> Settings:
    """获取 Settings 单例"""
    return Settings()


settings = get_settings()