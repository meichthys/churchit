<template>
	<MobileNav>
		<MobileNavItem
			v-for="tab in tabs"
			:key="tab.key"
			:label="tab.label"
			:route="tab.route"
			:active="isCurrent(tab, route)"
		>
			<template #default="{ active }">
				<span class="relative">
					<span
						class="block size-6"
						:class="[tab.icon, active ? 'text-accent' : 'text-ink-gray-6']"
						aria-hidden="true"
					/>
					<span
						v-if="tab.open"
						class="absolute -end-1 -top-0.5 size-2.5 rounded-full border-2 border-surface-elevation-2 bg-accent"
						aria-hidden="true"
					/>
				</span>
			</template>
		</MobileNavItem>
		<MobileNavItem :label="__('More')" @click="emit('more')">
			<span class="lucide-menu block size-6 text-ink-gray-6" aria-hidden="true" />
		</MobileNavItem>
	</MobileNav>
</template>

<script setup lang="ts">
import { MobileNav, MobileNavItem } from "frappe-ui";
import { useRoute } from "vue-router";

import { isCurrent, tabs } from "@/navigation";

const emit = defineEmits<{ more: [] }>();
const route = useRoute();
</script>
