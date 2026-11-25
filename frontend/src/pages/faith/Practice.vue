<template>
	<PageHead
		:crumbs="[
			{ label: __('Bible Memory'), route: '/memorize' },
			{ label: practice.data?.bible_reference || __('Practice') },
		]"
		back="/memorize"
	>
		<template #actions>
			<Button
				variant="subtle"
				:label="__('Back to your list')"
				route="/memorize"
			/>
		</template>
	</PageHead>

	<PageBody class="!max-w-[54rem]">
		<LoadState :resource="practice" v-slot="{ data }">
			<header>
				<p class="t-label text-ink-gray-6">
					{{ __("Practice, {0}", [data.translation]) }}
				</p>
				<h1 class="t-title mt-3 text-ink-gray-9">
					{{ data.bible_reference }}
				</h1>
				<div
					class="mt-4 flex flex-wrap items-baseline gap-x-7 gap-y-1 text-lg tabular-nums text-ink-gray-6"
				>
					<span class="font-medium text-ink-gray-9">{{
						__("{0}% learned", [progress])
					}}</span>
					<span
						v-if="data.memorized || result?.memorized"
						class="inline-flex items-center gap-1.5 text-ink-green-8"
					>
						<span
							class="lucide-check size-4"
							aria-hidden="true"
						/>{{ __("Memorized") }}
					</span>
				</div>
				<Progress
					:value="progress"
					size="md"
					:label="__('Progress')"
					class="mt-5 [&>div:first-child]:sr-only"
				/>
				<div class="mt-5">
					<TabButtons
						v-model="mode"
						class="[&_button]:min-h-11 md:[&_button]:min-h-0"
						:options="[
							{ label: __('Type'), value: 'type' },
							{ label: __('Blur'), value: 'blur' },
						]"
					/>
				</div>
			</header>

			<section
				v-if="result"
				class="mt-8 border-y border-outline-gray-1 py-6"
				role="status"
			>
				<p class="t-subhead text-ink-gray-9">
					{{ __("Session complete") }}
				</p>
				<p
					class="mt-2 flex flex-wrap items-center gap-x-3 text-lg text-ink-gray-7"
				>
					{{ resultWords(result) }}
					<span
						v-if="result.memorized"
						class="inline-flex items-center gap-1.5 text-ink-green-8"
						><span
							class="lucide-check size-4"
							aria-hidden="true"
						/>{{ __("Memorized") }}</span
					>
				</p>
				<div class="mt-5 flex flex-wrap gap-2">
					<Button
						variant="solid"
						size="lg"
						class="min-h-11"
						:label="__('Practice again')"
						@click="again"
					/>
					<Button
						variant="outline"
						size="lg"
						class="min-h-11"
						:label="__('Back to your list')"
						route="/memorize"
					/>
				</div>
			</section>

			<div v-else class="mt-8" :key="`${mode}-${attempt}`">
				<EmptyState
					v-if="!hasWords(data.text)"
					:title="__('No passage text')"
					:body="
						__(
							'This translation has no text for the passage. Try again from your list.',
						)
					"
				>
					<Button
						variant="outline"
						size="lg"
						class="min-h-11"
						:label="__('Your list')"
						route="/memorize"
					/>
				</EmptyState>
				<TypePractice
					v-else-if="mode === 'type'"
					:name="data.name"
					:text="data.text"
					:progress="progress"
					:word-mistakes="data.word_mistakes"
					@progress="progress = $event"
					@finished="finish"
				/>
				<BlurPractice
					v-else
					:name="data.name"
					:text="data.text"
					@finished="finish"
				/>
			</div>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Button, Progress, TabButtons } from "frappe-ui";
import { ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import EmptyState from "@/components/EmptyState.vue";
import LoadState from "@/components/LoadState.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import { useRead } from "@/api";
import { __ } from "@/translate";

import BlurPractice from "./BlurPractice.vue";
import TypePractice from "./TypePractice.vue";

interface PracticeData {
	name: string;
	bible_reference: string;
	translation: string;
	text: string;
	progress: number;
	memorized: boolean;
	times_memorized: number;
	word_mistakes: Record<string, number>;
}
interface SessionResult {
	progress: number;
	memorized: number;
	bonus: number;
}

const route = useRoute();
const router = useRouter();

const practice = useRead<PracticeData, { item: string }>("faith.get_practice", {
	params: { item: String(route.params.item) },
});
const mode = ref(route.query.mode === "blur" ? "blur" : "type");
const progress = ref(0);
const result = ref<SessionResult | null>(null);
const attempt = ref(0);

watch(
	() => practice.data,
	(data) => data && (progress.value = data.progress),
	{ immediate: true },
);
watch(mode, (value) =>
	router.replace({ query: { ...route.query, mode: value } }),
);

const hasWords = (text: string) => /\p{L}/u.test(text);

function finish(finished: Record<string, unknown>) {
	result.value = finished as unknown as SessionResult;
	progress.value = result.value.progress;
}

async function again() {
	await practice.reload();
	result.value = null;
	attempt.value += 1;
}

function resultWords(finished: SessionResult): string {
	return finished.bonus
		? __("Progress: {0}%, +{1}% this session", [
				finished.progress,
				finished.bonus,
			])
		: __("Progress: {0}%", [finished.progress]);
}
</script>
