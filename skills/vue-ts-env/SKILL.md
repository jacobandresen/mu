---
name: vue-ts-env
description: Vue 3 TypeScript project rules — Vite build tool, Vitest test runner, @vue/test-utils for component tests, npm for dependency management. Apply to any Vue 3 TypeScript task.
---

Rules for Vue 3 + TypeScript projects. Each rule exists because the model
repeatedly fails without it.

## 0. REQUIRED files — the plan must include ALL of these

Every Vue 3 TypeScript project needs these five files. Omitting any one of them
causes the test to fail before any code is evaluated.

```
package.json        — declares ALL devDependencies (vue, vite, vitest, @vitejs/plugin-vue, @vue/test-utils, typescript, jsdom)
vite.config.ts      — configures the Vite/Vitest pipeline and jsdom environment
tsconfig.json       — TypeScript settings; must NOT list individual files on CLI
src/App.vue         — the Vue component
src/App.test.ts     — the Vitest test (sibling to App.vue, import from './App.vue')
Makefile            — install + test targets
```

The test command MUST be `make test`. The Makefile runs `npm install` before `npx vitest run`.

## 1. Always use Vite + Vitest — never webpack or jest

Vitest runs inside the Vite pipeline so TypeScript and `.vue` single-file
components work without extra transpilation config. Jest does not understand
`.vue` files without a custom transform; do not use it.

```json
{
  "devDependencies": {
    "vite": "^5.0.0",
    "vitest": "^1.0.0",
    "@vitejs/plugin-vue": "^5.0.0",
    "@vue/test-utils": "^2.0.0",
    "vue": "^3.0.0",
    "typescript": "^5.0.0",
    "jsdom": "^24.0.0"
  }
}
```

Use `jsdom >= 20` (not `jsdom@11` or older). Old jsdom versions pull in `contextify`,
a native module that fails to compile on Node 18+. Pin `^24.0.0` to be safe.
Never add `contextify` directly — it is an obsolete transitive dependency.

## 2. vite.config.ts must declare the test runner

Without the `test` block, `npx vitest` finds no test environment and exits 1.

```ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,        // ← REQUIRED: makes test/expect/describe available without import
  },
})
```

**Critical:** Without `globals: true`, calling `test(...)` in a test file raises
`ReferenceError: test is not defined`. With `globals: true`, `test`, `expect`,
`describe`, and `beforeEach` are automatically in scope in every test file.

Also add `"jsdom"` as a devDependency — Vitest does not bundle it.

## 3. tsconfig.json must include Vue compiler options

```json
{
  "compilerOptions": {
    "target": "ESNext",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "jsx": "preserve",
    "lib": ["ESNext", "DOM"]
  },
  "include": ["src/**/*", "*.ts"]
}
```

## 4. Component tests use @vue/test-utils mount, not the DOM directly

Test files live in `src/` alongside the component they test — NOT in `src/tests/`
or a separate `tests/` directory. This keeps import paths simple (e.g. `'./App.vue'`).

```ts
// src/App.test.ts — same directory as src/App.vue
import { mount } from '@vue/test-utils'
import App from './App.vue'         // relative import, no '../src/' prefix

test('adds a todo', async () => {
  const wrapper = mount(App)
  await wrapper.find('input').setValue('Buy milk')
  await wrapper.find('button').trigger('click')
  expect(wrapper.text()).toContain('Buy milk')
})
```

## 5. Makefile test target uses npx, not global binaries

Vite and Vitest are devDependencies — they are not on PATH until `npm install`
runs. Use `npx vitest run` (not `vitest run`) so npm resolves the binary from
`node_modules/.bin`.

```makefile
install:
	npm install

test: install
	npx vitest run
```

## 6. Never import from `@vue/composition-api`

`@vue/composition-api` is a Vue 2 compatibility shim — it does not exist in a
Vue 3 project and will cause `Cannot find module` errors. Vue 3 includes all
composition API built-in:

```ts
// Correct — Vue 3 built-in:
import { ref, reactive, computed, onMounted } from 'vue'

// Wrong — Vue 2 only:
import { ref } from '@vue/composition-api'
```

Never add `@vue/composition-api` to `package.json`. Never import from it.

## 7. Keep components simple — one file, no separate store

Do not create a separate `store.ts`, `store/index.ts`, or any Pinia/Vuex file.
Do not use Vuex, Pinia, Vue Router, or async setup with Suspense.

All state lives directly in the component using `ref` and `reactive` from Vue:

```ts
// App.vue — all state here, no separate store
import { ref, onMounted } from 'vue'
const todos = ref<string[]>([])
const input = ref('')
```

A `store.ts` that imports from `vue` or `pinia` is a common source of
`Cannot find module` errors and TypeScript failures. Don't create it.
