# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Churchit's rules for AI apps: the churchit skill, served by one method.

The skill files in skills/churchit/ are the one owner of the text. System Settings Agent Instructions
belong to the site admin: churchit adds its sentence only when a System Manager presses the button on
the AI Access panel, never on install, migrate or patch.
"""

from pathlib import Path

import frappe
from frappe import _
from frappe.permissions import SYSTEM_USER_ROLE

from churchit.ai.switch import require_ai

GUIDE_METHOD = "churchit.ai.guide.get_agent_guide"
POINTER = (
	f"Before you work with church records, call the method {GUIDE_METHOD}: it gives Churchit's rules "
	"for church scoping, private fields and drafts."
)


@frappe.whitelist(methods=["GET"])
def get_agent_guide(topic: str | None = None) -> str:
	"""Call first: Churchit rules for church scoping, private fields and drafts. Reads only.

	Without a topic it returns the churchit skill (Markdown), which links its reference files. A topic
	is the name of one of them, such as people or reports, and returns that file.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	if not topic:
		return (get_skill_folder() / "SKILL.md").read_text()

	topics = get_guide_topics()
	if Path(topic).stem not in topics:
		frappe.throw(_("There is no guide on that topic. The topics are: {0}.").format(", ".join(topics)))
	return (get_skill_folder() / "reference" / f"{Path(topic).stem}.md").read_text()


def get_skill_folder() -> Path:
	return Path(frappe.get_app_source_path("churchit", "skills", "churchit"))


def get_guide_topics() -> list[str]:
	"""The names of the skill's reference files, the topics get_agent_guide takes."""
	return sorted(path.stem for path in (get_skill_folder() / "reference").glob("*.md"))


def has_guide_pointer() -> bool:
	"""True when System Settings Agent Instructions name get_agent_guide, in any words."""
	return GUIDE_METHOD in (frappe.get_system_settings("agent_instructions") or "")


@frappe.whitelist(methods=["POST"])
def add_guide_pointer() -> bool:
	"""Add the sentence that names the Churchit guide to System Settings Agent Instructions. Changes data.

	For System Managers. It adds POINTER once, at the end, only when the instructions do not name the
	guide yet, and saves System Settings as that System Manager. True when it added the sentence.
	"""
	require_ai()
	frappe.only_for("System Manager", message=True)
	settings = frappe.get_single("System Settings")
	instructions = (settings.agent_instructions or "").rstrip()
	if GUIDE_METHOD in instructions:
		return False

	settings.agent_instructions = f"{instructions}\n\n{POINTER}" if instructions else POINTER
	settings.save()
	return True
