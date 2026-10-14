import { defineBoot } from '#q-app/wrappers';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart, LineChart } from 'echarts/charts';
import {
  DataZoomComponent,
  DataZoomSliderComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  ToolboxComponent,
  TooltipComponent,
} from 'echarts/components';
import VChart from 'vue-echarts';

// Graphiques (Apache ECharts, licence Apache-2.0) : seuls les modules utilisés
// sont chargés, pour garder un paquet léger.
use([
  CanvasRenderer,
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  DataZoomComponent,
  DataZoomSliderComponent,
  ToolboxComponent,
]);

export default defineBoot(({ app }) => {
  app.component('VChart', VChart);
});

declare module 'vue' {
  export interface GlobalComponents {
    VChart: typeof VChart;
  }
}
