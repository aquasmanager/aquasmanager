declare namespace NodeJS {
  interface ProcessEnv {
    NODE_ENV: string;
    VUE_ROUTER_MODE: 'hash' | 'history' | 'abstract' | undefined;
    VUE_ROUTER_BASE: string | undefined;
    // Numéro de version, commit compilé et date de compilation (quasar.config.ts)
    APP_VERSION: string | undefined;
    APP_BUILD: string | undefined;
    APP_BUILT_AT: string | undefined;
  }
}
