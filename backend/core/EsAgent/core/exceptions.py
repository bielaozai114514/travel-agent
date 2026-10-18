"""异常体系"""

class EsAgentException(Exception):
    """HelloAgents基础异常类"""
    pass

class LLMException(EsAgentException):
    """LLM相关异常"""
    pass

class AgentException(EsAgentException):
    """Agent相关异常"""
    pass

class ConfigException(EsAgentException):
    """配置相关异常"""
    pass

class ToolException(EsAgentException):
    """工具相关异常"""
    pass
