<template>
	<PageHead :crumbs="[{ label: __('Groups') }]">
		<template v-if="leadsAny" #actions>
			<Button
				v-if="!isPageHidden('group-leader')"
				variant="subtle"
				icon-left="lucide-user-round-cog"
				:label="__('Groups I lead')"
				route="/group-leader"
			/>
		</template>
	</PageHead>
	<PageBody>
		<Masthead
			:title="__('Groups')"
			:label="boot.church?.title"
			:dateline="__('The groups you are in and the ones open to join')"
		/>
		<LoadState :resource="groups" v-slot="{ data }">
			<section class="mt-8" aria-labelledby="your-groups">
				<SectionHead id="your-groups" :title="__('Your groups')">
					<Button
						v-if="leadsAny && !isPageHidden('group-leader')"
						class="min-h-11 md:hidden"
						variant="subtle"
						size="lg"
						icon-left="lucide-user-round-cog"
						:label="__('Groups I lead')"
						route="/group-leader"
					/>
				</SectionHead>
				<ul
					v-if="data.groups.length"
					class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
				>
					<li v-for="group in data.groups" :key="group.name">
						<IndexRow
							:title="group.group_name"
							:route="`/groups/${group.name}`"
							:facts="[
								group.meets,
								group.leaders && __('Led by {0}', [group.leaders]),
								group.is_leader ? __('You lead this group') : null,
							]"
							:fresh="isFresh(group.name)"
						/>
					</li>
				</ul>
				<EmptyState
					v-else
					:title="__('You are not in a group yet')"
					:body="
						data.joinable.length
							? __('Pick one of the groups below, or ask a leader to add you.')
							: __('Ask a leader to add you to one.')
					"
				/>
			</section>

			<section v-if="data.waiting.length" class="mt-10" aria-labelledby="waiting-groups">
				<SectionHead
					id="waiting-groups"
					:title="__('Waiting for a leader')"
					:note="__('A leader will answer your request.')"
				/>
				<ul class="divide-y divide-outline-gray-1 border-t border-outline-gray-1">
					<li v-for="group in data.waiting" :key="group.name">
						<IndexRow :title="group.group_name" status="Requested" />
					</li>
				</ul>
			</section>

			<section v-if="data.joinable.length" class="mt-10" aria-labelledby="open-groups">
				<SectionHead id="open-groups" :title="__('Open to join')" />
				<ul class="divide-y divide-outline-gray-1 border-t border-outline-gray-1">
					<li v-for="group in data.joinable" :key="group.name">
						<JoinRow :group="group" @done="groups.reload()" />
					</li>
				</ul>
			</section>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Button, toast } from "frappe-ui";
import { computed } from "vue";

import { useRead } from "@/api";
import { boot, isPageHidden } from "@/boot";
import EmptyState from "@/components/EmptyState.vue";
import IndexRow from "@/components/IndexRow.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import SectionHead from "@/components/SectionHead.vue";
import { useFreshInk } from "@/composables/useFreshInk";
import { useLiveRefresh } from "@/realtime";

import JoinRow from "./JoinRow.vue";
import type { MyGroups } from "./types";
import { __ } from "@/translate";

const groups = useRead<MyGroups>("groups.get_my_groups");
const { mark, isFresh } = useFreshInk();

const leadsAny = computed(() => groups.data?.groups.some((group) => group.is_leader));

useLiveRefresh(["groups"], async (hint) => {
	const before = new Set(groups.data?.groups.map((group) => group.name));
	const wasWaiting = groups.data?.waiting.some((group) => group.name === hint?.name);
	await groups.reload();

	const added = groups.data?.groups.filter((group) => !before.has(group.name)) ?? [];
	added.forEach((group) => mark(group.name));
	const isListed = [
		...(groups.data?.groups ?? []),
		...(groups.data?.joinable ?? []),
		...(groups.data?.waiting ?? []),
	].some((group) => group.name === hint?.name);
	if (!added.length && wasWaiting && !isListed)
		toast.success(__("A leader answered your request."));
});
</script>
