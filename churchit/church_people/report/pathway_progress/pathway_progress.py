# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Where each person is on a pathway: the steps they have done, how many, and the first step still ahead."""

import frappe
from frappe import _

from churchit.utils import set_report_link_titles


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.pathway:
		return get_columns([]), []
	pathway = frappe.get_doc("Pathway", filters.pathway)
	pathway.check_permission("read")
	steps = [row.step for row in pathway.steps]
	columns = get_columns(steps)
	data = get_data(pathway, steps)
	set_report_link_titles(columns, data)
	counts = [sum(row[step_field(index)] for row in data) for index in range(len(steps))]
	return columns, data, None, get_chart(steps, counts), get_summary(steps, counts)


def step_field(index: int) -> str:
	return f"step_{index + 1}"


def get_columns(steps: list[str]) -> list[dict]:
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 220},
		*(
			{"fieldname": step_field(index), "fieldtype": "Check", "label": step, "width": 120}
			for index, step in enumerate(steps)
		),
		{"fieldname": "steps_done", "fieldtype": "Int", "label": _("Steps Done"), "width": 120},
		{"fieldname": "next_step", "fieldtype": "Data", "label": _("Next Step"), "width": 180},
	]


def get_data(pathway, steps: list[str]) -> list[dict]:
	"""A row for each person who has done a step, those furthest along first."""
	rows = []
	for person, done in pathway.get_steps_done().items():
		row = {"person": person, "steps_done": len(done)}
		row.update({step_field(index): int(step in done) for index, step in enumerate(steps)})
		row["next_step"] = next((step for step in steps if step not in done), _("Done"))
		rows.append(row)
	return sorted(rows, key=lambda row: (-row["steps_done"], row["person"]))


def get_chart(steps: list[str], counts: list[int]) -> dict:
	return {
		"data": {"labels": steps, "datasets": [{"name": _("People"), "values": counts}]},
		"type": "bar",
		"colors": ["blue"],
	}


def get_summary(steps: list[str], counts: list[int]) -> list[dict]:
	return [
		{"value": count, "label": step, "datatype": "Int", "indicator": "Blue"}
		for step, count in zip(steps, counts, strict=True)
	]
