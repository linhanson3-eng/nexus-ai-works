import { describe, it, expect, beforeEach, vi } from "vitest";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

import { fetchCsrfToken, api } from "../api";

beforeEach(() => {
  mockFetch.mockReset();
});

describe("fetchCsrfToken", () => {
  it("fetches CSRF token", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ token: "test-csrf-token" }),
    });

    await fetchCsrfToken();

    expect(mockFetch).toHaveBeenCalledWith("/api/csrf-token", {
      credentials: "include",
    });
  });
});

describe("api.health", () => {
  it("returns health status", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok", version: "1.0.0" }),
    });

    const result = await api.health();

    expect(result).toEqual({ status: "ok", version: "1.0.0" });
  });

  it("throws on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
    });

    await expect(api.health()).rejects.toThrow("500: Internal Server Error");
  });
});

describe("api.listWorkshops", () => {
  it("returns workshops list", async () => {
    const mockWorkshops = [{ name: "test", workflow_name: "simple", agent_count: 1 }];
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockWorkshops,
    });

    const result = await api.listWorkshops();

    expect(result).toEqual(mockWorkshops);
  });
});

describe("api create/delete", () => {
  it("sends POST with correct body", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ name: "new-ws" }),
    });

    await api.createWorkshop("new-ws");

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/workshops",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("new-ws"),
      }),
    );
  });

  it("calls DELETE method", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, status: 204 });

    await api.deleteBoard("board-1");

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/boards/board-1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
