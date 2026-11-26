import { ApiError, createPurchase, type NewPurchase } from "./api";

const DB_NAME = "nico-queue";
const STORE = "purchases";

export type Sender = (purchase: NewPurchase) => Promise<unknown>;

export type DroppedItem = { purchase: NewPurchase; error: ApiError };

export type FlushResult = {
  sent: number;
  dropped: DroppedItem[];
  // Sobraram itens por falha de rede, servidor (5xx) ou sessão expirada.
  stopped: boolean;
};

export type QueueOptions = {
  send?: Sender;
  dbName?: string;
  onDrop?: (item: DroppedItem) => void;
};

function request<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

// 409 = já existe (o servidor é idempotente pelo id): conta como enviado.
// 401, 408, 429 e 5xx são temporários: o item fica. Outros 4xx são recusa
// definitiva da validação: o item sai da fila.
function isDefinitiveRejection(err: unknown): err is ApiError {
  return (
    err instanceof ApiError &&
    err.status >= 400 &&
    err.status < 500 &&
    ![401, 408, 429].includes(err.status)
  );
}

export function createQueue({
  send = createPurchase,
  dbName = DB_NAME,
  onDrop,
}: QueueOptions = {}) {
  let dbPromise: Promise<IDBDatabase> | null = null;
  let running: Promise<FlushResult> | null = null;

  function db(): Promise<IDBDatabase> {
    dbPromise ??= new Promise((resolve, reject) => {
      const open = indexedDB.open(dbName, 1);
      open.onupgradeneeded = () => {
        open.result.createObjectStore(STORE, { keyPath: "id" });
      };
      open.onsuccess = () => resolve(open.result);
      open.onerror = () => reject(open.error);
    });
    return dbPromise;
  }

  async function store(mode: IDBTransactionMode): Promise<IDBObjectStore> {
    return (await db()).transaction(STORE, mode).objectStore(STORE);
  }

  async function enqueue(purchase: NewPurchase): Promise<void> {
    // put: guardar o mesmo id duas vezes não duplica.
    await request((await store("readwrite")).put(purchase));
  }

  async function pending(): Promise<NewPurchase[]> {
    return request((await store("readonly")).getAll());
  }

  async function pendingCount(): Promise<number> {
    return request((await store("readonly")).count());
  }

  async function remove(id: string): Promise<void> {
    await request((await store("readwrite")).delete(id));
  }

  async function run(): Promise<FlushResult> {
    const result: FlushResult = { sent: 0, dropped: [], stopped: false };
    for (const purchase of await pending()) {
      try {
        await send(purchase);
        await remove(purchase.id);
        result.sent += 1;
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          await remove(purchase.id);
          result.sent += 1;
        } else if (isDefinitiveRejection(err)) {
          await remove(purchase.id);
          const item = { purchase, error: err };
          result.dropped.push(item);
          onDrop?.(item);
        } else {
          result.stopped = true;
          break;
        }
      }
    }
    return result;
  }

  // Chamadas simultâneas dividem a mesma execução: nada é enviado duas vezes.
  function flush(): Promise<FlushResult> {
    running ??= run().finally(() => {
      running = null;
    });
    return running;
  }

  function startAutoFlush(): () => void {
    const handler = () => void flush().catch(() => {});
    window.addEventListener("online", handler);
    return () => window.removeEventListener("online", handler);
  }

  async function close(): Promise<void> {
    if (!dbPromise) return;
    (await dbPromise).close();
    dbPromise = null;
  }

  return { enqueue, flush, pendingCount, startAutoFlush, close };
}

const defaultQueue = createQueue();

export const enqueue = defaultQueue.enqueue;
export const flush = defaultQueue.flush;
export const pendingCount = defaultQueue.pendingCount;
export const startAutoFlush = defaultQueue.startAutoFlush;
