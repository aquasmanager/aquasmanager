<!-- État vide commun : icône, titre, explication et actions éventuelles -->
<template>
  <q-card flat bordered class="empty-state text-center q-pa-xl">
    <q-icon :name="icon" size="48px" :color="iconColor" />
    <div class="text-h6 text-grey-8 q-mt-sm">{{ title }}</div>
    <div v-if="message" class="text-body2 text-grey-7 q-mt-xs empty-state__message">{{ message }}</div>
    <div v-if="$slots.default" class="row justify-center gap-sm q-mt-md">
      <slot />
    </div>
  </q-card>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ icon: string; title: string; message?: string | undefined; iconColor?: string | undefined }>(), {
  iconColor: 'grey-5',
});
</script>

<style scoped>
.empty-state__message {
  max-width: 560px;
  margin-left: auto;
  margin-right: auto;
}
</style>
