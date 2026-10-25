import type { Api } from './types';
import { demoApi } from './demoApi';
import { mockApi } from './mockApi';
import { realApi } from './realApi';
import { getSettings } from '../state/settings';

const adapters: Record<'demo' | 'mock' | 'real', Api> = {
  demo: demoApi,
  mock: mockApi,
  real: realApi,
};

export const api: Api = new Proxy({} as Api, {
  get(_target, property: keyof Api) {
    const activeAdapter = adapters[getSettings().adapter];
    const value = activeAdapter[property];
    return typeof value === 'function' ? value.bind(activeAdapter) : value;
  },
});
export { getSettings } from '../state/settings';
export function getAdapter(): 'demo' | 'mock' | 'real' {
  return getSettings().adapter;
}
export type { Api } from './types';
export * from './types';
