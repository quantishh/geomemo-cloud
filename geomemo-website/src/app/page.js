// Import the fetch function (assuming it's still needed, adjust if moved)
async function getApprovedArticles() {
  // Fetch data from our API's approved endpoint
  // Use the correct API address if it's different
  const res = await fetch('http://localhost:8000/articles/approved', { cache: 'no-store' });

  if (!res.ok) {
    throw new Error('Failed to fetch data');
  }
  return res.json();
}

export default async function Home() {
  const articles = await getApprovedArticles();

  return (
    // Main container, centered, with max width
    <main className="max-w-3xl mx-auto px-4 py-8"> 
      
      {/* Header Section */}
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold mb-2">GeoMemo</h1>
        <p className="text-lg text-gray-600">Your briefing on global geopolitics and market trends.</p>
      </div>

      {/* Article Feed Section */}
      <div className="space-y-8"> 
        {articles.map((article) => (
          // Container for a single article block
          <div key={article.id} className="pb-4 border-b border-gray-200"> 
            
            {/* Headline */}
            <h2 className="text-xl font-semibold mb-1 hover:text-blue-700">
              <a href={article.url} target="_blank" rel="noopener noreferrer">
                {article.headline}
              </a>
            </h2>

            {/* Source and Author Line */}
            <div className="text-sm text-gray-500 mb-2">
              {article.publication_name}
              {article.author && <span className="italic"> / {article.author}</span>}
            </div>

            {/* Summary */}
            <p className="text-gray-700 text-base"> 
              {article.summary}
            </p>

          </div>
        ))}
        
        {/* Add a message if no articles are approved yet */}
        {articles.length === 0 && (
            <p className="text-center text-gray-500">No approved articles yet. Check back soon!</p>
        )}
      </div>
    </main>
  )
}