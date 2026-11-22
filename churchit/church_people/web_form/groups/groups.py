import frappe

from churchit.church_people.group_leaders import get_led_groups
from churchit.church_people.membership import living_people_filter


def get_leader_names(groups: list[str]) -> dict[str, str]:
	"""{group: its living leaders' names, comma separated}: a member sees who leads their own group."""
	# church-scope: the leaders of groups the reader is a member of
	rows = frappe.get_all(
		"Group Member",
		filters={"parenttype": "Group", "parent": ("in", groups), "group_role.is_leader": 1},
		fields=["parent", "person"],
	)
	# church-scope: the leaders' names, a leader being known to their own group
	names = dict(
		frappe.get_all(
			"Person",
			filters=[{"name": ("in", [row.person for row in rows])}, living_people_filter()],
			fields=["name", "full_name"],
			order_by="full_name asc",
			as_list=True,
		)
	)
	leaders: dict[str, list[str]] = {}
	for row in rows:
		if row.person in names:
			leaders.setdefault(row.parent, []).append(names[row.person])
	return {group: ", ".join(sorted(people)) for group, people in leaders.items()}


def get_context(context):
	pass


def get_portal_groups(
	person: str | None,
	fields: str | list[str] = "*",
	filters: list | None = None,
	limit_start: int = 0,
	limit_page_length: int = 20,
) -> list[frappe._dict]:
	"""The groups *person* is in that are shown in the portal, plus the groups they lead, with their leaders' names."""
	if not person:
		return []

	# church-scope: the groups of one person's own member rows
	my_groups = frappe.get_all(
		"Group Member", {"person": person, "parenttype": "Group"}, pluck="parent", distinct=True
	)
	led_groups = get_led_groups(person)
	rows = frappe.get_list(
		"Group",
		fields=fields,
		distinct=True,
		filters=[*(filters or []), ["name", "in", my_groups or [""]]],
		or_filters=[["show_in_portal", "=", 1], ["name", "in", led_groups or [""]]],
		limit_start=limit_start,
		limit_page_length=limit_page_length,
		order_by="group_name",
		ignore_permissions=True,
	)
	leaders = get_leader_names([row.name for row in rows]) if rows else {}
	for row in rows:
		row["leaders"] = leaders.get(row.name, "")
	return rows


def get_list_context(context):
	"""Filter the /groups listing to groups the user is a member of
	(restricted to ``show_in_portal``, except the groups the user leads)."""
	user = frappe.session.user
	person = frappe.db.get_value("Person", {"user": user}, "name") if user != "Guest" else None

	def get_list(doctype, txt, filters, limit_start, limit_page_length=20, **kwargs):
		return get_portal_groups(person, "*", filters, limit_start, limit_page_length)

	context.get_list = get_list
	context.order_by = "group_name"
	return context
