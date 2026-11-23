import preset, { content } from "frappe-ui/tailwind";

export default {
	presets: [preset],
	content: [...content, "./index.html", "./src/**/*.{vue,js,ts}"],
	theme: {
		extend: {
			// The accent of the website theme's palette, which the page's head sets (churchit/church_website/palette.py).
			colors: {
				accent: "var(--accent)",
				"accent-wash": "var(--accent-wash)",
			},
		},
	},
};
