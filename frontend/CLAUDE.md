# Frontend — docling-lens

Vue 3 + TypeScript (strict) + Vite + Pinia + Vitest.

## Commandes

```bash
npm run dev           # Dev server (port 5173)
npm run build         # vue-tsc --noEmit + vite build
npm run test:run      # Vitest (une passe)
npm run lint:fix      # ESLint auto-fix
npm run format        # Prettier
npm run type-check    # Type-check seul
```

## Architecture

Feature-based, avec un **workspace shell partagé** sous `shared/` :

```
src/
  shared/
    api/        # http.ts (apiFetch + ApiError class), documents.ts, health.ts
    docling/    # parseDoc.ts + useDocTree.ts composable + tests
    stores/
      useAppStore.ts        # mode toggle (rag | enrich | …)
      useDocumentStore.ts   # doc state + focus state (focusedCitations, focusTick)
    workspace/
      WorkspaceShell.vue    # layout shell — 5 named slots
      TopBar.vue            # brand + breadcrumb + mode toggle + New run
      DocumentPane.vue      # tree + by-type views, accepts decorations prop
      PdfViewer.vue         # pdf.js renderer + bbox overlay, lazy-loaded
      decorations.ts        # NodeDecoration + DecorationsMap types
  features/
    rag/
      api.ts                # runReasoning
      store.ts              # useRagStore (conversation only, delegates doc/focus)
      types.ts              # wire types mirroring backend Pydantic schemas
      ui/                   # ConversationPane, ReasoningTracePane, TimelineGantt,
                            # StatusBar, RagDebuggerPage
    enrich/
      api.ts                # runEnrich
      store.ts              # useEnrichStore (ops + runs history + focus prop)
      types.ts
      ui/                   # EnrichComposer, EnrichTimelinePane,
                            # EnrichStatusBar, EnrichDebuggerPage
  App.vue                   # mounts the page for appStore.mode
```

Règles d'ownership :

- **Doc state vit dans `useDocumentStore`** (jamais dans une feature) : filename,
  JSON brut, `parsedDocument` (computed via `parseDoc`), PDF blob, lifecycle
  conversion. **Focus state** (`focusedCitations`, `focusTick`) vit là aussi —
  chaque feature appelle `docStore.setFocus(citations)` quand sa propre
  sélection change.
- **Feature stores** ne possèdent QUE leur état spécifique : turns + steps pour
  rag, ops + runs pour enrich.
- **`DocumentPane` est feature-agnostique** : son seul couplage aux features
  passe par la prop `decorations: DecorationsMap`. Chaque feature page
  calcule la map depuis son state et la passe — l'agent-pane ne sait rien
  d'enrich, rag, ou autre.

**Ajouter un nouvel agent docling** (extract, write, edit) :
1. Nouvelle feature `features/<name>/` avec api/store/types/ui
2. Ajouter `<name>` à `AppMode` dans `useAppStore`
3. Ajouter une entrée dans `MODES` dans `TopBar.vue`
4. Brancher la page dans `App.vue`
5. Si pertinent, calculer une `DecorationsMap` et la passer à `DocumentPane`

## Validation pipeline

```bash
npm run lint:fix
npm run format
npm run lint
npm run format:check
npm run type-check
npm run test:run
```

Tout nouveau code doit avoir des tests. Zéro violation tolérée.

## Conventions

- **Path alias** : `@/` pointe vers `src/`.
- **ESLint** : flat config (ESLint 9+), `eslint-plugin-vue`, `typescript-eslint`.
  Pas de rules de formatting (Prettier).
- **Prettier** : sans semicolons, single quotes, trailing commas, 100 chars,
  2 espaces.
- **Sécurité** : ne JAMAIS utiliser `v-html` sur du contenu provenant du
  backend ou de l'utilisateur. Le contenu agent est rendu en text brut via
  `{{ }}`. Si du markdown / HTML devient nécessaire, ajouter DOMPurify +
  marked à ce moment-là — ils ne sont pas installés par défaut.
- **Tests** : colocalisés (`*.test.ts`), Vitest.
- **TypeScript** : mode strict.
- **Composants** : `vue/multi-word-component-names` désactivé.
- **Variables inutilisées** : préfixer avec `_` si intentionnel.
