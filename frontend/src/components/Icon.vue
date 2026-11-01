<script setup>
defineProps({
  name: { type: String, required: true },
  size: { type: Number, default: 20 },
  width: { type: Number, default: 2 },
})
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" :stroke-width="width"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <template v-if="name === 'home'"><path d="M3 10.5 12 3l9 7.5V21H3z" /></template>
    <template v-else-if="name === 'calendar'"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" /></template>
    <template v-else-if="name === 'grid'"><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></template>
    <template v-else-if="name === 'user'"><circle cx="12" cy="8" r="4" /><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" /></template>
    <template v-else-if="name === 'bell'"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></template>
    <template v-else-if="name === 'back'"><path d="m15 18-6-6 6-6" /></template>
    <template v-else-if="name === 'next'"><path d="m9 18 6-6-6-6" /></template>
    <template v-else-if="name === 'check'"><path d="M20 6 9 17l-5-5" /></template>
    <template v-else-if="name === 'spark'"><path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z" /></template>
    <template v-else-if="name === 'settings'"><circle cx="12" cy="12" r="3" /><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.600 5.600l2.100 2.100M16.300 16.300l2.100 2.100M18.400 5.600l-2.100 2.100M7.700 16.300l-2.100 2.100" /></template>
    <template v-else-if="name === 'trash'"><path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 11v6M14 11v6" /></template>
    <template v-else-if="name === 'mail'"><path d="M3 10 12 4l9 6v10H3z" /><path d="m3 10 9 6 9-6" /></template>
    <template v-else-if="name === 'refresh'"><path d="M20 12a8 8 0 1 1-2.300-5.600L20 8.700V4M20 8.700h-4.500" /></template>
    <template v-else-if="name === 'shield'"><path d="M12 3 5 6v5c0 4.500 3 8 7 10 4-2 7-5.500 7-10V6z" /></template>
    <template v-else-if="name === 'doc'"><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4M9 12h6M9 16h6" /></template>
    <template v-else-if="name === 'lock'"><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></template>
    <template v-else-if="name === 'edit'"><path d="M4 20h4L19 9l-4-4L4 16z" /><path d="m13.500 6.500 4 4" /></template>
    <template v-else-if="name === 'download'"><path d="M12 4v11M7 11l5 5 5-5M4 20h16" /></template>
    <template v-else-if="name === 'logout'"><path d="M10 4H5v16h5M14 8l4 4-4 4M18 12H9" /></template>
    <template v-else-if="name === 'info'"><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></template>
    <template v-else-if="name === 'logo'"><path d="M4 6h16M4 12h10M4 18h7" /></template>
    <template v-else-if="name === 'scholarship'"><path d="m2 9 10-5 10 5-10 5z" /><path d="M6 11.5V16c0 1.5 2.7 3 6 3s6-1.5 6-3v-4.5" /></template>
    <template v-else-if="name === 'briefcase'"><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 13h18" /></template>
    <template v-else-if="name === 'book'"><path d="M12 6c-2-1.5-5-2-8-2v15c3 0 6 .5 8 2 2-1.5 5-2 8-2V4c-3 0-6 .5-8 2z" /><path d="M12 6v15" /></template>
    <template v-else-if="name === 'trophy'"><path d="M8 4h8v6a4 4 0 0 1-8 0zM8 6H4c0 3 1.5 5 4 5M16 6h4c0 3-1.5 5-4 5M12 14v4M8 20h8" /></template>
    <template v-else-if="name === 'people'"><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c1-3.5 3.500-5 6.500-5s5.500 1.500 6.500 5M16 4.700a3.500 3.500 0 0 1 0 6.600M18 15.300c1.700.7 2.900 2.200 3.500 4.700" /></template>
    <template v-else-if="name === 'badge'"><circle cx="12" cy="9" r="6" /><path d="m8.500 14-1.500 7 5-2.500 5 2.500-1.500-7" /></template>
  </svg>
</template>
