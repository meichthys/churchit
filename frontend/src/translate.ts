import type { App } from "vue";

import { boot } from "./boot";

/** Translate *text* the way Frappe's __() does: "text:context" first, then "text", then {0} placeholders. */
export function __(text: string, replace?: (string | number)[], context?: string): string {
	const messages = boot.translations || {};
	let translated = (context && messages[`${text}:${context}`]) || messages[text] || text;
	if (replace) {
		translated = translated.replace(/{(\d+)}/g, (match, index) =>
			replace[index] === undefined ? match : String(replace[index]),
		);
	}
	return translated;
}

export const translation = {
	install(app: App) {
		app.config.globalProperties.__ = __;
	},
};

declare module "vue" {
	interface ComponentCustomProperties {
		__: typeof __;
	}
}
