<!--
  Saisie des lignes d'une demande de commande groupée : article, lien direct,
  quantité ; bouton « Ajouter un article ».
-->
<template>
  <div class="column gap-sm">
    <div v-for="(item, i) in items" :key="item.key" class="row q-col-gutter-sm items-start">
      <div class="col-12 col-sm-4">
        <q-input v-model="item.name" outlined dense maxlength="120" :label="t('groupOrders.join.itemName')" />
      </div>
      <div class="col">
        <q-input v-model="item.url" outlined dense type="url" maxlength="300" inputmode="url"
          :label="t('groupOrders.join.itemUrl')" :error="!urlValid(item.url)"
          :error-message="t('groupOrders.join.invalidUrl')" hide-bottom-space />
      </div>
      <div class="col-auto" style="width: 76px">
        <q-input v-model.number="item.quantity" outlined dense type="number" min="1" max="99" :label="t('groupOrders.join.itemQuantity')" />
      </div>
      <div class="col-auto">
        <q-btn flat round dense icon="remove_circle_outline" color="grey-7" :disable="items.length === 1"
          :aria-label="t('groupOrders.join.removeItem')" @click="items.splice(i, 1)">
          <q-tooltip>{{ t('groupOrders.join.removeItem') }}</q-tooltip>
        </q-btn>
      </div>
    </div>
    <div>
      <q-btn flat dense no-caps color="primary" icon="add" :label="t('groupOrders.join.addItem')"
        :disable="items.length >= 30" @click="items.push(newItem())" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import { newItem, urlValid, type EditableItem } from 'src/utils/groupOrderItems';

const items = defineModel<EditableItem[]>({ required: true });
const { t } = useI18n();
</script>
