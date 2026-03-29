import { DEFAULT_PROJECT, apiRequest } from './config.js';

const lastHandled = new Map(); // tabId -> `${project}|${url}`

// Create a context menu item for saving selected text as a citation
chrome.runtime.onInstalled.addListener(() => {
  try {
    chrome.contextMenus.create({
      id: 'save-as-citation',
      title: 'Save as citation',
      contexts: ['selection']
    });
  } catch (err) {
    console.error('Failed to create context menu:', err);
  }
});

// Handle clicks on the context menu and send the selected text to the server
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== 'save-as-citation') return;
  try {
    const project = await getStoredProject();
    const selection = info.selectionText || null;
    const pageUrl = info.pageUrl || (tab && tab.url) || null;
    const title = (tab && tab.title) || null;

    if (!pageUrl) {
      console.warn('No page URL available for citation');
      return;
    }

    const encodedProject = encodeURIComponent(project);
    await apiRequest(`/projects/${encodedProject}/citations`, {
      method: 'POST',
      body: JSON.stringify({ url: pageUrl, selected_text: selection, title }),
    });
  } catch (err) {
    console.error('Failed to save citation:', err);
  }
});

async function getStoredProject() {
  const stored = await chrome.storage.sync.get(['project']);
  return stored.project || DEFAULT_PROJECT;
}

async function checkVisited(project, url) {
  const encodedProject = encodeURIComponent(project);
  try {
    const response = await apiRequest(`/projects/${encodedProject}/visited/check?url=${encodeURIComponent(url)}`);
    return Boolean(response?.exists);
  } catch (err) {
    // Don't treat API errors as fatal; return false so we attempt to record the visit.
    console.warn('checkVisited API error (ignored):', err?.message || err);
    return false;
  }
}

async function recordVisit(project, url) {
  const encodedProject = encodeURIComponent(project);
  try {
    // First try to obtain a client-side snapshot (text + images) and POST to /snapshot
    try {
      const snapshot = await requestSnapshotFromTab(url);
      if (snapshot) {
        return await apiRequest(`/projects/${encodedProject}/snapshot`, {
          method: 'POST',
          body: JSON.stringify(snapshot),
        });
      }
    } catch (err) {
      // fall back to server-side fetch if content script snapshot fails
      console.warn('Snapshot via content script failed, falling back to simple visit:', err?.message || err);
    }

    return await apiRequest(`/projects/${encodedProject}/visited`, {
      method: 'POST',
      body: JSON.stringify({ url, lenient: true }),
    });
  } catch (err) {
    // The server may fail to fetch a title for some sites (403, timeouts); don't bubble that
    // into an uncaught error here — just log and continue.
    console.warn('recordVisit API error (ignored):', err?.message || err);

async function handleTab(tabId, url) {
  if (!url || !url.startsWith('http')) {

async function requestSnapshotFromTab(url) {
  try {
    // Find a tab with the URL and ask it to run the content script
    const tabs = await chrome.tabs.query({ url: url });
    const tab = tabs && tabs[0];
    if (!tab) return null;

    return new Promise((resolve, reject) => {
      const onMessage = (msg, sender) => {
        if (msg && msg.type === 'PAGE_SNAPSHOT' && sender.tab && sender.tab.id === tab.id) {
          chrome.runtime.onMessage.removeListener(onMessage);
          resolve(msg.payload);
        }
      };
      chrome.runtime.onMessage.addListener(onMessage);

      try {
        chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ['contentScript.js'],
        }).catch((e) => {
          chrome.runtime.onMessage.removeListener(onMessage);
          reject(e);
        });
      } catch (e) {
        chrome.runtime.onMessage.removeListener(onMessage);
        reject(e);
      }
      // Timeout in 8s
      setTimeout(() => {
        chrome.runtime.onMessage.removeListener(onMessage);
        resolve(null);
      }, 8000);
    });
  } catch (err) {
    return null;
  }
}
    return;
  }

  try {
    // Respect user preference for automatic checking
    const s = await chrome.storage.sync.get(['autoCheck']);
    const autoCheck = s.autoCheck !== undefined ? Boolean(s.autoCheck) : true;
    if (!autoCheck) return;

    const project = await getStoredProject();
    const key = `${project}|${url}`;
    if (lastHandled.get(tabId) === key) {
      return;
    }
    lastHandled.set(tabId, key);

    const exists = await checkVisited(project, url);
    if (!exists) {
      await recordVisit(project, url);
    }
  } catch (err) {
    // Log as a warning (trim long server error payloads) so the user console isn't spammed
    // with large JSON error bodies when remote sites block scraping.
    const msg = err?.message || String(err);
    const short = msg.length > 200 ? msg.slice(0, 200) + '…' : msg;
    console.warn('SourceTracker background warning:', short);
  }
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete') {
    handleTab(tabId, tab?.url);
  }
});

chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    handleTab(activeInfo.tabId, tab?.url);
  } catch (err) {
    console.error('SourceTracker tab activation error:', err);
  }
});
