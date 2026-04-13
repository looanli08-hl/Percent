// Percent — Xiaohongshu Data Export Script
// 1. Go to your profile page on xiaohongshu.com
// 2. Click the "点赞" (Liked) or "收藏" (Bookmarked) tab
// 3. Run this script in the browser console

(async function() {
  const SCROLL_DELAY = 800;
  const MAX_SCROLLS = 50;

  const sleep = ms => new Promise(r => setTimeout(r, ms));

  console.log('Percent: Starting export... Scrolling to load all notes.');

  // Scroll to load all content
  let prevCount = 0;
  let noChangeCount = 0;

  for (let i = 0; i < MAX_SCROLLS; i++) {
    window.scrollTo(0, document.body.scrollHeight);
    await sleep(SCROLL_DELAY);

    const cards = document.querySelectorAll('section.note-item, [class*="note-item"], a[href*="/explore/"], a[href*="/search_result/"]');
    const currentCount = cards.length;

    if (currentCount === prevCount) {
      noChangeCount++;
      if (noChangeCount >= 3) {
        console.log(`Percent: No more content to load (${currentCount} notes found).`);
        break;
      }
    } else {
      noChangeCount = 0;
      console.log(`Percent: Scroll ${i + 1}, found ${currentCount} notes...`);
    }
    prevCount = currentCount;
  }

  // Extract notes from DOM
  const notes = [];
  const seen = new Set();

  // Try multiple selectors for different XHS page layouts
  const selectors = [
    'section.note-item',
    '[class*="note-item"]',
    '.feeds-page .note-item',
    'div[class*="NoteContainer"]',
  ];

  let noteElements = [];
  for (const sel of selectors) {
    noteElements = document.querySelectorAll(sel);
    if (noteElements.length > 0) break;
  }

  // Fallback: find all links to notes
  if (noteElements.length === 0) {
    noteElements = document.querySelectorAll('a[href*="/explore/"], a[href*="/search_result/"]');
  }

  // If still nothing, try to get all visible card-like elements
  if (noteElements.length === 0) {
    noteElements = document.querySelectorAll('[class*="cover"], [class*="card"]');
  }

  for (const el of noteElements) {
    try {
      // Extract note link and ID
      const link = el.querySelector('a[href*="/explore/"], a[href*="/search_result/"]') || el.closest('a[href*="/explore/"]') || el;
      const href = link?.href || link?.getAttribute('href') || '';
      const noteIdMatch = href.match(/\/explore\/([a-f0-9]+)/) || href.match(/\/search_result\/([a-f0-9]+)/);
      const noteId = noteIdMatch ? noteIdMatch[1] : '';

      if (noteId && seen.has(noteId)) continue;
      if (noteId) seen.add(noteId);

      // Extract title
      const titleEl = el.querySelector('[class*="title"], [class*="desc"], .note-text, span');
      const title = titleEl?.textContent?.trim() || '';

      // Extract author
      const authorEl = el.querySelector('[class*="author"], [class*="name"], [class*="nickname"]');
      const author = authorEl?.textContent?.trim() || '';

      // Extract like count
      const likeEl = el.querySelector('[class*="like"], [class*="count"]');
      const likeCount = likeEl?.textContent?.trim() || '';

      if (!title && !noteId) continue;

      notes.push({
        note_id: noteId,
        title: title,
        desc: '',
        type: 'normal',
        nickname: author,
        interact_info: { liked_count: likeCount },
        source_url: href || '',
      });
    } catch(e) {
      // Skip malformed elements
    }
  }

  if (notes.length === 0) {
    console.log('Percent: Could not find any notes on this page.');
    console.log('Percent: Make sure you are on your profile page with the "点赞" or "收藏" tab selected.');
    console.log('Percent: Trying alternative extraction...');

    // Alternative: extract from page's embedded data
    try {
      const state = window.__INITIAL_STATE__;
      if (state) {
        const userData = state.user || {};
        const noteList = userData.notes || userData.likes || userData.collects || [];
        if (Array.isArray(noteList)) {
          for (const item of noteList) {
            notes.push({
              note_id: item.id || item.note_id || '',
              title: item.title || item.display_title || '',
              desc: item.desc || '',
              type: item.type || 'normal',
              nickname: item.user?.nickname || item.nickname || '',
              interact_info: {
                liked_count: String(item.likes || item.liked_count || '0'),
                collected_count: String(item.collects || item.collected_count || '0'),
              },
            });
          }
        }
        console.log(`Percent: Found ${notes.length} notes from page state.`);
      }
    } catch(e) {
      console.log('Percent: Could not read page state.');
    }
  }

  if (notes.length === 0) {
    console.error('Percent: Export failed. No notes found.');
    console.log('Percent: Try scrolling down manually first, then run this script again.');
    return;
  }

  // Download as JSON
  const blob = new Blob([JSON.stringify(notes, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `xiaohongshu_export_${new Date().toISOString().slice(0,10)}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  console.log(`Percent: Done! Exported ${notes.length} notes.`);
  console.log('Percent: Upload the downloaded JSON file to Percent.');
})();
