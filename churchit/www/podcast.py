# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""/podcast.xml: the selected church's published sermons as an RSS 2.0 podcast feed."""

import mimetypes
import re
from email.utils import format_datetime
from html import escape, unescape
from urllib.parse import quote
from xml.etree.ElementTree import Element, SubElement, register_namespace, tostring
from zoneinfo import ZoneInfo

import frappe
from frappe import _
from frappe.utils import get_datetime, get_system_timezone, get_url, strip_html_tags

from churchit.church_foundations.doctype.church.church import get_church
from churchit.church_scope import church_filters, is_multi_church
from churchit.www.directory import is_public

base_template_path = "www/podcast.xml"
no_cache = 1
sitemap = 0

ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM = "http://www.w3.org/2005/Atom"
DEFAULT_IMAGE = "/assets/churchit/icons/pwa/icon-512.png"
LINE_BREAKS = re.compile(r"<br\s*/?>|</(p|div|li|h[1-6])>", re.IGNORECASE)

register_namespace("itunes", ITUNES)
register_namespace("atom", ATOM)


def get_context(context):
	context.feed = get_feed()


def get_feed_url(church: str | None) -> str:
	"""The feed of *church*. A podcast app has no session, so a branch is named in the URL."""
	return "/podcast.xml" + church_query(church)


def church_query(church: str | None) -> str:
	return f"?church={quote(church)}" if is_multi_church() and church else ""


def get_feed() -> str:
	"""The feed as XML text. ElementTree escapes every value, so no record text is joined in by hand."""
	church = get_church() or frappe._dict()
	rss = Element("rss", version="2.0")
	channel = add_channel(rss, church)
	for episode in get_episodes(church.name):
		add_item(channel, episode)
	# Frappe replaces "{index}" and "{next}" in a rendered page, so no brace is left bare.
	return tostring(rss, encoding="unicode").replace("{", "&#123;")


def plain_text(value: str | None) -> str:
	"""*value* as a listener reads it: Frappe stores record text as HTML, entities included."""
	text = unescape(strip_html_tags(LINE_BREAKS.sub("\n", value or "")))
	return re.sub(r"\n\s*\n", "\n\n", text).strip()


def add_channel(rss: Element, church: frappe._dict) -> Element:
	title = plain_text(church.church_name) or _("Sermons")
	channel = SubElement(rss, "channel")
	SubElement(channel, "title").text = title
	SubElement(channel, "link").text = get_url("/sermons" + church_query(church.name))
	# Readers parse a description as HTML, so text that reads as a tag stays text.
	SubElement(channel, "description").text = escape(plain_text(church.about) or title, quote=False)
	SubElement(channel, "language").text = frappe.get_system_settings("language") or "en"
	SubElement(
		channel,
		f"{{{ATOM}}}link",
		href=get_url(get_feed_url(church.name)),
		rel="self",
		type="application/rss+xml",
	)
	SubElement(channel, f"{{{ITUNES}}}author").text = title
	image = church.image if is_public(church.image) else DEFAULT_IMAGE
	SubElement(channel, f"{{{ITUNES}}}image", href=get_url(image))
	category = SubElement(channel, f"{{{ITUNES}}}category", text="Religion & Spirituality")
	SubElement(category, f"{{{ITUNES}}}category", text="Christianity")
	SubElement(channel, f"{{{ITUNES}}}explicit").text = "false"
	if church.email:
		owner = SubElement(channel, f"{{{ITUNES}}}owner")
		SubElement(owner, f"{{{ITUNES}}}name").text = title
		SubElement(owner, f"{{{ITUNES}}}email").text = church.email
	return channel


def get_episodes(church: str | None) -> list[frappe._dict]:
	"""Published sermons of *church* with a public recording, newest first.

	A sermon without public audio of its own uses its newest presentation that has some.
	"""
	sermons = frappe.get_all(
		"Sermon",
		filters=church_filters(church, publish=1),
		fields=["name", "title", "scripture", "notes", "audio_recording", "sermon_date", "creation"],
	)
	if not sermons:
		return []

	presentations = frappe.get_all(
		"Sermon Presentation",
		filters={
			"parenttype": "Sermon",
			"parent": ("in", [sermon.name for sermon in sermons]),
			"audio_recording": ("is", "set"),
		},
		fields=["parent", "date", "audio_recording"],
		order_by="date desc",
	)
	sizes = get_public_file_sizes(
		[sermon.audio_recording for sermon in sermons] + [row.audio_recording for row in presentations]
	)
	newest = {}
	for row in presentations:
		if row.audio_recording in sizes:
			newest.setdefault(row.parent, row)

	episodes = []
	for sermon in sermons:
		if sermon.audio_recording in sizes:
			recording, date = sermon.audio_recording, sermon.sermon_date or sermon.creation
		elif sermon.name in newest:
			recording, date = newest[sermon.name].audio_recording, newest[sermon.name].date
		else:
			continue
		episodes.append(frappe._dict(sermon, recording=recording, size=sizes[recording], date=date))
	return sorted(episodes, key=lambda episode: get_datetime(episode.date), reverse=True)


def get_public_file_sizes(file_urls: list[str | None]) -> dict[str, int]:
	"""Size by URL of each file a guest may download."""
	file_urls = [url for url in file_urls if url]
	if not file_urls:
		return {}
	files = frappe.get_all(
		"File", filters={"file_url": ("in", file_urls), "is_private": 0}, fields=["file_url", "file_size"]
	)
	return {file.file_url: file.file_size or 0 for file in files}


def add_item(channel: Element, episode: frappe._dict):
	item = SubElement(channel, "item")
	SubElement(item, "title").text = plain_text(episode.title)
	SubElement(item, "link").text = get_url("/sermon/" + quote(episode.name))
	description = [plain_text(episode.scripture), plain_text(episode.get("notes"))]
	SubElement(item, "description").text = escape("\n\n".join(filter(None, description)), quote=False)
	moment = get_datetime(episode.date).replace(tzinfo=ZoneInfo(get_system_timezone()))
	SubElement(item, "pubDate").text = format_datetime(moment)
	SubElement(item, "guid", isPermaLink="false").text = f"{get_url()}/sermon/{episode.creation.isoformat()}"
	SubElement(
		item,
		"enclosure",
		url=get_url(episode.recording),
		length=str(episode.size),
		type=mimetypes.guess_type(episode.recording)[0] or "audio/mpeg",
	)
