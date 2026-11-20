import { CaseStudy, Checklist, FurtherReading, KeyTakeaways, KnowledgeCheck, Reflection, ResourceLink, TryThis } from './LearningBlocks'

// Block type -> renderer for lesson content (passed to ArticleContent's
// `extraRenderers`). Keys match backend content_blocks.LEARNING_BLOCK_SANITIZERS.
export const LEARNING_RENDERERS = {
  keyTakeaways: KeyTakeaways,
  tryThis: TryThis,
  reflection: Reflection,
  caseStudy: CaseStudy,
  checklist: Checklist,
  knowledgeCheck: KnowledgeCheck,
  resourceLink: ResourceLink,
  furtherReading: FurtherReading,
}
