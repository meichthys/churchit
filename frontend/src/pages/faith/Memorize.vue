<template>
	<PageHead :crumbs="[{ label: __('Bible Memory') }]">
		<template #actions>
			<Button
				variant="solid"
				icon-left="lucide-plus"
				:label="__('Add a passage')"
				@click="openAdd"
			/>
		</template>
		<template #mobile>
			<Button
				variant="ghost"
				size="lg"
				icon="lucide-plus"
				class="min-h-11 min-w-11"
				:label="__('Add a passage')"
				@click="openAdd"
			/>
		</template>
	</PageHead>

	<PageBody>
		<Masthead
			:title="__('Bible Memory')"
			:label="boot.church?.title"
			:dateline="__('Passages you are memorizing')"
		>
			<template #aside>
				<figure class="hidden max-w-[22rem] pb-1 text-end md:block">
					<blockquote class="t-dateline text-ink-gray-7">
						{{ __("I have stored up your word in my heart.") }}
					</blockquote>
					<figcaption class="t-label mt-1.5 text-ink-gray-5">
						{{ __("Psalm 119:11") }}
					</figcaption>
				</figure>
			</template>
		</Masthead>

		<LoadState :resource="list" v-slot="{ data }">
			<div v-if="groupOptions(data).length > 1" class="mt-6">
				<TabButtons
					v-model="groupFilter"
					class="[&_button]:min-h-11 md:[&_button]:min-h-0"
					:options="groupOptions(data)"
				/>
			</div>

			<section class="mt-8" aria-labelledby="learning">
				<SectionHead id="learning" :title="__('Learning')" />
				<ul v-if="learning(data).length" class="border-t border-outline-gray-1">
					<li
						v-for="item in learning(data)"
						:key="item.name"
						class="grid gap-x-10 gap-y-4 border-b border-outline-gray-1 py-6 md:grid-cols-[minmax(0,1fr)_11rem] md:py-7"
						:class="{ 'is-fresh': isFresh(item.name) }"
					>
						<div class="min-w-0">
							<div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
								<h3 class="t-subhead text-ink-gray-9">
									{{ item.bible_reference }}
								</h3>
								<span class="t-label text-ink-gray-6">{{ item.translation }}</span>
							</div>
							<p
								v-if="item.assigned_by_name"
								class="mt-1 text-lg text-ink-gray-6 md:text-md"
							>
								{{ __("Assigned by {0}", [item.assigned_by_name])
								}}<template v-if="item.group_name">
									{{ __("through {0}", [item.group_name]) }}</template
								>
							</p>
							<p
								v-if="item.preview"
								class="t-scripture mt-3 line-clamp-2 text-ink-gray-7"
							>
								{{ item.preview }}
							</p>
							<div class="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2">
								<div class="w-36">
									<Progress
										:value="item.progress"
										:intervals="10"
										size="md"
										:label="__('{0} learned', [item.bible_reference])"
										class="[&>div:first-child]:sr-only"
									/>
								</div>
								<span class="text-lg text-ink-gray-6 md:text-md">{{
									stateWords(item)
								}}</span>
							</div>
						</div>
						<div
							class="flex flex-wrap items-center justify-between gap-3 md:flex-col md:items-end md:justify-start"
						>
							<p
								v-if="item.progress"
								class="t-numeral text-[44px] text-ink-gray-9 md:text-[52px]"
							>
								{{ item.progress
								}}<span class="ms-0.5 text-[0.45em] text-ink-gray-6">%</span>
							</p>
							<Badge
								v-else
								:label="__('New')"
								theme="gray"
								variant="outline"
								size="lg"
							/>
							<div class="flex flex-wrap items-center gap-2">
								<Button
									variant="ghost"
									size="lg"
									class="min-h-11"
									:label="__('Remove')"
									@click="confirmRemove(item)"
								/>
								<Button
									:variant="item.progress ? 'solid' : 'outline'"
									size="lg"
									class="min-h-11 min-w-[7.5rem]"
									:label="__('Practice')"
									:route="`/memorize/${item.name}`"
								/>
							</div>
						</div>
					</li>
				</ul>
				<EmptyState
					v-else
					:title="__('Nothing to learn yet')"
					:body="
						__('Add a passage by its reference. It lists here with a Practice button.')
					"
				>
					<Button
						variant="solid"
						size="lg"
						class="min-h-11"
						icon-left="lucide-plus"
						:label="__('Add a passage')"
						@click="openAdd"
					/>
				</EmptyState>
			</section>

			<section class="mt-14" aria-labelledby="memorized">
				<SectionHead id="memorized" :title="__('Memorized')" />
				<ul
					v-if="memorized(data).length"
					class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
				>
					<li
						v-for="item in memorized(data)"
						:key="item.name"
						:class="{ 'is-fresh': isFresh(item.name) }"
					>
						<IndexRow
							:title="item.bible_reference"
							:facts="[item.translation, stateWords(item)]"
						>
							<template #prefix
								><span
									class="lucide-check size-5 text-ink-green-8"
									aria-hidden="true"
							/></template>
							<template #suffix>
								<div class="flex flex-wrap gap-2">
									<Button
										variant="ghost"
										size="lg"
										class="min-h-11"
										:label="__('Remove')"
										@click="confirmRemove(item)"
									/>
									<Button
										variant="outline"
										size="lg"
										class="min-h-11"
										:label="__('Practice')"
										:route="`/memorize/${item.name}`"
									/>
								</div>
							</template>
						</IndexRow>
					</li>
				</ul>
				<EmptyState
					v-else
					:title="__('None yet')"
					:body="__('A passage moves here once you know it by heart.')"
				/>
			</section>
		</LoadState>
	</PageBody>

	<FormSheet
		v-model:open="addOpen"
		:title="__('Add a passage')"
		:description="__('Type a reference such as John 3:16-18.')"
	>
		<div class="space-y-4">
			<FormControl
				v-model="reference"
				type="text"
				size="lg"
				class="[&_button]:min-h-11 [&_input]:min-h-11"
				:label="__('Reference')"
				:placeholder="__('John 3:16-18')"
				:error="referenceError"
				@blur="checkReference"
			/>
			<FormControl
				v-model="translation"
				type="select"
				size="lg"
				class="[&_button]:min-h-11 [&_input]:min-h-11"
				:label="__('Translation')"
				:options="
					(list.data?.translations || []).map((name) => ({
						label: `${list.data?.translation_titles[name] || name} (${name})`,
						value: name,
					}))
				"
			/>
		</div>
		<template #actions>
			<Button
				variant="solid"
				size="lg"
				:loading="add.loading"
				:label="__('Add')"
				@click="addPassage"
			/>
			<Button variant="outline" size="lg" :label="__('Cancel')" @click="addOpen = false" />
		</template>
	</FormSheet>
