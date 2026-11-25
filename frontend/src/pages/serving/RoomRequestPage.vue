<template>
	<PageHead
		:crumbs="[
			{ label: __('Room Requests'), route: '/room-request' },
			{ label: booking.data?.purpose || __('Request') },
		]"
		back="/room-request"
	>
		<template v-if="booking.data?.can_edit" #actions>
			<Button
				variant="outline"
				:label="__('Change this request')"
				icon-left="lucide-pencil"
				@click="editing = true"
			/>
		</template>
	</PageHead>
	<PageBody>
		<LoadState :resource="booking" v-slot="{ data }">
			<Masthead
				:title="data.purpose || data.room_name || data.name"
				:label="boot.church?.title"
				:dateline="data.date_label"
			/>
			<section
				class="mt-8 max-w-[40rem]"
				:class="fresh && 'is-fresh -mx-3 rounded-4 px-3 py-2'"
			>
				<dl
					class="divide-y divide-outline-gray-1 border-t border-outline-gray-1 text-lg md:text-md"
				>
					<div
						class="flex flex-wrap items-baseline justify-between gap-2 py-4"
					>
						<dt class="t-label text-ink-gray-7">
							{{ __("Status") }}
						</dt>
						<dd><StatusBadge :status="data.status" /></dd>
					</div>
					<div
						class="flex flex-wrap items-baseline justify-between gap-2 py-4"
					>
						<dt class="t-label text-ink-gray-7">
							{{ __("Room") }}
						</dt>
						<dd class="text-ink-gray-9">{{ data.room_name }}</dd>
					</div>
					<div
						class="flex flex-wrap items-baseline justify-between gap-2 py-4"
					>
						<dt class="t-label text-ink-gray-7">
							{{ __("Time") }}
						</dt>
						<dd class="text-ink-gray-9">
							<bdi>{{ timeRange(data) }}</bdi>
						</dd>
					</div>
					<div v-if="data.notes" class="py-4">
						<dt class="t-label text-ink-gray-7">
							{{ __("Notes") }}
						</dt>
						<dd class="mt-1 whitespace-pre-line text-ink-gray-9">
							{{ data.notes }}
						</dd>
					</div>
				</dl>
				<p
					v-if="data.status === 'Requested'"
					class="mt-4 text-lg text-ink-gray-6 md:text-md"
				>
					{{
						__(
							"The office has not answered yet. You will get a message when it does.",
						)
					}}
				</p>
				<Button
					v-if="data.can_edit"
					class="mt-4 min-h-11 md:hidden"
					variant="outline"
					size="lg"
					:label="__('Change this request')"
					@click="editing = true"
				/>
			</section>
			<RoomRequestForm
				v-model:open="editing"
				:rooms="roomOptions"
				:booking="data"
				@saved="saved"
			/>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Button, toast } from "frappe-ui";
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useRead } from "@/api";
import { boot } from "@/boot";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { useLiveRefresh } from "@/realtime";
import { __ } from "@/translate";
import RoomRequestForm from "./RoomRequestForm.vue";
import { timeRange } from "./bookingTime";
import type { Booking } from "./types";

const route = useRoute();
const router = useRouter();
const name = computed(() => String(route.params.name));

const booking = useRead<Booking, { name: string }>("serving.get_room_request", {
	params: () => ({ name: name.value }),
	refetch: true,
});
const rooms = useRead<{ rooms: { name: string; room_name: string }[] }>(
	"serving.get_rooms",
);
const roomOptions = computed(() =>
	(rooms.data?.rooms || []).map((room) => ({
		label: room.room_name,
		value: room.name,
	})),
);

/** /room-request/<name>/edit (a link from the old form) opens the change sheet when the request can still change. */
const editing = ref(false);
watch(editing, (open) => {
	if (!open && route.path.endsWith("/edit"))
		router.replace(`/room-request/${name.value}`);
});
watch(
	() => booking.data,
	(data) => {
		if (!data || !route.path.endsWith("/edit")) return;
		if (data.can_edit) editing.value = true;
		else router.replace(`/room-request/${name.value}`);
	},
	{ immediate: true },
);

const fresh = ref(false);

function saved() {
	toast.success(__("Your request was saved."));
	booking.reload();
}

useLiveRefresh(["rooms"], async (hint) => {
	const before = booking.data?.status;
	await booking.reload();
	if (
		hint?.name === name.value &&
		booking.data &&
		booking.data.status !== before
	) {
		fresh.value = true;
		setTimeout(() => (fresh.value = false), 8000);
	}
});
</script>
