# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The one way churchit's own AI actions run a model: Flow's run API, as the caller, with the answer
sent to the caller's browser and never saved by itself.

An action calls start with its prompt and the doctypes whose records the prompt holds. start picks
the agent (Private Work for a doctype in Church AI Settings' Only for Local or Zero Retention Models,
else Writer), checks the privacy label of the agent's model and starts a Flow run. Flow calls complete
as the run's owner when the run ends; complete reads the answer as JSON, passes it through the
action's check and publishes it to the owner's browser (RESULT_EVENT), where public/js/ai_actions.js
shows it; the browser can also ask for it with get_answer, because a realtime message sent while its
socket reconnects is lost. A run that no browser waits for, such as a suggestion on a new request
(churchit.ai.triage), names a deliver function instead: Flow keeps it on the Flow Run as on_complete
and calls it with the run as the caller, however long the run waits in the queue.
Each run leaves a chat in the person's own Flow chat list, which nobody can continue or share
(flow_switch.has_session_permission). It reads Flow's doctypes and loads no Flow code, so churchit
loads on a Frappe without Flow.
"""

import json
import re
from collections.abc import Iterable

import frappe
from frappe import _
from frappe.permissions import SYSTEM_USER_ROLE
from frappe.utils import escape_html

from churchit.ai.flow_models import DEFAULT_LABEL, LABEL_FIELD, PRIVATE_WORK, WRITER, is_flow_ready
from churchit.ai.private_doctypes import get_private_doctypes
from churchit.ai.switch import has_flow, is_ai_on, require_ai

RESULT_EVENT = "churchit_ai_result"
ON_COMPLETE = "churchit.ai.runner.complete"
# Not under Frappe's "user:" prefix, which a sign-in clears.
RUN_KEY = "churchit:ai_run:"
# Longer than the dialog waits (ai_actions.js), so a slow run still finds its caller.
RUN_SECONDS = 60 * 60
# The answer of a run, by its token, for a browser that missed the realtime message.
ANSWER_KEY = RUN_KEY + "answer:"
ANSWER_SECONDS = 10 * 60
# The labels a model needs for a prompt with church records, and with a record of a private doctype.
RECORD_LABELS = ("No training", "Zero retention", "Local")
PRIVATE_LABELS = ("Zero retention", "Local")
# Person fields that no churchit AI feature sends (roadmap Q5).
PERSON_HEALTH_FIELDS = ("alergies", "medical_notes", "emergency_contact_name", "emergency_contact_phone")
UNUSABLE = "The AI answer could not be used."
NOT_FINISHED = "The AI did not finish its answer. Try again, or ask your administrator to check Flow."
FENCED_BLOCK = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
THINKING = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
DATA_END = re.compile(r"<\s*/\s*data", re.IGNORECASE)


def start(
	feature: str,
	prompt: str,
	*,
	sends: Iterable[str] = (),
	reference_doctype: str | None = None,
	reference_name: str | None = None,
	check: str | None = None,
	deliver: str | None = None,
	attachments: Iterable[str] = (),
) -> dict:
	"""Start a run of the churchit agent that may get *prompt*, as the caller; return {"token"}.

	*sends* names the doctypes whose records the prompt holds; give none when it holds only text the
	caller typed, text the church publishes, field labels and options or group names. *check* is the
	dotted path of a function that takes the parsed answer and returns the result to show, or raises.
	*deliver* is the dotted path of a function that Flow calls with the ended Flow Run as the caller,
	instead of complete; it reads the answer with get_result and checks its own gates again, and start
	returns {}. *attachments* names Files that the caller may read, which Flow sends with the prompt as
	chat attachments (an image goes to a model that sees images). The caller checks its own rights and
	writes its Access Log row first.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	if not (has_flow() and is_flow_ready()):
		frappe.throw(_("Churchit's AI actions need Flow with an enabled chat model. Ask your administrator."))

	sends = set(sends)
	agent = get_agent(sends)
	check_label(feature, agent, bool(sends))
	# A titled chat never goes to Flow's Helper Model (Flow Settings), which titles a chat from its prompt.
	session = frappe.get_doc("Flow Agent", get_agent_name(agent)).new_session(title=_(feature))
	files = {"attachments": list(attachments)} if attachments else {}
	run = session.chat(
		prompt,
		**files,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
		on_complete=deliver or ON_COMPLETE,
	)
	if deliver:
		return {}

	# Flow's run-end callback locks the session until this request commits, so it finds the key.
	token = frappe.generate_hash(length=32)
	job = {"token": token, "feature": feature, "user": frappe.session.user, "check": check}
	frappe.cache.set_value(RUN_KEY + run.name, job, expires_in_sec=RUN_SECONDS)
	return {"token": token}


def get_agent(sends: set[str]) -> str:
	"""Private Work for a prompt with a record of a doctype in get_private_doctypes(), else Writer."""
	return PRIVATE_WORK if sends & get_private_doctypes() else WRITER


