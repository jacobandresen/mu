---
name: vue-ts-env
description: Vue 3 TypeScript project rules — Vite build tool, Vitest test runner, @vue/test-utils for component tests, npm for dependency management. Apply to any Vue 3 TypeScript task.
---

Rules for Vue 3 + TypeScript projects. Each rule exists because the model
repeatedly fails without it.

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
    "typescript": "^5.0.0"
  }
}
```

## 2. vite.config.ts must declare the test runner

Without the `test` block, `npx vitest` finds no test environment and exits 1.

```ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
  },
})
```

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

```ts
import { mount } from '@vue/test-utils'
import TodoApp from '../src/TodoApp.vue'

test('adds a todo', async () => {
  const wrapper = mount(TodoApp)
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

## 6. Keep components simple — props in, events out

Do not use Vuex, Pinia, Vue Router, or async data fetching in a dojo problem.
A single-file component with `ref` state is enough to demonstrate the pattern
and is reliably testable with `@vue/test-utils`.
