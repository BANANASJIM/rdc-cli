import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  site: 'https://bananasjim.github.io',
  base: '/rdc-cli/',
  integrations: [tailwind()],
  output: 'static',
});
