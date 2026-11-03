/// <reference types="vite/client" />

declare const __MAPTILER_KEY__: string

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}