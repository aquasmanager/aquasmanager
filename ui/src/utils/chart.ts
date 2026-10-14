// Réglages communs des graphiques ECharts, accordés au thème « océan »

export const CHART_FONT = "'Geist Variable', ui-sans-serif, system-ui, sans-serif";

export function escapeHtml(value: string | number | null | undefined): string {
  return String(value ?? '').replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

export function chartColors(dark: boolean) {
  return {
    text: dark ? 'rgba(226, 232, 240, 0.65)' : '#64748b',
    grid: dark ? 'rgba(148, 197, 255, 0.10)' : 'rgba(15, 23, 42, 0.08)',
    markerBorder: dark ? '#050a12' : '#ffffff',
    ok: dark ? '#4ade80' : '#16a34a',
    accent: dark ? '#38bdf8' : '#0284c7',
  };
}

// Base : fond transparent, police de l'appli, info-bulles et axes aux couleurs du thème
export function chartBase(dark: boolean) {
  const c = chartColors(dark);
  return {
    backgroundColor: 'transparent',
    animation: false,
    textStyle: { fontFamily: CHART_FONT, color: c.text },
    tooltip: {
      backgroundColor: dark ? 'rgba(11, 20, 32, 0.96)' : 'rgba(255, 255, 255, 0.98)',
      borderColor: dark ? 'rgba(148, 197, 255, 0.18)' : 'rgba(15, 23, 42, 0.10)',
      textStyle: { color: dark ? '#e2e8f0' : '#0f172a', fontFamily: CHART_FONT, fontSize: 12 },
      extraCssText: 'border-radius: 10px; box-shadow: 0 8px 24px rgba(0,0,0,.18);',
    },
    legend: { textStyle: { color: c.text, fontFamily: CHART_FONT }, icon: 'roundRect', itemWidth: 12, itemHeight: 4 },
  };
}

export function axisStyle(dark: boolean) {
  const c = chartColors(dark);
  return {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: c.text, fontFamily: CHART_FONT, fontSize: 11 },
    splitLine: { lineStyle: { color: c.grid, type: 'dashed' as const } },
  };
}

// Pastille de couleur d'une série dans une info-bulle
export function dot(color: unknown): string {
  const css = typeof color === 'string' ? color : 'currentColor';
  return `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${escapeHtml(css)};margin-right:6px"></span>`;
}
