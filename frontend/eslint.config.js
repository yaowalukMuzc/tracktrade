import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import pluginVue from 'eslint-plugin-vue'
import vueI18n from '@intlify/eslint-plugin-vue-i18n'
import globals from 'globals'

export default tseslint.config(
  { ignores: ['dist/**', 'dev-dist/**', 'node_modules/**', 'playwright-report/**', 'test-results/**'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  {
    files: ['**/*.{ts,vue}'],
    languageOptions: {
      globals: { ...globals.browser },
      parserOptions: { parser: tseslint.parser, extraFileExtensions: ['.vue'] },
    },
    rules: {
      // Formatting is not linted; vue/recommended layout rules fight long Tailwind class lists.
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
      'vue/multiline-html-element-content-newline': 'off',
      'vue/html-self-closing': 'off',
      'vue/html-indent': 'off',
      'vue/html-closing-bracket-newline': 'off',
      'vue/attributes-order': 'off',
      'vue/require-default-prop': 'off',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    },
  },
  // F-23 AC2: no hard-coded UI strings — everything goes through vue-i18n.
  {
    files: ['src/**/*.vue'],
    plugins: { '@intlify/vue-i18n': vueI18n },
    settings: { 'vue-i18n': { localeDir: './src/i18n/locales/*.json', messageSyntaxVersion: '^11.0.0' } },
    rules: {
      '@intlify/vue-i18n/no-raw-text': [
        'error',
        {
          // Brand wordmark, language names shown in their own script, and pure symbols are not translatable copy.
          ignorePattern: '^[\\s·•—–\\-+/:()|*%$R0-9.,]+$',
          ignoreText: ['Track', 'Trade', 'ไทย', 'EN', 'English'],
        },
      ],
    },
  },
  // Dev-only showcase (/dev/ui is not registered in production builds).
  { files: ['src/views/dev/**'], rules: { '@intlify/vue-i18n/no-raw-text': 'off' } },
  {
    files: ['*.config.{js,ts}', 'scripts/**', 'e2e/**'],
    languageOptions: { globals: { ...globals.node } },
  },
)
