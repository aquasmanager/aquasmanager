import { useQuasar } from 'quasar';
import { apiErrorMessage } from 'src/utils/apiError';
import { t } from 'src/i18n/instance';

export function useConfirmRemove() {
  const $q = useQuasar();

  /**
   * Demande confirmation puis exécute la suppression. Les notifications
   * (succès, ou erreur avec le détail renvoyé par l'API) sont affichées ici :
   * l'action ne doit pas en afficher elle-même et doit laisser remonter ses
   * erreurs.
   */
  function confirmRemove(
    itemName: string,
    onConfirm: () => Promise<unknown>,
    options: { message?: string; silent?: boolean } = {},
  ) {
    $q.dialog({
      title: t('confirm.deleteTitle'),
      message: options.message ?? t('confirm.deleteMessage', { item: itemName }),
      ok: { label: t('actions.delete'), color: 'negative', unelevated: true },
      cancel: { label: t('common.cancel'), flat: true, color: 'grey-8' },
      persistent: true,
    }).onOk(() => {
      onConfirm().then(
        () => {
          if (!options.silent) $q.notify({ type: 'positive', message: t('confirm.deleted', { item: itemName }) });
        },
        (err: unknown) => {
          console.error(err);
          $q.notify({ type: 'negative', message: apiErrorMessage(err, t('confirm.deleteFailed', { item: itemName })) });
        },
      );
    });
  }

  return { confirmRemove };
}

/** Confirmation d'une action (autre qu'une suppression), même présentation partout. */
export function useConfirm() {
  const $q = useQuasar();

  function confirmAction(options: {
    title: string;
    message: string;
    okLabel: string;
    okColor?: string;
    onOk: () => void | Promise<unknown>;
  }) {
    $q.dialog({
      title: options.title,
      message: options.message,
      ok: { label: options.okLabel, color: options.okColor ?? 'primary', unelevated: true },
      cancel: { label: t('common.cancel'), flat: true, color: 'grey-8' },
      persistent: true,
    }).onOk(() => {
      void options.onOk();
    });
  }

  return { confirmAction };
}
