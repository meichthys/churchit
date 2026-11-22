import type { RouteRecordRaw } from "vue-router";

import { __ } from "@/translate";

const room = { page: "room-request", title: __("Room Requests") };

const routes: RouteRecordRaw[] = [
	{ path: "/ministry-team", component: () => import("@/pages/serving/ServingPage.vue"), meta: { page: "ministry-team", title: __("Serving") } },
	{ path: "/room-request", component: () => import("@/pages/serving/RoomRequestsPage.vue"), meta: room },
	{ path: "/room-request/list", component: () => import("@/pages/serving/RoomRequestsPage.vue"), meta: room },
	{ path: "/room-request/new", component: () => import("@/pages/serving/RoomRequestsPage.vue"), meta: room },
	{ path: "/room-request/:name/edit", component: () => import("@/pages/serving/RoomRequestPage.vue"), meta: room },
	{ path: "/room-request/:name", component: () => import("@/pages/serving/RoomRequestPage.vue"), meta: room },
];

export default routes;
