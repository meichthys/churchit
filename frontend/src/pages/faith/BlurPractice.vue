<template>
	<div>
		<div class="text-lg text-ink-gray-6" role="status" aria-live="polite">
			{{ statusLine }}
		</div>

		<p
			class="t-scripture is-large mt-6 text-ink-gray-9"
			:aria-label="__('The passage, with some words blurred')"
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
						class="transition-[filter] duration-150"
						:style="wordStyle(token.wordIndex)"
						>{{ token.raw }}</span>{{ " " }}
				</template>
			</template>
		</p>

		<div
			class="mt-8 flex flex-wrap items-center gap-2 border-t border-outline-gray-1 pt-5"
		>
			<Button
				variant="subtle"
				size="lg"
				class="min-h-11 touch-none select-none"
				icon-left="lucide-eye"
				:label="__('Hold to show')"
				@pointerdown="revealing = true"
				@pointerup="revealing = false"
				@pointerleave="revealing = false"
				@pointercancel="revealing = false"
				@contextmenu.prevent
				@keydown.space.prevent="revealing = true"
				@keyup.space="revealing = false"
			/>
			<Button
				variant="subtle"
				size="lg"
				class="min-h-11"
				icon-left="lucide-eye-off"
				:label="__('Hide more words')"
				@click="hideMore"
			/>
			<Button
				variant="ghost"
				size="lg"
				class="min-h-11"
				icon-left="lucide-undo-2"
				:disabled="!history.length"
				:label="__('Undo')"
				@click="undo"
			/>
			<Button
				variant="ghost"
				size="lg"
				class="min-h-11"
				icon-left="lucide-rotate-ccw"
				:label="__('Start again')"
				@click="reset"
			/>
			<Button
				variant="solid"
				size="lg"
				class="min-h-11 sm:ms-auto"
				:loading="saving"
				:label="__('Done')"
				@click="save"
			/>
		</div>
		<p class="mt-4 text-p-lg text-ink-gray-6 md:text-p-md">
			{{
				__(
					"Hold the eye to show the whole passage. Hide more words, then say the passage aloud. Done adds 5% to your progress, up to 99%. Only Type reaches 100%.",
				)
			}}
		</p>
	</div>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { computed, ref } from "vue";

import { useFrappeAction } from "@/api";
import { __ } from "@/translate";

import { tokenize } from "./tokenize";

const props = defineProps<{ name: string; text: string }>();
const emit = defineEmits<{ finished: [result: Record<string, unknown>] }>();

const MAX_LEVEL = 4;
const BLUR_BY_LEVEL = [0, 3, 6, 9, 14];

const tokens = tokenize(props.text);
const total = tokens.filter((token) => token.kind === "word").length;
const levels = ref<number[]>(new Array(total).fill(0));
const history = ref<number[][]>([]);
const revealing = ref(false);
const saving = ref(false);

const completeSession = useFrappeAction<
	Record<string, unknown>,
	{
		name: string;
		mode: string;
		mistakes: number;
		correct_word_indices: number[];
	}
>(
	"churchit.church_study.doctype.bible_memory_item.bible_memory_item.complete_session",
);

const hiddenCount = computed(
	() => levels.value.filter((level) => level > 0).length,
);
const statusLine = computed(() =>
	__("{0} of {1} words hidden", [hiddenCount.value, total]),
);

function wordStyle(index: number): Record<string, string> | undefined {
	const level = revealing.value ? 0 : levels.value[index];
	return level ? { filter: `blur(${BLUR_BY_LEVEL[level]}px)` } : undefined;
}

/** Each step hides about a sixth of the passage, chosen at random among words that can still blur more. */
function hideMore() {
	const candidates = levels.value.flatMap((level, index) =>
		level < MAX_LEVEL ? [index] : [],
	);
	const picks: number[] = [];
	const stepSize = Math.max(1, Math.ceil(total / 6));
	while (picks.length < stepSize && candidates.length) {
		picks.push(
			candidates.splice(
				Math.floor(Math.random() * candidates.length),
				1,
			)[0],
		);
	}
	picks.forEach((index) => (levels.value[index] += 1));
	if (picks.length) history.value.push(picks);
}

function undo() {
	const last = history.value.pop();
	last?.forEach(
		(index) => (levels.value[index] = Math.max(0, levels.value[index] - 1)),
	);
}

function reset() {
	levels.value = new Array(total).fill(0);
	history.value = [];
}

async function save() {
	saving.value = true;
	await completeSession
		.submit({
			name: props.name,
			mode: "blur",
			mistakes: 0,
			correct_word_indices: [],
		})
		.then(
			(result) => result && emit("finished", result),
			() => {},
		);
	saving.value = false;
}
</script>
