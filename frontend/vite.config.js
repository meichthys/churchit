import vue from "@vitejs/plugin-vue";
import frappeui from "frappe-ui/vite";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";

export default defineConfig({
	plugins: [
		frappeui({
			frontendRoute: "/portal",
			buildConfig: {
				outDir: "../churchit/public/frontend",
				baseUrl: "/assets/churchit/frontend/",
				// www/portal.html is the list page of other apps, so the app has its own shell.
				indexHtmlPath: "../churchit/www/member_portal.html",
			},
		}),
		vue(),
	],
	resolve: {
		alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
	},
});
