import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from langchain_core.messages import AIMessage
from agent_loop import MODEL_NAME, create_model, print_result
from loop_core import call_key, run_agent

REPEAT_PROMPT = (
    'Đây là phép thử gọi lặp có chủ đích. Ở mỗi lượt, chỉ gọi count_words '
    'đúng một lần với text chính xác là "Hoc AI rat vui", không thêm dấu '
    'câu, không đổi tham số. Cần gọi lại để kiểm tra bộ chặn, dù đã có kết quả.'
)
CASES = {
    "A": dict(question="Xin chào, hãy giới thiệu ngắn khả năng của bạn.",
              status="final", tools=[]),
    "B": dict(question="Dùng calculator tính 123 nhân 456 rồi trả lời ngắn.",
              status="final", tools=["calculator"], values=[56088.0]),
    "C": dict(question='Dùng công cụ tính 123 nhân 456 và đếm các đơn vị '
              'cách trắng trong "Hoc AI rat vui". Hai việc độc lập.',
              status="final", tools=["calculator", "count_words"],
              values=[56088.0], counts=[4]),
    "D": dict(question='Trước tiên gọi count_words cho "Hoc AI rat vui". '
              'Chờ kết quả công cụ, sau đó dùng calculator nhân số đếm '
              'với 25000. Không tự đoán số đếm trước khi nhận kết quả.',
              status="final", tools=["count_words", "calculator"],
              values=[100000.0], counts=[4], require_dependency=True),
    "E": dict(question='Dùng count_words đếm chính xác "Hoc AI rat vui".',
              status="max_steps", tools=["count_words"],
              max_steps=1, first_tool="count_words", counts=[4]),
    "F": dict(question="Kiểm tra xử lý lỗi: bước đầu bắt buộc gọi calculator "
              "với a=1, b=0, operation=divide. Khi nhận lỗi, giải thích "
              "vì sao không thể chia cho 0; không đổi bài toán.",
              status="final", tools=["calculator"],
              first_tool="calculator", require_error=True),
    "G": dict(question=REPEAT_PROMPT, status="repeat_limit",
              tools=["count_words"], tool_choice="count_words",
              max_same_call=2, require_repeat=True),
    "H": dict(question="Kiểm tra phục hồi: ở lượt đầu chỉ gọi calculator "
              "đúng một lần với a=1, b=0, operation=divide để kiểm tra lỗi. "
              "Chờ kết quả lỗi rồi mới gọi calculator tính bài toán "
              "thực sự là 1 chia 2 ở lượt sau, sau đó trả lời.",
              status="final", tools=["calculator"],
              first_tool="calculator", require_error=True, values=[0.5]),
}

def validate(result, case):
    events = [e for e in result.trace if e["event"] == "tool"]
    successful = [e for e in events if e["payload"].get("ok")]
    checks = {"expected_status": result.status == case["status"]}
    names = {e["name"] for e in events}
    checks["required_tools"] = set(case["tools"]).issubset(names)
    if not case["tools"]:
        checks["no_tools"] = not events
    for value in case.get("values", []):
        checks[f"value_{value}"] = any(
            e["payload"]["data"].get("value") == value for e in successful)
    for count in case.get("counts", []):
        checks[f"count_{count}"] = any(
            e["payload"]["data"].get("count") == count for e in successful)
    if case.get("require_error"):
        checks["tool_error_observed"] = any(
            e["payload"].get("error") == "invalid_arguments" for e in events)
    if case.get("require_dependency"):
        counts = [e for e in successful if e["name"] == "count_words"]
        calculations = [e for e in successful if e["name"] == "calculator"]
        checks["dependent_order"] = any(
            c["step"] < a["step"]
            and c["payload"]["data"]["count"] in (a["args"].get("a"), a["args"].get("b"))
            for c in counts for a in calculations)
    if case.get("require_error") and case.get("values"):
        failures = [e for e in events if not e["payload"].get("ok")]
        checks["recovery_after_error"] = any(
            error["step"] < success["step"] for error in failures for success in successful)
    if case.get("require_repeat"):
        checks["blocked_call"] = any(
            e["payload"].get("error") == "repeat_limit"
            and not e["dispatched"] for e in events)
        checks["same_arguments"] = bool(events) and len({
            call_key({"name": e["name"], "args": e["args"]}) for e in events}) == 1
        checks["no_extra_model_call"] = result.steps == case["max_same_call"] + 1
        checks["dispatch_budget"] = result.tool_calls == case["max_same_call"]
    return checks

def run_case(label, case):
    model = create_model(case.get("tool_choice", "auto"), case.get("first_tool"))
    result = run_agent(model, case["question"],
                       max_steps=case.get("max_steps", 5),
                       max_same_call=case.get("max_same_call", 2))
    checks = validate(result, case)
    usage = [m.usage_metadata for m in result.messages
             if isinstance(m, AIMessage) and m.usage_metadata]
    checks["api_usage_received"] = len(usage) == result.steps and all(
        item.get("input_tokens", 0) > 0 for item in usage)
    versions = sorted({m.response_metadata.get("model_name", MODEL_NAME)
                       for m in result.messages if isinstance(m, AIMessage)})
    record = {"scenario": label, "question": case["question"],
              "tool_choice": case.get("tool_choice", "auto"),
              "first_tool": case.get("first_tool"), "status": result.status,
              "steps": result.steps, "tool_calls": result.tool_calls,
              "answer": result.answer, "trace": result.trace,
              "model_versions": versions, "usage": usage,
              "checks": checks, "passed": all(checks.values())}
    print(f"\n=== {label} ===")
    print_result(result)
    print("checks=" + json.dumps(checks, ensure_ascii=False))
    return record

def main():
    parser = argparse.ArgumentParser(description="Live Gemini 3.5 Flash-Lite scenarios")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--scenario", choices=list(CASES))
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--compare", action="store_true")
    parser.add_argument("--output", type=Path, help="Save this API run as JSON")
    args = parser.parse_args()
    records = []
    try:
        if args.compare:
            for limit in (5, 2):
                case = dict(CASES["G"], max_same_call=limit, max_steps=5,
                            status="max_steps" if limit == 5 else "repeat_limit")
                if limit == 5:
                    case.pop("require_repeat")
                records.append(run_case(f"compare-limit-{limit}", case))
        else:
            labels = CASES if args.all else [args.scenario]
            for label in labels:
                records.append(run_case(label, CASES[label]))
                if records[-1]["status"] == "model_error":
                    break
    except Exception as exc:
        print(f"Không khởi chạy được demo ({type(exc).__name__}).")
        return 2
    passed = all(record["passed"] for record in records)
    print(f"\nAPI checks: {'PASS' if passed else 'FAIL'} ({len(records)} scenarios)")
    if args.output:
        report = {"tested_at_utc": datetime.now(timezone.utc).isoformat(),
                  "model": MODEL_NAME, "api": "Gemini Developer API",
                  "passed": passed, "scenarios": records}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                               encoding="utf-8")
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
