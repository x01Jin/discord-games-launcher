import { useEffect, useRef, useState } from "react";

export interface VirtualWindow {
  /** Attach to the scrolling element. */
  scroller: React.RefObject<HTMLDivElement | null>;
  start: number;
  end: number;
  /** Height of the spacer above the rendered rows. */
  offsetTop: number;
  /** Height of the full list, so the scrollbar is honest. */
  totalHeight: number;
}

/**
 * Fixed-height row windowing. The catalogue can hold thousands of rows; only
 * the ones the viewport can show are mounted.
 */
export function useVirtualRows(
  count: number,
  rowHeight: number,
  overscan = 6,
): VirtualWindow {
  const ref = useRef<HTMLDivElement | null>(null);
  const [range, setRange] = useState({ start: 0, end: 0 });
  const frame = useRef(0);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const measure = () => {
      frame.current = 0;
      const height = node.clientHeight || 0;
      const first = Math.max(0, Math.floor(node.scrollTop / rowHeight) - overscan);
      const visible = Math.ceil(height / rowHeight) + overscan * 2;
      const last = Math.min(count, first + Math.max(visible, 1));
      setRange((previous) =>
        previous.start === first && previous.end === last
          ? previous
          : { start: first, end: last },
      );
    };

    const onScroll = () => {
      if (frame.current) return;
      frame.current = requestAnimationFrame(measure);
    };

    measure();
    node.addEventListener("scroll", onScroll, { passive: true });
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => {
      node.removeEventListener("scroll", onScroll);
      observer.disconnect();
      if (frame.current) cancelAnimationFrame(frame.current);
    };
  }, [count, rowHeight, overscan]);

  return {
    scroller: ref,
    start: range.start,
    end: range.end,
    offsetTop: range.start * rowHeight,
    totalHeight: count * rowHeight,
  };
}
