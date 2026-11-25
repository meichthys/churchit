<template>
	<FormSheet
		v-model:open="open"
		:title="
			request ? __('Change your request') : __('Share a prayer request')
		"
		:description="__('Choose who can see it. You can change this later.')"
	>
		<form id="prayer-form" class="space-y-5" @submit.prevent="submit">
			<FormControl
				v-model="form.title"
				:label="__('Title')"
				size="lg"
				required
				:error="errors.title"
			/>
			<FormControl
				v-model="form.type"
				type="select"
				:label="__('Type')"
				size="lg"
				required
				:options="types"
				:placeholder="__('Choose a type')"
				:error="errors.type"
			/>
			<RadioGroup
				v-model="form.visibility"
				:label="__('Who can see it')"
				size="md"
				padded
			>
				<Radio
					v-for="choice in data.visibilities"
					:key="choice.name"
					:value="choice.name"
					:label="__(choice.name)"
					:description="choice.description"
				/>
			</RadioGroup>
			<div class="flex min-h-11 items-center">
				<Checkbox
					v-model="form.urgent"
					class="w-full py-3"
					:label="__('This request is urgent')"
					size="md"
				/>
			</div>
			<FormControl
				v-model="form.recipient_type"
				type="select"
				:label="__('Prayer for')"
				size="lg"
				:options="recipientTypes"
			/>
			<RecipientPicker
				v-model="form.recipient"
				page="prayer-request"
				:doctype="form.recipient_type"
				:initial-label="initialRecipientLabel"
				:label="__('Who is it for?')"
				:description="__('Leave blank for a general request.')"
			/>
			<FormControl
				v-model="form.request"
				type="textarea"
				:rows="4"
				:label="__('Request')"
				size="lg"
				:required="isRequestRequired"
				:error="errors.request"
			/>
		</form>
		<template #actions>
			<Button
				variant="solid"
				size="lg"
				type="submit"
				form="prayer-form"
				:loading="save.loading"
				:label="__('Send')"
			/>
			<Button
				size="lg"
				variant="outline"
				:label="__('Cancel')"
				@click="open = false"
			/>
		</template>
	</FormSheet>
</template>

<script setup lang="ts">
import { __ } from "@/translate";
import { Button, Checkbox, FormControl, Radio, RadioGroup } from "frappe-ui";
import { computed, reactive, watch } from "vue";

import { useAction } from "@/api";
import FormSheet from "@/components/FormSheet.vue";

import RecipientPicker from "./RecipientPicker.vue";
import type { PrayerForm, PrayerRequest, Saved } from "./types";

const props = defineProps<{
	data: PrayerForm;
	request?: PrayerRequest | null;
}>();
const emit = defineEmits<{ saved: [] }>();
const open = defineModel<boolean>("open", { default: false });

type SaveParams = {
	title: string;
	type: string;
	visibility: string;
	urgent: number;
	recipient_type: string;
	recipient: string;
	request: string;
	name?: string;
};

const save = useAction<Saved, SaveParams>("care.save_prayer_request");
const errors = reactive({ title: "", type: "", request: "" });
const form = reactive({
	title: "",
	type: "",
	visibility: "Private",
	urgent: false,
	recipient_type: "Person",
	recipient: null as string | null,
	request: "",
});

const types = computed(() =>
	props.data.types.map((type) => ({ label: type.name, value: type.name })),
);
const recipientTypes = computed(() =>
	props.data.recipient_doctypes.map((name) => ({
		label: __(name),
		value: name,
	})),
);
const isRequestRequired = computed(
	() => !["Unspoken", "Salvation"].includes(form.type),
);
const initialRecipientLabel = computed(() => {
	if (props.request) return props.request.recipient_name || undefined;
	return props.data.me.full_name;
});

function reset() {
	const request = props.request;
	Object.assign(errors, { title: "", type: "", request: "" });
	Object.assign(form, {
		title: request?.title || "",
		type: request?.type || "",
		visibility: request?.visibility || "Private",
		urgent: Boolean(request?.urgent),
		recipient_type: request?.recipient_type || "Person",
		recipient: request ? request.recipient || null : props.data.me.name,
		request: request?.request || "",
	});
}

watch(open, (isOpen) => isOpen && reset(), { immediate: true });

async function submit() {
	errors.title = form.title.trim() ? "" : __("Enter a title.");
	errors.type = form.type ? "" : __("Choose a type.");
	errors.request =
		!isRequestRequired.value || form.request.trim()
			? ""
			: __("Write the request.");
	if (errors.title || errors.type || errors.request) return;

	const params: SaveParams = {
		...form,
		urgent: form.urgent ? 1 : 0,
		recipient: form.recipient || "",
		name: props.request?.name,
	};
	await save.submit(params).then(
		() => {
			open.value = false;
			emit("saved");
		},
		() => {},
	);
}
</script>
