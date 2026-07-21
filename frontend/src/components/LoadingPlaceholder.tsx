interface LoadingPlaceholderProps {
  lines?: number;
}

export default function LoadingPlaceholder({ lines = 3 }: LoadingPlaceholderProps) {
  return (
    <div className="animate-pulse space-y-3" aria-label="Loading content">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className={`h-4 bg-gray-200 rounded ${
            i === lines - 1 ? 'w-2/3' : 'w-full'
          }`}
        />
      ))}
    </div>
  );
}
