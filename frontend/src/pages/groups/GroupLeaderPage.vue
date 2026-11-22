<template>
	<PageHead
		:crumbs="[{ label: __('Groups'), route: '/groups' }, { label: __('Groups I lead') }]"
		back="/groups"
	/>
	<PageBody>
		<Masthead
			:title="__('Groups I lead')"
			:label="boot.church?.title"
			:dateline="__('Your people, your meetings and the ones asking to join')"
		/>
		<LoadState :resource="view" v-slot="{ data }">
			<EmptyState
				v-if="!data.groups.length"
				:title="__('You do not lead a group')"
				:body="__('This page opens for the leaders of a group.')"
			>
				<Button
					size="lg"
					class="min-h-11"
					:label="__('Go to your groups')"
					route="/groups"
				/>
			</EmptyState>
			<LeaderGroup
				v-for="group in data.groups"
				:key="group.name"
				:group="group"
				:can-email="data.can_send_email"
				:can-text="data.can_send_texts"
				:is-fresh="isFresh"
				@changed="view.reload()"
			/>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { useRoute } from "vue-router";

import { useRead } from "@/api";
import { boot } from "@/boot";
import EmptyState from "@/components/EmptyState.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import { useFreshInk } from "@/composables/useFreshInk";
import { useLiveRefresh } from "@/realtime";

import LeaderGroup from "./LeaderGroup.vue";
import type { LeaderView } from "./types";

const route = useRoute();
const view = useRead<LeaderView, { group?: string }>("groups.get_leader_view", {
	params: () => (route.query.group ? { group: String(route.query.group) } : {}),
	refetch: true,
});
const { mark, isFresh } = useFreshInk();

useLiveRefresh(["group-requests", "group-meetings", "groups"], async (hint) => {
	const requests = new Set(
		view.data?.groups.flatMap((group) => group.join_requests.map((request) => request.name))
	);
	await view.reload();

	view.data?.groups.forEach((group) =>
		group.join_requests
			.filter((request) => !requests.has(request.name))
			.forEach((request) => mark(request.name))
	);
	if (hint?.topic === "group-meetings" && hint.name) mark(hint.name);
});
</script>
