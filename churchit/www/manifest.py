# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""/manifest.json, served the way frappe serves sitemap.xml: the file is its own base template."""

import json

from churchit.church_website.pwa import get_manifest

base_template_path = "www/manifest.json"
no_cache = 1


def get_context(context):
	context.manifest = json.dumps(get_manifest(), indent=1)
