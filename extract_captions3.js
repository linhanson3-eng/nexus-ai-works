const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-blink-features=AutomationControlled']
  });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 800 },
  });
  const page = await context.newPage();

  // Collect ALL XHR/fetch responses
  const allResponses = [];
  page.on('response', async resp => {
    const url = resp.url();
    const ct = resp.headers()['content-type'] || '';
    if (ct.includes('json') || ct.includes('text') || url.includes('api') || url.includes('detail') || url.includes('video')) {
      try {
        const body = await resp.text();
        if (body.length < 50000) {
          allResponses.push({ url: url.substring(0, 150), ct, len: body.length, body: body.substring(0, 2000) });
        }
      } catch {}
    }
  });

  await page.goto('https://www.toutiao.com/video/7638818556376908315/', {
    waitUntil: 'domcontentloaded',
    timeout: 30000
  });
  await page.waitForTimeout(20000);

  // Look for subtitle/subtitle_url/video_detail in all responses
  console.log(`=== Collected ${allResponses.length} responses ===\n`);
  for (const r of allResponses) {
    if (r.body.includes('subtitle') || r.body.includes('caption') || r.body.includes('content') || r.body.includes('text') || r.body.includes('detail') || r.body.includes('group_id')) {
      console.log('URL:', r.url);
      console.log('CT:', r.ct);
      console.log('BODY:', r.body.substring(0, 3000));
      console.log('---\n');
    }
  }

  // Dump all response URLs for inspection
  console.log('\n=== ALL RESPONSE URLs ===');
  for (const r of allResponses) {
    console.log(r.url, '|', r.ct, '|', r.len, 'bytes');
  }

  await browser.close();
})();
