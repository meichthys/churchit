<template>
	<PageHead :crumbs="[{ label: __('Bible') }]" />

	<PageBody>
		<Masthead
			:title="__('Bible')"
			:label="boot.church?.title"
			:dateline="__('Read a chapter in the church\'s translations')"
		/>

		<LoadState :resource="translations" v-slot="{ data: choices }">
			<EmptyState
				v-if="!choices.length"
				:title="__('No Bible text yet')"
				:body="
					__('The church has not set up a translation to read. Ask the church office.')
				"
			/>
			<template v-else>
				<div
					class="mt-6 grid gap-3 sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1.4fr)_minmax(0,0.7fr)]"
				>
					<FormControl
						type="select"
						size="lg"
						class="[&_button]:min-h-11 [&_input]:min-h-11"
						:label="__('Translation')"
						:model-value="translation"
						:options="
							choices.map((item) => ({
								label: `${item.name} · ${item.translation}`,
								value: item.name,
							}))
						"
						@update:model-value="pickTranslation(String($event))"
					/>
					<FormControl
						type="select"
						size="lg"
						class="[&_button]:min-h-11 [&_input]:min-h-11"
						:label="__('Book')"
						:disabled="!books.data"
						:model-value="book"
						:options="
							(books.data || []).map((item) => ({
								label: item.name,
								value: item.id,
							}))
						"
						@update:model-value="pickBook(String($event))"
					/>
					<FormControl
						type="select"
						size="lg"
						class="[&_button]:min-h-11 [&_input]:min-h-11"
						:label="__('Chapter')"
						:disabled="!currentBook"
						:model-value="String(chapter)"
						:options="chapterOptions"
						@update:model-value="go(book, Number($event))"
					/>
				</div>

				<div
					v-if="books.error || chapterCall.error"
					class="mt-8 border-t border-outline-gray-1 py-8"
					role="alert"
				>
					<p class="text-lg text-ink-gray-8">
						{{ errorText(books.error || chapterCall.error) }}
					</p>
					<p class="mt-1 text-p-lg text-ink-gray-6">
						{{ __("Pick another translation, or try again.") }}
					</p>
					<Button
						class="mt-4 min-h-11"
						size="lg"
						:label="__('Try again')"
						@click="loadBooks"
					/>
				</div>
				<div
					v-else-if="!books.data || chapterCall.loading"
					class="mt-8 space-y-4 border-t border-outline-gray-1 pt-8"
					aria-busy="true"
					:aria-label="__('Loading')"
				>
					<p v-if="!books.data" class="t-dateline text-ink-gray-6">
						{{ __("Opening {0}. The first time can take a minute.", [translation]) }}
					</p>
					<div
						v-for="line in 6"
						:key="line"
						class="h-5 animate-pulse rounded-4 bg-surface-gray-2"
						:style="{ width: `${96 - line * 8}%` }"
					/>
				</div>
				<article v-else-if="currentBook" class="mt-8 border-t border-outline-gray-1 pt-8">
					<h2 class="t-title text-ink-gray-9" :dir="direction">
						{{ currentBook.name }} {{ chapter }}
					</h2>
					<div class="mt-6 max-w-[40rem]" :dir="direction">
						<template v-for="(block, index) in blocks" :key="index">
							<h3
								v-if="block.type === 'heading'"
								class="t-subhead mb-2 mt-8 text-ink-gray-9"
							>
								{{ block.text }}
							</h3>
							<p
								v-else-if="block.type === 'subtitle'"
								class="t-dateline mb-3 text-ink-gray-6"
							>
								{{ block.text }}
							</p>
							<p
								v-else-if="block.type === 'verses'"
								class="t-scripture text-ink-gray-9"
							>
								<template v-for="verse in block.verses" :key="verse.number">
									<span class="verse-number">{{ verse.number }}</span
									><span class="whitespace-pre-line">{{ verse.text }}</span
									>{{ " " }}
								</template>
							</p>
						</template>
					</div>
					<nav
						class="mt-10 flex flex-wrap items-center justify-between gap-3 border-t border-outline-gray-1 pt-5"
						:aria-label="__('Chapters')"
					>
						<Button
							v-if="previous"
							variant="outline"
							size="lg"
							class="min-h-11"
							:label="chapterLabel(previous)"
							@click="go(previous.id, previous.chapter)"
						>
							<template #prefix
								><span
									class="lucide-chevron-left size-4 rtl:-scale-x-100"
									aria-hidden="true"
							/></template>
						</Button>
						<span v-else />
						<Button
							v-if="following"
							variant="outline"
							size="lg"
							class="min-h-11"
							:label="chapterLabel(following)"
							@click="go(following.id, following.chapter)"
						>
							<template #suffix
								><span
									class="lucide-chevron-right size-4 rtl:-scale-x-100"
									aria-hidden="true"
							/></template>
						</Button>
					</nav>
					<p class="t-label mt-8 text-ink-gray-5">{{ translationTitle }}</p>
				</article>
			</template>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Button, FormControl, shellScrollContainer, useCall } from "frappe-ui";
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { boot } from "@/boot";
import EmptyState from "@/components/EmptyState.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import { errorText } from "@/api";
import { __ } from "@/translate";

