<template>
  <div class="column gap-xs full-width">
    <!-- Barre d'outils / En-tête -->
    <div class="row items-center justify-between bg-grey-9 text-grey-4 q-px-sm q-py-xs rounded-top-editor">
      <div class="row items-center gap-xs">
        <q-icon name="terminal" size="18px" color="primary" />
        <span class="text-caption text-weight-bold font-mono">{{ filename }}</span>
        <q-badge
          dense
          :color="yamlError ? 'negative' : 'teal-6'"
          class="q-ml-xs text-caption"
        >
          {{ yamlError ? t('yaml.invalid') : t('yaml.valid') }}
        </q-badge>
      </div>

      <div class="row items-center gap-xs">
        <q-btn v-if="!readonly" flat dense icon="auto_fix_high" size="sm" color="amber" :aria-label="t('yaml.format')" @click="formatYaml">
          <q-tooltip>{{ t('yaml.format') }}</q-tooltip>
        </q-btn>
        <q-btn flat dense icon="content_copy" size="sm" color="grey-4" :aria-label="t('yaml.copy')" @click="copyYaml">
          <q-tooltip>{{ t('yaml.copy') }}</q-tooltip>
        </q-btn>
      </div>
    </div>

    <!-- Zone d'édition avec coloration et numérotation -->
    <div class="code-editor-wrapper" :class="{ 'has-error': !!yamlError }" :style="{ height: height }">
      <div class="line-numbers" aria-hidden="true">
        <span v-for="n in lineCount" :key="n">{{ n }}</span>
      </div>

      <div class="editor-area">
        <!-- Rendu HTML coloré (PrismJS) -->
        <pre class="highlight-layer" aria-hidden="true"><code v-html="highlightedCode"></code></pre>

        <!-- Champ de saisie overlay transparent -->
        <textarea
          ref="yamlTextarea"
          v-model="modelValue"
          class="code-textarea"
          spellcheck="false"
          :readonly="readonly"
          :placeholder="placeholder ?? t('yaml.placeholder')"
          @keydown.tab.prevent="handleTab"
          @scroll="syncScroll"
        ></textarea>
      </div>
    </div>

    <!-- Feedback sur la syntaxe -->
    <div v-if="yamlError" class="yaml-error-banner row items-center gap-xs q-pa-sm rounded-borders text-caption">
      <q-icon name="error_outline" size="18px" color="negative" />
      <span class="text-negative text-bold">{{ yamlError }}</span>
    </div>
    <div v-else class="text-caption text-grey-6 row items-center justify-between q-px-xs">
      <span>{{ readonly ? t('yaml.readonly') : t('yaml.tabHint') }}</span>
      <span>{{ t('yaml.lines', lineCount) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import * as yaml from 'js-yaml';
import Prism from 'prismjs';
import 'prismjs/components/prism-yaml';
import 'prismjs/themes/prism-tomorrow.css';
import 'prismjs/themes/prism.css';

withDefaults(
  defineProps<{
    filename?: string;
    placeholder?: string;
    height?: string;
    readonly?: boolean;
  }>(),
  {
    filename: 'CONFIG.YAML',
    height: '320px',
  }
);

// Support v-model
const modelValue = defineModel<string>({ required: true });
const emit = defineEmits<{
  (e: 'update:error', error: string | null): void;
}>();

const $q = useQuasar();
const { t } = useI18n();
const yamlError = ref<string | null>(null);
const yamlTextarea = ref<HTMLTextAreaElement | null>(null);

// Validation de la syntaxe YAML
function validateYaml() {
  if (!modelValue.value || !modelValue.value.trim()) {
    yamlError.value = t('yaml.empty');
    emit('update:error', yamlError.value);
    return;
  }
  try {
    const parsed = yaml.load(modelValue.value);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      yamlError.value = t('yaml.notObject');
    } else {
      yamlError.value = null;
    }
  } catch (err) {
    if (err instanceof Error) {
      yamlError.value = err.message.split('\n')[0] || t('yaml.syntax');
    } else {
      yamlError.value = t('yaml.syntax');
    }
  }
  emit('update:error', yamlError.value);
}

// Validation à chaque modification de la valeur
watch(modelValue, () => {
  validateYaml();
}, { immediate: true });

// Calcul du nombre de lignes
const lineCount = computed(() => {
  if (!modelValue.value) return 1;
  return modelValue.value.split('\n').length;
});

// Highlight dynamique avec fallback sécurisé
const highlightedCode = computed(() => {
  const code = modelValue.value || '';
  const formatted = code.endsWith('\n') ? code + ' ' : code;
  const grammar = Prism.languages.yaml;

  if (!grammar) return formatted;
  return Prism.highlight(formatted, grammar, 'yaml');
});

// Synchronisation du scroll entre textarea et vue Prism
function syncScroll(e: Event) {
  const target = e.target as HTMLTextAreaElement;
  const parent = target.parentElement;
  if (parent) {
    const highlightLayer = parent.querySelector('.highlight-layer') as HTMLElement;
    if (highlightLayer) {
      highlightLayer.scrollTop = target.scrollTop;
      highlightLayer.scrollLeft = target.scrollLeft;
    }
  }
}

// Insérer 2 espaces sur appui de Tab
async function handleTab(e: KeyboardEvent) {
  const target = e.target as HTMLTextAreaElement;
  const start = target.selectionStart;
  const end = target.selectionEnd;

  modelValue.value =
    modelValue.value.substring(0, start) + '  ' + modelValue.value.substring(end);

  await nextTick();
  target.selectionStart = target.selectionEnd = start + 2;
}

// Auto-formater le YAML
function formatYaml() {
  try {
    const parsed = yaml.load(modelValue.value);
    if (parsed && typeof parsed === 'object') {
      modelValue.value = yaml.dump(parsed, { indent: 2, noRefs: true });
      $q.notify({ message: t('yaml.formatted'), color: 'dark', timeout: 1000 });
    }
  } catch {
    $q.notify({ message: t('yaml.formatFailed'), color: 'negative' });
  }
}

// Copier dans le presse-papier
async function copyYaml() {
  try {
    await navigator.clipboard.writeText(modelValue.value);
    $q.notify({ message: t('yaml.copied'), color: 'positive', timeout: 1500 });
  } catch (err) {
    console.error(err);
    $q.notify({ message: t('yaml.copyFailed'), color: 'negative' });
  }
}

onMounted(() => {
  validateYaml();
});
</script>

<style scoped>
.gap-xs { gap: 4px; }
.font-mono { font-family: monospace; }

.rounded-top-editor {
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}

.code-editor-wrapper {
  display: flex;
  background-color: #f8f9fa; /* Fond clair très doux */
  border: 1px solid #dcdfe6;
  border-bottom-left-radius: 8px;
  border-bottom-right-radius: 8px;
  overflow: hidden;
  font-family: 'Fira Code', 'Cascadia Code', Consolas, Monaco, monospace;
  font-size: 13px;
  line-height: 1.5;
  transition: border-color 0.2s ease;
}

.code-editor-wrapper.has-error {
  border-color: #f44336;
}

/* Colonne des numéros de ligne */
.line-numbers {
  display: flex;
  flex-direction: column;
  padding: 12px 8px;
  background-color: #f0f2f5; /* Un gris légèrement plus soutenu */
  color: #8c92a4;
  user-select: none;
  text-align: right;
  min-width: 38px;
  border-right: 1px solid #dcdfe6;
}

.editor-area {
  position: relative;
  flex: 1;
  height: 100%;
  overflow: hidden;
}

.highlight-layer,
.code-textarea {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 12px;
  border: none;
  outline: none;
  font-family: inherit;
  font-size: inherit;
  line-height: inherit;
  white-space: pre;
  word-break: normal;
  overflow: auto;
  box-sizing: border-box;
}

.highlight-layer {
  pointer-events: none;
  background: transparent;
  z-index: 1;
}

.highlight-layer code {
  font-family: inherit !important;
  font-size: inherit !important;
  background: none !important;
  padding: 0 !important;
}

/* Zone de texte transparente (premier plan) */
.code-textarea {
  z-index: 2;
  color: transparent;
  caret-color: #1976d2; /* Curseur bleu Quasar bien visible sur fond clair */
  background: transparent;
  resize: none;
  tab-size: 2;
}

.code-textarea::selection {
  background: rgba(25, 118, 210, 0.15); /* Sélection bleutée transparente */
}

.yaml-error-banner {
  background-color: #ffebee;
  border: 1px solid #ffcdd2;
}

kbd {
  background-color: #eee;
  border-radius: 3px;
  border: 1px solid #b4b4b4;
  color: #333;
  padding: 1px 4px;
  font-size: 0.85em;
  font-weight: bold;
}
</style>
