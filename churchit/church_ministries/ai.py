# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What AI apps and the Church Office agent read about serving, as the caller, and Suggest Songs.

suggest_songs is a desk action (churchit.ai.runner): it sends the song list of a function's church and
the sermon on its schedule, and its check keeps only songs the caller may read.
"""

from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.permissions import SYSTEM_USER_ROLE
from frappe.rate_limiter import rate_limit
from frappe.utils import add_days, get_url_to_form, get_url_to_report_with_filters, getdate

from churchit.ai import opt_outs, runner
from churchit.ai.switch import require_ai
from churchit.church_people.ai import get_page, get_report_rows, get_window
from churchit.church_people.ai_actions import HOUR, RUNS_AN_HOUR
from churchit.church_scope import church_filters, is_multi_church

SCHEDULE = "Ministry Team Schedule"
DEFAULT_DAYS = 7
SONG_SUGGESTIONS = "Song suggestions"
# What Suggest Songs reads: never lyrics, slides, arrangements, media, CCLI numbers or people.
SONG_FIELDS = ("name", "title", "default_key", "_user_tags")
SERMON_FIELDS = ("title", "scripture", "series")
SONG_USAGE = "Song Usage"
USAGE_DAYS = 2 * 365
MAX_SONGS = 300
MAX_SUGGESTIONS = 8
SONG_INSTRUCTIONS = """Suggest songs for a church service from the church's song list in the data block. When the data names the sermon, choose songs that fit its scripture and themes. Prefer songs that were not used lately.
Answer with one JSON object and nothing else. Shape: {{"function": "{function}", "songs": ["<song title>", ...]}}.
Give at most {most} songs, each a title from the song list, written as listed."""


@frappe.whitelist(methods=["GET"])
def get_open_needs(start: str | None = None, end: str | None = None) -> dict:
	"""Open ministry team positions at functions from *start* to *end*, today and the next 7 days by default. Reads only.

	As the Ministry Team Schedule report shows them to the caller; at most 92 days. Returns total,
	rows (the first 50 by date: date, function, function_title, position, position_title, needed,
	accepted, pending, open, asked (the people asked and their answers), url) and url, the report
	for these dates.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	start, end = get_window(start, end, (getdate(), add_days(getdate(), DEFAULT_DAYS)))
	filters = {"from_date": start, "to_date": end, "only_open": 1}
	rows = [get_need(row) for row in get_report_rows(SCHEDULE, filters)]
	return get_page(rows, get_url_to_report_with_filters(SCHEDULE, urlencode(filters)))


def get_need(row: frappe._dict) -> dict:
	"""One row of the Ministry Team Schedule report, for an AI app."""
	return {
		"date": row.start_date,
		"function": row.function,
		"function_title": row.get("_function_link_title") or row.function,
		"position": row.position,
		"position_title": row.get("_position_link_title") or row.position,
		"needed": row.needed,
		"accepted": row.accepted,
		"pending": row.pending,
		"open": row.open,
		"asked": row.people,
		"url": get_url_to_form("Function", row.function),
	}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=RUNS_AN_HOUR, seconds=HOUR, user_based=True)
def suggest_songs(function: str) -> dict:
	"""Start an AI run that suggests songs for the schedule of a Function you may edit. Changes data.

	The prompt holds the title, scripture, series and tags of the sermon on the schedule, and the title,
	tags, default key and last use of each song of the function's church; never lyrics, slides,
	arrangements, media, CCLI numbers or people. A function of a church that keeps away from churchit's
	AI is refused. The answer comes to your browser as at most 8 of the church's songs; nothing is saved.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	doc = frappe.get_doc("Function", function)
	doc.check_permission("write")
	opt_outs.refuse_kept_away("Function", doc.name)
	songs = get_song_list(doc.church)
	if not songs:
		frappe.throw(_("Add your church's songs first."))

	sermon = get_schedule_sermon(doc)
	sends = ("Sermon", "Song") if sermon and not sermon["is_public"] else ("Song",)
	make_access_log(doctype="Function", document=doc.name, method=f"AI: {SONG_SUGGESTIONS}")
	if "Sermon" in sends:
		make_access_log(doctype="Sermon", document=sermon["name"], method=f"AI: {SONG_SUGGESTIONS}")
	instructions = SONG_INSTRUCTIONS.format(function=doc.name, most=MAX_SUGGESTIONS)
	return runner.start(
		SONG_SUGGESTIONS,
		f"{instructions}\n\n{runner.wrap_data(get_song_data(sermon, songs), 'service')}",
		sends=sends,
		reference_doctype="Function",
		reference_name=doc.name,
		check="churchit.church_ministries.ai.check_songs",
	)


def get_song_list(church: str | None) -> list[dict]:
	"""SONG_FIELDS of the songs of *church* and the shared ones that the caller may read, without those
	that keep away from churchit's AI, each with its last use."""
	songs = frappe.get_list(
		"Song",
		filters=church_filters(church),
		fields=list(SONG_FIELDS),
		order_by="title asc",
		limit=MAX_SONGS,
	)
	kept = opt_outs.get_kept_away("Song", [song.name for song in songs])
	last_used = get_last_uses(church)
	return [
		{
			"name": song.name,
			"title": song.title,
			"tags": get_tags(song._user_tags),
			"default_key": song.default_key,
			"last_used": last_used.get(song.name),
		}
		for song in songs
		if song.name not in kept
	]


