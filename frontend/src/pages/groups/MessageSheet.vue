<template>
	<FormSheet
		v-model:open="open"
		:title="__('Message the group')"
		:description="
			__(
				'Everyone in the group who has agreed to group messages gets it.',
			)
		"
	>
		<div class="space-y-4">
			<FormControl
				size="lg"
				class="[&_input]:min-h-11 [&_select]:min-h-11 [&_button]:min-h-11"
				v-if="channels.length > 1"
				v-model="form.channel"
				type="select"
				:label="__('Send by')"
				:options="channels"
			/>
			<FormControl
				size="lg"
				class="[&_input]:min-h-11"
				v-model="form.subject"
				type="text"
				:label="__('Subject')"
				:placeholder="__('Subject')"
			/>
			<FormControl
				size="lg"
				v-model="form.message"
				type="textarea"
				:rows="5"
				:label="__('Message')"
				:placeholder="__('Message')"
			/>
		</div>
		<template #actions>
			<Button
				variant="solid"
				size="lg"
				:label="__('Send')"
				:disabled="!canSend"
				:loading="send.loading"
				@click="submit"
			/>
			<Button
				variant="subtle"
				size="lg"
				:label="__('Cancel')"
				@click="open = false"
			/>
		</template>
	</FormSheet>
</template>

<script setup lang="ts">
import { Button, FormControl, toast } from "frappe-ui";
import { computed, reactive, watch } from "vue";

import { useFrappeAction } from "@/api";
import FormSheet from "@/components/FormSheet.vue";
import { __ } from "@/translate";

const props = defineProps<{
	group: string;
	canEmail: boolean;
	canText: boolean;
}>();
const open = defineModel<boolean>("open", { default: false });

const form = reactive({ channel: "Email", subject: "", message: "" });
const send = useFrappeAction<number, Record<string, unknown>>(
	"churchit.church_people.group_api.message_group",
);

const channels = computed(() => [
	...(props.canEmail ? [{ value: "Email", label: __("Email") }] : []),
	...(props.canText ? [{ value: "SMS", label: __("Text message") }] : []),
]);
const canSend = computed(() =>
	Boolean(form.subject.trim() && form.message.trim()),
);

watch(open, (isOpen) => {
	if (isOpen)
		Object.assign(form, {
			channel: channels.value[0]?.value || "Email",
			subject: "",
			message: "",
		});
});

async function submit() {
	const reached = await send
		.submit({ group: props.group, ...form })
		.catch(() => null);
	if (reached === null) return;

	open.value = false;
	if (reached) toast.success(__("Your message is on its way."));
	else
		toast.warning(
			__(
				"No one received it. People get group messages only when they have agreed to them.",
			),
		);
}
</script>
