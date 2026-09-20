export default function PageLoader() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <div className="h-8 w-8 animate-spin border-2 border-taupe-300 border-t-burgundy-500" role="status" aria-label="Loading" />
    </div>
  )
}
