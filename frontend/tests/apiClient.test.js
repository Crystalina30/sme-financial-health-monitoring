import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiRequest, clearToken, setToken } from '../src/services/apiClient.js';

afterEach(() => {
  vi.restoreAllMocks();
  clearToken();
});

describe('apiRequest', () => {
  it('attaches the bearer token when one is stored', async () => {
    setToken('test-token');
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await apiRequest('/companies');

    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers.Authorization).toBe('Bearer test-token');
  });

  it('omits the token on unauthenticated calls', async () => {
    setToken('test-token');
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({}),
    });
    vi.stubGlobal('fetch', fetchMock);

    await apiRequest('/auth/login', { method: 'POST', body: {}, auth: false });

    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers.Authorization).toBeUndefined();
  });

  it('surfaces the validation errors from a rejected record', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({
          detail: { message: 'Financial data failed validation.', errors: ['Accounting identity does not hold.'] },
        }),
      }),
    );

    await expect(apiRequest('/companies/1/financial-records')).rejects.toThrow(
      'Accounting identity does not hold.',
    );
  });

  it('carries the status code on the thrown error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Could not validate credentials.' }),
      }),
    );

    await expect(apiRequest('/auth/me')).rejects.toMatchObject({ status: 401 });
  });
});
