import { defineConfig } from 'astro/config';

// Deployed on Netlify at the domain root, so no `base` prefix is needed.
// `site` (used for canonical URLs / sitemaps) can be set via SITE_URL in the
// Netlify build environment once the domain is known.
export default defineConfig({
  site: process.env.SITE_URL,
  trailingSlash: 'ignore',
});