</template>

<script setup lang="ts">
import {
	Badge,
	Button,
	FormControl,
	Progress,
	TabButtons,
	dialog,
	toast,
	useCall,
} from "frappe-ui";
import { ref, watch } from "vue";

import { boot } from "@/boot";
import EmptyState from "@/components/EmptyState.vue";
import FormSheet from "@/components/FormSheet.vue";
import IndexRow from "@/components/IndexRow.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import SectionHead from "@/components/SectionHead.vue";
import { errorText, useAction, useRead } from "@/api";
import { useFreshInk } from "@/composables/useFreshInk";
import { useLiveRefresh } from "@/realtime";
import { __ } from "@/translate";

interface MemoryItem {
	name: string;
	bible_reference: string;
	translation: string;
	progress: number;
	memorized: boolean;
	memorized_on: string | null;
	times_memorized: number;
	assigned_by_name: string | null;
	group: string | null;
	group_name: string | null;
	preview: string | null;
}
interface MemoryList {
	items: MemoryItem[];
	translations: string[];
	translation_titles: Record<string, string>;
	default_translation: string | null;
}

const list = useRead<MemoryList>("faith.get_memory_list");
const add = useAction<{ name: string }, { reference: string; translation: string }>(
	"faith.add_memory_item",
	{ onError: () => {} }
);
const remove = useAction<{ name: string }, { item: string }>("faith.remove_memory_item");
const checkCall = useCall<{ reference?: string; problem?: string }, { text: string }>({
	url: "/api/v2/method/churchit.scripture.check_reference",
	method: "GET",
	immediate: false,
});

