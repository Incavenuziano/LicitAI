"use client";

import React, { useEffect, useMemo, useRef } from "react";

export type Column<T> = {
  header: React.ReactNode;
  render: (row: T) => React.ReactNode;
  headerClassName?: string;
  cellClassName?: string;
  widthClassName?: string;
};

export type KeyType = string | number;

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  rowKey: (row: T) => KeyType;
  selectable?: boolean;
  selectedKeys?: Set<KeyType>;
  onToggleRow?: (key: KeyType) => void;
  onToggleAll?: () => void;
  onRowClick?: (row: T) => void;
  className?: string;
  minWidthClassName?: string; // e.g. "min-w-[1000px]"
}

export default function DataTable<T>(props: DataTableProps<T>) {
  const {
    data,
    columns,
    rowKey,
    selectable = false,
    selectedKeys = new Set<KeyType>(),
    onToggleRow,
    onToggleAll,
    onRowClick,
    className,
    minWidthClassName = "min-w-[1000px]",
  } = props;

  const selectAllRef = useRef<HTMLInputElement | null>(null);

  const allSelected = useMemo(
    () => data.length > 0 && selectedKeys.size === data.length,
    [data.length, selectedKeys]
  );
  const someSelected = useMemo(
    () => selectedKeys.size > 0 && selectedKeys.size < data.length,
    [data.length, selectedKeys]
  );

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someSelected;
    }
  }, [someSelected]);

  return (
    <table className={`${minWidthClassName} w-full text-sm table-fixed ${className || ""}`}>
      <thead className="sticky top-0 z-10 bg-gray-50">
        <tr>
          {selectable && (
            <th className="py-3 px-3 border-b border-gray-200 w-12 text-center whitespace-nowrap">
              <input
                type="checkbox"
                ref={selectAllRef}
                checked={allSelected}
                onChange={onToggleAll}
                className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
            </th>
          )}
          {columns.map((col, idx) => (
            <th
              key={idx}
              className={
                col.headerClassName ||
                "py-3 px-4 border-b border-gray-200 text-left font-semibold text-gray-700"
              }
            >
              {col.header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((row) => {
          const key = rowKey(row);
          const selected = selectable && selectedKeys.has(key);
          return (
            <tr
              key={String(key)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={`${
                selected ? "bg-blue-100" : "odd:bg-gray-50 hover:bg-gray-100"
              } ${onRowClick ? "cursor-pointer" : ""}`}
            >
              {selectable && (
                <td className="py-2 px-3 border-b text-center whitespace-nowrap">
                  <input
                    type="checkbox"
                    checked={!!selected}
                    onClick={(e) => e.stopPropagation()}
                    onChange={() => onToggleRow && onToggleRow(key)}
                    className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                  />
                </td>
              )}
              {columns.map((col, idx) => (
                <td
                  key={idx}
                  className={col.cellClassName || "py-2 px-4 border-b whitespace-normal"}
                >
                  {col.render(row)}
                </td>
              ))}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

