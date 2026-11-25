<template>
	<PageHead :crumbs="[{ label: __('Prayer') }, { label: __('My requests') }]">
		<template #actions>
			<Button
				variant="solid"
				icon-left="lucide-plus"
				:label="__('Share a request')"
				@click="openNew"
			/>
		</template>
	</PageHead>
	<PageBody>
		<Masthead
			:title="__('My prayer requests')"
			:label="boot.church?.title"
			:dateline="__('What you asked the church to pray for')"
		/>

		<div class="mt-6 md:hidden">
			<Button
				class="min-h-11 w-full"
				variant="solid"
				size="lg"
				icon-left="lucide-plus"
				:label="__('Share a request')"
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
							:title="item.title"
							:facts="[
								item.urgent ? __('Urgent') : null,
								item.date_display,
								__(item.visibility),
								item.recipient_name,
								tally(item),
							]"
							:status="item.status"
							:fresh="isFresh(item.name)"
						>
							<p
								v-if="item.request"
								class="mt-2 whitespace-pre-line text-p-lg text-ink-gray-7 md:text-p-base"
							>
								{{ item.request }}
							</p>
							<div class="mt-3 flex flex-wrap gap-2">
								<Button
									class="min-h-11 md:min-h-0"
									size="lg"
									variant="subtle"
									icon-left="lucide-message-circle"
									:label="__('Comments')"
									@click="toggleComments(item.name)"
								/>
								<Button
									class="min-h-11 md:min-h-0"
									size="lg"
									variant="outline"
									icon-left="lucide-pencil"
									:label="__('Change')"
									@click="openEdit(item)"
								/>
								<Button
									class="min-h-11 md:min-h-0"
									size="lg"
									variant="outline"
									:icon-left="
										isAnswered(item)
											? 'lucide-rotate-ccw'
											: 'lucide-check'
									"
									:label="
										isAnswered(item)
											? __('Not answered yet')
											: __('Mark answered')
									"
									:loading="answering === item.name"
									@click="toggleAnswered(item)"
								/>
								<Button
									v-if="!item.prayer_count"
									class="min-h-11 md:min-h-0"
									size="lg"
									variant="ghost"
									icon-left="lucide-trash-2"
									:label="__('Delete')"
									@click="confirmDelete(item)"
								/>
							</div>
							<RequestComments
								v-if="openComments === item.name"
								page="prayer-request"
								topic="prayer"
								:name="item.name"
							/>
							<p
								v-if="item.prayer_count"
								class="mt-3 text-p-lg text-ink-gray-6 md:text-p-base"
							>
								{{
									__(
										"People have prayed for this request, so it stays. Change who can see it to Private to take it off the prayer list.",
									)
								}}
							</p>
						</IndexRow>
					</li>
				</ul>
				<EmptyState
					v-else
					:title="__('Nothing here yet')"
					:body="
						__(
							'A request you share is listed here, with how many are praying.',
						)
					"
				>
					<Button
						variant="solid"
						size="lg"
						icon-left="lucide-plus"
						:label="__('Share a request')"
						@click="openNew"
					/>
				</EmptyState>
				<p class="mt-8 text-p-lg text-ink-gray-6 md:text-p-base">
					<RouterLink
						to="/community-prayer-requests"
						class="underline underline-offset-2"
						>{{ __("Pray for the church's requests") }}</RouterLink
					>
				</p>
			</section>
		</LoadState>

		<PrayerRequestSheet
			v-if="form.data"
			v-model:open="sheetOpen"
			:data="form.data"
			:request="editing"
			@saved="requests.reload()"
		/>
	</PageBody>
</template>

<script setup lang="ts">
import { __ } from "@/translate";
import { Button, dialog, toast } from "frappe-ui";
import { computed, ref } from "vue";
import { RouterLink } from "vue-router";

import { useAction, useRead } from "@/api";
import { boot } from "@/boot";
import EmptyState from "@/components/EmptyState.vue";
import IndexRow from "@/components/IndexRow.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import { useFreshInk } from "@/composables/useFreshInk";
import { useLiveRefresh } from "@/realtime";

import RequestComments from "./RequestComments.vue";
import PrayerRequestSheet from "./PrayerRequestSheet.vue";
import { useRequestSheet } from "./useRequestSheet";
import type { PrayerForm, PrayerRequest } from "./types";

const requests = useRead<{ items: PrayerRequest[] }>(
	"care.get_my_prayer_requests",
);
const form = useRead<PrayerForm>("care.get_prayer_form");
const remove = useAction<null, { name: string }>("care.delete_prayer_request");
const setAnswered = useAction<
	{ status: string },
	{ name: string; answered: boolean }
>("care.set_prayer_request_answered");
const { mark, isFresh } = useFreshInk();

const {
	open: sheetOpen,
	editing,
	openNew,
	openEdit,
} = useRequestSheet<PrayerRequest>(
	"/prayer-request",
	computed(() => requests.data?.items),
);

const openComments = ref<string | null>(null);

function toggleComments(name: string) {
	openComments.value = openComments.value === name ? null : name;
}

function tally(item: PrayerRequest): string | null {
	if (!item.prayer_count) return null;
	return item.prayer_count === 1
		? __("1 prayer")
		: __("{0} prayers", [item.prayer_count]);
}

const answering = ref<string | null>(null);

function isAnswered(item: PrayerRequest): boolean {
	return item.status === "Answered";
}

async function toggleAnswered(item: PrayerRequest) {
	const answered = !isAnswered(item);
	answering.value = item.name;
	try {
		await setAnswered.submit({ name: item.name, answered });
		toast.success(
			answered
				? __("Marked answered. It is off the prayer list.")
				: __("Marked not answered yet."),
		);
		await requests.reload();
	} finally {
		answering.value = null;
	}
}

function confirmDelete(item: PrayerRequest) {
	dialog.danger({
		title: __("Delete this request?"),
		message: __(
			"{0} will be removed from your list and from the prayer list.",
			[item.title],
		),
		confirmLabel: __("Delete"),
		cancelLabel: __("Keep it"),
		onConfirm: async ({ close }) => {
			await remove.submit({ name: item.name });
			close();
			toast.success(__("Request deleted."));
			requests.reload();
		},
	});
}

useLiveRefresh(["prayer"], async (hint) => {
	await requests.reload();
	if (hint?.name) mark(hint.name);
});
</script>
