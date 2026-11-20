// Starting points for the in-article CTA block (ArticleBlockEditor). A
// preset only fills the block's normal editable fields; nothing about a
// preset is stored or linked, so editing the copy afterwards is safe.
// Every URL is an existing public route (see App.jsx).
export const CTA_PRESETS = [
  {
    key: 'career-hub',
    label: 'Career Hub',
    fields: {
      eyebrow: 'Career Hub',
      title: 'Plan your next career move',
      text: 'Guides, templates and tools to help you grow, negotiate and lead with confidence.',
      buttonLabel: 'Explore the Career Hub',
      buttonUrl: '/career-hub',
    },
  },
  {
    key: 'resources',
    label: 'Resources',
    fields: {
      eyebrow: 'Resources',
      title: 'Practical tools for your next step',
      text: 'Workbooks, checklists and templates made for women building their careers.',
      buttonLabel: 'Browse resources',
      buttonUrl: '/resources',
    },
  },
  {
    key: 'learning',
    label: 'Learning',
    fields: {
      eyebrow: 'Learning',
      title: 'Keep learning with WSF',
      text: 'Short programs and courses built around real career moments.',
      buttonLabel: 'See learning programs',
      buttonUrl: '/learning',
    },
  },
  {
    key: 'circle',
    label: 'WSF Circle',
    fields: {
      eyebrow: 'WSF Circle',
      title: 'Join a circle of women shaping the future',
      text: 'Membership with deeper resources, events and a community that has your back.',
      buttonLabel: 'Discover WSF Circle',
      buttonUrl: '/circle',
    },
  },
  {
    key: 'newsletter',
    label: 'Newsletter',
    fields: {
      eyebrow: 'WSF Weekly',
      title: 'Stories like this, every week',
      text: 'One thoughtful email with the best of Women Shaping Futures.',
      buttonLabel: 'Subscribe free',
      buttonUrl: '/newsletter',
    },
  },
  {
    key: 'submit',
    label: 'Submit your story',
    fields: {
      eyebrow: 'Share your story',
      title: 'Have a story the world should hear?',
      text: 'We feature women whose journeys inspire others. Tell us yours.',
      buttonLabel: 'Submit your story',
      buttonUrl: '/submit',
    },
  },
]
