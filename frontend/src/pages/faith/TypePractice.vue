<template>
	<div>
		<div
			class="flex flex-wrap items-baseline gap-x-7 gap-y-1 text-lg tabular-nums text-ink-gray-6"
			role="status"
			aria-live="polite"
		>
			<span>{{ statusLine }}</span>
		</div>

		<div ref="stage" class="mt-6 cursor-text" @click="focusInput">
			<p
				class="t-scripture is-large text-ink-gray-9"
				:aria-label="
					__('The passage, with the words you have not typed hidden')
				"
			>
				<template v-for="(token, index) in tokens" :key="index">
					<span v-if="token.kind === 'verse'" class="verse-number">{{
						token.raw
					}}</span>
					<span v-else-if="token.kind === 'other'"
						>{{ token.raw }}{{ " " }}</span
					>
					<template v-else>
						<span
							:ref="
								(element) => setWord(token.wordIndex, element)
							"
							:class="wordClass(token.wordIndex)"
							:style="wordStyle(token.wordIndex)"
							>{{ token.raw }}</span>{{ " " }}
					</template>
				</template>
			</p>
		</div>

		<input
			ref="input"
			class="fixed start-0 top-0 size-px border-0 p-0 opacity-0"
			type="text"
			autocapitalize="off"
			autocomplete="off"
			autocorrect="off"
			spellcheck="false"
			:aria-label="__('Type the first letter of each word')"
			@input="onInput"
			@compositionstart="composing = true"
			@compositionend="onCompositionEnd"
		/>

		<div class="mt-8 border-t border-outline-gray-1 pt-5">
			<p v-if="finished" class="text-lg text-ink-gray-8">
				{{ __("Saving your session...") }}
			</p>
			<p v-else class="text-p-lg text-ink-gray-6 md:text-p-md">
				{{ isTouch ? __("Tap the passage to open the keyboard.") : "" }}
				{{
					__(
						"Each wrong letter takes 2% off your progress. Finish with no mistakes to add 50%, or with 1 or 2 mistakes to add 10%.",
					)
				}}
			</p>
		</div>
	</div>
</template>

<script setup lang="ts">
import {
	computed,
	nextTick,
	onBeforeUnmount,
	onMounted,
	reactive,
	ref,
} from "vue";

import { useFrappeAction } from "@/api";
import { __ } from "@/translate";

import { baseLetter, tokenize } from "./tokenize";

const MODULE =
	"churchit.church_study.doctype.bible_memory_item.bible_memory_item";

const props = defineProps<{
	name: string;
	text: string;
	progress: number;
	wordMistakes: Record<string, number>;
}>();
const emit = defineEmits<{
	progress: [value: number];
	finished: [result: Record<string, unknown>];
}>();

const tokens = tokenize(props.text);
const words = tokens.filter((token) => token.kind === "word");
const position = ref(0);
const mistakes = ref(0);
const finished = ref(false);
const correct = new Set<number>();
const slips = reactive<Record<number, number>>(
	Object.fromEntries(
		Object.entries(props.wordMistakes).map(([index, count]) => [
			Number(index),
			count,
		]),
	),
);
const currentProgress = ref(props.progress);
const flashing = ref<number | null>(null);

const wordElements = new Map<number, HTMLElement>();
const input = ref<HTMLInputElement>();
const stage = ref<HTMLElement>();
const composing = ref(false);
let typedCount = 0;

const recordMistake = useFrappeAction<
	{ progress: number },
	{ name: string; word_index: number }
>(`${MODULE}.record_mistake`);
const completeSession = useFrappeAction<
	Record<string, unknown>,
	{
		name: string;
		mode: string;
		mistakes: number;
		correct_word_indices: number[];
	}
>(`${MODULE}.complete_session`);

const isTouch = window.matchMedia("(pointer: coarse)").matches;
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

const statusLine = computed(() =>
	mistakes.value === 1
		? __("{0} of {1} words, 1 mistake so far", [
				position.value,
				words.length,
			])
		: __("{0} of {1} words, {2} mistakes so far", [
				position.value,
				words.length,
				mistakes.value,
			]),
);

/** Words you have not typed blur more as your progress grows, and hide fully from 50%. */
function blurFor(progress: number): number {
	return Math.pow(Math.min(1, Math.max(0, progress / 50)), 2) * 20;
}

function wordClass(index: number): string {
	if (index < position.value) return slips[index] ? "word-slip" : "";
	const current =
		index === position.value ? "word-blank is-current" : "word-blank";
	return flashing.value === index ? `${current} word-slip` : current;
}

function wordStyle(index: number): Record<string, string> | undefined {
	if (index < position.value || currentProgress.value >= 50) return undefined;
	const blur = blurFor(currentProgress.value);
	return { color: "inherit", filter: blur > 0 ? `blur(${blur}px)` : "none" };
}

function setWord(index: number, element: unknown) {
	if (element instanceof HTMLElement) wordElements.set(index, element);
}

async function showCurrent() {
	await nextTick();
	wordElements
		.get(position.value)
		?.scrollIntoView({
			behavior: reducedMotion.matches ? "auto" : "smooth",
			block: "center",
		});
}

function focusInput() {
	input.value?.focus({ preventScroll: true });
}

function typeLetter(typed: string) {
	if (finished.value || position.value >= words.length) return;
	const key = baseLetter(typed);
	if (!/^\p{L}$/u.test(key)) return;
	const target = words[position.value];
	if (key === target.firstLetter) return acceptWord(target.wordIndex);
	rejectWord(target.wordIndex);
}

function acceptWord(index: number) {
	if (slips[index]) slips[index] -= 1;
	correct.add(index);
	position.value += 1;
	if (position.value < words.length) return showCurrent();
	finished.value = true;
	input.value?.blur();
	save();
}

function rejectWord(index: number) {
	slips[index] = (slips[index] || 0) + 1;
	mistakes.value += 1;
	flashing.value = index;
	setTimeout(() => flashing.value === index && (flashing.value = null), 350);
	recordMistake.submit({ name: props.name, word_index: index }).then(
		(result) => {
			if (!result) return;
			currentProgress.value = result.progress;
			emit("progress", result.progress);
		},
		() => {},
	);
}

async function save() {
	await completeSession
		.submit({
			name: props.name,
			mode: "type",
			mistakes: mistakes.value,
			correct_word_indices: [...correct],
		})
		.then(
			(result) => result && emit("finished", result),
			() => (finished.value = false),
		);
}

/** A keyboard types into the page; a phone's on-screen keyboard needs a focused field, which a tap opens. */
function onKeydown(event: KeyboardEvent) {
	if (document.activeElement === input.value) return;
	if (
		event.metaKey ||
		event.ctrlKey ||
		event.altKey ||
		event.key.length !== 1
	)
		return;
	event.preventDefault();
	typeLetter(event.key);
}

/** A phone keyboard may compose a word in the field: take only the new letters, and empty it once composed. */
function onInput() {
	const field = input.value;
	if (!field) return;
	const letters = [...field.value];
	letters.slice(typedCount).forEach(typeLetter);
	typedCount = letters.length;
	if (!composing.value) clearInput();
}

function onCompositionEnd() {
	composing.value = false;
	clearInput();
}

function clearInput() {
	if (input.value) input.value.value = "";
	typedCount = 0;
}

onMounted(() => {
	document.addEventListener("keydown", onKeydown);
	showCurrent();
	if (!isTouch) focusInput();
});
onBeforeUnmount(() => document.removeEventListener("keydown", onKeydown));
</script>
