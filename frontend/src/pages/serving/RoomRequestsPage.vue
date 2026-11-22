<template>
	<PageHead :crumbs="[{ label: __('Room Requests') }]">
		<template #actions>
			<Button
				variant="solid"
				:label="__('Ask for a room')"
				icon-left="lucide-plus"
				@click="asking = true"
			/>
		</template>
	</PageHead>
	<PageBody>
		<Masthead
			:title="__('Room Requests')"
			:label="boot.church?.title"
			:dateline="__('Rooms you asked for and how each stands')"
		/>
		<PageIntro page="room-request" />

		<LoadState :resource="requests" v-slot="{ data }">
			<section class="mt-8">
				<SectionHead :title="__('Your requests')">
					<Button
						class="min-h-11 md:hidden"
						variant="solid"
						size="lg"
						:label="__('Ask for a room')"
						icon-left="lucide-plus"
						@click="asking = true"
					/>
				</SectionHead>
				<ul
					v-if="data.items.length"
					class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
				>
					<li v-for="item in data.items" :key="item.name">
						<IndexRow
							:title="item.purpose || item.room_name || item.name"
							:route="`/room-request/${item.name}`"
							:facts="[item.room_name, item.date_label, timeRange(item)]"
							:status="item.status"
							:fresh="isFresh(item.name)"
						>
							<template #prefix>
								<DateStack :date="item.start_datetime" />
							</template>
						</IndexRow>
					</li>
				</ul>
				<EmptyState
					v-else
					:title="__('No requests yet')"
					:body="__('Ask for a room and the request shows here with its answer.')"
				>
					<Button
						variant="solid"
						size="lg"
						class="min-h-11"
						:label="__('Ask for a room')"
						@click="asking = true"
					/>
				</EmptyState>
			</section>
		</LoadState>
	</PageBody>

	<RoomRequestForm v-model:open="asking" :rooms="roomOptions" @saved="saved" />
</template>

<script setup lang="ts">
import { Button, toast } from "frappe-ui";
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useRead } from "@/api";
import { boot } from "@/boot";
import DateStack from "@/components/DateStack.vue";
import EmptyState from "@/components/EmptyState.vue";
import IndexRow from "@/components/IndexRow.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageIntro from "@/components/PageIntro.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import SectionHead from "@/components/SectionHead.vue";
import { useFreshInk } from "@/composables/useFreshInk";
import { useLiveRefresh } from "@/realtime";
import { __ } from "@/translate";
import RoomRequestForm from "./RoomRequestForm.vue";
import { timeRange } from "./bookingTime";
import type { Booking } from "./types";

const route = useRoute();
const router = useRouter();

const requests = useRead<{ items: Booking[] }>("serving.get_room_requests");
const rooms = useRead<{ rooms: { name: string; room_name: string }[] }>("serving.get_rooms");
const roomOptions = computed(() =>
	(rooms.data?.rooms || []).map((room) => ({ label: room.room_name, value: room.name }))
);
const { mark, isFresh } = useFreshInk();

/** /room-request/new (a link from the old form) opens the request sheet. */
const asking = ref(route.path.endsWith("/new"));
watch(asking, (open) => {
	if (!open && route.path.endsWith("/new")) router.replace("/room-request");
});

function saved(name: string) {
	toast.success(__("Your request was sent."));
	requests.reload();
	router.push(`/room-request/${name}`);
}

useLiveRefresh(["rooms"], async (hint) => {
	const before = new Map((requests.data?.items || []).map((item) => [item.name, item.status]));
	await requests.reload();
	const item = requests.data?.items.find((row) => row.name === hint?.name);
	if (item && before.has(item.name) && before.get(item.name) !== item.status) mark(item.name);
});
</script>
