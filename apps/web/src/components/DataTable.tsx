import React, { useMemo, useState } from "react";

export interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => React.ReactNode;
  sortValue?: (row: T) => string | number;
  width?: string;
}

export function DataTable<T>({ columns, rows, onRowClick, keyFn, emptyLabel = "No rows" }: {
  columns: Column<T>[]; rows: T[]; onRowClick?: (row: T) => void; keyFn: (row: T) => string | number; emptyLabel?: string;
}) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<1 | -1>(1);

  const sorted = useMemo(() => {
    if (!sortKey) return rows;
    const col = columns.find((c) => c.key === sortKey);
    if (!col?.sortValue) return rows;
    return [...rows].sort((a, b) => {
      const av = col.sortValue!(a);
      const bv = col.sortValue!(b);
      if (av < bv) return -1 * sortDir;
      if (av > bv) return 1 * sortDir;
      return 0;
    });
  }, [rows, sortKey, sortDir, columns]);

  function toggleSort(col: Column<T>) {
    if (!col.sortValue) return;
    if (sortKey === col.key) setSortDir((d) => (d === 1 ? -1 : 1));
    else { setSortKey(col.key); setSortDir(1); }
  }

  if (rows.length === 0) {
    return <div className="text-tertiary center-col" style={{ padding: "32px 0", fontSize: 13 }}>{emptyLabel}</div>;
  }

  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                style={{ width: c.width, cursor: c.sortValue ? "pointer" : undefined }}
                onClick={() => toggleSort(c)}
                tabIndex={c.sortValue ? 0 : undefined}
                role={c.sortValue ? "button" : undefined}
                onKeyDown={(e) => { if (c.sortValue && (e.key === "Enter" || e.key === " ")) toggleSort(c); }}
              >
                {c.header}{sortKey === c.key ? (sortDir === 1 ? " \u2191" : " \u2193") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr
              key={keyFn(row)}
              className={onRowClick ? "clickable focus-ring" : ""}
              onClick={() => onRowClick?.(row)}
              tabIndex={onRowClick ? 0 : undefined}
              onKeyDown={(e) => { if (onRowClick && (e.key === "Enter" || e.key === " ")) onRowClick(row); }}
            >
              {columns.map((c) => (
                <td key={c.key}>{c.render ? c.render(row) : String((row as any)[c.key] ?? "\u2014")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
