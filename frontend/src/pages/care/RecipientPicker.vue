<template>
	<Combobox
		v-model="value"
		v-model:query="query"
		:options="options"
		:filterable="false"
		:loading="search.loading"
		:label="label"
		:description="description"
		:placeholder="__('Type a name')"
		:empty-text="__('No one found')"
		size="lg"
		@update:open="onOpen"
		@update:query="find"
	/>
</template>

<script setup lang="ts">
import { Combobox } from "frappe-ui";
import { computed, ref, watch } from "vue";

import { useRead } from "@/api";

import type { Recipient } from "./types";

const props = defineProps<{
	doctype: string;
	initialLabel?: string;
	label: string;
	description?: string;
}>();
const value = defineModel<string | null>({ default: null });

const search = useRead<{ items: Recipient[] }, { doctype: string; txt: string }>(
	"care.search_recipients",
	{ immediate: false }
);
const found = ref<Recipient[]>([]);
const picked = ref<Recipient | null>(null);
const query = ref(props.initialLabel || "");
let requestId = 0;

const options = computed(() => {
	const rows = [...found.value];
	const current =
		picked.value ||
		(value.value && props.initialLabel
			? { name: value.value, label: props.initialLabel }
			: null);
	if (current && !rows.some((row) => row.name === current.name)) rows.unshift(current);
	return rows.map((row) => ({ label: row.label, value: row.name }));
});

async function find(text: string) {
	const id = ++requestId;
	const result = await search.submit({ doctype: props.doctype, txt: text }).catch(() => null);
	if (id === requestId && result) found.value = result.items;
}

function onOpen(open: boolean) {
	if (open) find("");
}

watch(value, (name) => {
	picked.value = found.value.find((row) => row.name === name) || picked.value;
});
watch(
	() => props.doctype,
	() => {
		found.value = [];
		picked.value = null;
		value.value = null;
		query.value = "";
	}
);
</script>
