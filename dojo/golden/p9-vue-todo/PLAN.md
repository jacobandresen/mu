## Summary
Develop a Vue 3 TypeScript todo list web app using Vite as the build tool and Vitest for unit tests. The app will display a list of todos and allow adding new ones via a text input and button. A test file will be created to verify functionality, specifically testing adding and displaying todos. The correctness of the implementation will be verified by running the provided Makefile command.

## Files
- [ ] package.json — declares all devDependencies (vue, vite, vitest, @vitejs/plugin-vue, @vue/test-utils, typescript, jsdom)
- [ ] vite.config.ts — configures the Vite/Vitest pipeline and jsdom environment
- [ ] tsconfig.json — TypeScript settings; must NOT list individual files on CLI
- [ ] src/App.vue — the Vue component
- [ ] src/App.test.ts — the Vitest test (sibling to App.vue, import from './App.vue')
- [ ] Makefile — install + test targets

## Test Command
make test

## Dependencies
vite>=5.0.0, vitest>=1.0.0, @vitejs/plugin-vue>=5.0.0, @vue/test-utils>=2.0.0, vue>=3.0.0, typescript>=5.0.0, jsdom>=24.0.0