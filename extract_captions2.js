const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-blink-features=AutomationControlled']
  });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 800 },
    bypassCSP: true
  });
  const page = await context.newPage();
  
  // Collect subtitle URLs from network
  const subtitleUrls = [];
  page.on('request', req => {
    const url = req.url();
    if (url.includes('subtitle') || url.includes('caption') || url.includes('tts')) {
      subtitleUrls.push(url);
    }
  });
  
  page.on('response', async resp => {
    const url = resp.url();
    if (url.includes('subtitle') || url.includes('caption') || url.includes('tts')) {
      try {
        const body = await resp.text();
        console.log('SUBTITLE RESPONSE:', url.substring(0, 200));
        console.log(body.substring(0, 5000));
        console.log('---');
      } catch {}
    }
  });

  try {
    console.log('Loading page...');
    await page.goto('https://www.toutiao.com/video/7638818556376908315/', {
      waitUntil: 'domcontentloaded',
      timeout: 30000
    });
    
    console.log('Page loaded. Waiting for video...');
    await page.waitForTimeout(15000);

    // Check for video element
    const videoInfo = await page.evaluate(() => {
      const v = document.querySelector('video');
      if (!v) return { hasVideo: false };
      const tracks = Array.from(v.querySelectorAll('track') || []).map(t => ({
        kind: t.getAttribute('kind'), src: t.getAttribute('src'), label: t.getAttribute('label')
      }));
      return { hasVideo: true, src: v.src?.substring(0, 200), tracks };
    });
    console.log('VIDEO INFO:', JSON.stringify(videoInfo, null, 2));

    // Try clicking play to trigger subtitle loading
    const playBtn = await page.$('[class*="play"], [class*="Play"], video');
    if (playBtn) {
      console.log('Clicking play...');
      await playBtn.click();
      await page.waitForTimeout(8000);
    }

    // Check all subtitle URLs found
    console.log('SUBTITLE URLs found:', subtitleUrls);

    // Dump all text  
    const text = await page.evaluate(() => document.body.innerText);
    console.log('\n=== PAGE TEXT (first 3000 chars) ===');
    console.log(text.substring(0, 3000));

  } catch(e) {
    console.error('ERROR:', e.message);
  }

  await browser.close();
})();