def get_last_uses(church: str | None) -> dict[str, str]:
	"""{song: last date on a schedule}, from the Song Usage report run as the caller."""
	today = getdate()
	filters = {"from_date": add_days(today, -USAGE_DAYS), "to_date": today}
	if church and is_multi_church():
		filters["church"] = church
	return {row.song: str(row.last_used) for row in get_report_rows(SONG_USAGE, filters) if row.last_used}


def get_tags(tags: str | None) -> list[str]:
	return [tag.strip() for tag in (tags or "").split(",") if tag.strip()]


def get_schedule_sermon(function) -> dict | None:
	"""The first sermon on *function*'s schedule that the caller may read and that does not keep away
	from churchit's AI, as its readable SERMON_FIELDS, tags, name and is_public; else None."""
	for row in function.schedule:
		is_usable = row.item_type == "Sermon" and row.item and not opt_outs.is_kept_away("Sermon", row.item)
		if is_usable and frappe.has_permission("Sermon", doc=row.item):
			return get_sermon_values(frappe.get_doc("Sermon", row.item))
	return None


def get_sermon_values(sermon) -> dict:
	"""SERMON_FIELDS of *sermon* that the caller may read, the series by its name, and its tags."""
	sermon.apply_fieldlevel_read_permissions()
	masked = sermon.flags.masked_fieldnames or set()
	values = {field: sermon.get(field) for field in SERMON_FIELDS if field not in masked}
	if values.get("series"):
		series = frappe.get_list("Sermon Series", filters={"name": values["series"]}, pluck="series_name")
		values["series"] = series[0] if series else None
	tags = get_tags(sermon.get("_user_tags"))
	return {**values, "tags": tags, "name": sermon.name, "is_public": sermon.is_public}


def get_song_data(sermon: dict | None, songs: list[dict]) -> str:
	"""The sermon and the song list as text for the data block."""
	lines = []
	if sermon:
		lines.append("Sermon:")
		for label, value in (
			("Title", sermon.get("title")),
			("Scripture", sermon.get("scripture")),
			("Series", sermon.get("series")),
			("Themes", ", ".join(sermon["tags"])),
		):
			if value:
				lines.append(f"- {label}: {value}")
	lines.append("Songs (title | themes | key | last used):")
	lines += [
		" | ".join(
			(song["title"], ", ".join(song["tags"]), song["default_key"] or "", song["last_used"] or "never")
		)
		for song in songs
	]
	return "\n".join(lines)


def check_songs(answer: dict) -> dict:
	"""The runner's check for suggest_songs: {function, songs}, at most 8 songs of the function's church
	that the caller may read, each a song of the answer's titles; any other title is dropped."""
	if not isinstance(answer, dict) or not isinstance(answer.get("songs"), list):
		frappe.throw(_(runner.UNUSABLE))
	function = answer.get("function")
	function = function if isinstance(function, str) else None
	churches = frappe.get_list("Function", filters={"name": function}, pluck="church") if function else []
	if not churches or not frappe.has_permission("Function", "write", doc=function):
		frappe.throw(_("The AI answered for another function."))
	opt_outs.refuse_kept_away("Function", function)

	songs = {song["title"].casefold(): song for song in get_song_list(churches[0])}
	chosen = {}
	for title in answer["songs"]:
		song = songs.get(title.strip().casefold()) if isinstance(title, str) else None
		if song and song["name"] not in chosen:
			chosen[song["name"]] = {key: song[key] for key in ("name", "title", "default_key", "last_used")}
	if not chosen:
		frappe.throw(_("The AI suggested none of your church's songs."))
	return {"function": function, "songs": list(chosen.values())[:MAX_SUGGESTIONS]}
