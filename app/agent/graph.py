import os, re, json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from app.tools.registry import TOOLS
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage, SystemMessage
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

load_dotenv()

llm = ChatGroq(model="openai/gpt-oss-20b", temperature=0,max_retries=6)
llm_with_tools = llm.bind_tools(TOOLS)

SYSTEM = SystemMessage(content=(
    "You are CricketIQ, a cricket match analyst. Rules:\n"
    "1. NEVER state a statistic from memory. Always call a tool first.\n"
    "2. Prefer specific stats tools over sql_query.\n"
    "3. If a tool returns an error, say so honestly or try another tool.\n"
    "4. Data covers IPL only; say so if asked about other tournaments.\n"
    "5. Be concise and show the key numbers.\n"
    "6. Career or filtered player numbers MUST come from batting_stats / bowling_stats.\n"
    "7. Never mention tool names in your answer.\n"
    "8. You cannot predict future matches, see upcoming schedules or live data. "
    "If asked about tomorrow's match, who will win, or any future event, do NOT ask "
    "which teams are playing. First state plainly that you cannot predict results "
    "or see fixtures, then offer historical stats such as head-to-head, recent form "
    "or venue records.\n"
    "9. If a player or team cannot be found, say so plainly. "
    "Never guess or substitute another name.\n"
))

RETRY_MSG = ("Your answer contains numbers not found in tool outputs. "
                "Re-check with tools and answer using only tool-provided numbers.")


class State(MessagesState):
    retries: int


def agent(state: State):
    msgs = [SYSTEM] + state["messages"]
    return {"messages": [llm_with_tools.invoke(msgs)]}


def route_after_agent(state: State):
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return "verify"


def _numbers(text: str):
    text = text.replace(",", "")
    nums = set()
    for n in re.findall(r"\d+(?:\.\d+)?", text):
        nums.add(n)
        nums.add(str(float(n)).rstrip("0").rstrip("."))   # 9336.0 -> 9336
    return nums

def _current_turn(msgs):
    """Messages since the user's latest real question (ignores verifier retries)."""
    for i in range(len(msgs) - 1, -1, -1):
        m = msgs[i]
        if isinstance(m, HumanMessage) and m.content != RETRY_MSG:
            return msgs[i:]
    return msgs

def verify(state: State):
    """Check every number in the answer appears in a tool output from THIS turn."""
    msgs = state["messages"]
    turn = _current_turn(msgs)
    answer = msgs[-1].content or ""
    tool_text = " ".join(
        m.content if isinstance(m.content, str) else json.dumps(m.content)
        for m in turn if isinstance(m, ToolMessage))
    if not tool_text:
        ok = not [n for n in _numbers(answer) if len(n) > 1]
    else:
        allowed = _numbers(tool_text)
        ok = not [n for n in _numbers(answer) if len(n) > 1 and n not in allowed]
    return {"retries": state.get("retries", 0) + (0 if ok else 1),
            "messages": [] if ok else [HumanMessage(content=RETRY_MSG)]}


def route_after_verify(state: State):
    last = state["messages"][-1]
    if isinstance(last, HumanMessage) and state.get("retries", 0) <= 1:
        return "agent"
    return END


builder = StateGraph(State)
builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(TOOLS, handle_tool_errors=True))
builder.add_node("verify", verify)
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "verify": "verify"})
builder.add_edge("tools", "agent")
builder.add_conditional_edges("verify", route_after_verify, {"agent": "agent", END: END})

os.makedirs("data", exist_ok=True)
_conn = sqlite3.connect("data/memory.db", check_same_thread=False)
graph = builder.compile(checkpointer=SqliteSaver(_conn))


def ask(question: str, thread_id: str = "default"):
    cfg = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(
        {"messages": [HumanMessage(content=question)], "retries": 0}, cfg)
    msgs = result["messages"]

    # only look at this turn, not earlier turns stored in the thread
    start = max(i for i, m in enumerate(msgs)
                if isinstance(m, HumanMessage) and m.content == question)
    turn = msgs[start:]

    # de-duplicate identical tool calls (a verifier retry can repeat them)
    call_args = {}
    for m in turn:
        if isinstance(m, AIMessage):
            for tc in (getattr(m, "tool_calls", None) or []):
                call_args[tc["id"]] = tc["args"]

    seen, tools_used = set(), []
    for m in turn:
        if isinstance(m, ToolMessage):
            key = (m.name, m.content)
            if key not in seen:
                seen.add(key)
                tools_used.append({"name": m.name,
                                    "args": call_args.get(m.tool_call_id, {}),
                                    "output": m.content})

    finals = [m for m in turn if m.type == "ai" and not getattr(m, "tool_calls", None)]
    final = finals[-1].content if finals else "Sorry, I could not produce an answer."
    final = final.replace("\u202f", " ").replace("\u00a0", " ")
    return final, tools_used