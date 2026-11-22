<template>
	<FormSheet
		v-model:open="open"
		:title="request ? __('Change your request') : __('Ask for help')"
		:description="
			__(
				'The care team reviews each request. You can change or delete it until it is reviewed.'
			)
		"
	>
		<form id="alms-form" class="space-y-5" @submit.prevent="submit">
			<FormControl
				v-model="form.amount"
				type="number"
				:label="__('Amount')"
				size="lg"
				:min="0"
			/>
			<FormControl
				v-model="form.recipient_type"
				type="select"
				:label="__('Help for')"
				size="lg"
				:options="recipientTypes"
			/>
			<RecipientPicker
				v-model="form.recipient"
				:doctype="form.recipient_type"
				:initial-label="initialLabel"
				:label="__('Who is it for?')"
			/>
			<p v-if="errors.recipient" class="-mt-3 text-p-base text-ink-red-8" role="alert">
				{{ errors.recipient }}
			</p>
			<FormControl
				v-model="form.description"
				type="textarea"
				:rows="4"
				:label="__('What is the need?')"
				size="lg"
				required
				:error="errors.description"
			/>
		</form>
		<template #actions>
			<Button
				variant="solid"
				size="lg"
				type="submit"
				form="alms-form"
				:loading="save.loading"
				:label="__('Send')"
			/>
			<Button size="lg" variant="outline" :label="__('Cancel')" @click="open = false" />
		</template>
	</FormSheet>
</template>

<script setup lang="ts">
import { __ } from "@/translate";
import { Button, FormControl } from "frappe-ui";
import { computed, reactive, watch } from "vue";

import { useAction } from "@/api";
import FormSheet from "@/components/FormSheet.vue";

import RecipientPicker from "./RecipientPicker.vue";
import type { AlmsRequest, Saved } from "./types";

const props = defineProps<{
	me: { name: string; full_name: string };
	request?: AlmsRequest | null;
}>();
const emit = defineEmits<{ saved: [] }>();
const open = defineModel<boolean>("open", { default: false });

type SaveParams = {
	recipient_type: string;
	recipient: string | null;
	description: string;
	amount: number;
	name?: string;
};

const save = useAction<Saved, SaveParams>("care.save_alms_request");
const errors = reactive({ recipient: "", description: "" });
const form = reactive({
	amount: "" as string | number,
	recipient_type: "Person",
	recipient: null as string | null,
	description: "",
});
const recipientTypes = [
	{ label: __("Person"), value: "Person" },
	{ label: __("Family"), value: "Family" },
];
const initialLabel = computed(() =>
	props.request ? props.request.recipient_name : props.me.full_name
);

function reset() {
	const request = props.request;
	Object.assign(errors, { recipient: "", description: "" });
	Object.assign(form, {
		amount: request?.amount || "",
		recipient_type: request?.recipient_type || "Person",
		recipient: request ? request.recipient : props.me.name,
		description: request?.description || "",
	});
}

watch(open, (isOpen) => isOpen && reset(), { immediate: true });

async function submit() {
	errors.recipient = form.recipient ? "" : __("Choose who the help is for.");
	errors.description = form.description.trim() ? "" : __("Say what the need is.");
	if (errors.recipient || errors.description) return;

	const params = { ...form, amount: Number(form.amount) || 0, name: props.request?.name };
	await save.submit(params).then(
		() => {
			open.value = false;
			emit("saved");
		},
		() => {}
	);
}
</script>