interface TranslationChoice {
	name: string;
	translation: string;
	text_direction: string | null;
}
interface BookEntry {
	id: string;
	name: string;
	chapters: number;
}
interface ChapterItem {
	type: "heading" | "hebrew_subtitle" | "line_break" | "verse";
	text?: string;
	number?: number;
}
type Block =
	| { type: "heading" | "subtitle"; text: string }
	| { type: "verses"; verses: { number: number; text: string }[] };
interface Place {
	id: string;
	name: string;
	chapter: number;
}

const SCRIPTURE = "/api/v2/method/churchit.scripture";
const route = useRoute();
const router = useRouter();

const translations = useCall<TranslationChoice[]>({
	url: `${SCRIPTURE}.get_readable_translations`,
	method: "GET",
});
const books = useCall<BookEntry[], { translation: string }>({
	url: `${SCRIPTURE}.get_books`,
	method: "GET",
	immediate: false,
});
const chapterCall = useCall<ChapterItem[], { book: string; chapter: number; translation: string }>(
	{
		url: `${SCRIPTURE}.get_chapter`,
		method: "GET",
		immediate: false,
	}
);

const translation = ref(String(route.query.translation || ""));
const book = ref(String(route.query.book || "").toUpperCase());
const chapter = ref(Number(route.query.chapter) || 1);

const currentBook = computed(() => books.data?.find((entry) => entry.id === book.value) || null);
const translationTitle = computed(
	() =>
		translations.data?.find((entry) => entry.name === translation.value)?.translation ||
		translation.value
);
const direction = computed(() =>
	translations.data?.find((entry) => entry.name === translation.value)?.text_direction === "RTL"
		? "rtl"
		: "ltr"
);
const chapterOptions = computed(() =>
	Array.from({ length: currentBook.value?.chapters || 0 }, (_, index) => ({
		label: String(index + 1),
		value: String(index + 1),
	}))
);

const places = computed<Place[]>(() =>
	(books.data || []).flatMap((entry) =>
		Array.from({ length: entry.chapters }, (_, index) => ({
			id: entry.id,
			name: entry.name,
			chapter: index + 1,
		}))
	)
);
const position = computed(() =>
	places.value.findIndex((place) => place.id === book.value && place.chapter === chapter.value)
);
const previous = computed(() => (position.value > 0 ? places.value[position.value - 1] : null));
const following = computed(() =>
	position.value >= 0 ? places.value[position.value + 1] || null : null
);

/** Verses join one paragraph until a line break; a heading or subtitle stands on its own. */
const blocks = computed<Block[]>(() => {
	const result: Block[] = [];
	let verses: { number: number; text: string }[] | null = null;
	for (const item of chapterCall.data || []) {
		if (item.type === "verse") {
			if (!verses) result.push({ type: "verses", verses: (verses = []) });
			verses.push({ number: item.number || 0, text: item.text || "" });
			continue;
		}
		verses = null;
		if (item.type === "heading") result.push({ type: "heading", text: item.text || "" });
		if (item.type === "hebrew_subtitle")
			result.push({ type: "subtitle", text: item.text || "" });
	}
	return result;
});

function chapterLabel(place: Place): string {
	return `${place.name} ${place.chapter}`;
}

async function loadBooks() {
	if (!translation.value) return;
	const found = await books.submit({ translation: translation.value }).catch(() => null);
	if (!found) return;
	if (!found.some((entry) => entry.id === book.value)) {
		book.value = found[0]?.id || "";
		chapter.value = 1;
	}
	chapter.value = Math.min(
		Math.max(chapter.value, 1),
		found.find((entry) => entry.id === book.value)?.chapters || 1
	);
	await loadChapter();
}

async function loadChapter() {
	if (!book.value) return;
	await chapterCall
		.submit({ book: book.value, chapter: chapter.value, translation: translation.value })
		.catch(() => {});
	router.replace({
		query: {
			translation: translation.value,
			book: book.value,
			chapter: String(chapter.value),
		},
	});
}

function pickTranslation(name: string) {
	translation.value = name;
	books.reset();
	loadBooks();
}

function pickBook(id: string) {
	go(id, 1);
}

function go(id: string, number: number) {
	book.value = id;
	chapter.value = number;
	loadChapter();
	shellScrollContainer.value?.scrollTo({ top: 0 });
}

watch(
	() => translations.data,
	(choices) => {
		if (!choices?.length) return;
		if (!choices.some((entry) => entry.name === translation.value))
			translation.value = choices[0].name;
		loadBooks();
	},
	{ immediate: true }
);
</script>
