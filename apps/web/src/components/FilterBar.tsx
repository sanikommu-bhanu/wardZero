import React from "react";

export function SegmentedFilter<T extends string>({ value, onChange, options }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: string }[];
}) {
  return (
    <div className="segmented" role="tablist">
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={value === o.value}
          className={`focus-ring ${value === o.value ? "active" : ""}`}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function SearchInput({ value, onChange, placeholder = "Search...", ariaLabel }: {
  value: string; onChange: (v: string) => void; placeholder?: string; ariaLabel?: string;
}) {
  return (
    <input
      className="input-field focus-ring"
      style={{ padding: "9px 14px", fontSize: 13, maxWidth: 280 }}
      placeholder={placeholder}
      aria-label={ariaLabel || placeholder}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

export function FilterBar<T extends string>({
  search, onSearchChange, segment, onSegmentChange, segmentOptions, searchPlaceholder, right,
}: {
  search?: string; onSearchChange?: (v: string) => void;
  segment?: T; onSegmentChange?: (v: T) => void; segmentOptions?: { value: T; label: string }[];
  searchPlaceholder?: string; right?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between" style={{ gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
      <div className="flex items-center gap-8" style={{ flexWrap: "wrap" }}>
        {segment !== undefined && segmentOptions && onSegmentChange && (
          <SegmentedFilter value={segment} onChange={onSegmentChange} options={segmentOptions} />
        )}
        {onSearchChange && <SearchInput value={search || ""} onChange={onSearchChange} placeholder={searchPlaceholder} />}
      </div>
      {right}
    </div>
  );
}
