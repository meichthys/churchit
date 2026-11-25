<template>
	<PageHead :crumbs="[{ label: __('Giving') }, { label: __('Pledges') }]">
		<template #actions>
			<Button
				v-if="canPledge"
				variant="solid"
				icon-left="lucide-plus"
				:label="__('Make a pledge')"
				@click="startNew"
			/>
		</template>
	</PageHead>
	<PageBody>
		<Masthead
			:title="__('Pledges')"
			:label="boot.church?.title"
			:dateline="
				__('What you plan to give, and what you have given so far')
			"
		/>
		<LoadState :resource="pledges" v-slot="{ data }">
			<section class="mt-8">
				<div
					v-if="data.items.length"
					class="divide-y divide-outline-gray-1 border-y border-outline-gray-1"
				>
					<PledgeReceipt
						v-for="pledge in data.items"
						:key="pledge.name"
						:pledge="pledge"
						:fresh="isFresh(pledge.name)"
						@edit="startEdit(pledge)"
					/>
				</div>
				<EmptyState
					v-else
					:title="__('No pledges yet')"
					:body="
						data.campaigns.length
							? __(
									'Pledge to a campaign of the church, and your gifts toward it are counted here.',
								)
							: __('No campaign is open for pledges now.')
					"
				/>
				<div
					v-if="data.items.length || data.campaigns.length"
					class="mt-6 md:hidden"
				>
					<Button
						v-if="data.campaigns.length"
						class="min-h-11 w-full"
						variant="solid"
						size="lg"
						icon-left="lucide-plus"
						:label="__('Make a pledge')"
						@click="startNew"
					/>
				</div>
			</section>
			<PledgeSheet
				v-model:open="sheetOpen"
				:pledges="data"
				:editing="editing"
				@saved="pledges.reload()"
				@edit="startEditByName"
			/>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useRead } from "@/api";
import { boot } from "@/boot";
import EmptyState from "@/components/EmptyState.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import { useFreshInk } from "@/composables/useFreshInk";
import { useLiveRefresh } from "@/realtime";
import { __ } from "@/translate";

import PledgeReceipt from "./PledgeReceipt.vue";
import PledgeSheet from "./PledgeSheet.vue";
import type { Pledge, Pledges } from "./types";

const route = useRoute();
const router = useRouter();
const pledges = useRead<Pledges>("giving.get_pledges");
const { mark, isFresh } = useFreshInk();

const sheetOpen = ref(false);
const editing = ref<Pledge | null>(null);
const canPledge = computed(() => Boolean(pledges.data?.campaigns.length));

function startNew() {
	editing.value = null;
	sheetOpen.value = true;
}

function startEdit(pledge: Pledge) {
	editing.value = pledge;
	sheetOpen.value = true;
}

function startEditByName(name: string) {
	const pledge = pledges.data?.items.find((row) => row.name === name);
	if (pledge?.can_edit) startEdit(pledge);
}

// The old web form's paths still work: /pledge/new, and /pledge/<name>/edit.
function openFromPath() {
	const [first, second] = ([] as string[]).concat(
		(route.params.rest as string[] | undefined) ?? [],
	);
	if (first === "new" && canPledge.value) startNew();
	else if (first && first !== "list" && second === "edit")
		startEditByName(first);
}

watch(
	() => pledges.data,
	(data, before) => {
		if (data && !before) openFromPath();
	},
);

watch(sheetOpen, (isOpen) => {
	if (!isOpen && route.params.rest) router.replace("/pledge");
});

useLiveRefresh(["pledges"], async () => {
	const before = new Map(
		pledges.data?.items.map((pledge) => [
			pledge.name,
			pledge.amount + pledge.frequency + pledge.given_display,
		]),
	);
	await pledges.reload();
	for (const pledge of pledges.data?.items ?? []) {
		if (
			before.get(pledge.name) !==
			pledge.amount + pledge.frequency + pledge.given_display
		)
			mark(pledge.name);
	}
});
</script>
