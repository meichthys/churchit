<template>
	<PageHead :crumbs="[{ label: __('Care') }, { label: __('Benevolence requests') }]">
		<template #actions>
			<Button
				v-if="requests.data?.can_add"
				variant="solid"
				icon-left="lucide-plus"
				:label="__('Ask for help')"
				@click="openNew"
			/>
		</template>
	</PageHead>
	<PageBody>
		<Masthead
			:title="__('Benevolence requests')"
			:label="boot.church?.title"
			:dateline="__('Ask the church for financial help, for you or for someone you know')"
		/>
		<PageIntro page="alms-request" />

		<LoadState :resource="requests" v-slot="{ data }">
			<div v-if="data.can_add" class="mt-6 md:hidden">
				<Button
					class="min-h-11 w-full"
					variant="solid"
					size="lg"
					icon-left="lucide-plus"
					:label="__('Ask for help')"
					@click="openNew"
				/>
			</div>
			<section class="mt-8">
				<ul
					v-if="data.items.length"
					class="divide-y divide-outline-gray-1 border-y border-outline-gray-1"
				>
					<li v-for="item in data.items" :key="item.name">
						<IndexRow
							:title="__('For {0}', [item.recipient_name])"
							:facts="[
								item.date_display,
								item.amount ? formatMoney(item.amount) : null,
							]"
							:status="item.status"
							:fresh="isFresh(item.name)"
						>
							<p
								class="mt-2 whitespace-pre-line text-p-lg text-ink-gray-7 md:text-p-base"
							>
								{{ item.description }}
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
								<template v-if="item.can_change">
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
										variant="ghost"
										icon-left="lucide-trash-2"
										:label="__('Delete')"
										@click="confirmDelete(item)"
									/>
								</template>
							</div>
							<p
								v-if="!item.can_change"
								class="mt-3 text-p-lg text-ink-gray-6 md:text-p-base"
							>
								{{
									__(
										"The church has reviewed this request. To change it, contact the church office."
									)
								}}
							</p>
							<RequestComments
								v-if="openComments === item.name"
								form="alms-request"
								topic="alms"
								:name="item.name"
							/>
						</IndexRow>
					</li>
				</ul>
				<EmptyState
					v-else
					:title="__('No requests yet')"
					:body="
						__('When you ask for help, your request and its status are listed here.')
					"
				>
					<Button
						v-if="data.can_add"
						variant="solid"
						size="lg"
						icon-left="lucide-plus"
						:label="__('Ask for help')"
						@click="openNew"
					/>
				</EmptyState>
			</section>
		</LoadState>

		<AlmsRequestSheet
			v-if="requests.data?.can_add"
			v-model:open="sheetOpen"
			:me="requests.data.me"
			:request="editing"
			@saved="requests.reload()"
		/>
	</PageBody>
</template>

<script setup lang="ts">
import { __ } from "@/translate";
import { Button, dialog, toast } from "frappe-ui";
import { computed, ref } from "vue";

import { useFrappeAction, useRead } from "@/api";
import { boot } from "@/boot";
import EmptyState from "@/components/EmptyState.vue";
import IndexRow from "@/components/IndexRow.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageIntro from "@/components/PageIntro.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import { useFreshInk } from "@/composables/useFreshInk";
import { formatMoney } from "@/format";
import { useLiveRefresh } from "@/realtime";

import RequestComments from "./RequestComments.vue";
import AlmsRequestSheet from "./AlmsRequestSheet.vue";
import { WEB_FORMS, type DeleteParams, type AlmsRequest } from "./types";
import { useRequestSheet } from "./useRequestSheet";

const requests = useRead<{
	items: AlmsRequest[];
	can_add: boolean;
	me: { name: string; full_name: string };
}>("care.get_my_alms_requests");
const remove = useFrappeAction<unknown, DeleteParams>(
	"frappe.website.doctype.web_form.web_form.delete"
);
const { mark, isFresh } = useFreshInk();
const {
	open: sheetOpen,
	editing,
	openNew,
	openEdit,
} = useRequestSheet<AlmsRequest>(
	"/alms-request",
	computed(() => requests.data?.items),
	(item) => item.can_change
);

const openComments = ref<string | null>(null);

function toggleComments(name: string) {
	openComments.value = openComments.value === name ? null : name;
}

function confirmDelete(item: AlmsRequest) {
	dialog.danger({
		title: __("Delete this request?"),
		message: __("The request for {0} will be removed.", [item.recipient_name]),
		confirmLabel: __("Delete"),
		cancelLabel: __("Keep it"),
		onConfirm: async ({ close }) => {
			await remove.submit({ web_form_name: WEB_FORMS.alms, docname: item.name });
			close();
			toast.success(__("Request deleted."));
			requests.reload();
		},
	});
}

useLiveRefresh(["alms"], async (hint) => {
	await requests.reload();
	if (hint?.name) mark(hint.name);
});
</script>
