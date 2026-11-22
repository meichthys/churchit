<template>
	<PageHead :crumbs="[{ label: __('Care') }, { label: __('Care requests') }]">
		<template #actions>
			<Button
				variant="solid"
				icon-left="lucide-plus"
				:label="__('Ask for care')"
				@click="openNew"
			/>
		</template>
	</PageHead>
	<PageBody>
		<Masthead
			:title="__('Care requests')"
			:label="boot.church?.title"
			:dateline="
				__(
					'Ask the care team for practical help. A deacon or pastor will follow up shortly.'
				)
			"
		/>

		<div class="mt-6 md:hidden">
			<Button
				class="min-h-11 w-full"
				variant="solid"
				size="lg"
				icon-left="lucide-plus"
				:label="__('Ask for care')"
				@click="openNew"
			/>
		</div>

		<LoadState :resource="requests" v-slot="{ data }">
			<section class="mt-8">
				<ul
					v-if="data.items.length"
					class="divide-y divide-outline-gray-1 border-y border-outline-gray-1"
				>
					<li v-for="item in data.items" :key="item.name">
						<IndexRow
							:title="item.category"
							:facts="[item.date_display, __(item.urgency)]"
							:fresh="isFresh(item.name)"
						>
							<StatusBadge
								class="mt-2"
								:status="item.status"
								:theme="STATUS_THEMES[item.status]"
							/>
							<p
								class="mt-2 whitespace-pre-line text-p-lg text-ink-gray-7 md:text-p-base"
							>
								{{ item.description }}
							</p>
							<Button
								class="mt-3 min-h-11 md:min-h-0"
								size="lg"
								variant="outline"
								icon-left="lucide-pencil"
								:label="__('Change')"
								@click="openEdit(item)"
							/>
						</IndexRow>
					</li>
				</ul>
				<EmptyState
					v-else
					:title="__('No requests yet')"
					:body="
						__('When you ask for care, your request and its status are listed here.')
					"
				>
					<Button
						variant="solid"
						size="lg"
						icon-left="lucide-plus"
						:label="__('Ask for care')"
						@click="openNew"
					/>
				</EmptyState>
			</section>
		</LoadState>

		<CareRequestSheet
			v-if="form.data"
			v-model:open="sheetOpen"
			:data="form.data"
			:request="editing"
			@saved="requests.reload()"
		/>
	</PageBody>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { computed } from "vue";

import { useRead } from "@/api";
import { boot } from "@/boot";
import EmptyState from "@/components/EmptyState.vue";
import IndexRow from "@/components/IndexRow.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import { useFreshInk } from "@/composables/useFreshInk";
import { useLiveRefresh } from "@/realtime";

import CareRequestSheet from "./CareRequestSheet.vue";
import { useRequestSheet } from "./useRequestSheet";
import type { CareForm, CareRequest } from "./types";

const STATUS_THEMES: Record<string, "gray" | "blue" | "green"> = {
	Requested: "gray",
	Triaged: "blue",
	"In Progress": "blue",
	Resolved: "green",
	Closed: "green",
};

const requests = useRead<{ items: CareRequest[] }>("care.get_my_care_requests");
const form = useRead<CareForm>("care.get_care_form");
const { mark, isFresh } = useFreshInk();

const {
	open: sheetOpen,
	editing,
	openNew,
	openEdit,
} = useRequestSheet<CareRequest>(
	"/care-request",
	computed(() => requests.data?.items)
);

useLiveRefresh(["care"], async (hint) => {
	await requests.reload();
	if (hint?.name) mark(hint.name);
});
</script>
