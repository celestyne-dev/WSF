// Which block types each ArticleBlockEditor caller offers.
// Default (Resource/Person/Page/Event… descriptions): unchanged.
export const DEFAULT_CONTENT_BLOCK_TYPES = ['paragraph', 'heading', 'list', 'blockquote', 'pullquote', 'image', 'highlight', 'divider']

// Articles add the in-article CTA blocks and "Related article" (resolved
// live by ArticlePage, which is why other content types don't offer it).
export const ARTICLE_BLOCK_TYPES = [...DEFAULT_CONTENT_BLOCK_TYPES, 'cta', 'button', 'relatedBlock']
