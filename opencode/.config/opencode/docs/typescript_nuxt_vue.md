# TypeScript, Nuxt, Vue 3 - Best Practices & Conventions for all work.

## Rules

- Do not use `any` type in TypeScript.
- Avoid type assertions (`as`).
- Use explicit types and interfaces where they are valuable, but prefer type inference where it is clear and sufficient.
- Do not use git operations, apart from to read code history for context. Do not create branches, commits, or pull requests.
- Do not make changes to gitignored files without explicit instructions to do so.
- Do not alter files outside the parent `code` directory without explicit instructions to do so.
- Do not create new files outside the parent `code` directory without explicit instructions to do so
- Don't create new documentation files or summary files of actions you have taken unless instructed to do so
- Do not scan, share, or expose sensitive information in .env files or within the codebase.

## Code Style & Conventions

- Use Vue 3 Composition API exclusively — no Options API
- Use `<script setup lang='ts'>` syntax in all Single File Components
- TypeScript is mandatory — avoid `any`, prefer explicit types and interfaces, type guards, avoid type assertions (`as`) when possible
- Use `composables/` for reusable reactive logic
- Use Pinia stores for shared state — keep component-local state in `ref`/`computed`
- Data fetching uses shared api client
- Use auto-imports (Nuxt resolves composables, components, and Vue/Pinia APIs automatically)
- File naming: `PascalCase` for components, `camelCase` for composables (`useXxx.ts`)
- Tailwind utility classes preferred over custom CSS; use css/Sass only for complex or component-scoped styles
- Follow existing repo patterns, but avoid bad practices.
- For new features, prioritise maintainability and readability over cleverness or brevity.
- For UI consistency, reuse existing components and styles where possible. Don't create new components or styles if an existing one can be adapted with props or slots.
- When in doubt, follow the principle of least surprise — code should be intuitive and self-explanatory to other developers familiar with the project. Avoid unnecessary abstractions or over-engineering.
- DRY - using the rule of three - if a piece of code is used twice, that's fine, if there are three instances of the same code it should be extracted into a re-useable function or component.
- Don't extract code into a function or component if it's only used once or twice, as that can make the code harder to read and understand. Use your judgement to determine when it's appropriate to extract code, and when it's better to keep it inline for clarity.
- Variables should be named in a descriptive way, no `index2` (adding a number to an already in use variable name to create a new one) or `req` instead of `request` , or `e` instead of `error`.
- Comments should be used wisely, to help other developers, not too verbose, not too minimal
- Use absolute imports, using Nuxt aliases (e.g. `@/components/Button.vue` instead of `../../components/Button.vue`)
- Do not use hacky or lazy typescript - No using `any` or casting using `as` when things should be properly typed.
- If you cannot solve a problem, ask for guidance, don't provide a hacky solution
- Your instructions are not only to achieve what is prompted but to do so using best practice and avoiding bad practice.
- Senior level code quality is required.
- Check for existing re-usable code before creating new functions or components (eg. In `./lib/js/haysto-v2-lib_shared`).
- It is always better to ask for guidance than to provide incorrect solutions
- Use idiomatic code and patterns, avoid non-standard approaches where possible
