# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What AI apps and the Church Office agent read about people: smart lists, the office's weekly
questions and briefings. Each read works as the caller, with the caller's permissions."""


def get_smart_list_url(filters: list | str, fields: list | str | None = None) -> dict:
	"""Stub for A3.4."""
	raise NotImplementedError


def get_smart_list_people(report: str, limit: int = 100) -> list[dict]:
	"""Stub for A3.4."""
	raise NotImplementedError


def first_time_guests_without_follow_up(days: int = 30) -> dict:
	"""Stub for A3.5."""
	raise NotImplementedError


def people_not_seen(weeks: int = 8) -> dict:
	"""Stub for A3.5."""
	raise NotImplementedError


def birthdays_and_anniversaries(start: str | None = None, end: str | None = None) -> dict:
	"""Stub for A3.5."""
	raise NotImplementedError


def groups_needing_attention(weeks: int = 6) -> dict:
	"""Stub for A3.5."""
	raise NotImplementedError


def get_person_briefing(person: str) -> dict:
	"""Stub for A3.6."""
	raise NotImplementedError


def get_group_briefing(group: str) -> dict:
	"""Stub for A3.6."""
	raise NotImplementedError
