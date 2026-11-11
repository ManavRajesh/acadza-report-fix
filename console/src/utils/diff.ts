/**
 * High-performance word-level diff utility for faculty review.
 */

export interface DiffPart {
  type: 'same' | 'added' | 'removed';
  value: string;
}

/**
 * Tokenizes text into words and punctuation tokens preserving whitespace.
 */
function tokenize(text: string): string[] {
  // Matches whitespace blocks OR non-whitespace words/punctuation
  const tokens = text.match(/\s+|[^\s]+/g);
  return tokens || [];
}

/**
 * Simple LCS-based word diff algorithm between two strings.
 */
export function computeWordDiff(before: string, after: string): DiffPart[] {
  const bTokens = tokenize(before);
  const aTokens = tokenize(after);

  const bLen = bTokens.length;
  const aLen = aTokens.length;

  // Build matrix for LCS
  // Note: For typical question stems or solution snippets (< 500 words), this is < 0.5ms
  const maxTokens = 600;
  if (bLen > maxTokens || aLen > maxTokens) {
    // If text is extraordinarily long, fall back to simple replacement view
    return [
      { type: 'removed', value: before },
      { type: 'added', value: after },
    ];
  }

  const dp: number[][] = Array.from({ length: bLen + 1 }, () => new Array(aLen + 1).fill(0));

  for (let i = 1; i <= bLen; i++) {
    for (let j = 1; j <= aLen; j++) {
      if (bTokens[i - 1] === aTokens[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Backtrack to build diff
  let i = bLen;
  let j = aLen;
  const result: DiffPart[] = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && bTokens[i - 1] === aTokens[j - 1]) {
      result.unshift({ type: 'same', value: bTokens[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({ type: 'added', value: aTokens[j - 1] });
      j--;
    } else if (i > 0 && (j === 0 || dp[i][j - 1] < dp[i - 1][j])) {
      result.unshift({ type: 'removed', value: bTokens[i - 1] });
      i--;
    }
  }

  // Consolidate consecutive same types
  const consolidated: DiffPart[] = [];
  for (const part of result) {
    if (consolidated.length > 0 && consolidated[consolidated.length - 1].type === part.type) {
      consolidated[consolidated.length - 1].value += part.value;
    } else {
      consolidated.push({ ...part });
    }
  }

  return consolidated;
}

/**
 * Renders inline HTML diff with <del> and <ins> tags.
 */
export function renderInlineDiffHtml(before: string, after: string): string {
  const parts = computeWordDiff(before, after);
  return parts
    .map((p) => {
      const escaped = escapeHtml(p.value);
      if (p.type === 'removed') {
        return `<del class="diff-del">${escaped}</del>`;
      }
      if (p.type === 'added') {
        return `<ins class="diff-ins">${escaped}</ins>`;
      }
      return escaped;
    })
    .join('');
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

