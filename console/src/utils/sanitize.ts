import DOMPurify from 'dompurify';

const MATHML_TAGS = [
  'math',
  'mrow',
  'mfrac',
  'msqrt',
  'mroot',
  'msub',
  'msup',
  'msubsup',
  'mn',
  'mi',
  'mo',
  'mtext',
  'mspace',
  'mover',
  'munder',
  'munderover',
  'mtable',
  'mtr',
  'mtd',
  'annotation',
  'semantics',
];

const MATHML_ATTRS = ['xmlns', 'display', 'displaystyle', 'mathvariant', 'columnalign', 'rowalign'];

/**
 * Sanitizes raw HTML while preserving MathML and stripping inline styles (e.g. color:#000000).
 */
export function sanitizeHtml(html: string): string {
  if (!html) return '';

  return DOMPurify.sanitize(html, {
    ADD_TAGS: MATHML_TAGS,
    ADD_ATTR: MATHML_ATTRS,
    FORBID_ATTR: ['style'],
    USE_PROFILES: { html: true, mathMl: true },
  });
}

