<template>
	<FormSheet
		v-model:open="open"
		:title="booking ? __('Change your request') : __('Ask for a room')"
		:description="
			__(
				'A room can be asked for up to one day at a time. The office answers a request that needs approval.'
			)
		"
	>
		<div
			class="space-y-4 [&_input:not([type=checkbox])]:min-h-11 [&_select]:min-h-11 [&_textarea]:text-lg [&_button]:min-h-11"
		>
			<FormControl
				size="lg"
				v-model="form.room"
				type="select"
				:label="__('Room')"
				:options="rooms"
				:placeholder="__('Choose a room')"
				required
			/>
			<FormControl
				size="lg"
				v-model="form.start"
				type="datetime-local"
				:label="__('Starts')"
				required
			/>
			<FormControl
				size="lg"
				v-model="form.end"
				type="datetime-local"
				:label="__('Ends')"
				required
			/>
			<FormControl
				size="lg"
				v-model="form.purpose"
				type="text"
				:label="__('What it is for')"
				required
			/>
			<FormControl
				size="lg"
				v-model="form.notes"
				type="textarea"
				:rows="3"
				:label="__('Notes')"
			/>
		</div>
		<template #actions>
			<Button
				variant="solid"
				size="lg"
				:label="booking ? __('Save') : __('Send request')"
				:disabled="!form.room || !form.start || !form.end || !form.purpose"
				:loading="request.loading || update.loading"
				@click="save"
			/>
			<Button variant="outline" size="lg" :label="__('Cancel')" @click="open = false" />
		</template>
	</FormSheet>
</template>

<script setup lang="ts">
import { Button, FormControl } from "frappe-ui";
import { reactive, watch } from "vue";

import { useAction } from "@/api";
import FormSheet from "@/components/FormSheet.vue";
import { __ } from "@/translate";
import type { Booking } from "./types";

const props = defineProps<{
	rooms: { label: string; value: string }[];
	booking?: Booking | null;
}>();
const open = defineModel<boolean>("open", { default: false });
const emit = defineEmits<{ saved: [name: string] }>();

const form = reactive({ room: "", start: "", end: "", purpose: "", notes: "" });

/** "2036-04-04 09:00:00" for the datetime-local input. */
const toInput = (value: string) => value.slice(0, 16).replace(" ", "T");
const toServer = (value: string) =>
	`${value.replace("T", " ")}:00`.replace(/(:\d\d):00:00$/, "$1:00");

watch(
	open,
	(isOpen) => {
		if (!isOpen) return;
		const booking = props.booking;
		Object.assign(form, {
			room: booking?.room || "",
			start: booking ? toInput(booking.start_datetime) : "",
			end: booking ? toInput(booking.end_datetime) : "",
			purpose: booking?.purpose || "",
			notes: booking?.notes || "",
		});
	},
	{ immediate: true }
);

type Fields = {
	room: string;
	start_datetime: string;
	end_datetime: string;
	purpose: string;
	notes: string;
};
const request = useAction<{ name: string }, Fields>("serving.request_room");
const update = useAction<{ name: string }, Fields & { name: string }>(
	"serving.update_room_request"
);

async function save() {
	const fields = {
		room: form.room,
		start_datetime: toServer(form.start),
		end_datetime: toServer(form.end),
		purpose: form.purpose,
		notes: form.notes,
	};
	const done = props.booking
		? update.submit({ name: props.booking.name, ...fields })
		: request.submit(fields);
	await done.then(
		(result) => {
			open.value = false;
			emit("saved", result?.name || "");
		},
		() => {}
	);
}
</script>
