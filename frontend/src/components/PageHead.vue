<template>
	<!-- The running head: like the top line of a printed page, it says where you are and stays put. -->
	<PageHeader v-if="!isMobile">
		<nav :aria-label="__('You are here')" class="flex min-w-0 items-center gap-2.5">
			<template v-for="(crumb, index) in crumbs" :key="crumb.label">
				<span v-if="index" class="text-ink-gray-4" aria-hidden="true">/</span>
				<RouterLink
					v-if="crumb.route"
					:to="crumb.route"
					class="t-label text-ink-gray-6 hover:text-ink-gray-9"
				>
					{{ crumb.label }}
				</RouterLink>
				<span v-else class="t-label truncate text-ink-gray-8" aria-current="page">{{
					crumb.label
				}}</span>
			</template>
		</nav>
		<div class="flex shrink-0 flex-wrap items-center justify-end gap-2">
			<slot name="actions" />
		</div>
	</PageHeader>

	<PageHeaderMobile v-else>
		<template v-if="back" #prefix>
			<Button
				variant="ghost"
				size="lg"
				icon="lucide-chevron-left"
				:aria-label="__('Back')"
				class="min-h-11 min-w-11 rtl:[&_span]:-scale-x-100"
				@click="goBack"
			/>
		</template>
		<template v-else-if="boot.church?.logo" #prefix>
			<img :src="boot.church.logo" alt="" class="ms-2 size-8 rounded-4 object-contain" />
		</template>
		<!-- The masthead below carries the title, so the bar names the church until the masthead scrolls away. -->
		<PageHeaderMobileTitle>
			<span class="relative grid">
				<span
					class="t-label col-start-1 row-start-1 truncate text-ink-gray-6 transition-opacity duration-200"
					:class="scrolled || back ? 'opacity-0' : 'opacity-100'"
					:aria-hidden="scrolled || Boolean(back)"
				>
					{{ boot.church?.title }}
				</span>
				<span
					class="t-label col-start-1 row-start-1 truncate text-ink-gray-8 transition-opacity duration-200"
					:class="scrolled ? 'opacity-100' : 'opacity-0'"
				>
					{{ crumbs[crumbs.length - 1]?.label }}
				</span>
			</span>
		</PageHeaderMobileTitle>
		<template v-if="$slots.mobile" #suffix>
			<slot name="mobile" />
		</template>
	</PageHeaderMobile>
</template>

<script setup lang="ts">
import {
	Button,
	PageHeader,
	PageHeaderMobile,
	PageHeaderMobileTitle,
	useShellScrolled,
} from "frappe-ui";
import { useRouter } from "vue-router";

import { boot } from "@/boot";
import { useIsMobile } from "@/layouts/useIsMobile";

const props = defineProps<{
	/** Where the page sits, ending with the page itself: [{ label: "Groups", route: "/groups" }, { label: "Young Families" }]. */
	crumbs: { label: string; route?: string }[];
	/** On phones, a back button to this route instead of the church logo (used when there is no history). */
	back?: string;
}>();

const isMobile = useIsMobile();
const router = useRouter();
const scrolled = useShellScrolled({ threshold: 72 });

function goBack() {
	if (window.history.state?.back) router.back();
	else router.push(props.back || "/");
}
</script>
