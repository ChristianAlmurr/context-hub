#!/usr/bin/env python3
"""Offline checks of how a choice on Claude Code's screen is read: no server, no Claude session.

The screens in tests/screens/ were captured from real panes of Claude Code 2.1.330 (capture-pane, and capture-pane -e for
the .ansi ones, whose colours say which of several questions is open), with paths made generic. They cover
AskUserQuestion (one question and several, single and multiple choice, its own answer typed or not, the cursor on Next,
the review), permission prompts (a command, an edit, Tab to add words), a plan to approve, a picker, the trust menu,
a narrow terminal, and Claude's own input box, which is no choice.
Run: /usr/bin/python3 tests/dialog_check.py (with the six HUB_* variables of a second instance, as for the other tests)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import hub_status

SCREENS = Path(__file__).resolve().parent / "screens"
fails = 0


def check(label, ok, extra=""):
    global fails
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f"  [{str(extra)[:600]}]"), flush=True)
    fails += 0 if ok else 1


def read(name):
    screen = (SCREENS / name).read_text(encoding="utf-8")
    return hub_status.dialog_in(screen) or hub_status.menu_dialog(screen)


def labels(d):
    return [o["label"] for o in d["options"]] if d else None


def opt(d, n):
    return next(o for o in d["options"] if o["n"] == n)


# ── AskUserQuestion, several questions ──
d = read("q1.txt")
check("a question of several is read as a question, with its four steps", d and d["kind"] == "question" and [s["label"] for s in d["steps"]] == ["Color", "Toppings", "Size", "Submit"] and d["steps"][3].get("submit"), d)
check("its question is the line under the tab row", d and d["question"] == "Pick a color for the new dashboard theme?", d and d["question"])
check("a description stays apart from its label", d and labels(d)[:3] == ["Red", "Blue", "Green"] and opt(d, 2)["description"] == "Calm and readable on dark backgrounds, the default most people keep", d and d["options"])
check("Type something is the row that takes words, and nothing is typed in it yet", d and opt(d, 4).get("text") == "type" and opt(d, 4)["value"] == "" and d["text_option"] == 4, d and opt(d, 4))
check("Chat about this, below the rule, is still an option, set apart", d and opt(d, 5)["label"] == "Chat about this" and opt(d, 5).get("apart") and not opt(d, 4).get("apart"), d and d["options"])
check("a single choice is not multiple, and nothing is ticked", d and not d["multi"] and not any(o.get("checked") for o in d["options"]))
check("where the cursor stands is said as a row", d and d["cursor"] == 0 and [o["row"] for o in d["options"]] == [0, 1, 2, 3, 4], d)
check("without colours, which question is open is left unknown, never guessed", d and d["step"] is None, d and d["step"])

d = read("color-answered.txt")
check("an answered question marks its answer and drops the ✔ from the label", d and opt(d, 2)["label"] == "Blue" and opt(d, 2)["checked"] is True and d["steps"][0]["done"], d and d["options"])
d = read("narrow-color.txt")
check("a description the terminal wrapped is one description", d and opt(d, 2)["description"] == "Calm and readable on dark backgrounds, the default most people keep" and opt(d, 2)["label"] == "Blue", d and d["options"])

d = read("m-toggled.txt")
check("a multiple choice is read with its ticks, its checkboxes out of the labels", d and d["multi"] and labels(d)[:3] == ["Cheese", "Ham", "Olives"] and [opt(d, n)["checked"] for n in (1, 2, 3)] == [True, False, True], d and d["options"])
check("its description sits deeper, still apart", d and opt(d, 1)["description"] == "Mozzarella", d and opt(d, 1))
check("its Next row is known, between the typed row and Chat about this", d and d["next"] == {"row": 4, "label": "Next"} and opt(d, 5)["row"] == 5 and "checked" not in opt(d, 5), d)
d = read("m-typed.txt")
check("words typed in a multiple choice are its value, and tick it", d and opt(d, 4)["value"] == "Pineapple, extra 1 2" and opt(d, 4)["checked"] and d["cursor"] == 3, d and opt(d, 4))
d = read("m-next.txt")
check("the cursor on Next still reads as a live choice", d and d["cursor"] == 4 and d["next"]["row"] == 4 and d["question"] == "Which toppings?", d)
d = read("single-multi-onsubmit.txt")
check("a single multiple-choice question's Submit row is its Next, with the cursor on it", d and d["multi"] and d["next"] == {"row": 4, "label": "Submit"} and d["cursor"] == 4, d)
check("one question and its review: the open one is known without colours", d and d["step"] == 0 and len(d["steps"]) == 2, d and d.get("steps"))

d = read("submit-partial.txt")
check("the review is read as a review: each question and its answer", d and d["kind"] == "review" and d["review"] == [{"question": "Which toppings?", "answer": 'Cheese, Olives, "Pineapple, extra 1 2"'}, {"question": "What size?", "answer": "Medium, cut in 8"}], d)
check("the review says what is missing, and offers Submit and Cancel", d and d["warning"] == "Some questions are unanswered" and labels(d) == ["Submit answers", "Cancel"] and d["step"] == 3, d)
d = read("single.txt")
check("one question alone has one step and no review", d and d["kind"] == "question" and d["steps"] == [{"label": "Deploy", "done": False}] and d["step"] == 0 and d["text_option"] == 3, d)

# ── which question is open: the tab drawn on a coloured background ──
for name, step, question in (("single-step0.ansi", 0, "Pick a color for the new dashboard theme?"), ("multi-step1.ansi", 1, "Which toppings?"), ("review.ansi", 3, "Review your answers")):
    d = read(name)
    check(f"with colours, the open question is known: {question}", d and d["step"] == step and d["question"] == question, d and (d["step"], d["question"]))
d = read("multi-step1.ansi")
check("colours don't leak into labels or values", d and labels(d)[:3] == ["Cheese", "Ham", "Olives"] and opt(d, 4)["value"] == "Fig", d and d["options"])

# ── permission prompts ──
d = read("perm-bash.txt")
check("a permission prompt is read as one, with what it would run", d and d["kind"] == "permission" and d["question"] == "Do you want to proceed?" and d["detail"] == "Bash command\nList first entries of /tmp\nls -la /tmp | head -3", d)
check("Yes and No take words with Tab; the others don't", d and [o.get("text") for o in d["options"]] == ["amend", None, None, "amend"] and d["text_option"] == 4, d and d["options"])
d = read("perm-amend.txt")
check("after Tab, the row's words go straight in", d and opt(d, 4)["label"] == "No, and tell Claude what to do differently" and opt(d, 4)["text"] == "type" and d["cursor"] == 3, d and d["options"])
d = read("perm-edit.txt")
check("an edit's prompt shows its diff and its long option whole", d and d["question"] == "Do you want to overwrite notes.txt?" and "+hello world" in d["detail"] and opt(d, 2)["label"].endswith("for this session (shift+tab)"), d)
d = read("perm-bash.ansi")
check("a permission prompt read with its colours is the same", d and d["kind"] == "permission" and labels(d)[0] == "Yes" and opt(d, 3)["label"] == "No" and "ls -la / | head -2" in d["detail"], d)

# ── a plan to approve ──
d = read("plan.txt")
check("a plan to approve is read as a plan, the plan itself its detail", d and d["kind"] == "plan" and d["detail"].startswith("Plan: add README.md"), d and d.get("detail"))
check("a plan's wrapped lines are joined back, so it reads as Markdown", d and "- Context: The folder (qlab2) is a scratch git repo holding notes.txt and caps/, a directory of captured text outputs (e.g. after-submit.txt, chat-q.txt). It has no README." in d["detail"], d and d.get("detail"))
check("Tell Claude what to change takes words, without the shift+tab hint", d and opt(d, 3)["text"] == "type" and opt(d, 3)["value"] == "" and "description" not in opt(d, 3), d and d["options"])
d = read("plan-typed.txt")
check("words typed for the plan are its value", d and opt(d, 3)["value"] == "Say test lab, not QLab" and d["cursor"] == 2, d and d["options"])
d = read("plan.ansi")
check("a plan read with its colours is the same", d and d["kind"] == "plan" and d["text_option"] == 3, d)

# ── pickers and menus ──
d = read("model-picker.txt")
check("a picker's two columns are a label and a description, and its ✔ a tick", d and opt(d, 5)["label"] == "Haiku 5.5" and opt(d, 5)["checked"] and opt(d, 1)["description"] == "Opus 5.5 · Best for everyday, complex tasks", d and d["options"])
check("a picker's unnumbered row is offered as a row", d and d["rows"] == [{"row": 5, "label": "More models"}] and d["question"] == "Select model", d)
d = read("trust.txt")
check("a menu without numbers is read as rows, with its question", d and d["kind"] == "menu" and [r["label"] for r in d["rows"]] == ["No, exit", "Yes, I trust this folder"] and d["cursor"] == 0 and d["question"].startswith("Quick safety check"), d)
check("Claude's own input box is no choice", read("start.txt") is None)
check("a numbered list higher up, with Claude's input below it, isn't a choice", hub_status.dialog_in("❯ Review comments:\n  1. a.md:2\n  2. b.md:1\n\n⏺ done\n───\n❯ \n───") is None and hub_status.menu_dialog("❯ Review comments:\n  1. a.md:2\n\n───\n❯ \n───") is None)

# ── the words a row shows are compared loosely: the terminal may wrap or cut them ──
check("words are the same when the screen shows their start", hub_status._same_words("Medium, cut in 8", "Medium,  cut in 8") and not hub_status._same_words("Small", "Medium"))
print(f"--- failures: {fails}")
sys.exit(1 if fails else 0)
