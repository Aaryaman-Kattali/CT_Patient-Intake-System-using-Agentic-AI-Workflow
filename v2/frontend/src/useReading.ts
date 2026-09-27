import { useEffect, useState } from "react";

/** True once a request has been waiting for 1 second. Nothing is shown for fast replies. */
export function useReading(pending: boolean, delayMs = 1000): boolean {
  const [show, setShow] = useState(false);
  useEffect(() => {
    if (!pending) {
      setShow(false);
      return;
    }
    const timer = window.setTimeout(() => setShow(true), delayMs);
    return () => window.clearTimeout(timer);
  }, [pending, delayMs]);
  return show;
}
