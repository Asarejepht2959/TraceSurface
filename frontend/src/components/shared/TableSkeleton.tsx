
type TableSkeletonProps = {
  columns: number;
  rows?: number;
};

export function TableSkeleton({ columns, rows = 6 }: TableSkeletonProps) {
  return (
    <>
      {Array.from({ length: rows }, (_, row) => (
        <tr key={row} className="table-skeleton-row">
          {Array.from({ length: columns }, (_, col) => (
            <td key={col}>
              <div
                className="table-skeleton-bar"
                style={{ width: col === 2 ? "72%" : col === 0 ? "48px" : "64%" }}
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}
