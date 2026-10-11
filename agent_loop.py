import argparse
import json
import os
import math
from pathlib import Path
from time import monotonic, sleep
from dotenv import load_dotenv
from langchain_core.runnables import RunnableLambda
from langchain_google_genai import ChatGoogleGenerativeAI
from loop_core import run_agent
from tools import TOOLS

MODEL_NAME = "gemini-3.5-flash-lite"
_last_request = 0.0

def create_model(tool_choice="auto", first_tool=None):
    load_dotenv(Path(__file__).with_name(".env"), override=False)
    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not key or key == "your_google_api_key_here":
        raise ValueError("Set GOOGLE_API_KEY in .env or environment")
    if os.getenv("GEMINI_MODEL", MODEL_NAME).strip() != MODEL_NAME:
        raise ValueError("Set GEMINI_MODEL=gemini-3.5-flash-lite")
    interval = float(os.getenv("GEMINI_REQUEST_INTERVAL", "10"))
    if not math.isfinite(interval) or not 0 <= interval <= 60:
        raise ValueError("GEMINI_REQUEST_INTERVAL must be in [0, 60]")
    llm = ChatGoogleGenerativeAI(
        model=MODEL_NAME, api_key=key, vertexai=False,
        thinking_level="minimal", max_output_tokens=1024,
        timeout=30, max_retries=0)
    normal = llm.bind_tools(TOOLS, tool_choice=tool_choice)
    forced = llm.bind_tools(TOOLS, tool_choice=first_tool) if first_tool else normal
    def invoke(messages):
        global _last_request
        sleep(max(0, _last_request + interval - monotonic()))
        _last_request = monotonic()
        # Every branch calls Gemini; first_tool overrides only the first request.
        selected = forced if len(messages) == 2 else normal
        return selected.invoke(messages)
    return RunnableLambda(invoke)

def print_result(result):
    print(f"model={MODEL_NAME}")
    for event in result.trace:
        if event["event"] == "tool":
            args = json.dumps(event["args"], ensure_ascii=False)
            payload = json.dumps(event["payload"], ensure_ascii=False)
            print(f"[step {event['step']}] {event['name']} args={args}")
            print(f"  dispatched={event['dispatched']}; payload={payload}")
        elif event["event"] == "model_error":
            print(f"[step {event['step']}] API error: {event['error_type']}")
    print(f"status={result.status}; steps={result.steps}; "
          f"tool_calls={result.tool_calls}")
    print(result.answer)

def main():
    parser = argparse.ArgumentParser(description="Gemini 3.5 Flash-Lite tool loop")
    parser.add_argument("question")
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--max-same-call", type=int, default=2)
    args = parser.parse_args()
    try:
        result = run_agent(create_model(), args.question,
                           max_steps=args.max_steps,
                           max_same_call=args.max_same_call)
    except Exception as exc:
        print(f"Không khởi chạy được Agent ({type(exc).__name__}).")
        return 2
    print_result(result)
    return 0 if result.status == "final" else 1

if __name__ == "__main__":
    raise SystemExit(main())
