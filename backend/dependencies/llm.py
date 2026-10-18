from core.agent import get_esagent_service
from core.EsAgent import EsAgentLLM


def get_esagent_llm() -> EsAgentLLM:
    service = get_esagent_service()
    return service.llm


_esagent_service_instance = None


def get_esagent_service_instance():
    global _esagent_service_instance
    if _esagent_service_instance is None:
        _esagent_service_instance = get_esagent_service()
    return _esagent_service_instance