# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Video links that a church page can play in an iframe.

Only players whose address follows from the link are known: Let's Church media, YouTube
videos and channel streams, PeerTube videos on any instance, and an Owncast player link.
Every other link, and every link that is not https, is shown as a plain link.
"""

import re
from urllib.parse import parse_qs, urlsplit, urlunsplit

VIDEO_ID = re.compile(r"[A-Za-z0-9_-]+")
LETS_CHURCH_HOSTS = ("lets.church", "www.lets.church")
LETS_CHURCH_MEDIA = re.compile(r"/(?:embed/)?media/([A-Za-z0-9_-]+)")
YOUTUBE_HOSTS = ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be")
YOUTUBE_VIDEO = re.compile(r"/(?:live|embed)/([A-Za-z0-9_-]+)")
YOUTUBE_CHANNEL_LIVE = re.compile(r"/channel/(UC[A-Za-z0-9_-]+)/live")
YOUTUBE_PLAYER = "https://www.youtube.com/embed/"
PEERTUBE_VIDEO = re.compile(r"/(?:w|videos/watch)/([A-Za-z0-9_-]+)")
OWNCAST_PLAYER_PATH = "/embed/video"


def get_embed_url(url: str | None) -> str | None:
	"""The player URL for *url*, or None when the page must show a plain link."""
	try:
		parts = urlsplit(url or "")
		host = parts.hostname
	except ValueError:
		return None
	if parts.scheme != "https" or not host:
		return None

	path = parts.path.rstrip("/")
	if host in LETS_CHURCH_HOSTS:
		match = LETS_CHURCH_MEDIA.fullmatch(path)
		return f"https://lets.church/embed/media/{match[1]}" if match else None
	if host in YOUTUBE_HOSTS:
		return get_youtube_embed_url(host, path, parse_qs(parts.query))
	if parts.path == OWNCAST_PLAYER_PATH:
		return url
	match = PEERTUBE_VIDEO.fullmatch(path)
	return urlunsplit(("https", parts.netloc, f"/videos/embed/{match[1]}", "", "")) if match else None


def get_youtube_embed_url(host: str, path: str, query: dict[str, list[str]]) -> str | None:
	"""The YouTube player for a video, or for a channel's live stream."""
	channel = query.get("channel", [""])[0] if path == "/embed/live_stream" else None
	if channel is None and (match := YOUTUBE_CHANNEL_LIVE.fullmatch(path)):
		channel = match[1]
	if channel is not None:
		is_channel = channel.startswith("UC") and VIDEO_ID.fullmatch(channel)
		return f"{YOUTUBE_PLAYER}live_stream?channel={channel}" if is_channel else None

	if host == "youtu.be":
		video = path.removeprefix("/")
	elif path == "/watch":
		video = query.get("v", [""])[0]
	else:
		match = YOUTUBE_VIDEO.fullmatch(path)
		video = match[1] if match else ""
	return f"{YOUTUBE_PLAYER}{video}" if VIDEO_ID.fullmatch(video) else None
