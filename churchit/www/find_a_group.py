# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import flt, getdate

from churchit.church_foundations.doctype.church.church import selected_church_name
from churchit.church_people.group_meetings import describe_schedule_time
from churchit.church_scope import church_filters, requested_church

no_cache = 1
sitemap = 1

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
# Two decimals put the pin about a kilometre from the place, so a pin never marks a home.
PIN_DECIMALS = 2
OPEN, FULL, CLOSED = "open", "full", "closed"


def get_context(context):
	"""The public group finder: the selected church's active, public, portal-visible groups."""
	context.no_cache = 1
	context.title = _("Find a Group")
	context.is_guest = frappe.session.user == "Guest"
	church = selected_church_name()
	groups = frappe.get_all(
		"Group",
		filters=church_filters(church, public=1, show_in_portal=1, status="Active"),
		fields=["name", "group_name", "description", "group_type", "requires_approval"],
		order_by="group_name",
	)
	schedules = get_schedules(church, [group.name for group in groups])
	for group in groups:
		group.update(schedules.get(group.name) or {"days": []})
		group.join_state = get_state(frappe.get_doc("Group", group.name))
		group.login_link = get_login_link(group.name)

	context.groups = groups
	context.group_types = sorted({group.group_type for group in groups if group.group_type})
	context.weekdays = [day for day in WEEKDAYS if any(day in group.days for group in groups)]
	context.pins = [
		{"name": group.name, "group_name": group.group_name, "pin": group.pin}
		for group in groups
		if group.pin
	]


def get_schedules(church: str | None, groups: list[str]) -> dict[str, dict]:
	"""Each group's days, meeting time, city and map pin, from its first recurring Function that has not ended."""
	if not groups:
		return {}
	functions = frappe.get_all(
		"Function",
		filters=church_filters(church, auto_repeat=1, group=("in", groups)),
		fields=[
			"group",
			"start_date",
			"start_time",
			"all_day",
			"address",
			"repeat_until",
			"repeat_frequency",
			"repeat_interval",
			"repeat_day_of_week",
			"repeat_monthly_by",
			"repeat_week_of_month",
			"repeat_month_day",
		],
		order_by="creation asc",
	)
	addresses = {
		address.name: address
		for address in frappe.get_all(
			"Address",
			filters={"name": ("in", [function.address for function in functions if function.address])},
			fields=["name", "city", "latitude", "longitude"],
		)
	}
	schedules = {}
	for function in functions:
		if function.group in schedules or (
			function.repeat_until and getdate(function.repeat_until) < getdate()
		):
			continue
		address = addresses.get(function.address) or frappe._dict()
		schedules[function.group] = {
			"days": get_days(function),
			"when": describe_schedule_time(function),
			"city": address.city,
			"pin": get_pin(address),
		}
	return schedules


def get_days(function) -> list[str]:
	"""The weekdays a schedule meets on, for the day filter."""
	if function.repeat_frequency == "Daily":
		return list(WEEKDAYS)
	if function.repeat_frequency == "Weekly":
		return [function.repeat_day_of_week or getdate(function.start_date).strftime("%A")]
	if function.repeat_frequency == "Monthly" and function.repeat_monthly_by == "Weekday":
		return [function.repeat_day_of_week]
	return []


def get_pin(address) -> list[float] | None:
	if not (flt(address.latitude) or flt(address.longitude)):
		return None
	return [round(flt(address.latitude), PIN_DECIMALS), round(flt(address.longitude), PIN_DECIMALS)]


def get_state(group) -> str:
	if group.is_enrollment_open:
		return OPEN
	return FULL if group.is_full else CLOSED


def get_login_link(group: str) -> str:
	"""Sign in, then come back to this group on this church's finder."""
	church = requested_church()
	target = f"/find-a-group?group={quote(group)}" + (f"&church={quote(church)}" if church else "")
	return f"/login?redirect-to={quote(target, safe='')}"
