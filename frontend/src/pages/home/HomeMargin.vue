<template>
	<aside class="space-y-10" :aria-label="__('From the church')">
		<section v-if="home.notices.length" aria-labelledby="notices-head">
			<SectionHead id="notices-head" :title="__('Notices')" />
			<div class="space-y-6 border-t border-outline-gray-1 pt-4">
				<article v-for="notice in home.notices" :key="notice.name">
					<h3 class="t-subhead text-ink-gray-9">
						<a
							v-if="!isPageHidden('bulletins')"
							:href="`/bulletins?name=${encodeURIComponent(notice.name)}`"
							class="inline-block py-2 underline decoration-outline-gray-3 underline-offset-4 hover:decoration-ink-gray-7 md:py-0"
							>{{ notice.title }}</a
						>
						<template v-else>{{ notice.title }}</template>
					</h3>
					<p class="t-dateline text-ink-gray-6">{{ notice.date_display }}</p>
					<!-- eslint-disable-next-line vue/no-v-html -->
					<div
						class="mt-2 text-p-lg text-ink-gray-8 [&_a]:underline [&_li]:ms-5 [&_li]:list-disc [&_p]:mt-2"
						v-html="notice.announcements"
					/>
				</article>
			</div>
		</section>

		<section v-if="home.prayer_requests.length" aria-labelledby="prayer-head">
			<SectionHead id="prayer-head" :title="__('Remember in prayer')" />
			<ul class="divide-y divide-outline-gray-1 border-t border-outline-gray-1 pt-4">
				<PrayerNotice
					v-for="request in home.prayer_requests"
					:key="request.name"
					:request="request"
				/>
			</ul>
			<RouterLink
				v-if="!isPageHidden('community-prayer-requests')"
				to="/community-prayer-requests"
				class="mt-2 inline-block min-h-11 py-2 text-lg text-ink-gray-7 underline underline-offset-4"
			>
				{{ __("All prayer requests") }}
			</RouterLink>
		</section>

		<section
			v-if="home.bulletin || home.members_only_pages.length || installable"
			aria-labelledby="church-head"
		>
			<SectionHead id="church-head" :title="__('From the church')" />
			<div class="divide-y divide-outline-gray-1 border-t border-outline-gray-1">
				<div v-if="home.bulletin" class="py-4">
					<p class="t-subhead text-ink-gray-9">{{ home.bulletin.title }}</p>
					<p class="t-dateline text-ink-gray-6">{{ home.bulletin.date_display }}</p>
					<div class="mt-3 flex flex-wrap gap-2">
						<Button
							variant="outline"
							size="lg"
							class="min-h-11"
							:label="__('Read it')"
							@click="
								open(`/bulletins?name=${encodeURIComponent(home.bulletin.name)}`)
							"
						/>
						<Button
							variant="outline"
							size="lg"
							class="min-h-11"
							:label="__('PDF')"
							@click="open(pdfUrl(home.bulletin.name))"
						/>
					</div>
				</div>
				<a
					v-for="page in home.members_only_pages"
					:key="page.name"
					:href="page.route"
					class="flex min-h-11 items-center justify-between gap-3 py-3 text-lg text-ink-gray-9"
				>
					<span>{{ page.title }}</span>
					<span
						class="lucide-chevron-right size-4 shrink-0 text-ink-gray-5 rtl:-scale-x-100"
						aria-hidden="true"
					/>
				</a>
				<div v-if="installable" class="py-4">
					<p class="rubric">{{ __("Add this app to your home screen.") }}</p>
					<Button
						class="mt-3 min-h-11"
						variant="outline"
						size="lg"
						icon-left="lucide-download"
						:label="__('Install the app')"
						@click="install"
					/>
				</div>
			</div>
		</section>
	</aside>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { computed } from "vue";

import { boot, isPageHidden } from "@/boot";
import SectionHead from "@/components/SectionHead.vue";
import { installPrompt } from "@/pwa";
import { __ } from "@/translate";

import PrayerNotice from "./PrayerNotice.vue";
import type { Home } from "./types";

defineProps<{ home: Home }>();

const installable = computed(() => boot.offer_app_install && Boolean(installPrompt.value));

function pdfUrl(name: string): string {
	return `/api/method/churchit.church_communications.doctype.bulletin.bulletin.download_pdf?name=${encodeURIComponent(
		name
	)}`;
}

/** These are website pages, so they load whole. */
function open(url: string) {
	window.location.href = url;
}

async function install() {
	await installPrompt.value?.prompt();
	installPrompt.value = null;
}
</script>
