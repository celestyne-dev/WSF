// Point-of-collection notices (Step 19): one short purpose line per form,
// always followed by a link to the Privacy Policy (and the Terms where the
// person is agreeing to them). Facts only — what this form's data is used
// for, as the code actually does it; the policies themselves say the rest.
// The newsletter, signup, contact and comment forms already carry their own
// approved wording and are not listed here.
export const NEWSLETTER_CONFIRM_NOTE = 'If you tick the newsletter box, we’ll email you a link to confirm first.'

export const COLLECTION_NOTICES = {
  story: {
    purpose: 'We use these details to review your story and contact you about it.',
    newsletterNote: true,
    terms: true,
  },
  eventRegistration: {
    purpose: 'We use your account name and email to record your place; the WSF events team can see your registration.',
  },
  learningEnrolment: {
    purpose: 'We keep your enrolment and lesson progress so you can pick up where you left off.',
  },
  nomination: {
    purpose: 'We use these details to review the nomination and contact you about it.',
    newsletterNote: true,
  },
  mentorship: {
    purpose: 'We use these details to review your application and contact you about it.',
    newsletterNote: true,
  },
  community: {
    purpose: 'We use these details to process your request to join.',
    newsletterNote: true,
  },
  resourceDownload: {
    purpose: 'We use your email to give you this download.',
    newsletterNote: true,
  },
  directory: {
    purpose: 'Your private contact details are used only to follow up about this submission.',
    terms: true,
  },
  partnership: {
    purpose: 'We use these details to respond to your enquiry.',
  },
  advertise: {
    purpose: 'We use these details to respond to your enquiry.',
  },
}

export function collectionNotice(kind) {
  const notice = COLLECTION_NOTICES[kind]
  if (!notice) throw new Error(`Unknown collection notice: ${kind}`)
  const sentences = [notice.purpose]
  if (notice.newsletterNote) sentences.push(NEWSLETTER_CONFIRM_NOTE)
  return { text: sentences.join(' '), terms: Boolean(notice.terms) }
}
