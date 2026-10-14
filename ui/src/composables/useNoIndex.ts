import { onBeforeUnmount, onMounted } from 'vue';

// Pages publiques (vitrine, signature) : demande aux moteurs de ne pas les indexer
export function useNoIndex() {
  let meta: HTMLMetaElement | null = null;
  onMounted(() => {
    meta = document.createElement('meta');
    meta.name = 'robots';
    meta.content = 'noindex, nofollow';
    document.head.appendChild(meta);
  });
  onBeforeUnmount(() => meta?.remove());
}
