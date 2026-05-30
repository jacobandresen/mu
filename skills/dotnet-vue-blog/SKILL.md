---
name: dotnet-vue-blog
description: ASP.NET Core + Vue 3 fullstack layout and Makefile rules. Apply to any fullstack .NET + Vue task. Complements dotnet-minimal-api, dotnet-xunit, and vue-ts-env.
---

## Layout — flat files only, no subdirectories inside backend/

Do NOT create `Controllers/`, `Data/`, `Migrations/`, or any subdirectory
inside `backend/`. The exact file list:

```
backend/
  backend.csproj
  Program.cs
  BlogDb.cs           (DbContext + model in one file)
backend-tests/
  backend-tests.csproj
  BlogApiTests.cs
frontend/
  package.json
  vite.config.ts
  src/App.vue
  src/App.test.ts
Makefile
```

Every path in PLAN.md must begin with `backend/`, `backend-tests/`,
`frontend/`, or `Makefile`. Nothing else.

## Makefile — install frontend, run both test suites

```makefile
.PHONY: install test

install:
	cd frontend && npm install

test: install
	dotnet test backend-tests/
	cd frontend && npx vitest run
```

- `dotnet test` restores packages automatically — do NOT call `dotnet restore`.
- Use `npx vitest run` — `vitest` is a devDependency, not a global binary.

## Frontend package.json — Vite + Vitest only, NO Vue CLI packages

Use only these devDependencies. Never add `@vue/cli-plugin-*`, `@vue/cli-service`,
`eslint`, `vue-router`, or any Vue CLI / webpack packages — they cause dependency
conflicts with modern Vite.

```json
{
  "name": "frontend",
  "private": true,
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

## Frontend vite.config.ts — jsdom + globals

```ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
```

## Frontend test — mock fetch, assert seeded post renders

Use a simple `globalThis.fetch` assignment — do NOT use `vi.stubGlobal` (it
causes deeply nested arrow functions that are easy to mis-parenthesize):

```ts
// src/App.test.ts
import { mount } from '@vue/test-utils'
import App from './App.vue'

const posts = [{ id: 1, title: 'Hello World', content: 'Welcome to the blog.' }]
globalThis.fetch = () => Promise.resolve({ json: () => Promise.resolve(posts) }) as any

test('displays seeded post', async () => {
  const wrapper = mount(App)
  await wrapper.vm.$nextTick()
  await wrapper.vm.$nextTick()
  expect(wrapper.text()).toContain('Hello World')
})
```
