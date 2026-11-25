<template>
	<div
		class="[&_input:not([type=checkbox])]:min-h-11 [&_select]:min-h-11 [&_input]:text-lg"
	>
		<ul
			class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
		>
			<li
				v-for="(row, index) in rows"
				:key="row.name || `new-${index}`"
				class="space-y-3 py-4"
			>
				<div class="flex items-end gap-2">
					<FormControl
						size="lg"
						v-model="row[valueField]"
						class="min-w-0 flex-1"
						:type="kind === 'email' ? 'email' : 'tel'"
						:label="
							kind === 'email'
								? __('Email address')
								: __('Phone number')
						"
						autocomplete="off"
					/>
					<Button
						variant="ghost"
						size="lg"
						class="min-h-11 min-w-11"
						icon="lucide-trash-2"
						:aria-label="
							kind === 'email'
								? __('Remove this email address')
								: __('Remove this phone number')
						"
						@click="remove(index)"
					/>
				</div>
				<div class="flex flex-wrap items-end gap-x-4 gap-y-3">
					<FormControl
						size="lg"
						v-model="row[typeField]"
						class="min-w-[10rem] flex-1"
						type="select"
						:label="__('Type')"
						:options="
							types.map((type) => ({
								label: __(type),
								value: type,
							}))
						"
						:placeholder="__('Choose a type')"
					/>
					<FormControl
						type="checkbox"
						:model-value="Boolean(row.is_primary)"
						:label="
							kind === 'email'
								? __('Use this one to reach me')
								: __('Call this one')
						"
						class="min-h-11"
						@update:model-value="
							(value: boolean) => makePrimary(index, value)
						"
					/>
				</div>
				<div
					v-if="row.shared_from"
					class="flex flex-wrap items-center gap-2 text-lg text-ink-gray-7 md:text-md"
				>
					<span>{{
						__("Shared with {0}", [
							row.shared_from_title || row.shared_from,
						])
					}}</span>
					<Button
						variant="ghost"
						size="lg"
						class="min-h-11"
						:label="__('Not shared')"
						@click="unshare(row)"
					/>
				</div>
				<p
					v-else-if="holders[index] && !holders[index].length"
					class="text-lg text-ink-gray-7 md:text-md"
				>
					{{
						kind === "email"
							? __(
									"No one you can choose here has this email address. Ask the church office if it is shared.",
								)
							: __(
									"No one you can choose here has this phone number. Ask the church office if it is shared.",
								)
					}}
				</p>
				<div
					v-else-if="holders[index]"
					class="flex flex-wrap items-end gap-2"
				>
					<FormControl
						size="lg"
						class="min-w-[12rem] flex-1"
						type="select"
						:label="
							__('Someone else already has this. Shared with')
						"
						:options="
							holders[index].map((holder) => ({
								label: holder.title,
								value: holder.name,
							}))
						"
						:placeholder="__('Choose a person')"
						@update:model-value="
							(value: string) => share(row, index, value)
						"
					/>
				</div>
				<div v-else-if="row[valueField]">
					<Button
						variant="ghost"
						size="lg"
						class="min-h-11"
						:label="__('Shared with someone else?')"
						@click="findHolders(row, index)"
					/>
				</div>
			</li>
		</ul>
		<Button
			variant="outline"
			size="lg"
			class="mt-3 min-h-11"
			icon-left="lucide-plus"
			:label="
				kind === 'email'
					? __('Add an email address')
					: __('Add a phone number')
			"
			@click="add"
		/>
	</div>
</template>

<script setup lang="ts">
import { Button, FormControl } from "frappe-ui";
import { computed, reactive } from "vue";

import { reportError, useRead } from "@/api";
import { __ } from "@/translate";

export interface ContactRow {
	name?: string;
	is_primary: number | boolean;
	shared_from: string | null;
	shared_from_title?: string;
	[column: string]: unknown;
}

const props = defineProps<{
	kind: "email" | "phone";
	person: string;
	types: string[];
}>();
const rows = defineModel<ContactRow[]>("rows", { required: true });
const lookup = useRead<
	{ items: { name: string; title: string }[] },
	Record<string, any>
>("account.get_holders", { immediate: false });
const holders = reactive<Record<number, { name: string; title: string }[]>>({});

const valueField = computed(() =>
	props.kind === "email" ? "email_address" : "phone_number",
);
const typeField = computed(() =>
	props.kind === "email" ? "email_type" : "phone_type",
);

function add() {
	rows.value.push({
		[valueField.value]: "",
		[typeField.value]: props.types[0] ?? null,
		is_primary: rows.value.length === 0,
		shared_from: null,
	});
}

function remove(index: number) {
	rows.value.splice(index, 1);
	for (const key of Object.keys(holders)) delete holders[Number(key)];
}

function makePrimary(index: number, value: boolean) {
	rows.value.forEach(
		(row, position) =>
			(row.is_primary = value && position === index ? 1 : 0),
	);
	if (!value && rows.value.length) rows.value[index].is_primary = 1;
}

function share(row: ContactRow, index: number, person: string) {
	row.shared_from = person;
	row.shared_from_title = holders[index]?.find(
		(holder) => holder.name === person,
	)?.title;
}

function unshare(row: ContactRow) {
	row.shared_from = null;
	row.shared_from_title = undefined;
}

async function findHolders(row: ContactRow, index: number) {
	const result = await lookup
		.submit({
			kind: props.kind,
			value: String(row[valueField.value]),
			person: props.person,
		})
		.catch((error: unknown) => void reportError(error));
	if (result) holders[index] = result.items;
}
</script>
