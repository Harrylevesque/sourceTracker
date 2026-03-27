// Content script: collect page text and inline images as data URLs and send back to the caller
(async () => {
  function getVisibleText() {
    return document.body ? document.body.innerText : document.documentElement.innerText;
  }

  async function imgToDataUrl(img) {
    try {
      // If already a data URL just return it
      const src = img.currentSrc || img.src || img.getAttribute('data-src') || img.getAttribute('data-original');
      if (!src) return null;
      if (src.startsWith('data:')) return src;

      // Fetch the image as blob then convert
      const res = await fetch(src, { mode: 'cors' });
      const blob = await res.blob();
      return await new Promise((resolve) => {
        const r = new FileReader();
        r.onload = () => resolve(r.result);
        r.onerror = () => resolve(null);
        r.readAsDataURL(blob);
      });
    } catch (err) {
      return null;
    }
  }

  const text = getVisibleText();
  const imgs = Array.from(document.images || []);
  const images = [];
  for (const img of imgs) {
    const dataUrl = await imgToDataUrl(img);
    images.push({ src: img.getAttribute('src') || img.currentSrc || null, dataUrl });
  }

  // Return snapshot to the caller
  chrome.runtime.sendMessage({ type: 'PAGE_SNAPSHOT', payload: { url: location.href, title: document.title, text, images } });
})();

