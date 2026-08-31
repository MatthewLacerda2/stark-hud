import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, request } from "@/lib/api/client";

afterEach(() => {
  vi.restoreAllMocks();
});

function stubFetch(response: Response) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(response);
}

describe("request", () => {
  it("prefixes /api/v1 and sends no auth header", async () => {
    const spy = stubFetch(new Response("[]", { status: 200 }));
    await request("/board/items");
    const [url, init] = spy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/board/items");
    expect(init.headers).toEqual({});
  });

  it("sets a JSON content type only when there is a body", async () => {
    const spy = stubFetch(new Response("{}", { status: 200 }));
    await request("/board/items", { method: "POST", body: { a: 1 } });
    const [, init] = spy.mock.calls[0] as [string, RequestInit];
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(init.body).toBe('{"a":1}');
  });

  it("raises ApiError carrying the backend detail", async () => {
    stubFetch(
      new Response(JSON.stringify({ detail: "board is full" }), {
        status: 409,
      }),
    );
    await expect(request("/board/items")).rejects.toThrow(ApiError);
  });

  it("returns undefined for 204 rather than parsing an empty body", async () => {
    stubFetch(new Response(null, { status: 204 }));
    await expect(request("/board/items/x")).resolves.toBeUndefined();
  });
});
