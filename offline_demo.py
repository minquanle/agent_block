from langchain_core.messages import AIMessage
from loop_core import run_agent
class ScriptedModel:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.inputs = []
    def invoke(self, messages):
        self.inputs.append(list(messages))
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return reply
def tool_reply(*specs):
    return AIMessage(content="", tool_calls=[
        {"name": name, "args": args, "id": cid, "type": "tool_call"}
        for name, args, cid in specs])
def scenarios():
    calc = ("calculator", {"a": 123, "b": 456, "operation": "multiply"}, "c1")
    words = ("count_words", {"text": "Hoc AI rat vui"}, "w1")
    yield "A - no tool", [AIMessage(content="Xin chào!")], 5
    yield "B - one tool", [tool_reply(calc), AIMessage(content="123 x 456 = 56088.")], 5
    yield "C - two tools", [tool_reply(calc, words),
                           AIMessage(content="56088; 4 đơn vị cách trắng.")], 5
    yield "D - dependent tools", [tool_reply(words),
        tool_reply(("calculator", {"a": 4, "b": 25000, "operation": "multiply"}, "c2")),
        AIMessage(content="4 x 25000 = 100000.")], 5
    yield "E - max_steps", [tool_reply(words)], 1
    yield "F - tool error", [tool_reply(("calculator",
        {"a": 1, "b": 0, "operation": "divide"}, "e1")),
        AIMessage(content="Không thể chia cho 0.")], 5
    yield "G - repeated call", [tool_reply((words[0], words[1], f"r{i}"))
                                for i in range(1, 4)], 5
    yield "H - corrected arguments", [tool_reply(("calculator",
        {"a": 1, "b": 0, "operation": "divide"}, "e1")),
        tool_reply(("calculator", {"a": 1, "b": 2, "operation": "divide"}, "e2")),
        AIMessage(content="1 / 2 = 0.5.")], 5
def prepare_replies(title, replies, budget):
    if title.startswith("G -"):
        return [tool_reply(("count_words", {"text": "Hoc AI rat vui"}, f"r{i}"))
                for i in range(1, budget + 1)]
    if title.startswith("E -"):
        return [tool_reply(("count_words",
                {"text": "Hoc AI rat vui" if i == 1 else f"Hoc AI rat vui {i}"},
                f"w{i}")) for i in range(1, budget + 1)]
    return replies
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Offline loop scenarios")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--scenario", choices=list("ABCDEFGH"))
    parser.add_argument("--max-steps", type=int, choices=range(1, 21))
    parser.add_argument("--max-same-call", type=int, choices=range(1, 6), default=2)
    mode.add_argument("--compare", action="store_true")
    options = parser.parse_args()
    if options.compare:
        if options.max_steps is not None or options.max_same_call != 2:
            parser.error("--compare uses fixed budgets; omit budget overrides")
        for limit in (5, 2):
            replies = [tool_reply(("count_words", {"text": "Hoc AI rat vui"}, f"r{i}"))
                       for i in range(1, 6)]
            result = run_agent(ScriptedModel(replies), "So sánh chính sách dừng.",
                               max_steps=5, max_same_call=limit)
            print(f"max_same_call={limit}: status={result.status}; "
                  f"steps={result.steps}; tool_calls={result.tool_calls}")
        return
    for title, replies, budget in scenarios():
        if options.scenario and not title.startswith(options.scenario + " -"):
            continue
        budget = options.max_steps or budget
        replies = prepare_replies(title, replies, budget)
        question = "Tính 1 chia 2 bằng calculator." if title.startswith("H -") else "Kiểm tra vòng lặp."
        result = run_agent(ScriptedModel(replies), question,
                           max_steps=budget,
                           max_same_call=options.max_same_call)
        print(f"{title}: status={result.status}; steps={result.steps}; tool_calls={result.tool_calls}")
        for event in result.trace:
            if event["event"] == "tool":
                print(f"  {event['name']}: {event['payload']}")
        print(f"  {result.answer}")
if __name__ == "__main__":
    main()
