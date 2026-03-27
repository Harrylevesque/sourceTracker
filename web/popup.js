import { API_BASE, DEFAULT_PROJECT, apiRequest } from './config.js';

const projectSelect = document.getElementById('projectSelect');
const refreshBtn = document.getElementById('refreshProjects');
const newProjectInput = document.getElementById('newProject');
const createProjectBtn = document.getElementById('createProject');
const saveTabBtn = document.getElementById('saveTab');
const autoCheckEl = document.getElementById('autoCheck');
const statusEl = document.getElementById('status');

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.style.color = isError ? 'red' : 'inherit';
}

async function getStoredProject() {
  const stored = await chrome.storage.sync.get(['project']);
  return stored.project || DEFAULT_PROJECT;
}

async function setStoredProject(project) {
  await chrome.storage.sync.set({ project });
}

async function getAutoCheck() {
  const stored = await chrome.storage.sync.get(['autoCheck']);
  return stored.autoCheck !== false; // default true
}

async function setAutoCheck(v) {
  await chrome.storage.sync.set({ autoCheck: Boolean(v) });
}

async function loadProjects(selectedProject) {
  try {
    const data = await apiRequest('/projects');
    const projects = data.projects || [];
    projectSelect.innerHTML = '';
    projects.forEach((name) => {
      const option = document.createElement('option');
      option.value = name;
      option.textContent = name;
      projectSelect.appendChild(option);
    });

    const toSelect = selectedProject && projects.includes(selectedProject)
      ? selectedProject
      : projects[0] || DEFAULT_PROJECT;
    projectSelect.value = toSelect;
    await setStoredProject(toSelect);
    const auto = await getAutoCheck();
    autoCheckEl.checked = Boolean(auto);
    setStatus(`Active project: ${toSelect}`);
  } catch (err) {
    setStatus(`Failed to load projects: ${err.message}`, true);
  }
}

async function createProject() {
  const name = (newProjectInput.value || '').trim();
  if (!name) {
    setStatus('Enter a project name first.', true);
    return;
  }
  try {
    const result = await apiRequest('/projects', {
      method: 'POST',
      body: JSON.stringify({ name }),
    });
    await loadProjects(result.name);
    newProjectInput.value = '';
    setStatus(`Project ready: ${result.name}`);
  } catch (err) {
    setStatus(`Unable to create project: ${err.message}`, true);
  }
}

async function saveCurrentTab() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.url || !tab.url.startsWith('http')) {
      setStatus('Active tab is not a webpage.', true);
      return;
    }
    const project = await getStoredProject();
    // Try to request a snapshot from the content script and POST it to /snapshot
    try {
      const snapshot = await requestSnapshotFromActiveTab();
      if (snapshot) {
        const result = await apiRequest(`/projects/${encodeURIComponent(project)}/snapshot`, {
          method: 'POST',
          body: JSON.stringify(snapshot),
        });
        setStatus(result.history && result.history.changed ? 'Saved snapshot.' : 'Saved (no change).');
        return;
      }
    } catch (err) {
      console.warn('Snapshot via content script failed, falling back to simple save:', err?.message || err);
    }

    const result = await apiRequest(`/projects/${encodeURIComponent(project)}/visited`, {
      method: 'POST',
      body: JSON.stringify({ url: tab.url, lenient: true }),
    });
    setStatus(result.saved ? 'Saved this page.' : 'Already saved.');
  } catch (err) {
    setStatus(`Save failed: ${err.message}`, true);
  }
}

async function requestSnapshotFromActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
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
      chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['contentScript.js'] })
        .catch((e) => {
          chrome.runtime.onMessage.removeListener(onMessage);
          reject(e);
        });
    } catch (e) {
      chrome.runtime.onMessage.removeListener(onMessage);
      reject(e);
    }
    setTimeout(() => {
      chrome.runtime.onMessage.removeListener(onMessage);
      resolve(null);
    }, 8000);
  });
}

async function init() {
  const current = await getStoredProject();
  await loadProjects(current);

  projectSelect.addEventListener('change', async (event) => {
    const selected = event.target.value;
    await setStoredProject(selected);
    setStatus(`Active project: ${selected}`);
  });

  autoCheckEl.addEventListener('change', async (e) => {
    await setAutoCheck(e.target.checked);
    setStatus(e.target.checked ? 'Auto-check enabled' : 'Auto-check disabled');
  });

  refreshBtn.addEventListener('click', async () => {
    const stored = await getStoredProject();
    await loadProjects(stored);
  });

  createProjectBtn.addEventListener('click', createProject);
  saveTabBtn.addEventListener('click', saveCurrentTab);

  setStatus(`Using API at ${API_BASE}`);
}

init();
