"""
协议工具集合

提供基于协议实现的工具接口：
- MCP Tool: 基于 fastmcp 库，用于连接和调用 MCP 服务器 采用后台常驻异步事件循环模式
"""

from typing import Dict, Any, List, Optional
from ..base import Tool, ToolParameter
import os
import asyncio
import threading
import concurrent.futures
from ...protocols import MCPClient

# MCP服务器环境变量映射表
# 用于自动检测常见MCP服务器需要的环境变量
MCP_SERVER_ENV_MAP = {
    "server-github": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
    "server-slack": ["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"],
    "server-google-drive": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"],
    "server-postgres": ["POSTGRES_CONNECTION_STRING"],
    "server-sqlite": [],  # 不需要环境变量
    "server-filesystem": [],  # 不需要环境变量
}


class MCPTool(Tool):
    """MCP (Model Context Protocol) 工具（单例模式 + 惰性初始化）

    连接到 MCP 服务器并调用其提供的工具、资源和提示词。

    功能：
    - 列出服务器提供的工具
    - 调用服务器工具
    - 读取服务器资源
    - 获取提示词模板

    使用示例:
        >>> from tools.builtin import MCPTool
        >>>
        >>> # 方式1: 获取单例（推荐）
        >>> tool = MCPTool.get_or_create(server_command=["python", "examples/mcp_example.py"])
        >>> result = tool.run({"action": "list_tools"})

    注意：使用 fastmcp 库，已包含在依赖中
    """

    # ========== 单例管理 ==========
    _instances: Dict[str, 'MCPTool'] = {}
    _instance_lock = threading.Lock()

    @classmethod
    def get_or_create(cls,
                     name: str = "mcp",
                     description: Optional[str] = None,
                     server_command: Optional[List[str]] = None,
                     server_args: Optional[List[str]] = None,
                     server: Optional[Any] = None,
                     auto_expand: bool = True,
                     env: Optional[Dict[str, str]] = None,
                     env_keys: Optional[List[str]] = None) -> 'MCPTool':
        """
        获取或创建 MCPTool 单例

        Args:
            与 __init__ 参数相同

        Returns:
            MCPTool 单例实例
        """
        # 用 server_command 做 hash key
        key = cls._get_instance_key(name, server_command, server)

        with cls._instance_lock:
            if key not in cls._instances:
                cls._instances[key] = MCPTool(
                    name=name,
                    description=description,
                    server_command=server_command,
                    server_args=server_args,
                    server=server,
                    auto_expand=auto_expand,
                    env=env,
                    env_keys=env_keys
                )
            return cls._instances[key]

    @classmethod
    def _get_instance_key(cls, name: str, server_command: Optional[List[str]], server: Optional[Any]) -> str:
        """生成单例实例的key"""
        if server:
            # 使用server对象的id作为key
            return f"{name}:server:{id(server)}"
        elif server_command:
            return f"{name}:{':'.join(server_command)}"
        else:
            return name

    # ========== 实例方法 ==========

    def __init__(self,
                 name: str = "mcp",
                 description: Optional[str] = None,
                 server_command: Optional[List[str]] = None,
                 server_args: Optional[List[str]] = None,
                 server: Optional[Any] = None,
                 auto_expand: bool = True,
                 env: Optional[Dict[str, str]] = None,
                 env_keys: Optional[List[str]] = None):
        """
        初始化 MCP 工具（惰性初始化：不在 __init__ 中启动后台循环）

        注意：建议使用 get_or_create() 获取单例，而不是直接实例化
        """
        self.server_command = server_command
        self.server_args = server_args or []
        self.server = server
        self._client = None
        self._client_context = None
        self._available_tools = []
        self.auto_expand = auto_expand
        self.prefix = f"{name}_" if auto_expand else ""
        self._description = description

        # 持久化连接相关（惰性初始化）
        self._loop = None
        self._thread = None
        self._loop_ready = threading.Event()
        self._client_lock = threading.Lock()
        self._initialization_lock = threading.Lock()  # 初始化锁
        self._initialized = False  # 是否已初始化
        self._client_initialized = False
        self._shutdown_flag = False

        # 环境变量处理（优先级：env > env_keys > 自动检测）
        self.env = self._prepare_env(env, env_keys, server_command)

        # 如果没有指定任何服务器，抛出错误
        if not server_command and not server:
            raise ValueError("MCPTool 必须指定 server_command 或 server 参数")

        # 注意：不再在 __init__ 中启动后台循环和发现工具
        # 改为惰性初始化，第一次使用时才执行

        super().__init__(
            name=name,
            description=description or "MCP工具（待初始化）"
        )

    def _ensure_initialized(self):
        """确保已初始化（第一次使用时才执行）"""
        if self._initialized:
            return

        with self._initialization_lock:
            if self._initialized:
                return

            print("🔧 MCPTool 惰性初始化中...")
            # 启动后台事件循环
            self._start_background_loop()
            # 自动发现工具
            self._discover_tools()
            # 设置默认描述或自动生成
            if self._description is None:
                self._description = self._generate_description()
                self.description = self._description

            self._initialized = True
            print("✅ MCPTool 初始化完成")
    
    def _start_background_loop(self):
        """在后台线程中启动事件循环"""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop_ready.set()
            
            try:
                self._loop.run_forever()
            finally:
                self._loop.close()
        
        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()
        self._loop_ready.wait()
    
    def _run_async(self, coro):
        """在后台事件循环中运行异步函数"""
        with self._client_lock:
            if self._shutdown_flag:
                raise RuntimeError("Client has been shutdown")
            
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            return future.result()
    
    async def _ensure_client_connected(self):
        """确保客户端已连接，如果没有则建立连接"""
        if self._client is None or self._client_context is None:
            print("🔗 建立持久化 MCP 连接...")
            client_source = self.server if self.server else self.server_command
            self._client = MCPClient(client_source, self.server_args, env=self.env)
            self._client_context = await self._client.__aenter__()
            print("✅ 持久化连接已建立")
        else:
            # 检查连接是否正常
            try:
                is_connected = await self._client.ping()
                if not is_connected:
                    print("⚠️ 检测到连接异常，正在重新建立连接...")
                    await self._close_client()
                    await self._ensure_client_connected()
            except Exception as e:
                print(f"⚠️ 连接检查失败，正在重新建立连接: {e}")
                await self._close_client()
                await self._ensure_client_connected()
    
    async def _close_client(self):
        """关闭客户端连接"""
        if self._client_context is not None:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception as e:
                print(f"⚠️ 关闭连接时出错: {e}")
            finally:
                self._client_context = None
                self._client = None
    
    def close(self):
        """手动关闭连接并清理资源"""
        with self._client_lock:
            if not self._shutdown_flag:
                self._shutdown_flag = True
                if self._loop and self._loop.is_running():
                    try:
                        future = asyncio.run_coroutine_threadsafe(self._close_client(), self._loop)
                        future.result(timeout=2.0)
                    except Exception as e:
                        print(f"⚠️ 关闭连接时出错: {e}")
                    finally:
                        self._loop.call_soon_threadsafe(self._loop.stop)
                if self._thread:
                    self._thread.join(timeout=2.0)
                print("🔌 MCP 连接已关闭")
    
    def __del__(self):
        """析构函数，确保资源被清理"""
        try:
            self.close()
        except:
            pass

    def _prepare_env(self,
                     env: Optional[Dict[str, str]],
                     env_keys: Optional[List[str]],
                     server_command: Optional[List[str]]) -> Dict[str, str]:
        """
        准备环境变量

        优先级：env > env_keys > 自动检测

        Args:
            env: 直接传递的环境变量字典
            env_keys: 要从系统环境变量加载的key列表
            server_command: 服务器命令（用于自动检测）

        Returns:
            合并后的环境变量字典
        """
        result_env = {}

        # 1. 自动检测（优先级最低）
        if server_command:
            # 从命令中提取服务器名称
            server_name = None
            for part in server_command:
                if "server-" in part:
                    # 提取类似 "@modelcontextprotocol/server-github" 中的 "server-github"
                    server_name = part.split("/")[-1] if "/" in part else part
                    break

            # 查找映射表
            if server_name and server_name in MCP_SERVER_ENV_MAP:
                auto_keys = MCP_SERVER_ENV_MAP[server_name]
                for key in auto_keys:
                    value = os.getenv(key)
                    if value:
                        result_env[key] = value
                        print(f"🔑 自动加载环境变量: {key}")

        # 2. env_keys指定的环境变量（优先级中等）
        if env_keys:
            for key in env_keys:
                value = os.getenv(key)
                if value:
                    result_env[key] = value
                    print(f"🔑 从env_keys加载环境变量: {key}")
                else:
                    print(f"⚠️  警告: 环境变量 {key} 未设置")

        # 3. 直接传递的env（优先级最高）
        if env:
            result_env.update(env)
            for key in env.keys():
                print(f"🔑 使用直接传递的环境变量: {key}")

        return result_env

    def _discover_tools(self):
        """发现MCP服务器提供的所有工具"""
        try:
            async def discover():
                await self._ensure_client_connected()
                tools = await self._client.list_tools()
                return tools

            # 运行异步发现
            self._available_tools = self._run_async(discover())

        except Exception as e:
            # 工具发现失败不影响初始化
            print(f"⚠️ 工具发现失败: {e}")
            self._available_tools = []

    def _generate_description(self) -> str:
        """生成增强的工具描述"""
        if not self._available_tools:
            return "连接到 MCP 服务器，调用工具、读取资源和获取提示词。支持内置服务器和外部服务器。"

        if self.auto_expand:
            # 展开模式：简单描述
            return f"MCP工具服务器，包含{len(self._available_tools)}个工具。这些工具会自动展开为独立的工具供Agent使用。"
        else:
            # 非展开模式：详细描述
            desc_parts = [
                f"MCP工具服务器，提供{len(self._available_tools)}个工具："
            ]

            # 列出所有工具
            for tool in self._available_tools:
                tool_name = tool.get('name', 'unknown')
                tool_desc = tool.get('description', '无描述')
                # 简化描述，只取第一句
                short_desc = tool_desc.split('.')[0] if tool_desc else '无描述'
                desc_parts.append(f"  • {tool_name}: {short_desc}")

            # 添加调用格式说明
            desc_parts.append("\n调用格式：返回JSON格式的参数")
            desc_parts.append('{"action": "call_tool", "tool_name": "工具名", "arguments": {...}}')

            # 添加示例
            if self._available_tools:
                first_tool = self._available_tools[0]
                tool_name = first_tool.get('name', 'example')
                desc_parts.append(f'\n示例：{{"action": "call_tool", "tool_name": "{tool_name}", "arguments": {{...}}}}')

            return "\n".join(desc_parts)

    def get_expanded_tools(self) -> List['Tool']:  # type: ignore
        """
        获取展开的工具列表

        将MCP服务器的每个工具包装成独立的Tool对象

        Returns:
            Tool对象列表
        """
        # 惰性初始化（需要先获取工具列表）
        self._ensure_initialized()

        if not self.auto_expand:
            return []

        from .mcp_wrapper_tool import MCPWrappedTool

        expanded_tools = []
        for tool_info in self._available_tools:
            wrapped_tool = MCPWrappedTool(
                mcp_tool=self,
                tool_info=tool_info,
                prefix=self.prefix
            )
            expanded_tools.append(wrapped_tool)

        return expanded_tools

    def run(self, parameters: Dict[str, Any]) -> str:
        """
        执行 MCP 操作

        Args:
            parameters: 包含以下参数的字典
                - action: 操作类型 (list_tools, call_tool, list_resources, read_resource, list_prompts, get_prompt)
                  如果不指定action但指定了tool_name，会自动推断为call_tool
                - tool_name: 工具名称（call_tool 需要）
                - arguments: 工具参数（call_tool 需要）
                - uri: 资源 URI（read_resource 需要）
                - prompt_name: 提示词名称（get_prompt 需要）
                - prompt_arguments: 提示词参数（get_prompt 可选）

        Returns:
            操作结果
        """
        # 惰性初始化（第一次使用时才初始化）
        self._ensure_initialized()

        # 智能推断action：如果没有action但有tool_name，自动设置为call_tool
        action = parameters.get("action", "").lower()
        if not action and "tool_name" in parameters:
            action = "call_tool"
            parameters["action"] = action

        if not action:
            return "错误：必须指定 action 参数或 tool_name 参数"

        try:
            async def run_mcp_operation():
                await self._ensure_client_connected()

                if action == "list_tools":
                    tools = await self._client.list_tools()
                    if not tools:
                        return "没有找到可用的工具"
                    result = f"找到 {len(tools)} 个工具:\n"
                    for tool in tools:
                        result += f"- {tool['name']}: {tool['description']}\n"
                    return result

                elif action == "call_tool":
                    tool_name = parameters.get("tool_name")
                    arguments = parameters.get("arguments", {})
                    if not tool_name:
                        return "错误：必须指定 tool_name 参数"
                    result = await self._client.call_tool(tool_name, arguments)
                    return f"工具 '{tool_name}' 执行结果:\n{result}"

                elif action == "list_resources":
                    resources = await self._client.list_resources()
                    if not resources:
                        return "没有找到可用的资源"
                    result = f"找到 {len(resources)} 个资源:\n"
                    for resource in resources:
                        result += f"- {resource['uri']}: {resource['name']}\n"
                    return result

                elif action == "read_resource":
                    uri = parameters.get("uri")
                    if not uri:
                        return "错误：必须指定 uri 参数"
                    content = await self._client.read_resource(uri)
                    return f"资源 '{uri}' 内容:\n{content}"

                elif action == "list_prompts":
                    prompts = await self._client.list_prompts()
                    if not prompts:
                        return "没有找到可用的提示词"
                    result = f"找到 {len(prompts)} 个提示词:\n"
                    for prompt in prompts:
                        result += f"- {prompt['name']}: {prompt['description']}\n"
                    return result

                elif action == "get_prompt":
                    prompt_name = parameters.get("prompt_name")
                    prompt_arguments = parameters.get("prompt_arguments", {})
                    if not prompt_name:
                        return "错误：必须指定 prompt_name 参数"
                    messages = await self._client.get_prompt(prompt_name, prompt_arguments)
                    result = f"提示词 '{prompt_name}':\n"
                    for msg in messages:
                        result += f"[{msg['role']}] {msg['content']}\n"
                    return result

                else:
                    return f"错误：不支持的操作 '{action}'"

            # 运行异步操作
            return self._run_async(run_mcp_operation())

        except Exception as e:
            return f"MCP 操作失败: {str(e)}"

    async def arun(self, parameters: Dict[str, Any]) -> str:
        """
        异步执行 MCP 操作（不阻塞事件循环）

        Args:
            parameters: 包含以下参数的字典
                - action: 操作类型 (list_tools, call_tool, list_resources, read_resource, list_prompts, get_prompt)
                - tool_name: 工具名称（call_tool 需要）
                - arguments: 工具参数（call_tool 需要）

        Returns:
            操作结果
        """
        # 惰性初始化（第一次使用时才初始化）
        self._ensure_initialized()

        # 智能推断action：如果没有action但有tool_name，自动设置为call_tool
        action = parameters.get("action", "").lower()
        if not action and "tool_name" in parameters:
            action = "call_tool"
            parameters["action"] = action

        if not action:
            return "错误：必须指定 action 参数或 tool_name 参数"

        try:
            # 直接在后台事件循环中运行异步操作，避免双重线程开销
            async def run_mcp_operation():
                await self._ensure_client_connected()

                if action == "list_tools":
                    tools = await self._client.list_tools()
                    if not tools:
                        return "没有找到可用的工具"
                    result = f"找到 {len(tools)} 个工具:\n"
                    for tool in tools:
                        result += f"- {tool['name']}: {tool['description']}\n"
                    return result

                elif action == "call_tool":
                    tool_name = parameters.get("tool_name")
                    arguments = parameters.get("arguments", {})
                    if not tool_name:
                        return "错误：必须指定 tool_name 参数"
                    result = await self._client.call_tool(tool_name, arguments)
                    return f"工具 '{tool_name}' 执行结果:\n{result}"

                elif action == "list_resources":
                    resources = await self._client.list_resources()
                    if not resources:
                        return "没有找到可用的资源"
                    result = f"找到 {len(resources)} 个资源:\n"
                    for resource in resources:
                        result += f"- {resource['uri']}: {resource['name']}\n"
                    return result

                elif action == "read_resource":
                    uri = parameters.get("uri")
                    if not uri:
                        return "错误：必须指定 uri 参数"
                    content = await self._client.read_resource(uri)
                    return f"资源 '{uri}' 内容:\n{content}"

                elif action == "list_prompts":
                    prompts = await self._client.list_prompts()
                    if not prompts:
                        return "没有找到可用的提示词"
                    result = f"找到 {len(prompts)} 个提示词:\n"
                    for prompt in prompts:
                        result += f"- {prompt['name']}: {prompt['description']}\n"
                    return result

                elif action == "get_prompt":
                    prompt_name = parameters.get("prompt_name")
                    prompt_arguments = parameters.get("prompt_arguments", {})
                    if not prompt_name:
                        return "错误：必须指定 prompt_name 参数"
                    messages = await self._client.get_prompt(prompt_name, prompt_arguments)
                    result = f"提示词 '{prompt_name}':\n"
                    for msg in messages:
                        result += f"[{msg['role']}] {msg['content']}\n"
                    return result

                else:
                    return f"错误：不支持的操作 '{action}'"

            # 直接在后台事件循环中运行，避免 asyncio.to_thread 开销
            with self._client_lock:
                if self._shutdown_flag:
                    raise RuntimeError("Client has been shutdown")
                future = asyncio.run_coroutine_threadsafe(run_mcp_operation(), self._loop)
                return future.result()

        except Exception as e:
            return f"MCP 操作失败: {str(e)}"

    def get_parameters(self) -> List[ToolParameter]:
        """获取工具参数定义"""
        return [
            ToolParameter(
                name="action",
                type="string",
                description="操作类型: list_tools, call_tool, list_resources, read_resource, list_prompts, get_prompt",
                required=True
            ),
            ToolParameter(
                name="tool_name",
                type="string",
                description="工具名称（call_tool 操作需要）",
                required=False
            ),
            ToolParameter(
                name="arguments",
                type="object",
                description="工具参数（call_tool 操作需要）",
                required=False
            ),
            ToolParameter(
                name="uri",
                type="string",
                description="资源 URI（read_resource 操作需要）",
                required=False
            ),
            ToolParameter(
                name="prompt_name",
                type="string",
                description="提示词名称（get_prompt 操作需要）",
                required=False
            ),
            ToolParameter(
                name="prompt_arguments",
                type="object",
                description="提示词参数（get_prompt 操作可选）",
                required=False
            )
        ]
