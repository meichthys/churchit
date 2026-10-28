# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

STAFF_CHAT_ROUTE = "/raven"


def extend_bootinfo(bootinfo):
	"""Drop the Staff Chat sidebar link when the Apps screen does not offer Raven to this user.

	The Apps screen lists Raven only when it is installed and its own permission check lets the user
	in, so the link never leads to a missing page or to Raven's refusal.
	"""
	if any(app.get("route") == STAFF_CHAT_ROUTE for app in bootinfo.get("app_data") or []):
		return

	for sidebar in (bootinfo.get("module_sidebars") or {}).values():
		sidebar["items"] = [item for item in sidebar["items"] if item.get("url") != STAFF_CHAT_ROUTE]
