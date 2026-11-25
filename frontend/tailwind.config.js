import preset, { content } from "frappe-ui/tailwind";

export default {
	presets: [preset],
	content: [...content, "./index.html", "./src/**/*.{vue,js,ts}"],
	theme: {
		extend: {
			// The church's accent, made readable for each theme on the server (churchit/portal/accent.py).
			colors: {
				accent: "var(--accent)",
				"accent-wash": "var(--accent-wash)",
			},
		},
	},
};
