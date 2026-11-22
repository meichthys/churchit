<template>
	<FormSheet
		v-model:open="open"
		:title="__('Add a file')"
		:description="__('Only the members of the group and the church staff can open it.')"
	>
		<div class="space-y-4">
			<FormControl
				size="lg"
				class="[&_input]:min-h-11 [&_select]:min-h-11 [&_button]:min-h-11"
				v-model="form.group"
				type="select"
				:label="__('Group')"
				:options="groups"
				:placeholder="__('Choose a group')"
			/>
			<FormControl
				size="lg"
				class="[&_input]:min-h-11 [&_select]:min-h-11 [&_button]:min-h-11"
				v-model="form.title"
				type="text"
				:label="__('Title')"
				:placeholder="__('Title')"
			/>
			<div>
				<p class="mb-1.5 text-sm text-ink-gray-5">{{ __("File") }}</p>
				<FileUploader :validate-file="checkSize" @success="attachFile">
					<template #default="{ openFileSelector, uploading, progress, file, error }">
						<Button
							size="lg"
							class="min-h-11"
							icon-left="lucide-paperclip"
							:loading="uploading"
							:label="file && !error ? file.name : __('Choose a file')"
							@click="openFileSelector"
						/>
						<p v-if="uploading" class="mt-1.5 text-lg text-ink-gray-6 md:text-md">
							{{ __("Uploading, {0}%", [progress]) }}
						</p>
						<ErrorMessage v-if="error" class="mt-1.5" :message="error" />
					</template>
				</FileUploader>
			</div>
		</div>
		<template #actions>
			<Button
				variant="solid"
				size="lg"
				:label="__('Add the file')"
				:disabled="!canSave"
				:loading="save.loading"
				@click="submit"
			/>
			<Button variant="subtle" size="lg" :label="__('Cancel')" @click="open = false" />
		</template>
	</FormSheet>
</template>

<script setup lang="ts">
import { Button, ErrorMessage, FileUploader, FormControl, toast } from "frappe-ui";
import { computed, reactive, watch } from "vue";

import { useFrappeAction } from "@/api";
import FormSheet from "@/components/FormSheet.vue";
import { __ } from "@/translate";

const props = defineProps<{ groups: { value: string; label: string }[]; initialGroup?: string }>();
const emit = defineEmits<{ added: [] }>();
const open = defineModel<boolean>("open", { default: false });

const MAX_BYTES = 25 * 1024 * 1024;
const form = reactive({ group: "", title: "", file_url: "" });
const save = useFrappeAction<unknown, Record<string, unknown>>(
	"frappe.website.doctype.web_form.web_form.accept"
);
const canSave = computed(() => Boolean(form.group && form.title.trim() && form.file_url));

watch(
	open,
	(isOpen) => {
		if (!isOpen) return;
		Object.assign(form, {
			group: props.initialGroup || (props.groups.length === 1 ? props.groups[0].value : ""),
			title: "",
			file_url: "",
		});
	},
	{ immediate: true }
);

function checkSize(file: File) {
	if (file.size > MAX_BYTES) return __("This file is too large. Choose one under 25 MB.");
}

function attachFile(uploaded: { file_url: string }) {
	form.file_url = uploaded.file_url;
}

async function submit() {
	const data = {
		doctype: "Group File",
		group: form.group,
		title: form.title.trim(),
		attached_file: form.file_url,
	};
	await save.submit({ web_form: "group-files", data: JSON.stringify(data) }).then(
		() => {
			toast.success(__("File added."));
			open.value = false;
			emit("added");
		},
		() => {}
	);
}
</script>
