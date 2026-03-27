import { API_BASE, DEFAULT_PROJECT, apiRequest } from './config.js';

const lastHandled = new Map(); // tabId -> `${project}|${url}`

async function getStoredProject() {
  const stored = await chrome.storage.sync.get(['project']);
  return stored.project || DEFAULT_PROJECT;
}

async function checkVisited(project, url) {
  const encodedProject = encodeURIComponent(project);
  const response = await apiRequest(`/projects/${encodedProject}/visited/check?url=${encodeURIComponent(url)}`);
  return Boolean(response?.exists);
}

async function recordVisit(project, url) {
  const encodedProject = encodeURIComponent(project);
  return apiRequest(`/projects/${encodedProject}/visited`, {
    method: 'POST',
    body: JSON.stringify({ url, lenient: true }),
  });
}

async function handleTab(tabId, url) {
  if (!url || !url.startsWith('http')) {
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
    // Errors are logged to help diagnose connectivity issues from the extension background context.
    console.error('SourceTracker background error:', err);
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
