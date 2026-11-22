<template>
	<!-- reka-ui parts (the ScrollArea inside DesktopShell) read the direction from ConfigProvider, not <html dir>. -->
	<ConfigProvider :dir="boot.rtl ? 'rtl' : 'ltr'">
		<FrappeUIProvider>
			<AppShell />
		</FrappeUIProvider>
	</ConfigProvider>
</template>

<script setup lang="ts">
import { FrappeUIProvider } from "frappe-ui";
import { ConfigProvider } from "reka-ui";

import { boot } from "./boot";
import AppShell from "./layouts/AppShell.vue";
</script>
