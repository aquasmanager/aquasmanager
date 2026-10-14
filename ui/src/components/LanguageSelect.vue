<!--
  Choix de la langue de l'interface : gardé sur l'appareil, et sur le compte
  quand on est connecté (suivi sur les autres appareils).
-->
<template>
  <q-btn-toggle
    :model-value="locale"
    dense
    unelevated
    spread
    no-caps
    toggle-color="primary"
    :color="dark ? 'transparent' : 'grey-2'"
    :text-color="dark ? 'white' : 'grey-8'"
    :options="LOCALES.map((l) => ({ value: l.value, label: short ? l.value.toUpperCase() : l.label }))"
    :aria-label="t('common.language')"
    @update:model-value="(value: AppLocale) => void auth.setLanguage(value)"
  />
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import { LOCALES, type AppLocale } from 'src/i18n/instance';
import { useAuthStore } from 'src/stores/authStore';

// short : FR / EN, pour les en-têtes des pages publiques (vitrine, signature)
defineProps<{ dark?: boolean; short?: boolean }>();

const { t, locale } = useI18n();
const auth = useAuthStore();
</script>
