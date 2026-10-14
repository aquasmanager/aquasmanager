/** Copie uniquement les clés attendues d'un objet (valeurs validées ensuite par le schéma du formulaire). */
export function pickKeys<V extends object>(data: object, keys: readonly (keyof V & string)[]): Partial<V> {
  const source = data as Record<string, unknown>;
  return Object.fromEntries(keys.filter((key) => key in source).map((key) => [key, source[key]])) as Partial<V>;
}
