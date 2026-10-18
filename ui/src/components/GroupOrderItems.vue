<!--
  Lignes d'une demande de commande groupée : quantité, nom, lien direct vers le produit.
-->
<template>
  <q-list dense class="q-my-xs">
    <q-item v-for="(item, i) in items" :key="i" dense class="q-px-none" style="min-height: 28px">
      <q-item-section avatar style="min-width: 36px" class="text-weight-bold text-primary">{{ item.quantity }} ×</q-item-section>
      <q-item-section class="text-body2">{{ item.name }}</q-item-section>
      <q-item-section v-if="item.url" side>
        <q-btn flat round dense size="sm" icon="open_in_new" color="primary" type="a" :href="item.url"
          target="_blank" rel="noopener noreferrer" :aria-label="t('groupOrders.join.openItem')">
          <q-tooltip>{{ item.url }}</q-tooltip>
        </q-btn>
      </q-item-section>
    </q-item>
  </q-list>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import type { GroupOrderItem } from 'src/types/groupOrder';

defineProps<{ items: GroupOrderItem[] }>();
const { t } = useI18n();
</script>
