<template>
	<FormSheet
		v-model:open="open"
		:title="request ? __('Change your request') : __('Ask for care')"
		:description="
			__('The care team reads every request. Say how we can help.')
		"
	>
		<form id="care-form" class="space-y-5" @submit.prevent="submit">
			<FormControl
				v-model="form.category"
				type="select"
				:label="__('Category')"
				size="lg"
				required
				:options="categories"
				:placeholder="__('Choose a category')"
				:error="errors.category"
			/>
			<FormControl
				v-model="form.urgency"
				type="select"
				:label="__('Urgency')"
				size="lg"
				:options="urgencies"
			/>
			<FormControl
				v-model="form.description"
				type="textarea"
				:rows="5"
				:label="__('How can we help?')"
				size="lg"
				required
				:error="errors.description"
			/>
			<FormControl
				v-model="form.preferred_contact"
				type="select"
				:label="__('How should we reach you?')"
				size="lg"
				:options="contacts"
				:placeholder="__('No preference')"
			/>
		</form>
		<template #actions>
			<Button
				variant="solid"
				size="lg"
				type="submit"
				form="care-form"
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
import { Button, FormControl } from "frappe-ui";
import { computed, reactive, watch } from "vue";

import { useAction } from "@/api";
import FormSheet from "@/components/FormSheet.vue";

import type { CareForm, CareRequest, Saved } from "./types";

const props = defineProps<{ data: CareForm; request?: CareRequest | null }>();
const emit = defineEmits<{ saved: [] }>();
const open = defineModel<boolean>("open", { default: false });

const errors = reactive({ category: "", description: "" });
const form = reactive({
	category: "",
	urgency: "",
	description: "",
	preferred_contact: "",
});
const save = useAction<Saved, typeof form & { name?: string }>(
	"care.save_care_request",
);

const categories = computed(() =>
	props.data.categories.map((row) => ({ label: row.name, value: row.name })),
);
const urgencies = computed(() =>
	props.data.urgencies.map((name) => ({ label: __(name), value: name })),
);
const contacts = computed(() =>
	props.data.preferred_contacts.map((name) => ({
		label: __(name),
		value: name,
	})),
);

function reset() {
	const request = props.request;
	Object.assign(errors, { category: "", description: "" });
	Object.assign(form, {
		category: request?.category || "",
		urgency: request?.urgency || props.data.default_urgency,
		description: request?.description || "",
		preferred_contact: request?.preferred_contact || "",
	});
}

watch(open, (isOpen) => isOpen && reset(), { immediate: true });

async function submit() {
	errors.category = form.category ? "" : __("Choose a category.");
	errors.description = form.description.trim()
		? ""
		: __("Say how we can help.");
	if (errors.category || errors.description) return;

	await save.submit({ ...form, name: props.request?.name }).then(
		() => {
			open.value = false;
			emit("saved");
		},
		() => {},
	);
}
</script>
