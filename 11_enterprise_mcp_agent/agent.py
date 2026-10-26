from typing import Annotated, TypedDict
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_mcp_adapters.client import MultiServerMCPClient
import vector_db
import config
import asyncio

# 1. Состояние
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# 2. Инициализация MCP клиента и инструментов
mcp_client = MultiServerMCPClient({
    "local_tools": {
        "command": "python",
        "args": ["mcp_server.py"],
        "transport": "stdio",
    }
})

# Глобальная переменная для хранения инструментов (загружаем при старте)
TOOLS = []

async def init_tools():
    global TOOLS
    mcp_tools = await mcp_client.get_tools()
    # Добавляем наш инструмент RAG к инструментам из MCP
    from langchain_core.tools import tool
    
    @tool
    def search_database(query: str) -> str:
        """Ищет информацию в корпоративной базе знаний (RAG)."""
        return vector_db.search_knowledge_base(query)
        
    TOOLS = mcp_tools + [search_database]

# Запускаем загрузку инструментов (это выполнится при импорте модуля)
asyncio.run(init_tools())

# 3. Инициализируем модель и привязываем инструменты
llm = ChatOllama(model="qwen3.5:4b", base_url=config.OLLAMA_URL, temperature=0)
llm_with_tools = llm.bind_tools(TOOLS)

# 4. Узел агента
def agent_node(state: AgentState):
    sys_msg = SystemMessage(
        content="Ты умный корпоративный ассистент. Ты можешь искать в базе знаний (search_database), узнавать время (get_current_time) и читать локальные файлы (read_local_file)."
    )
    messages = [sys_msg] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

# 5. Узел выполнения инструментов
async def tool_node(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]
    tool_outputs = []
    
    # Создаем словарь доступных инструментов
    tools_map = {t.name: t for t in TOOLS}
    
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        if tool_name in tools_map:
            # Вызываем инструмент (MCP инструменты асинхронные)
            tool = tools_map[tool_name]
            result = await tool.ainvoke(tool_call["args"])
            tool_outputs.append(ToolMessage(
                tool_call_id=tool_call["id"],
                name=tool_name,
                content=str(result)
            ))
        else:
            tool_outputs.append(ToolMessage(
                tool_call_id=tool_call["id"],
                name=tool_name,
                content=f"Ошибка: инструмент {tool_name} не найден."
            ))
            
    return {"messages": tool_outputs}

# 6. Условный переход
def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END

# 7. Строим граф
workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)
workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
workflow.add_edge("tools", "agent")

app_graph = workflow.compile()