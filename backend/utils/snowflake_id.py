"""
雪花ID生成器
使用snowflake-id库生成分布式唯一ID
"""
from snowflake import SnowflakeGenerator
import time


class SnowflakeIDGenerator:
    """雪花ID生成器类"""
    
    _instance = None
    _generator = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, instance_id: int = 1):
        """
        初始化雪花ID生成器
        
        Args:
            instance_id: 实例ID，取值范围0-1023，用于区分不同的服务实例
        """
        if self._generator is None:
            self._generator = SnowflakeGenerator(instance_id)
    
    def generate_id(self) -> int:
        """
        生成一个雪花ID
        
        Returns:
            int: 64位的雪花ID
        """
        return next(self._generator)
    
    @staticmethod
    def get_id() -> int:
        """
        静态方法：获取一个雪花ID
        
        Returns:
            int: 64位的雪花ID
        """
        if SnowflakeIDGenerator._instance is None:
            SnowflakeIDGenerator._instance = SnowflakeIDGenerator()
        return SnowflakeIDGenerator._instance.generate_id()


snowflake_generator = SnowflakeIDGenerator(instance_id=1)


def generate_snowflake_id() -> int:
    """
    生成雪花ID的便捷函数
    
    Returns:
        int: 64位的雪花ID
    """
    return snowflake_generator.generate_id()
