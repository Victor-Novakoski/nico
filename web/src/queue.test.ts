import "fake-indexeddb/auto";
import { describe, expect, it, vi } from "vitest";
import { ApiError, type NewPurchase } from "./api";
import { createQueue } from "./queue";

let n = 0;
function purchase(id = `p${++n}`): NewPurchase {
  return {
    id,
    payment_method_id: "pm1",
    description: "pão",
    total_cents: 1500,
    purchase_date: "2026-01-10",
    installments: 1,
    status: "pendente",
  };
}

function newQueue(send: (p: NewPurchase) => Promise<unknown>, name?: string) {
  return createQueue({ send, dbName: name ?? `db${++n}` });
}

describe("fila local", () => {
  it("sem rede guarda o item e não perde", async () => {
    const send = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const q = newQueue(send);
    await q.enqueue(purchase("a"));
    const res = await q.flush();
    expect(res.stopped).toBe(true);
    expect(await q.pendingCount()).toBe(1);
  });

  it("com rede envia uma vez só e esvazia a fila", async () => {
    const send = vi.fn().mockResolvedValue({ id: "a" });
    const q = newQueue(send);
    await q.enqueue(purchase("a"));
    await q.flush();
    await q.flush();
    expect(send).toHaveBeenCalledTimes(1);
    expect(await q.pendingCount()).toBe(0);
  });

  it("guarda de novo o mesmo id sem duplicar", async () => {
    const q = newQueue(vi.fn());
    await q.enqueue(purchase("a"));
    await q.enqueue(purchase("a"));
    expect(await q.pendingCount()).toBe(1);
  });

  it("dois flushes ao mesmo tempo enviam uma vez só", async () => {
    let release!: () => void;
    const send = vi.fn(
      () => new Promise<void>((resolve) => (release = resolve)),
    );
    const q = newQueue(send);
    await q.enqueue(purchase("a"));
    const f1 = q.flush();
    const f2 = q.flush();
    await vi.waitFor(() => expect(send).toHaveBeenCalled());
    release();
    await Promise.all([f1, f2]);
    expect(send).toHaveBeenCalledTimes(1);
    expect(await q.pendingCount()).toBe(0);
  });

  it("erro 4xx descarta o item e avisa", async () => {
    const send = vi.fn().mockRejectedValue(new ApiError(422, "inválido"));
    const onDrop = vi.fn();
    const q = createQueue({ send, dbName: `db${++n}`, onDrop });
    await q.enqueue(purchase("a"));
    const res = await q.flush();
    expect(res.dropped).toHaveLength(1);
    expect(onDrop).toHaveBeenCalledTimes(1);
    expect(await q.pendingCount()).toBe(0);
  });

  it("409 (já existe) conta como enviado", async () => {
    const send = vi.fn().mockRejectedValue(new ApiError(409, "existe"));
    const q = newQueue(send);
    await q.enqueue(purchase("a"));
    const res = await q.flush();
    expect(res.sent).toBe(1);
    expect(await q.pendingCount()).toBe(0);
  });

  it("5xx e sessão expirada mantêm o item", async () => {
    for (const status of [500, 401]) {
      const send = vi.fn().mockRejectedValue(new ApiError(status, "x"));
      const q = newQueue(send);
      await q.enqueue(purchase("a"));
      await q.flush();
      expect(await q.pendingCount()).toBe(1);
    }
  });

  it("o item sobrevive a reabrir o banco", async () => {
    const name = `db${++n}`;
    const q1 = newQueue(vi.fn(), name);
    await q1.enqueue(purchase("a"));
    await q1.close();
    const send = vi.fn().mockResolvedValue({ id: "a" });
    const q2 = newQueue(send, name);
    expect(await q2.pendingCount()).toBe(1);
    await q2.flush();
    expect(send).toHaveBeenCalledTimes(1);
  });

  it("envia ao voltar a rede (evento online)", async () => {
    const send = vi.fn().mockResolvedValue({ id: "a" });
    const q = newQueue(send);
    await q.enqueue(purchase("a"));
    const stop = q.startAutoFlush();
    window.dispatchEvent(new Event("online"));
    await vi.waitFor(() => expect(send).toHaveBeenCalledTimes(1));
    stop();
    window.dispatchEvent(new Event("online"));
    expect(send).toHaveBeenCalledTimes(1);
  });
});
