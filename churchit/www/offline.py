# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""/offline: what the service worker shows when a page cannot be reached."""

from churchit.church_website.pwa import app_names

no_cache = 1


def get_context(context):
	context.title = app_names()[0]
