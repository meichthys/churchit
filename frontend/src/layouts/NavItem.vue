<template>
	<SidebarItem
		:label="item.label"
		:icon="item.icon"
		:route="item.route"
		:href="item.href"
		:active="isCurrent(item, route)"
		:target="item.target"
	>
		<span class="truncate text-base">{{ item.label }}</span>
		<template v-if="item.open || item.href" #suffix>
			<span v-if="item.open" class="t-label me-2 text-accent">{{
				__("Open")
			}}</span>
			<span
				v-else
				class="lucide-arrow-up-right me-2 size-3.5 text-ink-gray-5 rtl:-scale-x-100"
				aria-hidden="true"
			/>
		</template>
	</SidebarItem>
</template>

<script setup lang="ts">
import { SidebarItem } from "frappe-ui";
import { useRoute } from "vue-router";

import { isCurrent, type MenuItem } from "@/navigation";

defineProps<{ item: MenuItem }>();
const route = useRoute();
</script>
