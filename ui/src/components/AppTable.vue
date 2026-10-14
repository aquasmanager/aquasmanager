<!--
  Tableau commun (q-table) : sur téléphone, chaque ligne devient une carte
  de liste réutilisant les mêmes slots body-cell-* que le tableau :
  1re colonne en titre, actions à droite, autres colonnes en « libellé : valeur ».
-->
<template>
  <q-table
    v-bind="$attrs"
    :rows="rows"
    flat
    class="app-table"
    :class="{ 'app-table--cards': cards }"
    :grid="cards"
    :card-container-class="cards ? 'app-table__list' : undefined"
    :hide-bottom="cards && (rows?.length ?? 0) <= 25"
  >
    <template v-for="(_, slotName) in $slots" #[slotName]="scope">
      <slot :name="slotName" v-bind="scope || {}" />
    </template>

    <template v-if="cards && !$slots.item" #item="scope">
      <div class="app-table__item col-12">
        <div class="row items-start no-wrap">
          <div class="col app-table__title">
            <CellContent :scope="scope" :col="titleCol(scope)" />
          </div>
          <div v-if="actionsCol(scope)" class="app-table__actions">
            <CellContent :scope="scope" :col="actionsCol(scope)!" />
          </div>
        </div>
        <div v-if="fieldCols(scope).length" class="app-table__fields">
          <div v-for="col in fieldCols(scope)" :key="col.name" class="app-table__field">
            <div class="app-table__label text-grey-7">{{ col.label }}</div>
            <CellContent :scope="scope" :col="col" />
          </div>
        </div>
      </div>
    </template>
  </q-table>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, useSlots, type PropType } from 'vue';
import { useQuasar, type QTableProps } from 'quasar';

defineOptions({ name: 'AppTable', inheritAttrs: false });

interface Col {
  name: string;
  label: string;
  value?: unknown;
}
interface ItemScope {
  cols: Col[];
  [key: string]: unknown;
}

const props = defineProps<{ rows: QTableProps['rows']; cardsBelow?: 'sm' | 'md' }>();
const $q = useQuasar();
const slots = useSlots();
const cards = computed(() => (props.cardsBelow === 'md' ? $q.screen.lt.md : $q.screen.lt.sm));

const titleCol = (scope: ItemScope) => scope.cols[0]!;
const actionsCol = (scope: ItemScope) => scope.cols.find((c) => c.name === 'actions');
const fieldCols = (scope: ItemScope) => scope.cols.slice(1).filter((c) => c.name !== 'actions');

// Contenu d'une cellule : slot body-cell-<nom> de la page, sinon la valeur
const CellContent = defineComponent({
  props: {
    scope: { type: Object as PropType<ItemScope>, required: true },
    col: { type: Object as PropType<Col>, required: true },
  },
  setup(p) {
    return () => {
      const slot = slots[`body-cell-${p.col.name}`];
      if (slot) return h('div', { class: 'app-table__cell' }, slot({ ...p.scope, col: p.col, value: p.col.value }));
      const value = p.col.value;
      return h('div', { class: 'app-table__cell' }, value == null || value === '' ? '—' : `${value as string | number}`);
    };
  },
});
</script>

<style scoped>
.app-table--cards :deep(.app-table__list) {
  margin: 0;
}

.app-table__item {
  padding: 12px 12px 10px;
  border-bottom: 1px solid var(--app-border-color);
}

.app-table__title {
  min-width: 0;
  font-weight: 500;
}

.app-table__actions {
  margin: -6px -6px 0 4px;
  white-space: nowrap;
}

.app-table__fields {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  margin-top: 8px;
}

.app-table__label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  margin-bottom: 2px;
}

/* Les slots des pages rendent des <td> : affichés comme de simples blocs */
.app-table__cell :deep(td) {
  display: block;
  padding: 0;
  border: 0;
  height: auto;
  text-align: left;
  white-space: normal;
}

.app-table__actions .app-table__cell :deep(td) {
  text-align: right;
}
</style>