const { mark, isFresh } = useFreshInk();
const knownNames = ref<Set<string> | null>(null);
const namesOf = () => new Set((list.data?.items || []).map((item) => item.name));
watch(
	() => list.data,
	(data) => {
		if (!data) return;
		knownNames.value ??= namesOf();
	},
	{ immediate: true }
);
useLiveRefresh(["memory"], async (hint) => {
	await list.reload();
	const names = namesOf();
	const arrived = (list.data?.items || []).filter(
		(item) => knownNames.value && !knownNames.value.has(item.name)
	);
	knownNames.value = names;
	const hidden = arrived.filter((item) => groupFilter.value && item.group !== groupFilter.value);
	arrived.filter((item) => !hidden.includes(item)).forEach((item) => mark(item.name));
	if (hint && hidden.length) toast.success(__("A new passage is on your list."));
});

const groupFilter = ref("");
const addOpen = ref(false);
const reference = ref("");
const translation = ref("");
const referenceError = ref("");

function groupOptions(data: MemoryList) {
	const groups = [
		...new Map(
			data.items.filter((item) => item.group).map((item) => [item.group, item.group_name])
		).entries(),
	];
	return [
		{ label: __("All"), value: "" },
		...groups.map(([name, title]) => ({ label: title || String(name), value: String(name) })),
	];
}

function visible(data: MemoryList) {
	return data.items.filter((item) => !groupFilter.value || item.group === groupFilter.value);
}
const learning = (data: MemoryList) => visible(data).filter((item) => !item.memorized);
const memorized = (data: MemoryList) => visible(data).filter((item) => item.memorized);

function stateWords(item: MemoryItem): string {
	if (item.memorized) {
		const date = item.memorized_on
			? __("Memorized on {0}", [item.memorized_on])
			: __("Memorized");
		if (item.times_memorized === 1) return __("{0}, 1 perfect run", [date]);
		return item.times_memorized > 1
			? __("{0}, {1} perfect runs", [date, item.times_memorized])
			: date;
	}
	if (!item.progress) return __("Not started");
	if (item.times_memorized === 1)
		return __("{0} of 100 learned, 1 perfect run", [item.progress]);
	return item.times_memorized > 1
		? __("{0} of 100 learned, {1} perfect runs", [item.progress, item.times_memorized])
		: __("{0} of 100 learned", [item.progress]);
}

function openAdd() {
	reference.value = "";
	referenceError.value = "";
	translation.value = list.data?.default_translation || list.data?.translations[0] || "";
	addOpen.value = true;
}

async function checkReference() {
	if (!reference.value.trim()) return;
	const result = await checkCall.submit({ text: reference.value }).catch(() => null);
	referenceError.value = result?.problem || "";
	if (result?.reference) reference.value = result.reference;
}

async function addPassage() {
	referenceError.value = "";
	if (!reference.value.trim()) {
		referenceError.value = __("Type the reference of the passage.");
		return;
	}
	await add.submit({ reference: reference.value, translation: translation.value }).then(
		() => {
			addOpen.value = false;
			toast.success(__("Added to your list."));
			return list.reload();
		},
		() => {
			referenceError.value = errorText(add.error);
		}
	);
}

function confirmRemove(item: MemoryItem) {
	dialog.confirm({
		title: __("Remove {0}", [item.bible_reference]),
		message: __("The passage and your progress on it are removed from your list."),
		confirmLabel: __("Remove"),
		cancelLabel: __("Cancel"),
		theme: "red",
		onConfirm: async ({ close }) => {
			await remove.submit({ item: item.name }).then(
				() => list.reload(),
				() => {}
			);
			close();
		},
	});
}
</script>
