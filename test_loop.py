import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage, ToolMessage

from loop_core import call_key, run_agent
from offline_demo import ScriptedModel, tool_reply, prepare_replies, scenarios


def words(cid="w1"):
    return ("count_words", {"text": "Hoc AI rat vui"}, cid)


class LoopTests(unittest.TestCase):
    def test_trace_preserves_args_for_rejected_repetition(self):
        model = ScriptedModel([tool_reply(words("r1")), tool_reply(words("r2"))])
        result = run_agent(model, "Thử", max_same_call=1)
        self.assertEqual(result.trace[-1]["args"], {"text": "Hoc AI rat vui"})
        self.assertFalse(result.trace[-1]["dispatched"])

    def test_offline_overrides_do_not_exhaust_script(self):
        items = {title[0]: (title, replies) for title, replies, _ in scenarios()}
        for label, budget, limit, status, steps in [
                ("E", 2, 2, "max_steps", 2), ("E", 5, 2, "max_steps", 5),
                ("G", 5, 3, "repeat_limit", 4), ("G", 5, 5, "max_steps", 5)]:
            with self.subTest(label=label, budget=budget, limit=limit):
                title, replies = items[label]
                model = ScriptedModel(prepare_replies(title, replies, budget))
                result = run_agent(model, "Thử", max_steps=budget, max_same_call=limit)
                self.assertEqual((result.status, result.steps), (status, steps))

    def test_conflicting_offline_cli_options_are_rejected(self):
        import contextlib
        import io
        from offline_demo import main
        for args in [["--compare", "--scenario", "D"],
                     ["--compare", "--max-steps", "2"],
                     ["--compare", "--max-same-call", "3"]]:
            with self.subTest(args=args), patch("sys.argv", ["offline_demo.py", *args]):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as exc:
                        main()
                self.assertEqual(exc.exception.code, 2)

    def test_final_without_tool(self):
        result = run_agent(ScriptedModel([AIMessage(content="Chào!")]), "Chào")
        self.assertEqual((result.status, result.steps, result.tool_calls), ("final", 1, 0))

    def test_multi_tool_pairing_and_order(self):
        first = tool_reply(words(), ("calculator", {"a": 2, "b": 3, "operation": "add"}, "c1"))
        model = ScriptedModel([first, AIMessage(content="4 và 5")])
        result = run_agent(model, "Tính và đếm")
        history = model.inputs[1]
        self.assertIs(history[2], first)
        self.assertEqual([m.tool_call_id for m in history if isinstance(m, ToolMessage)], ["w1", "c1"])
        self.assertEqual(result.tool_calls, 2)

    def test_dependent_round_uses_previous_result(self):
        second = tool_reply(("calculator", {"a": 4, "b": 25000, "operation": "multiply"}, "c2"))
        model = ScriptedModel([tool_reply(words()), second, AIMessage(content="100000")])
        result = run_agent(model, "Đếm rồi nhân")
        self.assertIn('"count": 4', model.inputs[1][-1].content)
        self.assertEqual(result.steps, 3)

    def test_last_step_executes_tool_but_no_extra_model_call(self):
        model = ScriptedModel([tool_reply(words()), AIMessage(content="Không được gọi")])
        result = run_agent(model, "Đếm", 1)
        self.assertEqual((result.status, result.steps, result.tool_calls), ("max_steps", 1, 1))
        self.assertEqual(len(model.inputs), 1)
        self.assertIsInstance(result.messages[-1], ToolMessage)

    def test_tool_errors_are_returned_to_model(self):
        cases = [("missing", {}, "u1"), ("calculator", {"a": 1, "b": 0, "operation": "divide"}, "d1"),
                 ("calculator", {"a": 1}, "v1"), ("count_words", {"text": "a" * 4001}, "l1")]
        for call in cases:
            with self.subTest(call=call[0]):
                model = ScriptedModel([tool_reply(call), AIMessage(content="Có lỗi tool")])
                result = run_agent(model, "Thử")
                self.assertEqual(result.status, "final")
                self.assertEqual(model.inputs[1][-1].status, "error")

    def test_invalid_id_stops_before_any_tool(self):
        with patch("loop_core.execute_call") as execute:
            result = run_agent(ScriptedModel([tool_reply(words(""))]), "Thử")
            self.assertEqual(result.status, "protocol_error")
            execute.assert_not_called()

    def test_reused_id_stops_on_next_round(self):
        result = run_agent(ScriptedModel([tool_reply(words()), tool_reply(words())]), "Thử")
        self.assertEqual((result.status, result.tool_calls), ("protocol_error", 1))

    def test_oversized_batch_runs_no_tool_and_pairs_all_results(self):
        model = ScriptedModel([tool_reply(*(words(f"w{i}") for i in range(5))), AIMessage(content="Dừng")])
        with patch("loop_core.execute_call") as execute:
            result = run_agent(model, "Thử")
            execute.assert_not_called()
        self.assertEqual(result.tool_calls, 0)
        self.assertEqual(len([m for m in model.inputs[1] if isinstance(m, ToolMessage)]), 5)

    def test_model_error_counts_attempt(self):
        result = run_agent(ScriptedModel([RuntimeError("secret details")]), "Thử")
        self.assertEqual((result.status, result.steps), ("model_error", 1))
        self.assertNotIn("secret details", str(result.trace))

    def test_empty_and_invalid_tool_response(self):
        for reply, expected in [(AIMessage(content=""), "empty_response"),
            (AIMessage(content="", invalid_tool_calls=[{"name": "calculator", "args": "bad json", "id": "x", "error": "bad"}]), "protocol_error")]:
            self.assertEqual(run_agent(ScriptedModel([reply]), "Thử").status, expected)

    def test_budget_and_question_validation(self):
        for budget in (0, -1, 21, True, 1.5):
            with self.assertRaises(ValueError):
                run_agent(None, "Thử", budget)
        for question in ("", "  ", "a" * 4001):
            with self.assertRaises(ValueError):
                run_agent(None, question)
        for limit in (0, 6, True, 1.5):
            with self.assertRaises(ValueError):
                run_agent(None, "Thử", max_same_call=limit)

    def test_repeated_args_with_new_ids_stop_before_third_execution(self):
        model = ScriptedModel([tool_reply(words(f"r{i}")) for i in range(1, 5)])
        with patch("loop_core.execute_call", return_value={"ok": True, "data": {"count": 4}}) as execute:
            result = run_agent(model, "Thử")
        self.assertEqual((result.status, result.steps, result.tool_calls), ("repeat_limit", 3, 2))
        self.assertEqual(execute.call_count, 2)
        self.assertEqual(len(model.inputs), 3)
        self.assertEqual(result.messages[-1].tool_call_id, "r3")
        self.assertEqual(result.messages[-1].status, "error")
        self.assertFalse(result.trace[-1]["dispatched"])

    def test_call_key_ignores_id_and_argument_key_order(self):
        first = {"name": "calculator", "args": {"a": 1, "b": 2, "operation": "add"}, "id": "x"}
        second = {"name": "calculator", "args": {"operation": "add", "b": 2, "a": 1}, "id": "y"}
        self.assertEqual(call_key(first), call_key(second))
        second["name"] = "another_tool"
        self.assertNotEqual(call_key(first), call_key(second))

    def test_changed_arguments_can_recover(self):
        bad = ("calculator", {"a": 1, "b": 0, "operation": "divide"}, "d1")
        good = ("calculator", {"a": 1, "b": 2, "operation": "divide"}, "d2")
        model = ScriptedModel([tool_reply(bad), tool_reply(good), AIMessage(content="0.5")])
        result = run_agent(model, "Thử", max_same_call=1)
        self.assertEqual((result.status, result.steps, result.tool_calls), ("final", 3, 2))
        self.assertIn('"value": 0.5', model.inputs[2][-1].content)

    def test_nonconsecutive_repetition_is_counted_across_run(self):
        other = ("count_words", {"text": "different input"}, "b1")
        model = ScriptedModel([tool_reply(words("a1")), tool_reply(other),
                               tool_reply(words("a2")), tool_reply(words("a3"))])
        result = run_agent(model, "Thử")
        self.assertEqual((result.status, result.steps, result.tool_calls), ("repeat_limit", 4, 3))

    def test_duplicate_batch_is_blocked_before_any_execution(self):
        model = ScriptedModel([tool_reply(words("a1"), words("a2"), words("a3"))])
        with patch("loop_core.execute_call") as execute:
            result = run_agent(model, "Thử")
        execute.assert_not_called()
        self.assertEqual((result.status, result.steps, result.tool_calls), ("repeat_limit", 1, 0))
        self.assertEqual([m.tool_call_id for m in result.messages if isinstance(m, ToolMessage)],
                         ["a1", "a2", "a3"])

    def test_mixed_batch_is_blocked_as_a_whole(self):
        other = ("calculator", {"a": 2, "b": 3, "operation": "add"}, "c1")
        model = ScriptedModel([tool_reply(words("a1")), tool_reply(other, words("a2"))])
        with patch("loop_core.execute_call", return_value={"ok": True, "data": {"count": 4}}) as execute:
            result = run_agent(model, "Thử", max_same_call=1)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(result.status, "repeat_limit")
        self.assertEqual([m.tool_call_id for m in result.messages[-2:]], ["c1", "a2"])

    def test_failed_identical_tool_calls_also_use_repeat_budget(self):
        calls = [("calculator", {"a": 1, "b": 0, "operation": "divide"}, f"e{i}") for i in range(3)]
        result = run_agent(ScriptedModel([tool_reply(call) for call in calls]), "Thử")
        self.assertEqual((result.status, result.tool_calls), ("repeat_limit", 2))
        self.assertEqual(result.trace[-1]["payload"]["error"], "repeat_limit")

    def test_repeat_counts_do_not_leak_between_runs(self):
        for _ in range(2):
            result = run_agent(ScriptedModel([tool_reply(words()), AIMessage(content="4")]),
                               "Thử", max_same_call=1)
            self.assertEqual(result.status, "final")

    def test_repeat_limit_wins_on_last_step(self):
        model = ScriptedModel([tool_reply(words("a1")), tool_reply(words("a2"))])
        result = run_agent(model, "Thử", max_steps=2, max_same_call=1)
        self.assertEqual((result.status, result.steps, result.tool_calls), ("repeat_limit", 2, 1))
        for limit in (0, -1, 9, True, 1.5):
            with self.assertRaises(ValueError):
                run_agent(None, "Thử", max_calls_per_step=limit)

    def test_duplicate_ids_within_batch(self):
        with patch("loop_core.execute_call") as execute:
            result = run_agent(ScriptedModel([tool_reply(words(), words())]), "Thử")
            self.assertEqual(result.status, "protocol_error")
            self.assertEqual(result.tool_calls, 0)
            execute.assert_not_called()

    def test_changing_requests_stop_at_budget(self):
        replies = [tool_reply(("count_words", {"text": f"input {i}"}, f"w{i}")) for i in range(5)]
        replies.append(AIMessage(content="Không được gọi bước 6"))
        model = ScriptedModel(replies)
        result = run_agent(model, "Thử", max_steps=5)
        self.assertEqual((result.status, result.steps, result.tool_calls),
                         ("max_steps", 5, 5))
        self.assertEqual(len(model.inputs), 5)

    def test_final_at_exact_budget(self):
        model = ScriptedModel([tool_reply(words()), AIMessage(content="4")])
        result = run_agent(model, "Đếm", max_steps=2)
        self.assertEqual((result.status, result.steps), ("final", 2))

    def test_invalid_arguments_can_be_corrected(self):
        bad = ("calculator", {"a": 1, "b": 0, "operation": "divide"}, "c1")
        good = ("calculator", {"a": 1, "b": 2, "operation": "divide"}, "c2")
        model = ScriptedModel([tool_reply(bad), tool_reply(good),
                               AIMessage(content="1 / 2 = 0.5")])
        result = run_agent(model, "Thử")
        self.assertEqual((result.status, result.steps), ("final", 3))
        self.assertEqual(model.inputs[1][-1].status, "error")
        self.assertIn('"value": 0.5', model.inputs[2][-1].content)

    def test_unexpected_tool_error_is_sanitized(self):
        from unittest.mock import Mock
        broken = Mock()
        broken.invoke.side_effect = RuntimeError("sensitive tool details")
        with patch.dict("loop_core.TOOL_MAP", {"count_words": broken}):
            result = run_agent(ScriptedModel([tool_reply(words())]), "Thử", 1)
        self.assertIn('"tool_error"', result.messages[-1].content)
        self.assertNotIn("sensitive tool details", str(result.trace))

    def test_calculator_rejects_nonfinite_input_and_overflow(self):
        from loop_core import execute_call
        for a, b in ((float("inf"), 1), (float("nan"), 1), (1e308, 1e308)):
            call = {"name": "calculator", "args": {"a": a, "b": b, "operation": "multiply"}}
            self.assertEqual(execute_call(call),
                             {"ok": False, "error": "invalid_arguments"})

    def test_nonfinite_json_is_protocol_error_before_dispatch(self):
        call = ("calculator", {"a": float("nan"), "b": 1, "operation": "add"}, "c1")
        with patch("loop_core.execute_call") as execute:
            result = run_agent(ScriptedModel([tool_reply(call)]), "Thử")
        self.assertEqual(result.status, "protocol_error")
        execute.assert_not_called()

    def test_non_ai_response_is_protocol_error(self):
        result = run_agent(ScriptedModel(["Wrong response type"]), "Thử")
        self.assertEqual((result.status, result.tool_calls), ("protocol_error", 0))

    def test_text_with_tool_calls_is_not_final(self):
        first = tool_reply(words())
        first.content = "Tôi sẽ dùng công cụ."
        result = run_agent(ScriptedModel([first]), "Đếm", 1)
        self.assertEqual((result.status, result.tool_calls), ("max_steps", 1))

    def test_text_content_blocks_can_be_final(self):
        reply = AIMessage(content=[{"type": "text", "text": "Xin chào!"}])
        result = run_agent(ScriptedModel([reply]), "Chào")
        self.assertEqual((result.status, result.answer), ("final", "Xin chào!"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
