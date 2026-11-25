import type { RouteRecordRaw } from "vue-router";

import { __ } from "@/translate";

const signUps = { page: "function-sign-up", title: __("Sign-Ups") };

const routes: RouteRecordRaw[] = [
	{ path: "/attendance", component: () => import("./Attendance.vue"), meta: { page: "attendance", title: __("Attendance") } },
	{ path: "/function-sign-up", component: () => import("./SignUps.vue"), meta: signUps },
	{ path: "/function-sign-up/list", component: () => import("./SignUps.vue"), meta: signUps },
	{ path: "/function-sign-up/new", component: () => import("./SignUpNew.vue"), meta: signUps },
	{ path: "/function-sign-up/:name/edit", component: () => import("./SignUpEdit.vue"), meta: signUps },
	{ path: "/function-sign-up/:name", component: () => import("./SignUpDetail.vue"), meta: signUps },
];

export default routes;
