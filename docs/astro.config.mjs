// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightLlmsTxt from 'starlight-llms-txt';

export default defineConfig({
  site: 'https://lmgarret.github.io',
  base: '/llm-release-action',
  integrations: [
    starlight({
      title: 'LLM Release Action',
      logo: { src: './src/assets/logo.svg' },
      customCss: ['./src/styles/custom.css'],
      description:
        'GitHub Action that analyzes commits with an LLM, suggests semantic version bumps and writes changelogs for several audiences and languages.',
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/lmgarret/llm-release-action' },
      ],
      editLink: {
        baseUrl: 'https://github.com/lmgarret/llm-release-action/edit/master/docs/',
      },
      plugins: [
        starlightLlmsTxt({
          projectName: 'LLM Release Action',
          description:
            'A GitHub Action (lmgarret/llm-release-action@v2) that uses any LiteLLM-supported model to analyze commits, suggest a semver bump and generate multi-audience, multi-language changelogs.',
          details: [
            'Key facts:',
            '',
            '- Only the `model` input is required (a LiteLLM model string such as `anthropic/claude-sonnet-5`); provider credentials go in `env:`.',
            '- `actions/checkout` must use `fetch-depth: 0`.',
            '- Outputs are JSON strings. Changelogs and reasoning are LLM-generated from commits: pass them to scripts through `env:` or use `changelog_files`, never interpolate `${{ }}` into `run:` or `script:`.',
            '- The docs follow Diátaxis: tutorials (learning), how-to guides (tasks), reference (inputs, outputs, schemas), explanation (design).',
          ].join('\n'),
          customSets: [
            { label: 'Tutorials', paths: ['tutorials/**'], description: 'step-by-step introduction' },
            { label: 'How-to guides', paths: ['how-to/**'], description: 'workflow recipes for specific goals' },
            { label: 'Reference', paths: ['reference/**'], description: 'inputs, outputs, changelog_config schema, defaults' },
            { label: 'Explanation', paths: ['explanation/**'], description: 'how the action works and why' },
          ],
          promote: ['tutorials/**', 'reference/**'],
        }),
      ],
      sidebar: [
        { label: 'Tutorials', items: [{ autogenerate: { directory: 'tutorials' } }] },
        { label: 'How-to guides', items: [{ autogenerate: { directory: 'how-to' } }] },
        { label: 'Reference', items: [{ autogenerate: { directory: 'reference' } }] },
        { label: 'Explanation', items: [{ autogenerate: { directory: 'explanation' } }] },
      ],
    }),
  ],
});
