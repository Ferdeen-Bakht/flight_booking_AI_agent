"""Talk to the LangGraph agent from the terminal:  .venv\Scripts\python agent_demo.py"""
import uuid

from app.db import Base, engine
from app.agent.graph import run_agent

Base.metadata.create_all(engine)
sid = str(uuid.uuid4())
while True:
    try:
        msg = input("you> ")
    except (EOFError, KeyboardInterrupt):
        break
    r = run_agent(sid, msg)
    print(f"[{r['intent']}] {r['reply']}")
    if r["ui"]:
        print("   ui:", r["ui"]["type"], len(r["ui"].get("flights", [])) or r["ui"]["booking"]["reference"])
