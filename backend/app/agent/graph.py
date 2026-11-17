r"""LangGraph workflow for the flight assistant (the app's starting page).

 START -> extract -> (conditional) -> search | select | status | cancel | chat -> respond -> END

The LLM does two jobs only: (1) turn the chat into intent + slots JSON, (2) phrase the reply.
Search, trip lookup and cancellation are deterministic Python. Booking itself (passenger
details, price check, JazzCash payment) happens in the app's guided pages: the agent hands the
user to them by showing flight cards with a "Select" button.
"""
import json
import re
from datetime import date, timedelta
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from ..config import settings
from . import tools

SLOT_KEYS = ["origin", "destination", "date", "return_date", "passengers", "cabin", "option", "booking_ref"]


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    intent: str
    slots: dict
    last_results: list   # itineraries from the latest search ("the second one" refers to these)
    last_query: dict
    facts: str
    ui: dict | None


def _llm(json_mode: bool = False) -> ChatOllama:
    return ChatOllama(model=settings.ollama_model, base_url=settings.ollama_base_url, temperature=0,
                      reasoning=False, format="json" if json_mode else None)


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def _hm(iso: str) -> str:
    return iso[11:16]


def _dur(m: int) -> str:
    return f"{m // 60}h {m % 60:02d}m"


# ---------------------------------------------------------------- extract
def _relative_date(text: str) -> str | None:
    t = text.lower()
    today = date.today()
    if m := re.search(r"\b(20\d\d-\d\d-\d\d)\b", t):
        return m.group(1)
    if "day after tomorrow" in t:
        return (today + timedelta(days=2)).isoformat()
    if "tomorrow" in t:
        return (today + timedelta(days=1)).isoformat()
    if re.search(r"\btoday\b", t):
        return today.isoformat()
    if m := re.search(r"\bin (\d{1,3}) (day|week)s?\b", t):
        return (today + timedelta(days=int(m.group(1)) * (7 if m.group(2) == "week" else 1))).isoformat()
    if "next week" in t:
        return (today + timedelta(days=7)).isoformat()
    return None



EXTRACT_PROMPT = """You are the understanding step of a flight assistant.
Today is {today}. Read the conversation and output ONLY a JSON object with:
- "intent": "search" (find flights), "select" (user picks one of the listed results to continue/book), "status" (look up a booking), "cancel" (cancel a booking), or "chat" (anything else)
- "origin": departure city or airport code, or null
- "destination": arrival city or airport code, or null
- "date": departure date YYYY-MM-DD (resolve "tomorrow", "next Friday" using today's date), or null
- "return_date": return date YYYY-MM-DD for a round trip, or null for one-way
- "passengers": integer or null
- "cabin": one of "economy", "premium_economy", "business", "first", or null
- "option": integer position (1-based) of the chosen result when intent is "select" ("the first one"=1, "cheapest"=1 because results are sorted by price), or null
- "booking_ref": booking reference like FBAB12CD, or null
Last search results shown to the user:
{results}
Use null for anything the user has not said. Do not invent values."""


def extract(state: AgentState) -> dict:
    results = state.get("last_results") or []
    listing = "\n".join(
        f'  {i+1}) {r["owner"]["name"]} {_hm(r["slices"][0]["departure"])}-{_hm(r["slices"][0]["arrival"])} '
        f'{r["stops"]} stop(s) PKR {r["min_total_pkr"]:,}' for i, r in enumerate(results[:5])) or "  (none)"
    system = SystemMessage(content=EXTRACT_PROMPT.format(today=date.today().isoformat(), results=listing))
    try:
        raw = _llm(json_mode=True).invoke([system, *state["messages"][-8:]]).content
        data = json.loads(_strip_think(raw))
        if not isinstance(data, dict):
            raise ValueError
    except Exception:
        data = {"intent": "chat"}
    slots = dict(state.get("slots") or {})
    # a different route is a fresh trip: forget the old dates
    if any(data.get(k) not in (None, "", "null") and slots.get(k) not in (None, data.get(k))
           for k in ("origin", "destination")):
        for k in ("date", "return_date"):
            slots.pop(k, None)
    for k in SLOT_KEYS:
        v = data.get(k)
        if v not in (None, "", "null"):
            slots[k] = v
    # small models often miss relative dates; resolve the obvious ones in code
    if data.get("date") in (None, "", "null"):
        last_user = next((m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), "")
        rel = _relative_date(str(last_user))
        if rel:
            slots["date"] = rel
    intent = data.get("intent") if data.get("intent") in {"search", "select", "status", "cancel", "chat"} else "chat"
    return {"intent": intent, "slots": slots, "ui": None, "facts": ""}


def route(state: AgentState) -> str:
    return state["intent"]