def check_label(feature: str, agent: str, has_records: bool) -> None:
	"""Refuse a prompt with church records when the agent's model has a label that does not allow them."""
	if not has_records:
		return
	allowed = PRIVATE_LABELS if agent == PRIVATE_WORK else RECORD_LABELS
	_model, label = get_agent_model(agent)
	if label not in allowed:
		labels = [_(each) for each in allowed]
		frappe.throw(
			_(
				"{0} needs a model labelled {1} or {2}, but the model of the {3} agent is labelled {4}: a "
				"System Manager can change the model's Privacy Label in Flow Model or the agent's Model in "
				"Flow Agent."
			).format(_(feature), ", ".join(labels[:-1]), labels[-1], get_agent_name(agent), _(label)),
			frappe.PermissionError,
			title=_("Model Not Allowed"),
		)


def get_agent_name(agent: str) -> str:
	return f"churchit/{agent}"


def get_agent_model(agent: str) -> tuple[str | None, str]:
	"""The Flow Model of a churchit agent and its privacy label (Unknown when nobody set one)."""
	model = frappe.db.get_value("Flow Agent", get_agent_name(agent), "model")
	label = None
	if model and frappe.get_meta("Flow Model").has_field(LABEL_FIELD):  # the first migrate adds it
		label = frappe.db.get_value("Flow Model", model, LABEL_FIELD)
	return model, label or DEFAULT_LABEL


def get_usable_agents() -> set[str]:
	"""The churchit agents that the caller may run: enabled and open to them in Flow (desk boot).

	Flow's own list conditions apply (Roles on the agent, and churchit's AI switch). Call it only
	after switch.has_flow().
	"""
	if not frappe.has_permission("Flow Agent", "read"):
		return set()
	names = {get_agent_name(agent): agent for agent in (WRITER, PRIVATE_WORK)}
	readable = frappe.get_list(
		"Flow Agent", filters={"name": ("in", list(names)), "enabled": 1}, pluck="name"
	)
	return {names[name] for name in readable}


def wrap_data(text: str, source: str) -> str:
	"""*text* that guests, members or reports wrote, as a data block for the end of a prompt.

	The agents' instructions say that text in a data block is data. A closing tag inside the text is
	escaped, so the text cannot end the block. Never put the block inside an instruction.
	"""
	body = DATA_END.sub("&lt;/data", text or "")
	return f'<data source="{escape_html(source)}">\n{body}\n</data>'


def complete(run) -> None:
	"""Flow Run on_complete, as the run's owner: send the checked answer, or why it failed, to the caller.

	Does nothing while AI is off, for a run that churchit did not start, or as anyone but the caller.
	"""
	key = RUN_KEY + run.name
	job = frappe.cache.get_value(key)
	if not job or job["user"] != frappe.session.user:
		return
	frappe.cache.delete_value(key)
	if not is_ai_on():
		return

	message = {"token": job["token"]}
	try:
		message["result"] = get_result(run, job["check"])
	except frappe.ValidationError as error:
		message["error"] = str(error) or _(UNUSABLE)
	send_answer(job["user"], message)


def send_answer(user: str, message: dict) -> None:
	"""Publish *message* (with its token) to *user*'s browser, and keep it for get_answer."""
	answer = {"user": user, "message": message}
	frappe.cache.set_value(ANSWER_KEY + message["token"], answer, expires_in_sec=ANSWER_SECONDS)
	frappe.publish_realtime(RESULT_EVENT, message, user=user, after_commit=True)


@frappe.whitelist(methods=["GET"])
def get_answer(token: str) -> dict | None:
	"""The answer of your AI action run with *token*, as the realtime message gave it, or None until it ends. Reads only.

	public/js/ai_actions.js asks for it while it waits, in case the realtime message was lost. Gives
	nothing while AI is off, and only to the person who started the run.
	"""
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	if not is_ai_on() or not isinstance(token, str):
		return None
	answer = frappe.cache.get_value(ANSWER_KEY + token)
	return answer["message"] if answer and answer["user"] == frappe.session.user else None


def get_result(run, check: str | None):
	"""The run's answer as JSON, through *check*. Raises ValidationError with a sentence to show."""
	if run.status != "Completed":
		frappe.throw(_(NOT_FINISHED))
	try:
		answer = parse_answer(run.output)
	except ValueError:
		frappe.throw(_(UNUSABLE))
	if not check:
		return answer

	try:
		return frappe.get_attr(check)(answer)
	except frappe.ValidationError:
		raise
	except frappe.PermissionError:
		frappe.throw(_(UNUSABLE))
	except Exception:
		frappe.log_error(
			title="Churchit AI answer check failed", reference_doctype="Flow Run", reference_name=run.name
		)
		frappe.throw(_(UNUSABLE))


def parse_answer(text: str | None):
	"""The JSON of a model's answer, from the whole text or its fenced block. Raises ValueError."""
	text = THINKING.sub("", text or "").strip()
	if fenced := FENCED_BLOCK.search(text):
		text = fenced.group(1)
	return json.loads(text)
