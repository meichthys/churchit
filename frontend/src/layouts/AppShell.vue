<template>
	<MobileShell v-if="isMobile">
		<RouterView />
		<template #nav>
			<AppMobileNav @more="moreOpen = true" />
		</template>
	</MobileShell>
	<DesktopShell v-else>
		<template #sidebar>
			<AppSidebar />
		</template>
		<RouterView />
	</DesktopShell>
	<MoreSheet v-if="isMobile" v-model:open="moreOpen" />
</template>

<script setup lang="ts">
import { DesktopShell, MobileShell } from "frappe-ui";
import { ref } from "vue";

import AppMobileNav from "@/layouts/AppMobileNav.vue";
import AppSidebar from "@/layouts/AppSidebar.vue";
import MoreSheet from "@/layouts/MoreSheet.vue";
import { useIsMobile } from "@/layouts/useIsMobile";

const isMobile = useIsMobile();
const moreOpen = ref(false);
</script>
