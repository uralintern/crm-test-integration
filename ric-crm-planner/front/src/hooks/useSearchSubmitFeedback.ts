import { useCallback, useEffect, useRef, useState } from "react";

type ToastType = "success" | "error" | "info";

type SearchSubmitFeedbackOptions<T> = {
  getMatches: (query: string) => T[];
  getId: (item: T) => number | string;
  notFoundMessage: string;
  showToast: (type: ToastType, message: string) => void;
  animationDurationMs?: number;
};

export function useSearchSubmitFeedback<T>({
  getMatches,
  getId,
  notFoundMessage,
  showToast,
  animationDurationMs = 650,
}: SearchSubmitFeedbackOptions<T>) {
  const [animatedIds, setAnimatedIds] = useState<Array<number | string>>([]);
  const timeoutRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);

  const clearAnimation = useCallback(() => {
    if (timeoutRef.current !== null) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }

    if (rafRef.current !== null) {
      window.cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
  }, []);

  useEffect(() => () => clearAnimation(), [clearAnimation]);

  const runAnimation = useCallback(
    (ids: Array<number | string>) => {
      clearAnimation();
      setAnimatedIds([]);

      rafRef.current = window.requestAnimationFrame(() => {
        setAnimatedIds(ids);
        timeoutRef.current = window.setTimeout(() => {
          setAnimatedIds([]);
          timeoutRef.current = null;
        }, animationDurationMs);
      });
    },
    [animationDurationMs, clearAnimation]
  );

  const handleSearchSubmit = useCallback(
    (query: string) => {
      const trimmedQuery = query.trim();
      if (!trimmedQuery) return;

      const matches = getMatches(trimmedQuery);
      if (matches.length === 0) {
        showToast("error", notFoundMessage);
        return;
      }

      runAnimation(matches.map((item) => getId(item)));
    },
    [getId, getMatches, notFoundMessage, runAnimation, showToast]
  );

  return {
    animatedIds,
    handleSearchSubmit,
  };
}
