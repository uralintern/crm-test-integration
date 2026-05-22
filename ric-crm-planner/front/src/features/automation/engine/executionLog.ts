type ExecutionLogItem = {
  key: string;
  executedAt: string;
};

const EXECUTION_LOG_KEY = "ric_automation_execution_log_v1";
const MAX_EXECUTION_LOG_ITEMS = 500;

function readJson<T>(key: string, fallback: T): T {
  const raw = localStorage.getItem(key);
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function writeJson<T>(key: string, value: T) {
  localStorage.setItem(key, JSON.stringify(value));
}

export function wasExecuted(key: string) {
  return readJson<ExecutionLogItem[]>(EXECUTION_LOG_KEY, []).some((item) => item.key === key);
}

export function rememberExecution(key: string) {
  const log = readJson<ExecutionLogItem[]>(EXECUTION_LOG_KEY, []);
  if (log.some((item) => item.key === key)) return;
  writeJson(EXECUTION_LOG_KEY, [{ key, executedAt: new Date().toISOString() }, ...log].slice(0, MAX_EXECUTION_LOG_ITEMS));
}
