import { createApp } from "vue";

import App from "./App.vue";
import { boot } from "./boot";
import { setUpPwa } from "./pwa";
import router from "./router";
import { translation } from "./translate";
import "./style.css";

const root = document.documentElement;
root.lang = boot.lang;
root.dir = boot.rtl ? "rtl" : "ltr";

createApp(App).use(router).use(translation).mount("#app");
setUpPwa();
