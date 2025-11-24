import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://wishful.local',
  integrations: [
    starlight({
      title: 'wishful',
      description: 'LLM-generated imports that stay playful.',
      logo: {
        src: './src/content/imgs/wishful_logo (5).jpg',
        alt: 'wishful – magic wand and Python swirl'
      },
      sidebar: [
        { label: 'Welcome', link: '/' },
        { label: 'Quickstart', link: '/quickstart' },
        { label: 'How it works', link: '/how-it-works' },
        { label: 'Configuration', link: '/configuration' },
        { label: 'CLI', link: '/cli' },
        { label: 'Types', link: '/types' },
        { label: 'Advanced context discovery', link: '/advanced-context-discovery' },
        { label: 'Contributing', link: '/contributing' },
        { label: 'Changelog', link: '/changelog' }
      ],
      social: [
        { label: 'GitHub', icon: 'github', href: 'https://github.com/pyros-projects/wishful' }
      ],
      customCss: ['./src/styles/theme.css']
    })
  ]
});
