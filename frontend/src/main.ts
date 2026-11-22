import "@fontsource-variable/newsreader/opsz.css";
import "@fontsource-variable/newsreader/opsz-italic.css";
import { createApp } from "vue";

import App from "./App.vue";
import { boot } from "./boot";
import { setUpPwa } from "./pwa";
import router from "./router";
import { translation } from "./translate";
import "./style.css";

const root = document.documentElement;
root.style.setProperty("--accent-light", boot.accent.light);
root.style.setProperty("--accent-dark", boot.accent.dark);
root.lang = boot.lang;
root.dir = boot.rtl ? "rtl" : "ltr";

createApp(App).use(router).use(translation).mount("#app");
setUpPwa();
