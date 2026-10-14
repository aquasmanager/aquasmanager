<!--
  Proposer une idée de fonctionnalité : envoyée au hub de l'éditeur, qui ouvre
  une issue publique (étiquette « fonctionnalité »).
-->
<template>
  <FormDialog
    :model-value="modelValue"
    icon="lightbulb"
    :title="t('feature.title')"
    width="560px"
    :submit-label="t('livestock.propose.send')"
    submit-icon="send"
    :hide-submit="!!sent"
    :cancel-label="sent ? t('common.close') : t('common.cancel')"
    :loading="sending"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    @show="reset"
    @submit="send"
  >
    <template v-if="sent">
      <div class="app-callout app-callout--ok">
        <q-icon name="check_circle" size="22px" />
        <div>
          {{ t('feature.sent') }}
          <div><a :href="sent.url" target="_blank" rel="noopener">{{ t('livestock.propose.sentLink', { n: sent.number }) }}</a></div>
        </div>
      </div>
    </template>
    <template v-else>
      <div class="text-body2 text-grey-8">{{ t('feature.intro') }}</div>
      <q-input v-model="title" :label="t('feature.name')" outlined dense maxlength="100" counter />
      <q-input
        v-model="description"
        :label="t('feature.description')"
        :hint="t('feature.descriptionHint')"
        type="textarea"
        autogrow
        outlined
        dense
        maxlength="3000"
      />
      <q-input v-model="author" :label="t('livestock.propose.author')" outlined dense maxlength="40" />
      <div class="text-caption text-grey-7">
        <q-icon name="public" size="14px" class="q-mr-xs" />{{ t('feature.public') }}
      </div>
    </template>
  </FormDialog>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import FormDialog from 'src/components/FormDialog.vue';
import { APP_VERSION } from 'src/composables/useAppUpdate';
import { currentLocale } from 'src/i18n/instance';
import { hubErrorKey, proposeFeature } from 'src/utils/hub';

defineProps<{ modelValue: boolean }>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>();

const { t } = useI18n();
const $q = useQuasar();
const title = ref('');
const description = ref('');
const author = ref('');
const sending = ref(false);
const sent = ref<{ number: number; url: string } | null>(null);

function reset() {
  title.value = '';
  description.value = '';
  author.value = '';
  sent.value = null;
}

async function send() {
  if (title.value.trim().length < 5 || description.value.trim().length < 10) {
    $q.notify({ type: 'warning', message: t('feature.tooShort') });
    return;
  }
  sending.value = true;
  try {
    sent.value = await proposeFeature({
      title: title.value.trim(),
      description: description.value.trim(),
      author: author.value.trim() || null,
      app_version: APP_VERSION,
      locale: currentLocale(),
    });
  } catch (err) {
    $q.notify({ type: 'negative', message: t(`livestock.propose.errors.${hubErrorKey(err)}`), timeout: 6000 });
  } finally {
    sending.value = false;
  }
}
</script>
