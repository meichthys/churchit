import type { RouteRecordRaw } from "vue-router";

import { __ } from "@/translate";

const routes: RouteRecordRaw[] = [
	{ path: "/groups", component: () => import("@/pages/groups/GroupsPage.vue"), meta: { page: "groups", title: __("My Groups") } },
	{ path: "/groups/list", component: () => import("@/pages/groups/GroupsPage.vue"), meta: { page: "groups", title: __("My Groups") } },
	{ path: "/groups/:name", component: () => import("@/pages/groups/GroupPage.vue"), meta: { page: "groups", title: __("My Groups") } },
	{ path: "/group-files/:rest(.*)*", component: () => import("@/pages/groups/GroupFilesPage.vue"), meta: { page: "group-files", title: __("Group Files") } },
	{ path: "/group-leader", component: () => import("@/pages/groups/GroupLeaderPage.vue"), meta: { page: "group-leader", title: __("Groups I Lead") } },
];

export default routes;
