const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 800 }
  });
  const page = await context.newPage();

  // Collect all subtitle/caption network requests
  const captions = [];
  page.on('response', async (response) => {
    const url = response.url();
    if (url.includes('subtitle') || url.includes('caption') || url.includes('tts') || url.includes('transcript')) {
      try {
        const body = await response.text();
        captions.push({ url, body: body.substring(0, 3000) });
      } catch {}
    }
  });

  // Also collect XHR/fetch responses that might contain video data
  const apiResponses = [];
  page.on('response', async (response) => {
    const url = response.url();
    if (url.includes('video') && (url.includes('api') || url.includes('detail') || url.includes('data'))) {
      try {
        const body = await response.text();
        apiResponses.push({ url, body: body.substring(0, 5000) });
      } catch {}
    }
  });

  console.log('Opening page...');
  await page.goto('https://www.toutiao.com/video/7638818556376908315/', {
    waitUntil: 'networkidle',
    timeout: 60000
  });

  // Wait extra for dynamic content
  await page.waitForTimeout(8000);

  // Dump page title
  console.log('TITLE:', await page.title());

  // Try to find subtitle elements
  const subtitleTexts = await page.$$eval('[class*="subtitle"], [class*="caption"], [class*="tts"], [class*="transcript"], [class*="text-track"]', els =>
    els.map(el => el.textContent?.trim()).filter(Boolean)
  );
  console.log('SUBTITLE Elements:', subtitleTexts.slice(0, 20));

  // Try video element text tracks
  const tracks = await page.$$eval('video track, video texttrack', els =>
    els.map(el => ({ kind: el.getAttribute('kind'), src: el.getAttribute('src'), label: el.getAttribute('label') }))
  );
  console.log('TRACKS:', tracks);

  // Dump page text content (key parts)
  const bodyText = await page.$$eval('article, [class*="content"], [class*="article"], [class*="desc"]', els =>
    els.map(el => el.textContent?.trim().substring(0, 500)).filter(Boolean)
  );
  console.log('ARTICLE TEXT:', bodyText);

  // Network: captions
  console.log('\n=== CAPTION RESPONSES ===');
  for (const c of captions) {
    console.log('URL:', c.url);
    console.log('BODY:', c.body);
    console.log('---');
  }

  // Network: API responses
  console.log('\n=== API RESPONSES ===');
  for (const r of apiResponses) {
    console.log('URL:', r.url);
    console.log('BODY:', r.body);
    console.log('---');
  }

  // Dump all text on page
  const allText = await page.evaluate(() => document.body.innerText);
  console.log('\n=== ALL PAGE TEXT ===');
  console.log(allText.substring(0, 3000));

  await browser.close();
})();