# ------------------------------------------------------------- tool nodes
def search_node(state: AgentState) -> dict:
    s = state["slots"]
    missing = [k for k in ("origin", "destination", "date") if not s.get(k)]
    if missing:
        names = {"date": "departure date"}
        return {"facts": "To search flights I still need: " + ", ".join(names.get(m, m) for m in missing)
                         + ". Also ask if they want one-way or round trip (return date), passengers and cabin if not given."}
    try:
        pax = int(s.get("passengers") or 1)
    except (TypeError, ValueError):
        pax = 1
    res = tools.search_flights_tool(str(s["origin"]), str(s["destination"]), str(s["date"]),
                                    s.get("return_date"), pax, str(s.get("cabin") or "economy"))
    if "error" in res:
        return {"facts": f"Search failed: {res['error']} Tell the user and ask them to fix it."}
    its = res["itineraries"][:5]
    q = res["query"]
    if not its:
        return {"facts": f"No flights found {q['origin']} -> {q['destination']} on {q['departure_date']}. Suggest another date.",
                "last_results": [], "last_query": q}
    brief = "; ".join(
        f'{i+1}) {x["owner"]["name"]} {_hm(x["slices"][0]["departure"])}-{_hm(x["slices"][0]["arrival"])}, '
        f'{"non-stop" if x["stops"] == 0 else str(x["stops"]) + " stop(s)"}, {_dur(x["slices"][0]["duration_min"])}, '
        f'from PKR {x["min_total_pkr"]:,}' for i, x in enumerate(its))
    trip = "round trip" if q["return_date"] else "one way"
    return {
        "last_results": its, "last_query": q,
        "ui": {"type": "offers", "query": q, "itineraries": its},
        "facts": (f"Found flights ({trip}, {q['passengers']} pax, {q['cabin_class']}) {q['origin']} -> {q['destination']} "
                  f"on {q['departure_date']}: {brief}. Cards are shown below with a Select button; keep the reply short. "
                  "Mention they can also use the Search page for filters, and that booking needs login."),
    }


def select_node(state: AgentState) -> dict:
    results, q = state.get("last_results") or [], state.get("last_query")
    if not results:
        return {"facts": "There are no search results yet. Ask where/when they want to fly."}
    try:
        n = int(state["slots"].get("option") or 1)
    except (TypeError, ValueError):
        n = 1
    if not 1 <= n <= len(results):
        return {"facts": f"Ask the user to pick an option between 1 and {len(results)}."}
    pick = results[n - 1]
    return {"ui": {"type": "offers", "query": q, "itineraries": [pick], "highlight": True},
            "facts": (f"The user chose option {n} ({pick['owner']['name']}, from PKR {pick['min_total_pkr']:,}). "
                      "Tell them to press Select on the card to compare fares, enter passenger details and pay "
                      "(they will be asked to log in).")}


def _uid(config: RunnableConfig):
    return (config.get("configurable") or {}).get("user_id")


def _login_required(what: str) -> dict:
    return {"ui": {"type": "login"},
            "facts": f"The user is NOT logged in; {what} needs an account. Tell them to press the Log in button shown below."}


def status_node(state: AgentState, config: RunnableConfig) -> dict:
    uid = _uid(config)
    if not uid:
        return _login_required("checking a booking")
    ref = state["slots"].get("booking_ref")
    if not ref:
        return {"facts": "Ask the user for their booking reference (looks like FB1A2B3C), or tell them to open My trips."}
    res = tools.get_booking_tool(uid, str(ref))
    if "error" in res:
        return {"facts": res["error"]}
    return {"ui": {"type": "booking", "booking": res},
            "facts": f"Booking {res['reference']}: status {res['status']}, ticket {res['ticket_status']}, "
                     f"PNR {res['pnr'] or 'not issued'}, PKR {res['amount_pkr']:,}. Summarise briefly."}


def cancel_node(state: AgentState, config: RunnableConfig) -> dict:
    uid = _uid(config)
    if not uid:
        return _login_required("cancelling a booking")
    ref = state["slots"].get("booking_ref")
    if not ref:
        return {"facts": "Ask the user for the booking reference they want to cancel."}
    res = tools.cancel_booking_tool(uid, str(ref))
    if "error" in res:
        return {"facts": res["error"]}
    return {"ui": {"type": "booking", "booking": res},
            "facts": f"Booking {res['reference']} has been cancelled. Note: {res['note'] or 'none'}. Confirm to the user."}


def chat_node(state: AgentState) -> dict:
    return {"facts": "Small talk or unclear request. Reply briefly and steer toward searching flights "
                     "(from, to, dates, passengers, cabin), checking a booking, or cancelling."}


# ---------------------------------------------------------------- respond
RESPOND_PROMPT = """You are a friendly flight assistant (prices in PKR).
Write a SHORT reply (max 3 sentences) to the user based ONLY on the facts below. Never invent flights,
prices, references or policies. Do not use markdown tables.

FACTS: {facts}"""


def respond(state: AgentState) -> dict:
    sys = SystemMessage(content=RESPOND_PROMPT.format(facts=state.get("facts") or "None"))
    try:
        out = _strip_think(_llm().invoke([sys, *state["messages"][-6:]]).content)
    except Exception as e:  # Ollama down / model missing
        out = (f"The AI model isn't available ({e}). Make sure Ollama is running and the model is pulled: "
               f"`ollama pull {settings.ollama_model}`.")
    return {"messages": [AIMessage(content=out or state.get("facts", ""))]}


def build_graph():
    g = StateGraph(AgentState)
    for name, fn in (("extract", extract), ("search", search_node), ("select", select_node),
                     ("status", status_node), ("cancel", cancel_node), ("chat", chat_node), ("respond", respond)):
        g.add_node(name, fn)
    g.add_edge(START, "extract")
    g.add_conditional_edges("extract", route, {k: k for k in ("search", "select", "status", "cancel", "chat")})
    for n in ("search", "select", "status", "cancel", "chat"):
        g.add_edge(n, "respond")
    g.add_edge("respond", END)
    return g.compile(checkpointer=MemorySaver())


graph = build_graph()


def run_agent(session_id: str, message: str, user_id: int | None = None) -> dict[str, Any]:
    out = graph.invoke({"messages": [HumanMessage(content=message)]},
                       config={"configurable": {"thread_id": session_id, "user_id": user_id}})
    return {"reply": out["messages"][-1].content, "ui": out.get("ui"), "intent": out.get("intent")}
