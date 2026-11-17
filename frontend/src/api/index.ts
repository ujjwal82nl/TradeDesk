/**
 * Re-export the configured axios client as `api` for concise usage.
 *   import { api } from '../api/client';
 *   api.get('/portfolio/summary')
 */
export { apiClient as api } from './client';
export { apiClient } from './client';
